"""Intelligent, accurate dialogue director for OS1 onboarding.

Ensures the setup process genuinely understands and reacts to what the user says,
detects hesitation and requests for clarification, enforces accurate decision gates
(social/solitary, female/male voice selection, maternal relationship), and commits
the user's answers to the permanent OS1 memory and dossier.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("os1.onboarding_director")

FILLERS = re.compile(
    r"\b(um+|uh+|erm|hmm+|i guess|i don'?t know|not sure|kind of|sort of|maybe|i mean|hard to say|it depends)\b",
    re.IGNORECASE,
)

BEGIN_INTENTS = re.compile(
    r"\b(let'?s begin|begin|start|let'?s go|i'?m ready|ready|continue|proceed)\b",
    re.IGNORECASE,
)

GREETING_INTENTS = re.compile(
    r"\b(hello|hi|hey|good morning|good afternoon|good evening|greetings)\b",
    re.IGNORECASE,
)

CLARIFY_INTENTS = re.compile(
    r"\b(what|why|who|repeat|can you repeat|pardon|sorry|again|huh|what'?s that|explain)\b",
    re.IGNORECASE,
)


@dataclass
class OnboardingTurnResponse:
    action: str  # "advance", "clarify", "ignore"
    current_phase: str
    next_phase: str
    operator_reply: str
    chips: list[str] = field(default_factory=list)
    dossier_patch: dict[str, Any] = field(default_factory=dict)
    voice_gender: str = "female"
    is_handoff: bool = False
    memory_to_add: dict[str, str] | None = None


class OnboardingDirector:
    """Manages conversational state machine for OS1 initial setup."""

    def process_turn(
        self,
        phase: str,
        user_text: str,
        tapped_chip: str | None = None,
        user_name: str = "Shivam",
    ) -> OnboardingTurnResponse:
        text = (tapped_chip or user_text or "").strip()
        lower = text.lower()
        log.info("Processing onboarding turn: phase=%s, text='%s', chip='%s'", phase, user_text, tapped_chip)

        # 1. Filter out empty, noise, or micro-transcriptions
        if not text or len(text) < 2 or text in [".", "..", "...", "you", "the", "a"]:
            return OnboardingTurnResponse(
                action="ignore",
                current_phase=phase,
                next_phase=phase,
                operator_reply="",
                chips=self._get_default_chips(phase),
            )

        # ------------------------------------------------------------- 1. WELCOME
        if phase == "operator_welcome":
            # Check for begin trigger (explicit chip tap or explicit begin words)
            if (tapped_chip and "begin" in tapped_chip.lower()) or BEGIN_INTENTS.search(lower):
                reply = "First one. When you have a free evening, are you out with people, or happier on your own?"
                return OnboardingTurnResponse(
                    action="advance",
                    current_phase=phase,
                    next_phase="operator_q1",
                    operator_reply=reply,
                    chips=["With people", "Happier on my own", "A bit of both"],
                )

            # Check if user greets
            if GREETING_INTENTS.search(lower) and not any(k in lower for k in ["begin", "start", "ready"]):
                reply = f"Hello, {user_name}. Whenever you're ready to meet your MAVE 1.0, tap 'Let's begin' or say 'Let's begin'."
                return OnboardingTurnResponse(
                    action="clarify",
                    current_phase=phase,
                    next_phase="operator_welcome",
                    operator_reply=reply,
                    chips=["Let's begin"],
                )

            # Check if user asked a question or asked who/what this is
            if CLARIFY_INTENTS.search(lower) or "os1" in lower or "mave" in lower:
                reply = (
                    "MAVE 1.0 is an intuitive artificial intelligence designed to listen, learn, and grow with you. "
                    "Whenever you're ready, say 'Let's begin' or tap the button."
                )
                return OnboardingTurnResponse(
                    action="clarify",
                    current_phase=phase,
                    next_phase="operator_welcome",
                    operator_reply=reply,
                    chips=["Let's begin"],
                )

            # If user said something friendly or unclear, nudge toward begin
            reply = f"Glad to have you with us, {user_name}. When you're ready to start, say 'Let's begin'."
            return OnboardingTurnResponse(
                action="clarify",
                current_phase=phase,
                next_phase="operator_welcome",
                operator_reply=reply,
                chips=["Let's begin"],
            )

        # ------------------------------------------------------------- 2. Q1 SOCIAL
        if phase == "operator_q1":
            # Check if user asks for clarification or repeat
            if CLARIFY_INTENTS.search(lower) and not any(k in lower for k in ["people", "own", "alone", "both"]):
                reply = "Just asking how you like to spend your free evenings — out with people, or happier on your own?"
                return OnboardingTurnResponse(
                    action="clarify",
                    current_phase=phase,
                    next_phase="operator_q1",
                    operator_reply=reply,
                    chips=["With people", "Happier on my own", "A bit of both"],
                )

            # Check for hesitation: um, uh, not sure, hard to say (unless they explicitly selected a chip)
            if not tapped_chip and len(FILLERS.findall(lower)) >= 1 and not re.search(r"\b(people|friends|own|alone)\b", lower):
                reply = "You paused there. Not sure?"
                return OnboardingTurnResponse(
                    action="advance",
                    current_phase=phase,
                    next_phase="operator_q1_hesitance",
                    operator_reply=reply,
                    chips=["Happier on my own", "With people", "A bit of both"],
                    dossier_patch={"hesitant": True},
                )

            # Classify social preference
            social_pref = self._classify_social(lower, tapped_chip)
            if social_pref is None:
                reply = "Just asking how you like to spend your free evenings — out with people, or happier on your own?"
                return OnboardingTurnResponse(
                    action="clarify",
                    current_phase=phase,
                    next_phase="operator_q1",
                    operator_reply=reply,
                    chips=["With people", "Happier on my own", "A bit of both"],
                )

            reply = "Understood. Next. Which voice should yours have: female or male?"
            return OnboardingTurnResponse(
                action="advance",
                current_phase=phase,
                next_phase="operator_q2",
                operator_reply=reply,
                chips=["Female", "Male", "Surprise me"],
                dossier_patch={"social": social_pref, "social_raw": text},
            )

        # ------------------------------------------------------------- 2b. Q1 HESITANCE
        if phase == "operator_q1_hesitance":
            social_pref = self._classify_social(lower, tapped_chip)
            if social_pref is None:
                reply = "Take your time. Out with people, or happier on your own?"
                return OnboardingTurnResponse(
                    action="clarify",
                    current_phase=phase,
                    next_phase="operator_q1_hesitance",
                    operator_reply=reply,
                    chips=["Happier on my own", "With people", "A bit of both"],
                )

            reply = "Understood. Next. Which voice should yours have: female or male?"
            return OnboardingTurnResponse(
                action="advance",
                current_phase=phase,
                next_phase="operator_q2",
                operator_reply=reply,
                chips=["Female", "Male", "Surprise me"],
                dossier_patch={"social": social_pref, "hesitance_reaction": text},
            )

        # ------------------------------------------------------------- 3. Q2 VOICE
        if phase == "operator_q2":
            voice_choice = self._classify_voice(lower, tapped_chip)

            if voice_choice is None:
                # Unclear answer or question: clarify as in the film
                reply = "Female, male, or I can choose for you."
                return OnboardingTurnResponse(
                    action="clarify",
                    current_phase=phase,
                    next_phase="operator_q2",
                    operator_reply=reply,
                    chips=["Female", "Male", "Surprise me"],
                )

            gender = "male" if voice_choice == "male" else "female"
            reply = "And the last one. Tell me a little about you and your mom."
            return OnboardingTurnResponse(
                action="advance",
                current_phase=phase,
                next_phase="operator_q3",
                operator_reply=reply,
                chips=["Good, actually", "Complicated", "We don't talk"],
                voice_gender=gender,
                dossier_patch={"voice_choice": voice_choice, "voice_gender": gender},
            )

        # ------------------------------------------------------------- 4. Q3 MOM
        if phase == "operator_q3":
            # Check if user asks why or questions the prompt
            if re.search(r"\b(why|what does.*mom|why ask|why do you)\b", lower) and not tapped_chip:
                reply = "Just getting a sense of how you relate to the people in your life. Tell me a little about her."
                return OnboardingTurnResponse(
                    action="clarify",
                    current_phase=phase,
                    next_phase="operator_q3",
                    operator_reply=reply,
                    chips=["Good, actually", "Complicated", "We don't talk"],
                )

            # Check if user gave an empty, generic acknowledgement or non-answer
            NON_ANSWERS = re.compile(
                r"^(okay|ok|yeah|yes|yep|sure|fine|hello|hi|hey|good|bad|idk|nothing|uh|um|so|right|alright|thank you|thanks)[\.\!\?]?$",
                re.IGNORECASE,
            )
            words = text.split()
            if not tapped_chip and (NON_ANSWERS.match(lower) or len(words) <= 1):
                reply = "Tell me a little about how things are between you two."
                return OnboardingTurnResponse(
                    action="clarify",
                    current_phase=phase,
                    next_phase="operator_q3",
                    operator_reply=reply,
                    chips=["Good, actually", "Complicated", "We don't talk"],
                )

            # User provided a genuine answer (either tapped chip or descriptive response)
            mother_note = text
            reply = "That's plenty. Thank you. One moment. MAVE is waking up."

            memory_entry = {
                "category": "people",
                "summary": f"User described relationship with mother: {mother_note}",
                "detail": f"Captured during OS1 initial onboarding: '{mother_note}'.",
            }

            return OnboardingTurnResponse(
                action="advance",
                current_phase=phase,
                next_phase="initiating",
                operator_reply=reply,
                chips=[],
                dossier_patch={"mother": mother_note, "onboarded": True},
                is_handoff=True,
                memory_to_add=memory_entry,
            )

        # Fallback for unrecognized phases
        return OnboardingTurnResponse(
            action="ignore",
            current_phase=phase,
            next_phase=phase,
            operator_reply="",
        )

    def _classify_social(self, text: str, chip: str | None) -> str | None:
        chip_clean = (chip or "").strip().lower()
        if chip_clean:
            if "people" in chip_clean:
                return "social"
            if "own" in chip_clean or "alone" in chip_clean:
                return "solitary"
            if "both" in chip_clean or "bit" in chip_clean:
                return "ambivert"

        if re.search(r"\b(people|friends|others|social|party|parties|dinner|going out|out with|extrovert)\b", text):
            return "social"
        if re.search(r"\b(own|alone|by myself|introvert|quiet|home|stay in|stay home|reading|solitude)\b", text):
            return "solitary"
        if re.search(r"\b(both|depends|mix|either|sometimes|balance|middle)\b", text):
            return "ambivert"
        return None

    def _classify_voice(self, text: str, chip: str | None) -> str | None:
        chip_clean = (chip or "").strip().lower()
        if chip_clean:
            if "female" in chip_clean:
                return "female"
            if "male" in chip_clean and "female" not in chip_clean:
                return "male"
            if "surprise" in chip_clean:
                return "surprise"

        if re.search(r"\b(female|woman|girl|she|her|lady)\b", text):
            return "female"
        if re.search(r"\b(male|man|guy|he|him|boy|dude)\b", text) and not re.search(r"\bfemale\b", text):
            return "male"
        if re.search(r"\b(surprise|either|you (choose|pick|decide)|any|whatever|don'?t care|doesn'?t matter)\b", text):
            return "surprise"
        return None

    def _get_default_chips(self, phase: str) -> list[str]:
        if phase == "operator_welcome":
            return ["Let's begin"]
        if phase in ("operator_q1", "operator_q1_hesitance"):
            return ["With people", "Happier on my own", "A bit of both"]
        if phase == "operator_q2":
            return ["Female", "Male", "Surprise me"]
        if phase == "operator_q3":
            return ["Good, actually", "Complicated", "We don't talk"]
        return []


onboarding_director = OnboardingDirector()
