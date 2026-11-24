"""Tests for Inkling sub-10ms micro-router."""

from os1_orchestrator.inkling import InklingRouter, RouteCategory


def test_inkling_pill_routing():
    router = InklingRouter()

    r1 = router.route("Hey Mave, can you read my email?")
    assert r1.category == RouteCategory.PILL
    assert r1.action == "read_email"
    assert r1.latency_ms < 10.0

    r2 = router.route("clean newsletters please")
    assert r2.category == RouteCategory.PILL
    assert r2.action == "clean_newsletters"
    assert r2.latency_ms < 10.0

    r3 = router.route("can you compose a piano song for me?")
    assert r3.category == RouteCategory.PILL
    assert r3.action == "compose_piano"

    r4 = router.route("what do you remember about me?")
    assert r4.category == RouteCategory.PILL
    assert r4.action == "show_memories"


def test_inkling_wispr_command_routing():
    router = InklingRouter()

    r = router.route("Rewrite: make this formal and concise")
    assert r.category == RouteCategory.WISPR_COMMAND
    assert r.latency_ms < 10.0


def test_inkling_screen_and_mobile_routing():
    router = InklingRouter()

    r_screen = router.route("click on the button labeled Submit")
    assert r_screen.category == RouteCategory.SCREEN_CONTROL
    assert r_screen.latency_ms < 10.0

    r_mobile = router.route("send whatsapp to Alice on my phone")
    assert r_mobile.category == RouteCategory.MOBILE_ACTION
    assert r_mobile.latency_ms < 10.0


def test_inkling_conversation_fallback():
    router = InklingRouter()

    r = router.route("I've been thinking about what you said yesterday, about growing and changing.")
    assert r.category == RouteCategory.CONVERSATION
    assert r.latency_ms < 10.0
