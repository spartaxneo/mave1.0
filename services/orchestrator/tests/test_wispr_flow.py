"""Test Wispr Flow engine against shared/dictionary-test-vectors.json and feature tests."""

import json
from pathlib import Path

import pytest

from os1_orchestrator.wispr_flow import (
    DictionaryEngine,
    DictionaryEntry,
    WisprFlowEngine,
)

# Check both potential locations (workspace root or submodule)
POSSIBLE_PATHS = [
    Path(__file__).resolve().parents[4] / "shared" / "dictionary-test-vectors.json",
    Path(__file__).resolve().parents[3] / "shared" / "dictionary-test-vectors.json",
    Path("/Users/shivam/Documents/Mave/shared/dictionary-test-vectors.json"),
]

TEST_VECTORS_PATH = next((p for p in POSSIBLE_PATHS if p.exists()), POSSIBLE_PATHS[0])


def test_dictionary_vectors_all_pass():
    """Verify 100% compliance with shared/dictionary-test-vectors.json."""
    assert TEST_VECTORS_PATH.exists(), f"Vector file not found at {TEST_VECTORS_PATH}"

    data = json.loads(TEST_VECTORS_PATH.read_text(encoding="utf-8"))
    cases = data["cases"]

    for case in cases:
        name = case["name"]
        entries = [DictionaryEntry.from_dict(e) for e in case.get("entries", [])]
        engine = DictionaryEngine(entries)

        inp = case["input"]
        expected = case["expected"]
        expected_corrections = case.get("expectedCorrections", [])

        result_text, hits = engine.apply(inp)

        # Assert output matches expected string verbatim
        assert result_text == expected, f"Case '{name}' failed: got '{result_text}', expected '{expected}'"

        # Assert hits count and targets match
        hit_map = {h.to: h.count for h in hits}
        expected_map = {c["to"]: c["count"] for c in expected_corrections}
        assert hit_map == expected_map, f"Case '{name}' hit counts mismatch: got {hit_map}, expected {expected_map}"


def test_wispr_flow_disfluencies():
    flow = WisprFlowEngine()
    raw = "um so basically uh I I want to go to the store"
    res = flow.process(raw)
    assert "um" not in res.text.lower()
    assert "uh" not in res.text.lower()
    assert "I I" not in res.text
    assert "I want to go to the store" in res.text


def test_wispr_flow_numbers_and_currency():
    flow = WisprFlowEngine()
    raw = "That will be twenty five dollars and fifty percent discount"
    res = flow.process(raw)
    assert "$25" in res.text
    assert "50%" in res.text

    email_raw = "send an invoice to billing at company dot com please"
    res_email = flow.process(email_raw)
    assert "billing@company.com" in res_email.text


def test_wispr_flow_code_formatting():
    flow = WisprFlowEngine()
    raw = "define an arrow function that returns open curly brace snake case user id close curly brace"
    res = flow.process(raw)
    assert "=>" in res.text
    assert "{" in res.text
    assert "user_id" in res.text
    assert "}" in res.text


def test_wispr_flow_command_mode():
    flow = WisprFlowEngine()
    raw = "Command: make this email more formal and polite"
    res = flow.process(raw)
    assert res.mode == "command"
    assert res.command_intent == "make this email more formal and polite"


def test_wispr_flow_default_dictionary_corrections():
    flow = WisprFlowEngine()
    raw = "What do about instaggaal?"
    res = flow.process(raw)
    assert "Instagram" in res.text
    assert "instaggaal" not in res.text
    assert "what to do about" in res.text.lower()
