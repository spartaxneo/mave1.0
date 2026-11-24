"""Deterministic zero-LLM speakable-pill matcher (docs/architecture.md §5).

Every interactive control on screen carries a speakable phrase. Before any LLM or Jev
call is spent, the orchestrator matches the utterance against visible phrases, active
modal options, the 60 s undo toast, and built-in OS1 surface/safety phrases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

FILLER_PREFIX = re.compile(
    r"^(?:hey\s+mave|mave|hey\s+samantha|samantha|okay|ok|yeah|yes|sure|please|can\s+you|could\s+you|go\s+ahead\s+and|just)\s+",
    re.IGNORECASE,
)

# Always-available OS1 safety & navigation phrases (spoken voice-native navigation).
GLOBAL_PHRASES: list[dict[str, Any]] = [
    {"phrase": "let me drive", "aliases": ["take over", "stop computer use", "give me back my mouse", "hands off"], "target": "cua", "action": "revoke"},
    {"phrase": "undo that", "aliases": ["undo", "take that back", "reverse that"], "target": "undo", "action": "latest"},
    {"phrase": "show me your computer", "aliases": ["show me her computer", "open your computer", "let me watch your screen"], "target": "surface", "action": "her_computer"},
    {"phrase": "show me my computer", "aliases": ["what are you doing on my mac", "show my screen activity"], "target": "surface", "action": "your_computer"},
    {"phrase": "connect to gmail", "aliases": ["connect my email", "connect gmail", "link my gmail", "connect my gmail", "connect it to gmail", "connect mail"], "target": "connect", "action": "gmail"},
    {"phrase": "connect my calendar", "aliases": ["connect google calendar", "link my calendar", "connect calendar"], "target": "connect", "action": "googlecalendar"},
    {"phrase": "connect my drive", "aliases": ["connect google drive", "link my files", "connect files"], "target": "connect", "action": "googledrive"},
    {"phrase": "connect slack", "aliases": ["link slack", "connect my slack"], "target": "connect", "action": "slack"},
    {"phrase": "show me my inbox", "aliases": ["open my inbox", "show my email", "show me my mail", "look through my email", "check my email", "check my inbox"], "target": "inbox", "action": "open_inbox"},
    {"phrase": "show me what you remember", "aliases": ["open my memories", "show my memories", "show memory"], "target": "surface", "action": "memory"},
    {"phrase": "show connectors", "aliases": ["show my apps", "open connectors", "what are you connected to"], "target": "surface", "action": "connectors"},
    {"phrase": "change your voice", "aliases": ["open voice settings", "show voices", "voice settings"], "target": "surface", "action": "voice_picker"},
    {"phrase": "show everything running", "aliases": ["show swarm", "show background tasks", "open swarm"], "target": "surface", "action": "swarm"},
    {"phrase": "stop that", "aliases": ["stop it", "stop background task", "cancel task", "stop task"], "target": "swarm", "action": "stop_latest"},
    {"phrase": "how is it going", "aliases": ["how's it going", "how's the task going", "how is the background task going"], "target": "swarm", "action": "status_active"},
    {"phrase": "clear finished tasks", "aliases": ["clear done", "dismiss finished tasks", "clear swarm"], "target": "swarm", "action": "clear_done"},
    {"phrase": "go home", "aliases": ["back to home", "clear the screen", "just talk"], "target": "surface", "action": "conversation"},
    {"phrase": "show desktop", "aliases": ["open home", "show home"], "target": "surface", "action": "home"},
    {"phrase": "a little warmer", "aliases": ["sound warmer", "warmer voice"], "target": "voice_tweak", "action": "warmer"},
    {"phrase": "slow down", "aliases": ["speak slower", "a little slower"], "target": "voice_tweak", "action": "slower"},
    {"phrase": "a little faster", "aliases": ["speed up", "speak faster"], "target": "voice_tweak", "action": "faster"},
    {"phrase": "switch to voice two", "aliases": ["use bright voice", "try the brighter voice"], "target": "voice_tweak", "action": "voice_2_bright"},
    {"phrase": "switch to voice one", "aliases": ["use warm voice", "back to the warm voice"], "target": "voice_tweak", "action": "voice_1_warm"},
    {"phrase": "trash the newsletters", "aliases": ["trash newsletters", "delete newsletters", "clean newsletters", "clear newsletters", "trash junk"], "target": "inbox", "action": "trash_newsletters"},
    {"phrase": "play it", "aliases": ["play", "play audio sketch", "play the piano", "play music", "play song", "listen to it"], "target": "canvas", "action": "play"},
    {"phrase": "show canvas", "aliases": ["open canvas", "show made just now", "made just now", "show cards"], "target": "surface", "action": "canvas"},
    {"phrase": "read mom's email", "aliases": ["open mom's email", "read mom", "mom's email"], "target": "inbox", "action": "open", "payload": {"number": 1}},
]

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
}


def norm(text: str) -> str:
    s = re.sub(r"[^a-z0-9'\s]+", " ", text.lower()).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def strip_filler(text: str) -> str:
    s = norm(text)
    for _ in range(3):
        nxt = FILLER_PREFIX.sub("", s).strip()
        if nxt == s:
            break
        s = nxt
    return s


def _token_score(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    if inter == 0:
        return 0.0
    return (2.0 * inter) / (len(ta) + len(tb))


@dataclass(frozen=True)
class PillMatch:
    phrase: str
    target: str
    action: str
    confidence: float
    payload: dict[str, Any]


def match_pill(
    utterance: str,
    visible_pills: list[dict[str, Any]],
    *,
    active_surface: str = "conversation",
    has_undo: bool = False,
) -> PillMatch | None:
    """Resolve an utterance against visible pills + global phrases without an LLM call."""
    raw = norm(utterance)
    stripped = strip_filler(utterance)
    if not raw:
        return None

    # 1. Exact & stripped-filler match against currently visible screen/modal pills first (highest priority).
    for pill in visible_pills:
        candidates = [pill["phrase"], *pill.get("aliases", [])]
        for cand in candidates:
            nc = norm(cand)
            if not nc:
                continue
            if raw == nc or stripped == nc:
                return PillMatch(
                    phrase=pill["phrase"],
                    target=str(pill.get("target") or "chip"),
                    action=str(pill.get("action") or pill["phrase"]),
                    confidence=1.0,
                    payload=dict(pill.get("payload") or {}),
                )

    # 2. Spatial inbox voice addressing: "open number twelve" / "trash number 4" / "archive 3"
    if active_surface == "inbox_cascade":
        m = re.search(r"\b(open|read|archive|trash|delete|keep)\s+(?:number\s+)?(\d+|" + "|".join(NUMBER_WORDS) + r")\b", stripped)
        if m:
            verb = m.group(1)
            tok = m.group(2)
            num = int(tok) if tok.isdigit() else NUMBER_WORDS[tok]
            return PillMatch(
                phrase=f"{verb} number {num}",
                target="inbox",
                action=verb,
                confidence=0.95,
                payload={"number": num},
            )

    # 3. High-confidence fuzzy match against visible pills (>= 0.80 Dice token overlap).
    best: PillMatch | None = None
    for pill in visible_pills:
        candidates = [pill["phrase"], *pill.get("aliases", [])]
        for cand in candidates:
            score = _token_score(stripped, norm(cand))
            if score >= 0.80 and (best is None or score > best.confidence):
                best = PillMatch(
                    phrase=pill["phrase"],
                    target=str(pill.get("target") or "chip"),
                    action=str(pill.get("action") or pill["phrase"]),
                    confidence=score,
                    payload=dict(pill.get("payload") or {}),
                )
    if best is not None:
        return best

    # 4. Global navigation / safety / voice-tweak phrases.
    for entry in GLOBAL_PHRASES:
        if entry["target"] == "undo" and not has_undo:
            continue
        for cand in [entry["phrase"], *entry.get("aliases", [])]:
            nc = norm(cand)
            if raw == nc or stripped == nc or _token_score(stripped, nc) >= 0.84:
                return PillMatch(
                    phrase=entry["phrase"],
                    target=entry["target"],
                    action=entry["action"],
                    confidence=0.95 if (raw == nc or stripped == nc) else 0.85,
                    payload=dict(entry.get("payload") or {}),
                )

    return None
