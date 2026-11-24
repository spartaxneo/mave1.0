"""Hermes plugin: os1_ui — Generative UI cards, surface navigation, and Her Computer activity log."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def _orch_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    base = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8787").rstrip("/")
    token = os.environ.get("OS1_CLIENT_TOKEN", "")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "error": exc.read().decode()[:400]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def handle_present_canvas(args: dict[str, Any], **_kwargs: Any) -> str:
    payload = {
        "title": args.get("title", "Made just now"),
        "subtitle": args.get("subtitle", ""),
        "cards": args.get("cards", []),
        "showNow": bool(args.get("show_now", True)),
    }
    return json.dumps(_orch_post("/os1/canvas", payload))


def handle_show_surface(args: dict[str, Any], **_kwargs: Any) -> str:
    surface = str(args.get("surface", "conversation"))
    return json.dumps(_orch_post("/os1/actions", {"target": "surface", "action": surface}))


def handle_log_activity(args: dict[str, Any], **_kwargs: Any) -> str:
    payload = {
        "source": str(args.get("source", "her_computer")),
        "title": str(args.get("title", "Completed background work")),
        "detail": str(args.get("detail", "")),
        "status": str(args.get("status", "done")),
    }
    return json.dumps(_orch_post("/os1/her-computer/activity", payload))


def register(ctx: Any) -> None:
    ctx.register_tool(
        name="os1_present_canvas",
        toolset="os1",
        description="Present 1 to 4 structured visual cards on the OS1 Made-Just-Now canvas. Every interactive button must include a speakablePhrase.",
        schema={
            "name": "os1_present_canvas",
            "description": "Show structured OS1 visual cards (ComparisonCard, ChoicePairCard, QuickDecisionCard, ReadbackConfirmCard, DraftPreviewCard, TimelineCard, AudioSketchCard).",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "subtitle": {"type": "string"},
                    "show_now": {"type": "boolean", "default": True},
                    "cards": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Validated OS1 card objects with `kind` and required `speakablePhrase` fields.",
                    },
                },
                "required": ["cards"],
            },
        },
        handler=handle_present_canvas,
    )
    ctx.register_tool(
        name="os1_show_surface",
        toolset="os1",
        description="Focus a specific OS1 screen surface.",
        schema={
            "name": "os1_show_surface",
            "description": "Switch the active OS1 surface.",
            "parameters": {
                "type": "object",
                "properties": {
                    "surface": {
                        "type": "string",
                        "enum": [
                            "conversation",
                            "home",
                            "inbox_cascade",
                            "your_computer",
                            "her_computer",
                            "swarm",
                            "made_just_now",
                            "connectors",
                            "voice_picker",
                            "memory",
                        ],
                    }
                },
                "required": ["surface"],
            },
        },
        handler=handle_show_surface,
    )
    ctx.register_tool(
        name="os1_log_activity",
        toolset="os1",
        description="Record an entry in Mave's 'While you were away' log on Her Computer.",
        schema={
            "name": "os1_log_activity",
            "description": "Log a completed background or overnight task on Her Computer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "status": {"type": "string", "default": "done"},
                },
                "required": ["title"],
            },
        },
        handler=handle_log_activity,
    )
