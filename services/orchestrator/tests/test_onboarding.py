"""Tests for accurate, non-dummy OS1 onboarding dialogue director and memory persistence."""

import pytest
from os1_orchestrator.onboarding_director import onboarding_director
from os1_orchestrator.store import Os1Store


def test_onboarding_welcome_ignores_silence_and_noise():
    # 1. Silence or micro-transcriptions must NOT advance
    res_empty = onboarding_director.process_turn("operator_welcome", "")
    assert res_empty.action == "ignore"
    assert res_empty.next_phase == "operator_welcome"

    res_noise = onboarding_director.process_turn("operator_welcome", "...")
    assert res_noise.action == "ignore"
    assert res_noise.next_phase == "operator_welcome"


def test_onboarding_welcome_clarifies_questions_without_advancing():
    # 2. Asking what OS1 is should clarify and remain on welcome
    res_q = onboarding_director.process_turn("operator_welcome", "What is OS1?")
    assert res_q.action == "clarify"
    assert res_q.next_phase == "operator_welcome"
    assert "artificial intelligence" in res_q.operator_reply.lower() or "os1" in res_q.operator_reply.lower()


def test_onboarding_welcome_advances_on_begin():
    # 3. Explicit begin intent advances to Q1
    res_chip = onboarding_director.process_turn("operator_welcome", "", tapped_chip="Let's begin")
    assert res_chip.action == "advance"
    assert res_chip.next_phase == "operator_q1"
    assert "First one" in res_chip.operator_reply

    res_spoken = onboarding_director.process_turn("operator_welcome", "I'm ready, let's start")
    assert res_spoken.action == "advance"
    assert res_spoken.next_phase == "operator_q1"


def test_onboarding_q1_hesitance_detection():
    # 4. Hesitant answers trigger hesitance branch
    res_hesitant = onboarding_director.process_turn("operator_q1", "Um... I don't really know, hard to say")
    assert res_hesitant.action == "advance"
    assert res_hesitant.next_phase == "operator_q1_hesitance"
    assert "You paused there" in res_hesitant.operator_reply


def test_onboarding_q1_answers_advance_to_q2():
    # 5. Clear answers advance and accurately record preference
    res_solitary = onboarding_director.process_turn("operator_q1", "Definitely happier on my own, I like staying in")
    assert res_solitary.action == "advance"
    assert res_solitary.next_phase == "operator_q2"
    assert res_solitary.dossier_patch.get("social") == "solitary"

    res_social = onboarding_director.process_turn("operator_q1", "Out with people and friends")
    assert res_social.action == "advance"
    assert res_social.next_phase == "operator_q2"
    assert res_social.dossier_patch.get("social") == "social"


def test_onboarding_q2_voice_classification():
    # 6. Selecting female or male voice
    res_male = onboarding_director.process_turn("operator_q2", "I'd prefer a male voice")
    assert res_male.action == "advance"
    assert res_male.next_phase == "operator_q3"
    assert res_male.voice_gender == "male"
    assert res_male.dossier_patch.get("voice_choice") == "male"

    res_female = onboarding_director.process_turn("operator_q2", "Female please")
    assert res_female.action == "advance"
    assert res_female.next_phase == "operator_q3"
    assert res_female.voice_gender == "female"
    assert res_female.dossier_patch.get("voice_choice") == "female"

    # Unclear voice prompts retry
    res_unclear = onboarding_director.process_turn("operator_q2", "I have no idea what they sound like")
    assert res_unclear.action == "clarify"
    assert res_unclear.next_phase == "operator_q2"
    assert "choose for you" in res_unclear.operator_reply


def test_onboarding_q3_maternal_answer_and_handoff():
    # 7. User answers about their mom -> triggers cutoff and saves to memory
    res_mom = onboarding_director.process_turn("operator_q3", "Things are pretty complicated with my mother, we have some tension")
    assert res_mom.action == "advance"
    assert res_mom.next_phase == "initiating"
    assert res_mom.is_handoff is True
    assert "That's plenty" in res_mom.operator_reply
    assert res_mom.memory_to_add is not None
    assert res_mom.memory_to_add["category"] == "people"
    assert "mother" in res_mom.memory_to_add["summary"].lower()


def test_onboarding_rejects_unrelated_answers_and_fillers():
    # 8. Unrelated answer in Q1 does not advance
    res_offtopic = onboarding_director.process_turn("operator_q1", "What is the weather outside?")
    assert res_offtopic.action == "clarify"
    assert res_offtopic.next_phase == "operator_q1"
    assert "Just asking how you like to spend" in res_offtopic.operator_reply

    # 9. Single-word filler "okay" or "yeah" in Q3 does not advance
    res_filler_okay = onboarding_director.process_turn("operator_q3", "okay")
    assert res_filler_okay.action == "clarify"
    assert res_filler_okay.next_phase == "operator_q3"
    assert "Tell me a little about how things are" in res_filler_okay.operator_reply

    res_filler_yeah = onboarding_director.process_turn("operator_q3", "yeah")
    assert res_filler_yeah.action == "clarify"
    assert res_filler_yeah.next_phase == "operator_q3"
    assert "Tell me a little about how things are" in res_filler_yeah.operator_reply


def test_onboarding_welcome_greeting_stays_on_welcome():
    res_greet = onboarding_director.process_turn("operator_welcome", "Hello there")
    assert res_greet.action == "clarify"
    assert res_greet.next_phase == "operator_welcome"
    assert "Hello" in res_greet.operator_reply

