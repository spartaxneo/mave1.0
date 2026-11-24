"""Tests for application model connectors (UI-TARS, Mobile-Agent, Qwen-VL, BGE)."""

from os1_orchestrator.connectors import (
    BgeMemoryConnector,
    MobileAgentConnector,
    QwenVlConnector,
    UiTarsConnector,
)


def test_ui_tars_desktop_actions():
    ui_tars = UiTarsConnector()

    act_click = ui_tars.predict_action("Click on Submit button")
    assert act_click.action_type == "click"
    assert act_click.x == 720
    assert act_click.y == 450

    act_type = ui_tars.predict_action("Type 'hello world' into search")
    assert act_type.action_type == "type"
    assert act_type.text == "hello world"

    act_scroll = ui_tars.predict_action("Scroll down")
    assert act_scroll.action_type == "scroll"
    assert act_scroll.direction == "down"


def test_mobile_agent_actions():
    mobile = MobileAgentConnector()

    act_app = mobile.predict_action("Open WhatsApp on my phone")
    assert act_app.action_type == "open_app"
    assert act_app.app_id == "com.whatsapp"

    act_tap = mobile.predict_action("Tap center of screen")
    assert act_tap.action_type == "tap"


def test_qwen_vl_connector():
    qwen_vl = QwenVlConnector()
    res = qwen_vl.analyze_image(b"fake_image_bytes")

    assert len(res.detected_text) > 0
    assert len(res.bounding_boxes) >= 1
    assert res.bounding_boxes[0].label == "window_title"


def test_bge_memory_embeddings():
    bge = BgeMemoryConnector()
    v1 = bge.embed_text("My mother lives in Seattle and loves flowers")
    v2 = bge.embed_text("Mom lives in Seattle and likes plants")
    v3 = bge.embed_text("Quantum mechanics and black holes")

    assert len(v1) == 384
    sim_close = bge.cosine_similarity(v1, v2)
    sim_far = bge.cosine_similarity(v1, v3)

    assert sim_close > sim_far
