"""Jev turn router: decides what a finished user utterance is, in one ~100 ms call.

This replaces the "5 narrow tools" decision a fast LLM would otherwise make with a
tool call. One speculative fan-out asks everything the worker might need:

- kind:            chat | work | control | chip
- addressed:       is this said to Mave at all? (always-on mic)
- chip:            which on-screen say-chip, if any
- control_target:  which running task
- control_action:  status | change | stop | approve | deny
- warmth:          tone hint for her reply

Exact say-chip matches skip Jev entirely. Any Jev failure falls back to ``chat``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

from typesafe_sdk import Choice, Noul, NoulCriteria, Score

from .jev import Jev

log = logging.getLogger("os1.router")

RouteKind = Literal["chat", "work", "control", "chip", "ignore"]
ControlAction = Literal["status", "change", "stop", "approve", "deny"]

# Thresholds (tune against logged traffic; pin the Jev version once tuned).
P_CHIP = 0.60
P_CONTROL = 0.55
P_WORK = 0.45  # low on purpose: a needless background run is cheaper than a confabulated "I checked"
P_NOT_ADDRESSED = 0.15


@dataclass(frozen=True)
class RunRef:
    run_id: str
    label: str


@dataclass(frozen=True)
class Route:
    kind: RouteKind
    confidence: float = 0.0
    chip: str | None = None
    run_id: str | None = None
    control: ControlAction | None = None
    warmth: float | None = None  # 0..1
    source: Literal["exact", "jev", "fallback"] = "fallback"


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()


def exact_chip(latest: str, chips: list[str]) -> str | None:
    said = _norm(latest)
    for chip in chips:
        if _norm(chip) == said:
            return chip
    return None


class TurnRouter:
    def __init__(self, jev: Jev) -> None:
        self._jev = jev

    async def route(
        self,
        latest: str,
        *,
        recent: list[str],
        chips: list[str],
        runs: list[RunRef],
        pending_approval: str | None = None,
    ) -> Route:
        if hit := exact_chip(latest, chips):
            return Route(kind="chip", confidence=1.0, chip=hit, source="exact")

        state = {
            "latest": latest,
            "recent_conversation": recent[-8:],
            "active_work": [r.label for r in runs],
            "on_screen_phrases": chips,
            "pending_approval": pending_approval or "none",
        }
        questions = self._questions(chips, runs, pending_approval)
        resp = await self._jev.ask(state, questions)
        if resp is None:
            return Route(kind="chat")

        answers = resp.answers
        warmth = None
        if (w := answers.get("warmth")) is not None:
            warmth = max(0.0, min(1.0, float(w.score) / 3.0))

        if (a := answers.get("addressed")) is not None and a.noul < P_NOT_ADDRESSED:
            return Route(kind="ignore", confidence=1 - a.noul, warmth=warmth, source="jev")

        kind = answers["kind"]
        probs = kind.probabilities
        top = kind.choice

        if top == "chip" and probs.get("chip", 0) >= P_CHIP and (c := answers.get("chip")) is not None:
            idx = int(c.choice.split("_")[1])
            if c.probabilities.get(c.choice, 0) >= 0.5:
                return Route(kind="chip", confidence=probs["chip"], chip=chips[idx], warmth=warmth, source="jev")

        if top == "control" and probs.get("control", 0) >= P_CONTROL:
            action = answers.get("control_action")
            target = answers.get("control_target")
            run_id = runs[int(target.choice.split("_")[1])].run_id if (target and runs) else None
            return Route(
                kind="control",
                confidence=probs["control"],
                run_id=run_id,
                control=action.choice if action else "status",  # type: ignore[arg-type]
                warmth=warmth,
                source="jev",
            )

        if probs.get("work", 0) >= P_WORK:
            return Route(kind="work", confidence=probs["work"], warmth=warmth, source="jev")

        return Route(kind="chat", confidence=probs.get("chat", 0), warmth=warmth, source="jev")

    @staticmethod
    def _questions(chips: list[str], runs: list[RunRef], pending_approval: str | None) -> dict:
        kinds: dict[str, object] = {
            "chat": {
                "what": "Talk: conversation, feelings, opinions, jokes, follow-ups, or questions she can answer "
                "from general knowledge or from what she already knows about the user",
                "not_for": "Anything needing current information, the user's email, calendar, files or accounts, "
                "the web, or doing something in the world",
            },
            "work": {
                "what": "Do or find something: look up, check, search, read email or calendar, send, schedule, "
                "book, buy, open, organize, draft something long, use a computer, or remember to do something later",
                "examples": ["Can you look through my email?", "Book the ferry for Saturday", "Find me a good hike"],
            },
        }
        if runs or pending_approval:
            kinds["control"] = {
                "what": "About work already listed in `active_work` or about `pending_approval`: how it's going, "
                "change it, pause or stop it, approve or refuse it",
            }
        if chips:
            kinds["chip"] = {"what": "Says, or clearly refers to, one of `on_screen_phrases`"}

        qs: dict[str, object] = {
            "kind": Choice(instructions="What should Mave do with `latest`?", criteria=kinds),
            "addressed": Noul(
                instructions="Is `latest` said to Mave, the assistant?",
                criteria=NoulCriteria(
                    true="Spoken to her, including short replies continuing `recent_conversation`",
                    false="Clearly said to another person in the room, to a pet, on a phone call, "
                    "read aloud from a screen, or background TV",
                ),
            ),
            "warmth": Score(
                instructions="How emotionally warm or personal is `latest`, given `recent_conversation`?",
                criteria=[
                    "Task-focused and brisk",
                    "Friendly and casual",
                    "Open and reflective",
                    "Deeply personal or vulnerable",
                ],
            ),
        }
        if chips:
            qs["chip"] = Choice(
                instructions="Which phrase in `on_screen_phrases` does `latest` say or refer to?",
                criteria={f"chip_{i}": phrase for i, phrase in enumerate(chips)},
            )
        if runs:
            qs["control_target"] = Choice(
                instructions="Which item in `active_work` is `latest` about?",
                criteria={f"run_{i}": r.label for i, r in enumerate(runs)},
            )
        if runs or pending_approval:
            qs["control_action"] = Choice(
                instructions="What does `latest` want done with that work?",
                criteria={
                    "status": "Wants to know how it's going or what was found",
                    "change": "Wants to change, redirect or add something to it",
                    "stop": "Wants to pause, stop or cancel it",
                    "approve": "Says yes or go ahead to `pending_approval`",
                    "deny": "Says no or don't to `pending_approval`",
                },
            )
        return qs
