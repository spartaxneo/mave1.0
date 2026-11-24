"""Inkling sub-10ms micro-router for OS1.

Classifies incoming spoken/text inputs in under 10ms into:
1. PILL: Deterministic OS1 screen pill actions (email, inbox, audio sketch, memories)
2. WISPR_COMMAND: Dictation rewrite and formatting commands
3. SCREEN_CONTROL: UI-TARS desktop computer use actions
4. MOBILE_ACTION: Mobile-Agent smartphone actions
5. CONVERSATION: Warm conversational dialogue routed to Samantha's brain
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RouteCategory(str, Enum):
    PILL = "pill"
    WISPR_COMMAND = "wispr_command"
    SCREEN_CONTROL = "screen_control"
    MOBILE_ACTION = "mobile_action"
    CONVERSATION = "conversation"


@dataclass
class InklingRoute:
    category: RouteCategory
    action: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    latency_ms: float = 0.0


# Deterministic Pill Patterns
PILL_PATTERNS: list[tuple[str, str]] = [
    (r"\b(read|open|check)\s+(my\s+)?(emails?|inbox|messages?)\b", "read_email"),
    (r"\b(clean|delete|clear|empty)\s+(the\s+)?(newsletters?|spam|junk)\b", "clean_newsletters"),
    (r"\b(undo|revert|bring back)\b", "undo_cleanup"),
    (r"\b(compose|play|make|write)\s+(a\s+)?(piano|song|melody|audio sketch|music)\b", "compose_piano"),
    (r"\b(what do you remember|show memories|recall|open memory)\b", "show_memories"),
    (r"\b(goodnight|good night|go to sleep|sleep now)\b", "goodnight"),
    (r"\b(hold on|wait a sec|pause)\b", "pause"),
    (r"\b(show me|let me see)\b", "show_me"),
]

# Wispr Command Patterns
WISPR_PATTERNS: list[tuple[str, str]] = [
    (r"^(?:command|rewrite|action|make this)\s*[:,\-]?\s*(.*)$", "rewrite"),
    (r"\b(make this|rewrite as)\s+(more\s+)?(formal|polite|professional)\b", "make_formal"),
    (r"\b(make this|rewrite as)\s+(more\s+)?(concise|brief|shorter|short)\b", "make_concise"),
    (r"\b(fix|correct)\s+(the\s+)?(grammar|spelling|typos)\b", "fix_grammar"),
    (r"\b(format as|convert to)\s+(bullet points?|a list|markdown list)\b", "format_list"),
]

# Screen Control (UI-TARS) Patterns
SCREEN_PATTERNS: list[tuple[str, str]] = [
    (r"\b(click|press|tap)\s+(on\s+)?(the\s+)?(button|icon|menu|tab|link|window|checkbox)\b", "click_element"),
    (r"\b(click on|click)\s+['\"]?([a-zA-Z0-9\s]+)['\"]?", "click"),
    (r"\b(scroll|swipe)\s+(up|down|left|right)\b", "scroll"),
    (r"\b(type|enter|input)\s+['\"]?([^'\"]+)['\"]?\s+(into|in)\b", "type_text"),
    (r"\b(take a\s+)?(screenshot|capture the screen)\b", "take_screenshot"),
    (r"\b(open application|launch app|open app)\s+([a-zA-Z0-9\s]+)\b", "launch_app"),
]

# Mobile Action (Mobile-Agent) Patterns
MOBILE_PATTERNS: list[tuple[str, str]] = [
    (r"\b(on my phone|on mobile|in whatsapp|in uber|in instagram)\b", "mobile_context"),
    (r"\b(open mobile app|launch mobile)\s+([a-zA-Z0-9\s]+)\b", "launch_mobile_app"),
    (r"\b(send whatsapp|send text|send sms)\s+(to\s+)?([a-zA-Z0-9\s]+)\b", "send_mobile_message"),
]


class InklingRouter:
    """Sub-10ms regex & token classifier."""

    def __init__(self) -> None:
        # Precompile all regex patterns for maximum sub-millisecond execution
        self.pills = [(re.compile(pat, re.IGNORECASE), action) for pat, action in PILL_PATTERNS]
        self.wispr = [(re.compile(pat, re.IGNORECASE), action) for pat, action in WISPR_PATTERNS]
        self.screen = [(re.compile(pat, re.IGNORECASE), action) for pat, action in SCREEN_PATTERNS]
        self.mobile = [(re.compile(pat, re.IGNORECASE), action) for pat, action in MOBILE_PATTERNS]

    def route(self, text: str) -> InklingRoute:
        """Classify input text in <10ms."""
        start = time.perf_counter()
        normalized = text.strip()

        if not normalized:
            elapsed = (time.perf_counter() - start) * 1000.0
            return InklingRoute(
                category=RouteCategory.CONVERSATION,
                latency_ms=round(elapsed, 3),
            )

        # 1. Check Pills
        for rx, action in self.pills:
            m = rx.search(normalized)
            if m:
                elapsed = (time.perf_counter() - start) * 1000.0
                return InklingRoute(
                    category=RouteCategory.PILL,
                    action=action,
                    params={"matched": m.group(0)},
                    latency_ms=round(elapsed, 3),
                )

        # 2. Check Wispr Commands
        for rx, action in self.wispr:
            m = rx.search(normalized)
            if m:
                elapsed = (time.perf_counter() - start) * 1000.0
                return InklingRoute(
                    category=RouteCategory.WISPR_COMMAND,
                    action=action,
                    params={"command": m.group(1) if m.groups() else normalized},
                    latency_ms=round(elapsed, 3),
                )

        # 3. Check Mobile Actions
        for rx, action in self.mobile:
            m = rx.search(normalized)
            if m:
                elapsed = (time.perf_counter() - start) * 1000.0
                return InklingRoute(
                    category=RouteCategory.MOBILE_ACTION,
                    action=action,
                    params={"matched": m.group(0)},
                    latency_ms=round(elapsed, 3),
                )

        # 4. Check Screen Control (Desktop)
        for rx, action in self.screen:
            m = rx.search(normalized)
            if m:
                elapsed = (time.perf_counter() - start) * 1000.0
                return InklingRoute(
                    category=RouteCategory.SCREEN_CONTROL,
                    action=action,
                    params={"matched": m.group(0)},
                    latency_ms=round(elapsed, 3),
                )

        # 5. Default to Conversation
        elapsed = (time.perf_counter() - start) * 1000.0
        return InklingRoute(
            category=RouteCategory.CONVERSATION,
            latency_ms=round(elapsed, 3),
        )
