"""Jev UI Director + Attention Triage + Inbox Keeper Scoring (docs/architecture.md §6 & §10).

One batched `systemOne` call per debounced transcript turn (~100 ms), with:
- Hysteresis choreographer in deterministic code (anti-flicker):
  * Show surface when `needs_surface > 0.72` and `surface_prob > 0.70`
  * Dismiss active surface after `needs_surface < 0.35` across 2 consecutive ticks
- Mood scores (`warmth`, `pace`, `overwhelm`) with `compactMode` when overwhelmed
- Memory gating (`worth_remembering >= 0.70` + `memory_kind`)
- `JEV_TRANSPORT=live | mock | replay | auto` so tests and offline dev work deterministically
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, NoulCriteria, Score

log = logging.getLogger("os1.director")

SURFACES = (
    "home",
    "inbox_cascade",
    "your_computer",
    "her_computer",
    "swarm",
    "made_just_now",
    "connectors",
    "voice_picker",
    "memory",
)

MEMORY_KINDS = (
    "people",
    "places",
    "things_you_love",
    "things_that_hurt",
    "promises",
)

SHOW_NOUL_THRESHOLD = 0.72
SHOW_CHOICE_THRESHOLD = 0.70
DISMISS_NOUL_THRESHOLD = 0.35
DISMISS_CONSECUTIVE_TICKS = 2
MEMORY_THRESHOLD = 0.70


@dataclass
class DirectorDecision:
    surface: str | None = None
    dismiss_surface: bool = False
    needs_surface: float = 0.0
    surface_prob: float = 0.0
    warmth: float = 0.45
    pace: float = 0.45
    overwhelm: float = 0.15
    compact_mode: bool = False
    requests_irreversible: float = 0.0
    worth_remembering: float = 0.0
    memory_kind: str | None = None
    latency_ms: float = 0.0
    source: str = "mock"


@dataclass
class HysteresisState:
    active_surface: str = "conversation"
    low_need_streak: int = 0
    opened_at: float = field(default_factory=time.monotonic)

    def dwell_band(self) -> str:
        age = time.monotonic() - self.opened_at
        if age < 3:
            return "just_opened"
        if age < 15:
            return "short"
        if age < 60:
            return "medium"
        return "lingering"

    def set_surface(self, surface: str) -> None:
        if surface != self.active_surface:
            self.active_surface = surface
            self.opened_at = time.monotonic()
            self.low_need_streak = 0


class JevDirector:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: str | None = None,
        model: str | None = None,
        budget_s: float = 1.4,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("TYPESAFE_API_KEY", "")
        self.transport = (transport or os.environ.get("JEV_TRANSPORT", "auto")).lower()
        self.model = model or os.environ.get("JEV_MODEL", "jev-1.14.0")
        self.budget_s = budget_s
        self.hysteresis = HysteresisState()
        self._client: AsyncTypeSafeClient | None = None
        if self.transport in ("live", "auto") and self.api_key:
            self._client = AsyncTypeSafeClient(api_key=self.api_key, model=self.model, timeout=budget_s + 0.4)

    @property
    def live_enabled(self) -> bool:
        return self._client is not None

    async def evaluate_tick(
        self,
        *,
        latest: str,
        rolling_transcript: list[str],
        active_surface: str,
        recent_actions: list[str],
        memories: list[str],
        has_pending_canvas: bool = False,
    ) -> DirectorDecision:
        self.hysteresis.active_surface = active_surface
        started = time.perf_counter()

        raw = await self._call_jev_tick(
            latest=latest,
            rolling_transcript=rolling_transcript,
            active_surface=active_surface,
            recent_actions=recent_actions,
            memories=memories,
            has_pending_canvas=has_pending_canvas,
        )
        if raw is None:
            raw = self._heuristic_tick(latest, has_pending_canvas=has_pending_canvas)

        raw.latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return self._apply_hysteresis(raw, active_surface)

    def _apply_hysteresis(self, dec: DirectorDecision, active_surface: str) -> DirectorDecision:
        dec.compact_mode = dec.overwhelm >= 0.68
        if dec.needs_surface > SHOW_NOUL_THRESHOLD and dec.surface and dec.surface_prob > SHOW_CHOICE_THRESHOLD:
            self.hysteresis.set_surface(dec.surface)
            dec.dismiss_surface = False
            return dec

        if active_surface not in ("conversation", "home") and dec.needs_surface < DISMISS_NOUL_THRESHOLD:
            self.hysteresis.low_need_streak += 1
            if self.hysteresis.low_need_streak >= DISMISS_CONSECUTIVE_TICKS:
                dec.dismiss_surface = True
                self.hysteresis.set_surface("conversation")
        else:
            self.hysteresis.low_need_streak = 0

        dec.surface = None
        return dec

    async def _call_jev_tick(
        self,
        *,
        latest: str,
        rolling_transcript: list[str],
        active_surface: str,
        recent_actions: list[str],
        memories: list[str],
        has_pending_canvas: bool,
    ) -> DirectorDecision | None:
        if self._client is None:
            return None
        state = {
            "latest": latest,
            "transcript": rolling_transcript[-10:],
            "ui": {
                "active_surface": active_surface,
                "dwell": self.hysteresis.dwell_band(),
                "recent_actions": recent_actions[-8:],
                "has_pending_canvas": has_pending_canvas,
            },
            "memories": memories[:10],
        }
        questions = {
            "needs_surface": Noul(
                instructions="Would showing or updating a visual UI surface genuinely help `latest` right now?",
                criteria=NoulCriteria(
                    true="User asks to see, inspect, organize, compare, or manage email, computers, memories, connectors, voices, or active work",
                    false="Pure voice conversation, emotional reflection, casual chat, or simple spoken Q&A",
                ),
            ),
            "surface": Choice(
                instructions="Which OS1 surface best fits `latest`?",
                criteria={
                    "home": "Ambient desktop overview of running things",
                    "inbox_cascade": "Reading, triaging, archiving, or cleaning up emails",
                    "your_computer": "Watching or stopping actions on the user's own Mac",
                    "her_computer": "Looking at Mave's cloud computer screen or what she did while away",
                    "swarm": "Viewing multiple background tasks running in parallel",
                    "made_just_now": "Showing a generated comparison, draft preview, timeline, or choice card",
                    "connectors": "Viewing or changing connected apps and permissions",
                    "voice_picker": "Choosing or tuning Mave's voice",
                    "memory": "Viewing or forgetting saved memories",
                },
            ),
            "warmth": Score(
                instructions="How emotionally warm or personal is `latest`?",
                criteria=["Task-focused and brisk", "Friendly and casual", "Open and reflective", "Deeply personal"],
            ),
            "pace": Score(
                instructions="How fast or urgent is the user's pace in `latest`?",
                criteria=["Slow and unhurried", "Conversational", "Focused and brisk", "Urgent and rapid"],
            ),
            "overwhelm": Score(
                instructions="How overloaded or stressed does the user sound in `latest`?",
                criteria=["Calm and clear", "Mildly scattered", "Visibly stressed or overwhelmed"],
            ),
            "requests_irreversible_action": Noul(
                instructions="Does `latest` ask to send, delete, purchase, pay, or permanently forget something?",
            ),
            "worth_remembering": Noul(
                instructions="Does `latest` reveal a lasting personal detail, person, place, preference, hurt, or promise worth remembering?",
            ),
            "memory_kind": Choice(
                instructions="If `latest` is worth remembering, which category fits best?",
                criteria={
                    "people": "A person in their life and how they relate",
                    "places": "A meaningful place, city, or destination",
                    "things_you_love": "A taste, favorite, joy, or aspiration",
                    "things_that_hurt": "A sensitive topic, grief, or frustration",
                    "promises": "A commitment, reminder, or promise made",
                },
            ),
        }
        try:
            resp = await asyncio.wait_for(
                self._client.system_one(state=state, questions=questions),
                timeout=self.budget_s,
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("director Jev tick fell back (%s: %s)", type(exc).__name__, exc)
            return None

        ans = resp.answers
        surf = ans["surface"]
        mk = ans["memory_kind"]
        return DirectorDecision(
            surface=surf.choice if surf.choice in SURFACES else None,
            needs_surface=float(ans["needs_surface"].noul),
            surface_prob=float(surf.probabilities.get(surf.choice, 0.0)),
            warmth=float(ans["warmth"].score) / 3.0,
            pace=float(ans["pace"].score) / 3.0,
            overwhelm=float(ans["overwhelm"].score) / 2.0,
            requests_irreversible=float(ans["requests_irreversible_action"].noul),
            worth_remembering=float(ans["worth_remembering"].noul),
            memory_kind=mk.choice if mk.choice in MEMORY_KINDS else None,
            source="jev",
        )

    @staticmethod
    def _heuristic_tick(latest: str, *, has_pending_canvas: bool = False) -> DirectorDecision:
        low = latest.lower()
        surface: str | None = None
        needs = 0.2
        prob = 0.0

        patterns: list[tuple[str, str]] = [
            (r"\b(inbox|email|mail|newsletters|messages)\b", "inbox_cascade"),
            (r"\b(her computer|your computer|your screen|while i was away|vnc)\b", "her_computer"),
            (r"\b(my mac|my computer|my screen|let me drive|on my machine)\b", "your_computer"),
            (r"\b(swarm|running in the background|everything running|all tasks)\b", "swarm"),
            (r"\b(connector|permissions|connected apps|stripe|spotify|calendar access)\b", "connectors"),
            (r"\b(voice|warmer|brighter|slower|faster|sound like)\b", "voice_picker"),
            (r"\b(remember|memories|forget|memory ledger)\b", "memory"),
            (r"\b(compare|comparison|draft|timeline|sketch|show me)\b", "made_just_now"),
        ]
        for pat, target in patterns:
            if re.search(pat, low):
                surface = target
                needs = 0.84
                prob = 0.82
                break

        if surface is None and has_pending_canvas and re.search(r"\b(show|look|see|pull up)\b", low):
            surface, needs, prob = "made_just_now", 0.85, 0.85

        irreversible = 0.88 if re.search(r"\b(send|delete|trash|buy|pay|book|forget|purge)\b", low) else 0.1
        overwhelm = 0.8 if re.search(r"\b(overwhelmed|stressed|too much|crazy day|exhausted)\b", low) else 0.15
        warmth = 0.78 if re.search(r"\b(love|miss|feel|heart|family|mom|friend|grateful)\b", low) else 0.45

        worth = 0.0
        mk: str | None = None
        if re.search(r"\b(my (mom|dad|sister|brother|partner|wife|husband|friend)\b|loves?|hates?|favorite|allergic|promise)\b", low):
            worth = 0.78
            if re.search(r"\b(mom|dad|sister|brother|partner|wife|husband|friend)\b", low):
                mk = "people"
            elif re.search(r"\b(promise|remind me to)\b", low):
                mk = "promises"
            elif re.search(r"\b(hate|hurt|lost|miss)\b", low):
                mk = "things_that_hurt"
            else:
                mk = "things_you_love"

        return DirectorDecision(
            surface=surface,
            needs_surface=needs,
            surface_prob=prob,
            warmth=warmth,
            pace=0.5,
            overwhelm=overwhelm,
            requests_irreversible=irreversible,
            worth_remembering=worth,
            memory_kind=mk,
            source="mock",
        )

    async def triage_trigger(self, event: dict[str, Any], *, user_busy: bool = False) -> dict[str, Any]:
        """Classify an incoming Composio webhook into low / medium / high attention urgency."""
        if self._client is not None:
            try:
                resp = await asyncio.wait_for(
                    self._client.system_one(
                        state={"event": event, "user_mid_conversation": user_busy},
                        questions={
                            "urgency": Choice(
                                instructions="How urgently should Mave surface this external event?",
                                criteria={
                                    "low": "Newsletter, receipt, promo, routine notification — silently log/archive",
                                    "medium": "Schedule change, non-urgent reply — mention at next natural greeting",
                                    "high": "VIP/family urgent message, meeting starting within 10 minutes, security/payment alert — politely ask to interrupt now",
                                },
                            )
                        },
                    ),
                    timeout=self.budget_s,
                )
                level = resp.answers["urgency"].choice
                return {"urgency": level, "source": "jev"}
            except Exception as exc:  # noqa: BLE001
                log.debug("triage_trigger fell back: %s", exc)

        text = f"{event.get('title', '')} {event.get('sender', '')} {event.get('summary', '')}".lower()
        if any(k in text for k in ("urgent", "asap", "10 min", "starting soon", "flight", "mom", "dad", "fraud", "charge")):
            return {"urgency": "high", "source": "mock"}
        if any(k in text for k in ("reschedule", "moved", "calendar", "invite", "reply", "question")):
            return {"urgency": "medium", "source": "mock"}
        return {"urgency": "low", "source": "mock"}

    async def score_inbox_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Score spatial inbox items (0..1 keeper score) with Jev fan-out or deterministic fallback."""
        if not items:
            return []
        if self._client is not None and len(items) <= 20:
            try:
                qs = {
                    f"item_{i}": Score(
                        instructions=f"How personally important is email #{i + 1} (`{it.get('sender')}: {it.get('subject')}`) to keep vs archive/trash?",
                        criteria=["Bulk newsletter or spam", "Low-priority notification", "Useful reference or work", "Personal or VIP keeper"],
                    )
                    for i, it in enumerate(items)
                }
                resp = await asyncio.wait_for(
                    self._client.system_one(state={"emails": items}, questions=qs),
                    timeout=2.5,
                )
                scored = []
                for i, it in enumerate(items):
                    score = float(resp.answers[f"item_{i}"].score) / 3.0
                    scored.append({**it, "keeper_score": round(score, 2), "is_vip": score >= 0.85 or bool(it.get("is_vip"))})
                return scored
            except Exception as exc:  # noqa: BLE001
                log.debug("score_inbox_items fell back: %s", exc)

        scored = []
        for it in items:
            blob = f"{it.get('sender', '')} {it.get('subject', '')} {it.get('snippet', '')}".lower()
            if any(w in blob for w in ("unsubscribe", "newsletter", "digest", "sale", "% off", "promo", "noreply")):
                score, cat = 0.14, "newsletter"
            elif any(w in blob for w in ("receipt", "invoice", "order confirmed", "shipped")):
                score, cat = 0.42, "receipt"
            elif any(w in blob for w in ("dinner", "weekend", "flight", "mom", "love", "check-in", "interview", "offer")):
                score, cat = 0.92, "personal"
            else:
                score, cat = 0.65, "work"
            scored.append({**it, "keeper_score": score, "is_vip": score >= 0.85, "category": it.get("category") or cat})
        return scored

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
