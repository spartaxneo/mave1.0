"""Runtime configuration for the OS1 voice worker. Everything comes from the repo-root .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Voice:
    """One of Samantha's two voices (Paper screen 14)."""

    key: str
    label: str
    reference_id: str
    model: str = "drama-3"
    speed: float = 1.0
    temperature: float = 0.7


def voices() -> dict[str, Voice]:
    """Voice registry. Each LiveKit Agent gets its own TTS, so swapping voices mid-session
    (operator -> Samantha, or Voice I -> Voice II) is an agent handoff in the same room."""
    return {
        # The onboarding operator: matches Samantha voice by default so the voice never changes after Hello.
        "operator": Voice(
            key="operator",
            label="Operator",
            reference_id=_env("FISH_OPERATOR_VOICE_ID") or _env("FISH_VOICE_1_ID"),
            speed=0.96,
            temperature=0.72,
        ),
        "voice_1_warm": Voice(
            key="voice_1_warm",
            label="Voice I",
            reference_id=_env("FISH_VOICE_1_ID"),
            speed=0.96,
            temperature=0.72,
        ),
        "voice_2_bright": Voice(
            key="voice_2_bright",
            label="Voice II",
            reference_id=_env("FISH_VOICE_2_ID"),
            speed=1.05,
            temperature=0.65,
        ),
        # Optional: chosen when the user answers "male" in onboarding.
        "voice_male": Voice(
            key="voice_male",
            label="Voice (male)",
            reference_id=_env("FISH_VOICE_MALE_ID"),
            speed=1.0,
            temperature=0.7,
        ),
    }


# Onboarding Q2 answer -> voice key. "surprise" picks at random among configured ones.
VOICE_FOR_GENDER = {"female": "voice_1_warm", "male": "voice_male"}


@dataclass(frozen=True)
class Settings:
    hermes_api_url: str = field(default_factory=lambda: _env("HERMES_API_URL", "http://127.0.0.1:8642"))
    hermes_api_key: str = field(default_factory=lambda: _env("HERMES_API_KEY"))
    # Hermes model_routes aliases (hermes/profile/config.yaml).
    hermes_voice_model: str = field(default_factory=lambda: _env("HERMES_VOICE_MODEL", "samantha-voice"))
    hermes_work_model: str = field(default_factory=lambda: _env("HERMES_WORK_MODEL", "samantha-work"))
    # Durable memory scope: one per person, stable across calls.
    session_key: str = field(default_factory=lambda: _env("OS1_SESSION_KEY", "agent:samantha:voice:primary"))
    default_voice: str = field(default_factory=lambda: _env("OS1_DEFAULT_VOICE", "voice_1_warm"))
    # Jev (TypeSafe System One). live | off
    jev_transport: str = field(default_factory=lambda: _env("JEV_TRANSPORT", "live"))
    jev_model: str = field(default_factory=lambda: _env("JEV_MODEL", "jev-1.14.0"))
    jev_budget_s: float = field(default_factory=lambda: float(_env("JEV_BUDGET_S", "0.6")))
    typesafe_api_key: str = field(default_factory=lambda: _env("TYPESAFE_API_KEY"))

    @property
    def jev_enabled(self) -> bool:
        return self.jev_transport == "live" and bool(self.typesafe_api_key)
