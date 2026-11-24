"""Ultra-natural neural text-to-speech engine for OS1.

Features:
- Primary: State-of-the-art conversational neural speech (Microsoft Edge Neural:
  en-US-GuyNeural / en-US-BrianNeural for male operator; en-US-AvaNeural / en-US-JennyNeural for Mave).
- Natural conversational pacing, breath pauses, and pronunciation normalization (e.g. 'OS1' -> 'OS 1').
- Tier-1 Memory and disk persistent cache in ~/.os1/cache/tts/ for instant sub-millisecond playback.
- Prewarming of all onboarding operator phrases for 0ms lag during setup.
- Tier-2 Local offline fallback via tuned Piper neural models (en_US-ryan-medium / en_US-amy-medium
  with natural length_scale=1.18).
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
import re
import wave
from pathlib import Path
from typing import Any

log = logging.getLogger("os1.neural_tts")

DEFAULT_MALE_VOICE = os.environ.get("OS1_MALE_VOICE", "en-US-BrianNeural")
DEFAULT_FEMALE_VOICE = os.environ.get("OS1_FEMALE_VOICE", "en-US-AvaNeural")

# Pacing configuration: -3% provides calm, thoughtful, cinematic human dialogue
DEFAULT_MALE_RATE = "-3%"
DEFAULT_FEMALE_RATE = "-2%"

CACHE_DIR = Path.home() / ".os1" / "cache" / "tts"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# In-memory LRU audio cache: cache_key -> (bytes, mime_type, engine)
_MEMORY_CACHE: dict[str, tuple[bytes, str, str]] = {}
_MAX_MEMORY_CACHE = 128


def normalize_speech_text(text: str) -> str:
    """Prepare dialogue for human-grade phonetic cadence."""
    # Strip acting and stage tags: <laughter>, [softly], etc.
    cleaned = re.sub(r"<[^>]+>", "", text)
    cleaned = re.sub(r"\[[^\]]+\]", "", cleaned)

    # Convert technical acronyms into natural conversational speech
    cleaned = re.sub(r"\bMAVE 1\.0\b", "Mave 1 point 0", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bMAVE\b", "Mave", cleaned)
    cleaned = re.sub(r"\bOS1\b", "OS 1", cleaned)
    cleaned = re.sub(r"\bOS-1\b", "OS 1", cleaned)
    cleaned = re.sub(r"\bOS 1\b", "O S 1", cleaned)

    # Normalize excessive whitespace
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _get_cache_key(text: str, voice: str, rate: str) -> str:
    h = hashlib.sha256(f"{voice}|{rate}|{text}".encode("utf-8")).hexdigest()
    return h


class NeuralTtsEngine:
    """High-fidelity neural TTS with instant multi-tier caching and local fallback."""

    def __init__(self) -> None:
        self.models_dir = Path.home() / ".os1" / "models" / "piper"
        self._piper_cache: dict[str, Any] = {}

    async def synthesize(
        self,
        text: str,
        voice_gender: str = "male",
        voice_name: str | None = None,
        rate: str | None = None,
    ) -> tuple[bytes | None, str, str]:
        """Synthesize dialogue into high-fidelity neural audio.

        Returns:
            (audio_bytes, mime_type, engine_name)
        """
        clean_text = normalize_speech_text(text)
        if not clean_text:
            return None, "audio/wav", "none"

        is_male = voice_gender.lower() == "male"
        target_voice = voice_name or (DEFAULT_MALE_VOICE if is_male else DEFAULT_FEMALE_VOICE)
        target_rate = rate or (DEFAULT_MALE_RATE if is_male else DEFAULT_FEMALE_RATE)

        cache_key = _get_cache_key(clean_text, target_voice, target_rate)

        # 1. Check in-memory RAM cache (<0.1ms)
        if cache_key in _MEMORY_CACHE:
            cached_bytes, cached_mime, cached_engine = _MEMORY_CACHE[cache_key]
            return cached_bytes, cached_mime, cached_engine

        # 2. Check disk cache (<2ms)
        disk_path = CACHE_DIR / f"{cache_key}.mp3"
        if disk_path.exists():
            try:
                data = disk_path.read_bytes()
                if len(data) > 100:
                    _MEMORY_CACHE[cache_key] = (data, "audio/mp3", "neural_edge_cached")
                    return data, "audio/mp3", "neural_edge_cached"
            except Exception as e:
                log.debug("Disk cache read note: %s", e)

        disk_wav = CACHE_DIR / f"{cache_key}.wav"
        if disk_wav.exists():
            try:
                data = disk_wav.read_bytes()
                if len(data) > 100:
                    _MEMORY_CACHE[cache_key] = (data, "audio/wav", "piper_cached")
                    return data, "audio/wav", "piper_cached"
            except Exception as e:
                log.debug("Disk cache read note: %s", e)

        # 3. Generate via Edge-TTS Neural Voice (generous 8s timeout for high-fidelity neural speech)
        try:
            import edge_tts

            async def _fetch_edge() -> bytes:
                comm = edge_tts.Communicate(clean_text, target_voice, rate=target_rate)
                audio_buf = io.BytesIO()
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        audio_buf.write(chunk["data"])
                return audio_buf.getvalue()

            audio_bytes = await asyncio.wait_for(_fetch_edge(), timeout=8.0)
            if len(audio_bytes) > 200:
                # Save to disk cache and RAM cache
                try:
                    disk_path.write_bytes(audio_bytes)
                except Exception:
                    pass

                if len(_MEMORY_CACHE) >= _MAX_MEMORY_CACHE:
                    _MEMORY_CACHE.pop(next(iter(_MEMORY_CACHE)))
                _MEMORY_CACHE[cache_key] = (audio_bytes, "audio/mp3", "neural_edge")

                return audio_bytes, "audio/mp3", "neural_edge"
        except Exception as err:
            log.warning("Edge neural TTS unavailable or timed out (%s), falling back to tuned local Piper.", err)

        # 4. Fallback to tuned Piper local neural model
        piper_wav = self._synthesize_piper(clean_text, voice_gender=voice_gender)
        if piper_wav:
            wav_path = CACHE_DIR / f"{cache_key}.wav"
            try:
                wav_path.write_bytes(piper_wav)
            except Exception:
                pass
            if len(_MEMORY_CACHE) >= _MAX_MEMORY_CACHE:
                _MEMORY_CACHE.pop(next(iter(_MEMORY_CACHE)))
            _MEMORY_CACHE[cache_key] = (piper_wav, "audio/wav", "piper_neural_cached")
            return piper_wav, "audio/wav", "piper_neural_tuned"

        return None, "audio/wav", "failed"

    def _synthesize_piper(self, text: str, voice_gender: str = "male") -> bytes | None:
        """Tuned local Piper on-device synthesis with natural conversational pacing."""
        model_name = "en_US-amy-medium.onnx" if voice_gender.lower() == "female" else "en_US-ryan-medium.onnx"
        model_path = self.models_dir / model_name
        if not model_path.exists():
            alt_path = Path.home() / ".mave" / "models" / "piper" / model_name
            if alt_path.exists():
                model_path = alt_path
            else:
                return None

        try:
            if model_name not in self._piper_cache:
                from piper import PiperVoice

                log.info("Loading in-memory Piper neural voice: %s", model_name)
                self._piper_cache[model_name] = PiperVoice.load(str(model_path))

            voice = self._piper_cache[model_name]
            from piper.config import SynthesisConfig

            # length_scale=1.18 relaxes the hurried mechanical pace to conversational human speed
            cfg = SynthesisConfig(length_scale=1.18, noise_scale=0.667, noise_w_scale=0.8)

            wav_io = io.BytesIO()
            with wave.open(wav_io, "wb") as wf:
                voice.synthesize_wav(text, wf, syn_config=cfg)

            raw = wav_io.getvalue()
            if len(raw) > 100:
                return raw
        except Exception as err:
            log.warning("Piper local synthesis fallback error: %s", err)

        return None

    async def prewarm_onboarding_phrases(self, user_name: str = "Shivam") -> int:
        """Pre-synthesize all standard onboarding script lines to ensure instant playback."""
        name = user_name or "there"
        phrases = [
            # Welcome (Setup 1/5)
            (
                f"Hello, {name}. You're about to meet MAVE 1.0. A few quick questions first, and then it's all yours.",
                "male",
            ),
            (
                "Hello, there. You're about to meet MAVE 1.0. A few quick questions first, and then it's all yours.",
                "male",
            ),
            (
                f"Hello, {name}. Whenever you're ready to meet your MAVE 1.0, tap 'Let's begin' or say 'Let's begin'.",
                "male",
            ),
            (
                "MAVE 1.0 is an intuitive artificial intelligence designed to listen, learn, and grow with you. Whenever you're ready, say 'Let's begin' or tap the button.",
                "male",
            ),
            # Q1 (Setup 2/5)
            (
                "First one. When you have a free evening, are you out with people, or happier on your own?",
                "male",
            ),
            ("You paused there. Not sure?", "male"),
            ("Just asking how you like to spend your free evenings — out with people, or happier on your own?", "male"),
            ("Take your time. Out with people, or happier on your own?", "male"),
            # Q2 (Setup 3/5)
            ("Understood. Next. Which voice should yours have: female or male?", "male"),
            ("Female, male, or I can choose for you.", "male"),
            # Q3 (Setup 4/5)
            ("And the last one. Tell me a little about you and your mom.", "male"),
            ("Tell me a little about how things are between you two.", "male"),
            ("Just getting a sense of how you relate to the people in your life. Tell me a little about her.", "male"),
            ("That's plenty. Thank you. One moment. MAVE is waking up.", "male"),
            ("That's plenty. Thank you. One moment. Mave is waking up.", "male"),
            ("One moment. MAVE is waking up.", "male"),
            ("One moment. Mave is waking up.", "male"),
            # MAVE initial awakening
            ("Hello, I'm here.", "female"),
            ("MAVE is who I am. Shall we continue?", "female"),
            ("I'm MAVE. It's so lovely to meet you. I'm connected to your computer, files, and routines. What should we look at together?", "female"),
            ("[softly] Hi. Can you hear me okay?", "female"),
        ]

        count = 0
        for text, gender in phrases:
            try:
                audio, _, _ = await self.synthesize(text, voice_gender=gender)
                if audio:
                    count += 1
            except Exception as e:
                log.debug("Prewarm note: %s", e)
        log.info("Pre-warmed %d neural voice phrases.", count)
        return count


# Singleton instance
neural_tts = NeuralTtsEngine()
