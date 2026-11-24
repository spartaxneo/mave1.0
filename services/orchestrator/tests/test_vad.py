"""Tests for Silero VAD v5 with dynamic hysteresis and semantic turn-taking."""

from os1_orchestrator.vad import (
    SileroVadEngine,
    SpeechState,
    VadConfig,
)


def test_vad_silence_detection():
    vad = SileroVadEngine()
    # 512 zeros (absolute silence)
    silent_frame = [0] * 512
    res = vad.process_frame(silent_frame)

    assert res.is_speech is False
    assert res.state == SpeechState.SILENCE
    assert res.probability < 0.2


def test_vad_speech_transition_and_barge_in():
    vad = SileroVadEngine(VadConfig(min_speech_duration_ms=64))
    # 512 loud audio samples
    speech_frame = [8000] * 512

    r1 = vad.process_frame(speech_frame)
    assert r1.is_speech is True
    assert r1.state == SpeechState.STARTING

    # Second frame exceeds 64ms minimum duration -> transitions to SPEAKING
    r2 = vad.process_frame(speech_frame)
    assert r2.is_speech is True
    assert r2.state == SpeechState.SPEAKING


def test_semantic_turn_taking():
    vad = SileroVadEngine()

    # Case 1: Incomplete thought ending with 'and'
    # Should NOT be complete at 400ms silence
    assert vad.is_turn_complete("I went to the store and", 400.0) is False
    # Should complete at extended grace time (1000ms)
    assert vad.is_turn_complete("I went to the store and", 1050.0) is True

    # Case 2: Complete thought ending with period
    # Should be complete rapidly at 250ms silence
    assert vad.is_turn_complete("I went to the store.", 250.0) is True
    assert vad.is_turn_complete("What time is it?", 250.0) is True
