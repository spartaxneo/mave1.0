"""Tests for CosyVoice 2 engine, Mave default voice, and inline acting tags."""

import io
import wave
import pytest

from os1_orchestrator.cosyvoice2 import (
    CosyVoice2Engine,
    CosyVoiceConfig,
)


def test_cosyvoice_acting_tag_parsing():
    text = "Hello there! <laughter> That is so funny. <whisper> Keep this between us."
    script = CosyVoice2Engine.parse_acting_tags(text)

    assert script.clean_text == "Hello there! That is so funny. Keep this between us."
    assert len(script.tags) == 2
    assert script.tags[0].tag == "laughter"
    assert script.tags[1].tag == "whisper"
    assert script.has_laughter is True
    assert script.has_whisper is True


def test_bracketed_acting_tags():
    text = "[softly] Goodnight, Theodore. [small laugh]"
    script = CosyVoice2Engine.parse_acting_tags(text)

    assert script.clean_text == "Goodnight, Theodore."
    assert len(script.tags) == 2
    assert script.has_whisper is True
    assert script.has_laughter is True


@pytest.mark.anyio
async def test_cosyvoice_synthesis_and_wav_generation():
    engine = CosyVoice2Engine()
    pcm, script = await engine.synthesize("I'm right here with you. <breath>")

    assert len(pcm) > 0
    assert len(script.tags) == 1
    assert script.tags[0].tag == "breath"

    # Verify WAV header
    wav_bytes = engine.pcm_to_wav(pcm, sample_rate=24000)
    assert len(wav_bytes) > 44
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 24000
