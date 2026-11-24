"""Realtime OS1 State Hub: WebSocket /os1/events broadcast, PendingAction bus, Cua tunnel."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from .cards import extract_card_phrases
from .store import Os1Store

log = logging.getLogger("os1.bus")

BOUNDED_CUA_MANIFEST: dict[str, Any] = {
    "version": "3",
    "mode": "bounded",
    "desktop": {"display": False},
    "allowedApps": ["Finder", "Notes", "Calendar", "Safari", "Google Chrome", "Preview", "Music"],
    "allowedPaths": ["~/Desktop", "~/Documents", "~/Downloads"],
    "blockedApps": ["Terminal", "iTerm", "Keychain Access", "System Settings", "1Password", "Bitwarden"],
    "telemetryEnabled": False,
}


@dataclass
class PendingAction:
    id: str
    source: str  # "hermes" | "cua" | "triage" | "memory"
    title: str
    summaryLines: list[str]
    stakes: str  # "low" | "shared" | "money" | "forget" | "computer"
    options: list[dict[str, str]]  # [{"phrase": "...", "choice": "..."}]
    runId: str | None = None
    requestId: str | None = None
    executionGeneration: Any = None
    allowRememberRule: bool = False
    meta: dict[str, Any] = field(default_factory=dict)
    createdAt: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "summaryLines": self.summaryLines,
            "stakes": self.stakes,
            "options": self.options,
            "runId": self.runId,
            "requestId": self.requestId,
            "allowRememberRule": self.allowRememberRule,
            "createdAt": self.createdAt,
        }


class StateHub:
    """Canonical live UI state shared across all connected desktop clients and services."""

    def __init__(self, store: Os1Store) -> None:
        self.store = store
        self.clients: set[WebSocket] = set()
        self.active_surface: str = "conversation"
        self.mood: dict[str, Any] = {"warmth": 0.45, "pace": 0.45, "overwhelm": 0.15, "compactMode": False}
        self.runs: list[dict[str, Any]] = self.store.list_runs()
        self.canvas: dict[str, Any] | None = {
            "title": "Two ferries to Sausalito",
            "subtitle": "Sunny forecast · light breeze (68°F)",
            "cards": [
                {
                    "kind": "ChoicePairCard",
                    "id": "ferry",
                    "prompt": "Which boat feels better for Saturday?",
                    "left": {
                        "title": "10:30 AM",
                        "detail": "Quiet morning crossing · coffee on deck",
                        "speakablePhrase": "The 10:30",
                    },
                    "right": {
                        "title": "1:45 PM",
                        "detail": "Unhurried morning · golden light back",
                        "speakablePhrase": "The 1:45",
                    },
                },
                {
                    "kind": "AudioSketchCard",
                    "id": "sketch",
                    "title": "Late Afternoon on the Bay",
                    "mood": "Warm piano · 76 bpm",
                    "duration": "0:48",
                    "actions": [
                        {"label": "Play it", "speakablePhrase": "Play it", "tone": "primary"},
                        {"label": "Softer", "speakablePhrase": "A little softer"},
                    ],
                },
            ],
        }
        self.pending_actions: dict[str, PendingAction] = {}
        self.action_waiters: dict[str, asyncio.Future[str]] = {}
        # One-time server-verified approval tokens minted ONLY when a human approves a PendingAction.
        self.approved_tokens: dict[str, dict[str, Any]] = {}
        self.remembered_shimmer: dict[str, Any] | None = None
        self.next_greeting_queue: list[dict[str, Any]] = []
        self.recent_actions: list[str] = []

        # Cua Driver outbound tunnel state (user's Mac)
        self.cua_ws: WebSocket | None = None
        self.cua_status: str = "disconnected"
        self.cua_manifest: dict[str, Any] = dict(BOUNDED_CUA_MANIFEST)
        self.cua_pending_calls: dict[str, asyncio.Future[dict[str, Any]]] = {}

    def current_pending_action(self) -> PendingAction | None:
        if not self.pending_actions:
            return None
        # Highest stakes first, else oldest pending.
        rank = {"forget": 0, "money": 1, "computer": 2, "shared": 3, "low": 4}
        return min(self.pending_actions.values(), key=lambda p: (rank.get(p.stakes, 5), p.createdAt))

    def visible_pills(self) -> list[dict[str, Any]]:
        pills: list[dict[str, Any]] = []
        pending = self.current_pending_action()
        if pending:
            for opt in pending.options:
                pills.append(
                    {
                        "phrase": opt["phrase"],
                        "target": "approval",
                        "action": opt["choice"],
                        "payload": {"action_id": pending.id, "choice": opt["choice"]},
                    }
                )
        if self.active_surface == "made_just_now" and self.canvas:
            pills.extend(extract_card_phrases(self.canvas.get("cards", [])))
        if self.active_surface == "your_computer":
            pills.append({"phrase": "Let me drive", "target": "cua", "action": "revoke"})
        if self.active_surface == "her_computer":
            pills.extend(
                [
                    {"phrase": "Take control", "target": "her_computer", "action": "interactive"},
                    {"phrase": "Watch only", "target": "her_computer", "action": "readonly"},
                    {"phrase": "Back to talking", "target": "surface", "action": "conversation"},
                ]
            )
        if self.active_surface == "inbox_cascade":
            pills.extend(
                [
                    {"phrase": "Trash the newsletters", "target": "inbox", "action": "trash_newsletters"},
                    {"phrase": "Keep the VIPs", "target": "inbox", "action": "keep_vips"},
                    {"phrase": "Back to talking", "target": "surface", "action": "conversation"},
                ]
            )
        if self.active_surface == "swarm":
            for r in self.runs:
                lbl = r.get("label", "")
                rid = r.get("id", "")
                if r.get("status") in ("running", "waiting"):
                    pills.append({
                        "phrase": f"Stop {lbl}",
                        "target": "swarm",
                        "action": "stop",
                        "payload": {"run_id": rid, "label": lbl},
                    })
                pills.append({
                    "phrase": f"How is {lbl} going?",
                    "target": "swarm",
                    "action": "status",
                    "payload": {"run_id": rid, "label": lbl},
                })
            pills.extend(
                [
                    {"phrase": "How's it going?", "target": "swarm", "action": "status_active"},
                    {"phrase": "Stop it", "target": "swarm", "action": "stop_latest"},
                    {"phrase": "Clear finished tasks", "target": "swarm", "action": "clear_done"},
                    {"phrase": "Back to talking", "target": "surface", "action": "conversation"},
                ]
            )
        undo = self.store.latest_undo()
        if undo:
            pills.append({"phrase": "Undo that", "target": "undo", "action": undo["id"]})
        return pills

    def snapshot(self) -> dict[str, Any]:
        pending = self.current_pending_action()
        undo = self.store.latest_undo()
        profile = self.store.read_profile()
        shimmer = self.remembered_shimmer
        if shimmer and time.time() - shimmer.get("at", 0) > 6.0:
            self.remembered_shimmer = None
            shimmer = None
        return {
            "type": "snapshot",
            "activeSurface": self.active_surface,
            "mood": self.mood,
            "runs": self.runs,
            "canvas": self.canvas,
            "pendingAction": pending.to_dict() if pending else None,
            "undoToast": (
                {"id": undo["id"], "label": undo["label"], "expiresAt": undo["expires_at"]} if undo else None
            ),
            "rememberedShimmer": shimmer,
            "memories": self.store.list_memories(limit=60),
            "connectors": self.store.list_connectors(),
            "inbox": self.store.list_inbox(),
            "voice": {
                "voiceKey": profile.get("voice_key", "voice_1_warm"),
                "speed": profile.get("voice_speed", 0.96),
                "temperature": profile.get("voice_temperature", 0.72),
                "styleNote": profile.get("voice_style_note", ""),
            },
            "cua": {
                "connected": self.cua_ws is not None,
                "status": self.cua_status,
                "manifest": self.cua_manifest,
                "recentActivity": self.store.list_activity(source="your_computer", limit=15),
            },
            "herComputer": {
                "online": True,
                "resolution": "1920x1080",
                "recentActivity": self.store.list_activity(source="her_computer", limit=20),
            },
            "nextGreeting": self.next_greeting_queue[-5:],
            "visiblePhrases": [p["phrase"] for p in self.visible_pills()],
        }

    async def broadcast(self, event: dict[str, Any] | None = None) -> None:
        payload = json.dumps(event or self.snapshot())
        dead: list[WebSocket] = []
        for ws in list(self.clients):
            try:
                await ws.send_text(payload)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def record_action(self, label: str) -> None:
        self.recent_actions.append(label)
        self.recent_actions = self.recent_actions[-12:]

    async def set_surface(self, surface: str) -> None:
        self.active_surface = surface
        self.record_action(f"surface:{surface}")
        await self.broadcast()

    async def set_runs(self, runs: list[dict[str, Any]]) -> None:
        self.runs = runs
        await self.broadcast()

    async def set_canvas(self, title: str, subtitle: str, cards: list[dict[str, Any]], *, show_now: bool = True) -> None:
        self.canvas = {"title": title, "subtitle": subtitle, "cards": cards, "createdAt": time.time()}
        if show_now:
            self.active_surface = "made_just_now"
        self.record_action(f"canvas:{title}")
        await self.broadcast()

    async def create_pending_action(
        self,
        *,
        source: str,
        title: str,
        summary_lines: list[str],
        stakes: str,
        options: list[dict[str, str]],
        run_id: str | None = None,
        request_id: str | None = None,
        execution_generation: Any = None,
        allow_remember_rule: bool = False,
        meta: dict[str, Any] | None = None,
    ) -> PendingAction:
        action = PendingAction(
            id=f"pa_{uuid.uuid4().hex[:10]}",
            source=source,
            title=title,
            summaryLines=summary_lines,
            stakes=stakes,
            options=options,
            runId=run_id,
            requestId=request_id,
            executionGeneration=execution_generation,
            allowRememberRule=allow_remember_rule,
            meta=meta or {},
        )
        self.pending_actions[action.id] = action
        self.record_action(f"pending:{title}")
        await self.broadcast()
        return action

    async def resolve_pending_action(self, action_id: str, choice: str) -> PendingAction | None:
        action = self.pending_actions.pop(action_id, None)
        if action is None:
            return None
        if choice in ("allow", "once", "confirm", "confirm_trash", "forget"):
            self.approved_tokens[action.id] = {
                "source": action.source,
                "stakes": action.stakes,
                "meta": action.meta,
                "expiresAt": time.time() + 120.0,
            }
        waiter = self.action_waiters.pop(action_id, None)
        if waiter and not waiter.done():
            waiter.set_result(choice)
        self.record_action(f"resolved:{action.title}:{choice}")
        await self.broadcast()
        return action

    def consume_approval_token(self, approval_id: str, *, expected_source: str | None = None) -> dict[str, Any] | None:
        """Verify and consume a one-time human-confirmed approval token (prevents model self-approval)."""
        rec = self.approved_tokens.pop(approval_id, None)
        if rec is None or time.time() > float(rec.get("expiresAt", 0)):
            return None
        if expected_source and rec.get("source") != expected_source:
            return None
        return rec

    async def notify_remembered(self, memory: dict[str, Any]) -> None:
        self.remembered_shimmer = {
            "id": memory["id"],
            "category": memory["category"],
            "summary": memory["summary"],
            "at": time.time(),
        }
        await self.broadcast()

    # ------------------------------------------------------ Cua tunnel helpers

    async def call_cua(self, tool: str, arguments: dict[str, Any], *, timeout_s: float = 30.0) -> dict[str, Any]:
        # If external WebSocket Cua tunnel is active, route through it
        if self.cua_ws is not None:
            call_id = f"cua_{uuid.uuid4().hex[:10]}"
            fut: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
            self.cua_pending_calls[call_id] = fut
            try:
                self.cua_status = f"running: {tool}"
                self.store.add_activity(source="your_computer", title=f"{tool}", detail=json.dumps(arguments)[:160], status="running")
                await self.broadcast()
                await self.cua_ws.send_text(json.dumps({"type": "call", "id": call_id, "tool": tool, "arguments": arguments}))
                result = await asyncio.wait_for(fut, timeout=timeout_s)
                self.cua_status = "ready"
                self.store.add_activity(source="your_computer", title=f"{tool}", detail="completed", status="done")
                await self.broadcast()
                return result
            except Exception as exc:  # noqa: BLE001
                self.cua_status = "ready" if self.cua_ws else "disconnected"
                await self.broadcast()
                return {"ok": False, "error": str(exc)}
            finally:
                self.cua_pending_calls.pop(call_id, None)

        # 100% Real Native macOS & Mobile Automation Fallback
        from .mac_automation import mac_automation
        from .mobile_automation import mobile_automation

        self.cua_status = f"running: {tool}"
        self.store.add_activity(source="your_computer", title=f"{tool}", detail=json.dumps(arguments)[:160], status="running")
        await self.broadcast()

        try:
            if tool.startswith(("android_", "ios_")) or tool in ("tap", "swipe", "mobile_action", "devices"):
                res = mobile_automation.execute_mobile_tool(tool, arguments)
            else:
                res = mac_automation.execute_tool(tool, arguments)

            status_str = "done" if res.get("ok", True) else "failed"
            self.store.add_activity(source="your_computer", title=f"{tool}", detail=json.dumps(res)[:160], status=status_str)
            self.cua_status = "ready"
            await self.broadcast()
            return res
        except Exception as exc:
            self.cua_status = "ready"
            self.store.add_activity(source="your_computer", title=f"{tool}", detail=str(exc)[:160], status="error")
            await self.broadcast()
            return {"ok": False, "error": str(exc)}

    async def revoke_cua(self) -> dict[str, Any]:
        """Immediate 'Let me drive' kill switch: cancel pending computer approvals & revoke on client."""
        for pid in [p.id for p in self.pending_actions.values() if p.stakes == "computer" or p.source == "cua"]:
            await self.resolve_pending_action(pid, "deny")
        for fut in list(self.cua_pending_calls.values()):
            if not fut.done():
                fut.set_result({"ok": False, "error": "Revoked by user ('Let me drive')"})
        self.cua_pending_calls.clear()
        self.cua_status = "revoked"
        self.store.add_activity(source="your_computer", title="Let me drive", detail="All computer permissions revoked", status="revoked")
        sent = False
        if self.cua_ws is not None:
            try:
                await self.cua_ws.send_text(json.dumps({"type": "revoke", "reason": "user_kill_switch"}))
                sent = True
            except Exception:  # noqa: BLE001
                self.cua_ws = None
        await self.broadcast()
        return {"ok": True, "revoked": True, "tunnel_notified": sent}
