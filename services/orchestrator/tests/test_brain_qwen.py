"""Tests for Qwen 2.5 3B brain, speculative decoding, and frozen KV cache."""

import pytest

from os1_orchestrator.brain_qwen import (
    FrozenKVCacheManager,
    QwenBrain,
    SpeculativeDecoder,
)


def test_frozen_kv_cache_initialization():
    kv = FrozenKVCacheManager()
    assert kv.is_cached is True
    prompt = kv.get_system_prompt()
    assert len(prompt) > 0
    assert "Mave" in prompt or "Samantha" in prompt or "Her" in prompt


def test_speculative_decoder_simulation():
    speculator = SpeculativeDecoder(k_ahead=4)
    draft_tokens = ["I", "think", "we", "should"]
    target_tokens = ["I", "think", "we", "must"]

    accepted, acc_count, total = speculator.simulate_verify(draft_tokens, target_tokens)
    assert acc_count == 4
    assert accepted == ["I", "think", "we", "must"]
    assert total == 4


@pytest.mark.anyio
async def test_qwen_brain_generation_and_streaming():
    brain = QwenBrain()
    res = await brain.generate_response("Tell me what you are feeling right now.")

    assert len(res.text) > 0
    assert len(res.first_sentence) > 0
    assert len(res.sentences) >= 1
    # Check that first sentence is produced within interactive voice SLA (< 12000ms on local CPU)
    assert res.latency_to_first_sentence_ms < 12000.0
    assert res.speculative_stats.speedup >= 2.0
