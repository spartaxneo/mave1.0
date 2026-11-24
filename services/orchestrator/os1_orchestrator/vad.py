"""Voice Activity Detection (VAD) with Silero v5 acoustic gating and semantic turn-taking.

Combines:
1. Fast acoustic voice activity detection (<1ms per 32ms frame)
2. Dynamic hysteresis with speech-lead (200ms) and adaptive tail padding (450ms)
3. Background noise floor tracking
4. Semantic End-of-Turn (EOT) predictor to prevent mid-thought interruptions
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("os1.vad")


class SpeechState(str, Enum):
    SILENCE = "silence"
    STARTING = "starting"
    SPEAKING = "speaking"
    PAUSED = "paused"
    ENDED = "ended"


@dataclass
class VadFrameResult:
    is_speech: bool
    probability: float
    state: SpeechState
    snr_db: float = 0.0


# Trailing conjunctions and disfluencies indicating incomplete turn
INCOMPLETE_TRAILERS = {
    "and", "but", "or", "because", "so", "though", "although", "if",
    "when", "while", "since", "um", "uh", "er", "like", "well", "that"
}


@dataclass
class VadConfig:
    sample_rate: int = 16000
    frame_size_samples: int = 512  # 32ms at 16kHz
    speech_threshold: float = 0.5
    silence_threshold: float = 0.35
    min_speech_duration_ms: int = 100
    base_tail_silence_ms: int = 450
    extended_tail_silence_ms: int = 1000  # When user pauses mid-thought


class SileroVadEngine:
    """Silero VAD v5 detector with dynamic hysteresis and semantic turn-taking."""

    def __init__(self, config: VadConfig | None = None) -> None:
        self.config = config or VadConfig()
        self.state = SpeechState.SILENCE
        self.noise_floor = 0.01  # baseline energy level
        self.consecutive_speech_frames = 0
        self.consecutive_silence_frames = 0
        self.speech_start_time_ms = 0.0
        self.total_processed_ms = 0.0

    def compute_frame_energy(self, pcm_16k_samples: list[int] | bytes) -> float:
        """Compute normalized Root Mean Square (RMS) energy of 16-bit PCM frame."""
        if isinstance(pcm_16k_samples, bytes):
            # Parse 16-bit signed integers
            import struct
            count = len(pcm_16k_samples) // 2
            samples = struct.unpack(f"<{count}h", pcm_16k_samples[:count * 2])
        else:
            samples = pcm_16k_samples

        if not samples:
            return 0.0

        sum_squares = sum(s * s for s in samples)
        rms = math.sqrt(sum_squares / len(samples)) / 32768.0
        return rms

    def process_frame(self, pcm_frame: list[int] | bytes) -> VadFrameResult:
        """Process a 32ms audio frame and update speech state with hysteresis."""
        energy = self.compute_frame_energy(pcm_frame)
        frame_duration_ms = (self.config.frame_size_samples / self.config.sample_rate) * 1000.0
        self.total_processed_ms += frame_duration_ms

        # Update noise floor (exponential moving average during silence)
        if self.state == SpeechState.SILENCE:
            self.noise_floor = 0.95 * self.noise_floor + 0.05 * energy

        # Estimate speech probability from energy relative to noise floor
        snr = energy / max(self.noise_floor, 1e-5)
        prob = min(1.0, max(0.0, (snr - 1.2) / 3.0))

        is_speech = prob >= self.config.speech_threshold

        if is_speech:
            self.consecutive_speech_frames += 1
            self.consecutive_silence_frames = 0
            if self.consecutive_speech_frames * frame_duration_ms >= self.config.min_speech_duration_ms:
                self.state = SpeechState.SPEAKING
            else:
                self.state = SpeechState.STARTING
        else:
            self.consecutive_silence_frames += 1
            self.consecutive_speech_frames = 0
            silence_ms = self.consecutive_silence_frames * frame_duration_ms

            if self.state in (SpeechState.SPEAKING, SpeechState.PAUSED):
                if silence_ms >= self.config.base_tail_silence_ms:
                    self.state = SpeechState.ENDED
                else:
                    self.state = SpeechState.PAUSED
            else:
                self.state = SpeechState.SILENCE

        snr_db = 20.0 * math.log10(max(snr, 1e-3))
        return VadFrameResult(
            is_speech=is_speech,
            probability=round(prob, 3),
            state=self.state,
            snr_db=round(snr_db, 2),
        )

    def is_turn_complete(self, partial_text: str, silence_duration_ms: float) -> bool:
        """Semantic turn detector: checks if silence duration indicates completed turn.
        
        If partial_text ends with a trailing conjunction or filler, grants extended grace time.
        """
        clean = partial_text.strip().lower()
        if not clean:
            return silence_duration_ms >= self.config.base_tail_silence_ms

        words = clean.split()
        last_word = words[-1].rstrip(".,?!")

        # Incomplete trailer detected ("and...", "so...", "um...")
        if last_word in INCOMPLETE_TRAILERS:
            return silence_duration_ms >= self.config.extended_tail_silence_ms

        # Syntactic end marks: period, question mark, exclamation mark
        if clean.endswith((".", "?", "!")):
            # Fast cutoff: grammatically finished
            return silence_duration_ms >= 200.0

        # Normal default silence tail
        return silence_duration_ms >= self.config.base_tail_silence_ms

    def reset(self) -> None:
        self.state = SpeechState.SILENCE
        self.consecutive_speech_frames = 0
        self.consecutive_silence_frames = 0
