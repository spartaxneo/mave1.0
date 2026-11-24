"""Tests for ultra-natural neural text-to-speech engine and multi-tier cache."""

import pytest
from os1_orchestrator.neural_tts import neural_tts, normalize_speech_text


def test_normalize_speech_text():
    raw = "Hello, <laughter> Shivam. [softly] You're about to meet OS1. A few quick questions first, and then it's all yours."
    normalized = normalize_speech_text(raw)

    assert "<laughter>" not in normalized
    assert "[softly]" not in normalized
    assert "OS 1" in normalized or "O S 1" in normalized
    assert "Shivam" in normalized


@pytest.mark.anyio
async def test_neural_tts_synthesis_and_caching():
    text = "Hello, Shivam. You're about to meet OS1. A few quick questions first, and then it's all yours."

    # 1. First call: synthesize or fetch from pre-warmed cache
    audio_bytes, mime_type, engine = await neural_tts.synthesize(text, voice_gender="male")
    assert audio_bytes is not None
    assert len(audio_bytes) > 500
    assert mime_type in ["audio/mp3", "audio/wav"]
    assert engine in ["neural_edge", "neural_edge_cached", "piper_neural_tuned"]

    # 2. Second call: must hit memory cache instantly
    cached_bytes, cached_mime, cached_engine = await neural_tts.synthesize(text, voice_gender="male")
    assert cached_bytes == audio_bytes
    assert cached_mime == mime_type
