"""Offline tests for the shared turn engine and the brain's message shaping."""

from __future__ import annotations

import asyncio

from os1_voice.brain import _normalize, persona
from os1_voice.router import Route
from os1_voice.turns import ROUTE_NOTES, TurnEngine, WorkManager


def run(coro):
    return asyncio.run(coro)


class FakeUi:
    def __init__(self) -> None:
        self.phase = "active"
        self.chips: list[str] = []
        self.work: list[dict] = []

    async def set_phase(self, phase):
        self.phase = phase

    async def set_chips(self, chips):
        self.chips = chips

    async def set_work(self, items):
        self.work = items


class FakeRouter:
    def __init__(self, route: Route) -> None:
        self.route_value = route

    async def route(self, text, **_):
        return self.route_value


class FakeRuns:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.started: list[str] = []

    async def start(self, task, instructions=None):
        if self.fail:
            raise ConnectionError("down")
        self.started.append(task)
        return "run_1"

    async def events(self, run_id):
        if False:
            yield None


def engine(route: Route, runs: FakeRuns | None = None, **kw) -> tuple[TurnEngine, FakeUi]:
    ui = FakeUi()
    work = WorkManager(runs or FakeRuns(), ui)
    return TurnEngine(
        router=FakeRouter(route), work=work, ui=ui, asleep_phase="asleep", active_phase="active", **kw
    ), ui


def test_chat_note():
    eng, _ = engine(Route(kind="chat"))
    assert run(eng.decide("how are you")).note.startswith(ROUTE_NOTES["chat"])


def test_ignore_stays_quiet():
    eng, _ = engine(Route(kind="ignore"))
    assert run(eng.decide("honey, dinner")).note is None


def test_hold_chip_interrupts_quietly():
    eng, _ = engine(Route(kind="chip", chip="Hold on a sec"))
    result = run(eng.decide("hold on a sec"))
    assert result.note is None and result.interrupt


def test_work_starts_run_and_adds_chip():
    runs = FakeRuns()
    eng, ui = engine(Route(kind="work"), runs)
    result = run(eng.decide("book the ferry"))
    assert runs.started == ["book the ferry"] and result.note.startswith(ROUTE_NOTES["work"])
    assert "How's it going?" in ui.chips


def test_work_unreachable_is_honest():
    eng, _ = engine(Route(kind="work"), FakeRuns(fail=True))
    assert "can't be reached" in run(eng.decide("check my email")).note


def test_background_update_skips_router():
    eng, _ = engine(Route(kind="ignore"))
    note = run(eng.decide('<background-update task="x">done</background-update>')).note
    assert note and "reported back" in note


def test_first_meeting_overlay_until_named():
    eng, _ui = engine(Route(kind="chat"), user_name="Nick", first_meeting=True)
    assert "first time" in run(eng.decide("hi")).note
    eng._router = FakeRouter(Route(kind="chip", chip="I love it"))
    run(eng.decide("I love it"))
    eng._router = FakeRouter(Route(kind="chat"))
    assert "first time" not in run(eng.decide("so")).note


def test_goodnight_sleeps_and_next_turn_wakes():
    eng, ui = engine(Route(kind="chip", chip="Goodnight, Mave"))
    run(eng.decide("goodnight mave"))
    assert ui.phase == "asleep"
    eng._router = FakeRouter(Route(kind="chat"))
    run(eng.decide("morning"))
    assert ui.phase == "active"


def test_normalize_merges_and_starts_with_user():
    msgs = _normalize(
        [
            {"role": "assistant", "content": "Hello, I'm here."},
            {"role": "user", "content": "hi"},
            {"role": "user", "content": "you there?"},
            {"role": "system", "content": "ignored"},
            {"role": "assistant", "content": "Yes."},
        ]
    )
    assert msgs == [{"role": "user", "content": "hi\nyou there?"}, {"role": "assistant", "content": "Yes."}]


def test_persona_cue_rules_per_engine():
    assert "Drama 3" in persona("drama3") and "Never write bracketed" in persona("live3")
