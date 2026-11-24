"""Tests for Dual Brain architecture (Hermes + Qwen 2.5 3B)."""

import pytest

from os1_orchestrator.brain_dual import DualBrain
from os1_orchestrator.brain_qwen import QwenBrain
from os1_orchestrator.vision import VisionEngine


@pytest.mark.anyio
async def test_dual_brain_conversational_turn():
    dual = DualBrain()
    res = await dual.generate("Hello Samantha, how are you feeling today?")

    assert res.brain_used in ["qwen_voice", "qwen_voice_with_vision"]
    assert len(res.reply) > 0
    assert len(res.clean_voice_reply) > 0
    assert "speedup" in res.speculative_stats


@pytest.mark.anyio
async def test_dual_brain_vision_query():
    dual = DualBrain()
    res = await dual.generate("Samantha, look at my screen, what do you see?")

    assert res.brain_used == "qwen_voice_with_vision"
    assert res.vision_context is not None
    assert "screen" in res.vision_context.lower()


@pytest.mark.anyio
async def test_dual_brain_hermes_delegation():
    dual = DualBrain()
    res = await dual.generate("Please research and scrape recent articles about quantum computing.")

    assert res.brain_used == "dual_cooperative"
    assert res.hermes_task_id is not None
    assert "helpers" in res.reply.lower() or "background" in res.reply.lower()
