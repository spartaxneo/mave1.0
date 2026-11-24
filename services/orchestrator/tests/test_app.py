from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OS1_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "devkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "devsecret-devsecret-devsecret-devsecret")
    monkeypatch.setenv("OS1_CLIENT_TOKEN", "test-token")
    import os1_orchestrator.app as app_module

    importlib.reload(app_module)
    return TestClient(app_module.app, headers={"Authorization": "Bearer test-token"})


def test_profile_roundtrip_and_reset(client):
    assert client.get("/os1/profile").json()["onboarded"] is False
    client.patch("/os1/profile", json={"name": "Theo", "onboarded": True, "voice_key": "voice_male"})
    assert client.get("/os1/profile").json()["voice_key"] == "voice_male"
    reset = client.post("/os1/dev/reset-onboarding").json()
    assert reset["name"] == "Theo" and reset["onboarded"] is False and reset["voice_key"] == "voice_1_warm"


def test_token_dispatches_agent_and_saves_name(client):
    resp = client.post("/os1/token", json={"name": "Theo"}).json()
    assert resp["engine"] == "drama3"
    assert resp["url"].startswith("wss://") and resp["token"].count(".") == 2
    assert client.get("/os1/profile").json()["name"] == "Theo"


def test_requires_token(client):
    assert client.get("/health").status_code == 200
    assert client.get("/os1/profile", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/os1/token", json={}, headers={"Authorization": ""}).status_code == 401


def test_chat_conversational_and_pills(client):
    # Test conversational question
    conv = client.post("/os1/chat", json={"phrase": "how are you today"}).json()
    assert conv["matched"] is False
    assert len(conv["reply"]) > 5
    assert isinstance(conv["reply"], str)

    # Test pill matching
    inbox_match = client.post("/os1/chat", json={"phrase": "show me my inbox"}).json()
    assert inbox_match["matched"] is True
    assert inbox_match["target"] == "inbox"

    # Test memory remembering
    mem = client.post("/os1/chat", json={"phrase": "remember that I prefer herbal tea in the evening"}).json()
    assert mem["matched"] is True
    assert "remember" in mem["reply"].lower()

    # Test code generation
    code = client.post("/os1/chat", json={"phrase": "write a python script to test an api"}).json()
    assert "```python" in code["reply"]

    # Test Wispr Flow & Inkling metrics in chat
    wispr_chat = client.post(
        "/os1/chat",
        json={"phrase": "um so basically what do you remember about me"},
    ).json()
    assert wispr_chat["matched"] is True
    assert wispr_chat["action"] == "memory"

    # Test Wispr Flow command mode
    wispr_cmd = client.post(
        "/os1/chat",
        json={"phrase": "Command: make this more formal"},
    ).json()
    assert wispr_cmd["matched"] is True
    assert wispr_cmd["target"] == "wispr"
    assert "formal" in wispr_cmd["reply"].lower()


def test_dedicated_ai_endpoints(client):
    # 1. Transcribe (Wispr Flow)
    tr = client.post(
        "/os1/transcribe",
        json={"text": "um twenty five dollars and fifty percent discount"},
    ).json()
    assert "$25" in tr["text"]
    assert "50%" in tr["text"]
    assert "um" not in tr["text"].lower()

    # 1b. Audio Transcribe (Faster-Whisper on-device STT)
    # Generate 1 sec of silent WAV audio
    import io
    import wave
    import base64
    wav_buf = io.BytesIO()
    with wave.open(wav_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00" * 32000)
    audio_b64 = base64.b64encode(wav_buf.getvalue()).decode("ascii")
    atr = client.post("/os1/audio/transcribe", json={"audio_base64": audio_b64}).json()
    assert "text" in atr
    assert "raw_text" in atr

    # 2. Voice synthesize (CosyVoice 2)
    syn = client.post(
        "/os1/voice/synthesize",
        json={"text": "Hello there! <laughter> I'm so happy to see you. <whisper> Keep this between us."},
    ).json()
    assert syn["format"] == "audio/wav"
    assert syn["byte_length"] > 44
    assert "audio_base64" in syn
    assert "laughter" in syn["acting_tags"]
    assert syn["has_laughter"] is True
    assert syn["has_whisper"] is True

    # 2b. Ultra-natural neural voice synthesize local
    syn_local = client.post(
        "/os1/voice/synthesize-local",
        json={"text": "Hello Shivam. You're about to meet OS1.", "voice_gender": "male"},
    ).json()
    assert "audio_base64" in syn_local
    assert syn_local["byte_length"] > 100
    assert "engine" in syn_local

    # 3. VAD frame
    vad_res = client.post(
        "/os1/vad/frame",
        json={"samples": [0] * 512, "partial_text": "I went to the store and", "silence_duration_ms": 300.0},
    ).json()
    assert vad_res["is_speech"] is False
    assert vad_res["turn_complete"] is False  # Incomplete trailer 'and' holds turn

    # 4. Action execute (UI-TARS & Mobile-Agent)
    act_desk = client.post(
        "/os1/action/execute",
        json={"instruction": "Click on Submit button", "target": "desktop"},
    ).json()
    assert act_desk["target"] == "desktop"
    assert act_desk["action"]["type"] == "click"

    act_mob = client.post(
        "/os1/action/execute",
        json={"instruction": "Open WhatsApp on my phone", "target": "mobile"},
    ).json()
    assert act_mob["target"] == "mobile"
    assert act_mob["action"]["type"] == "open_app"
    assert act_mob["action"]["app_id"] == "com.whatsapp"
