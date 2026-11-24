"""Tests for OS1 Vision Engine (Screen and Camera perception)."""

from os1_orchestrator.vision import VisionEngine


def test_vision_screen_analysis():
    vision = VisionEngine()
    scene = vision.analyze_screen()

    assert scene.source == "screen"
    assert len(scene.summary) > 0
    assert len(scene.detected_text) > 0
    assert len(scene.objects) > 0
    assert scene.latency_ms >= 0.0


def test_vision_camera_analysis():
    vision = VisionEngine()
    scene = vision.analyze_camera()

    assert scene.source == "camera"
    assert "room" in scene.summary.lower() or "see you" in scene.summary.lower()
    assert scene.mood_observation is not None
    assert len(scene.objects) > 0


def test_vision_context_formatting():
    vision = VisionEngine()
    vision.analyze_screen()
    vision.analyze_camera()

    ctx = vision.format_vision_context_for_brain()
    assert "[Screen vision:" in ctx
    assert "[Camera vision:" in ctx
