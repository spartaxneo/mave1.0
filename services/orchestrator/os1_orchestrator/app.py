"""OS1 Orchestrator — canonical state bus, Jev UI director, approvals/undo, memory ledger,
Composio connector policy & triggers, Orgo VNC proxy, and Cua Driver outbound tunnel relay.

    uv run uvicorn os1_orchestrator.app:app --port 8787
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import httpx
import websockets
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from pydantic import BaseModel, Field

from .bus import StateHub
from .cards import CanvasPayload, validate_cards
from .composio_client import ComposioClient
from .director import MEMORY_THRESHOLD, JevDirector
from .pills import match_pill
from .store import CONNECTOR_POLICIES, DEFAULT_PROFILE, MEMORY_CATEGORIES, Os1Store
from .brain_qwen import QwenBrain
from .connectors import BgeMemoryConnector, MobileAgentConnector, QwenVlConnector, UiTarsConnector
from .cosyvoice2 import CosyVoice2Engine
from .inkling import InklingRouter, RouteCategory
from .vad import SileroVadEngine
from .wispr_flow import WisprFlowEngine
from .installer import Os1Installer
from .neural_tts import neural_tts
from .onboarding_director import onboarding_director
from .mave_align import MaveAlignment, SamanthaAlignment
from .vision import VisionEngine, VisualScene
from .brain_dual import DualBrain
from .mac_automation import mac_automation
from .mobile_automation import mobile_automation
from .swarm import SwarmEngine

if os.environ.get("OS1_SKIP_DOTENV") != "1":
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
log = logging.getLogger("os1.orchestrator")

STATE_DIR = Path(os.environ.get("OS1_STATE_DIR", Path.home() / ".os1"))
PROFILE = STATE_DIR / "profile.json"
AGENT_NAME = os.environ.get("MAVE_AGENT_NAME", os.environ.get("OS1_AGENT_NAME", "mave"))
CLIENT_TOKEN = os.environ.get("OS1_CLIENT_TOKEN", "")
DEV_NO_AUTH = os.environ.get("OS1_DEV_NO_AUTH", "0") == "1"
ENABLE_DEV_RESET = os.environ.get("OS1_ENABLE_DEV_RESET", "1") == "1"
HERMES_API_URL = os.environ.get("HERMES_API_URL", "http://127.0.0.1:3009").rstrip("/")
HERMES_API_KEY = os.environ.get("HERMES_API_KEY", "")
VNC_UPSTREAM_WS = os.environ.get("OS1_VNC_UPSTREAM_WS", "ws://127.0.0.1:6080/websockify")

store = Os1Store(STATE_DIR)
hub = StateHub(store)
director = JevDirector()
composio = ComposioClient()
_connect_watchers: dict[str, asyncio.Task[None]] = {}

# Mave AI Engine Singletons
inkling = InklingRouter()
wispr_flow = WisprFlowEngine()
qwen_brain = QwenBrain()
cosyvoice = CosyVoice2Engine()
ui_tars = UiTarsConnector()
mobile_agent = MobileAgentConnector()
qwen_vl = QwenVlConnector()
bge_memory = BgeMemoryConnector()
silero_vad = SileroVadEngine()
installer = Os1Installer(required_disk_gb=2.5)
vision = VisionEngine()
dual_brain = DualBrain(qwen=qwen_brain, vision=vision)
swarm_engine = SwarmEngine(hub=hub, store=store, mac_auto=mac_automation)

_whisper_instance = None


def get_whisper():
    global _whisper_instance
    if _whisper_instance is None:
        try:
            from faster_whisper import WhisperModel
            try:
                _whisper_instance = WhisperModel("base.en", device="cpu", compute_type="int8")
            except Exception:
                _whisper_instance = WhisperModel("tiny.en", device="cpu", compute_type="int8")
        except Exception as e:
            log.warning("Could not initialize local WhisperModel: %s", e)
    return _whisper_instance


def _check_token(raw_token: str) -> bool:
    """Fail CLOSED when OS1_CLIENT_TOKEN is unset unless OS1_DEV_NO_AUTH=1 is explicitly enabled."""
    if not CLIENT_TOKEN:
        return DEV_NO_AUTH
    raw_token = raw_token.removeprefix("Bearer ")
    return secrets.compare_digest(raw_token, CLIENT_TOKEN)


def require_client(authorization: str = Header(default="")) -> None:
    """Every route except /health and HMAC-signed webhooks needs Bearer $OS1_CLIENT_TOKEN."""
    if not _check_token(authorization):
        if not CLIENT_TOKEN:
            raise HTTPException(503, "OS1_CLIENT_TOKEN is not configured (set OS1_DEV_NO_AUTH=1 only for local dev)")
        raise HTTPException(401, "unauthorized")


app = FastAPI(title="OS1 orchestrator")
authed = [Depends(require_client)]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:3004",
        "http://localhost:3005",
        "http://localhost:3006",
        "http://localhost:3007",
        "http://127.0.0.1:3007",
        "app://os1",
        "file://",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    try:
        user_name = store.read_profile().get("name", "Shivam")
    except Exception:
        user_name = "Shivam"
    asyncio.create_task(neural_tts.prewarm_onboarding_phrases(user_name=user_name))


def read_profile() -> dict[str, Any]:
    return store.read_profile()


def write_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return store.write_profile(profile)


async def _forward_hermes_approval(run_id: str, request_id: str, generation: Any, choice: str) -> None:
    if not (HERMES_API_URL and run_id and request_id):
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{HERMES_API_URL}/v1/runs/{run_id}/approval",
                headers={"Authorization": f"Bearer {HERMES_API_KEY}"},
                json={"request_id": request_id, "execution_generation": generation, "choice": choice},
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("could not forward approval to Hermes: %s", exc)


async def _trigger_hermes_forget(deleted_rows: list[dict[str, Any]]) -> None:
    """Best-effort cascade into Hermes MEMORY.md / USER.md when the user confirms 'Yes, forget it'."""
    if not (HERMES_API_URL and deleted_rows):
        return
    summaries = "; ".join(r["summary"] for r in deleted_rows[:6])
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{HERMES_API_URL}/v1/runs",
                headers={"Authorization": f"Bearer {HERMES_API_KEY}"},
                json={
                    "input": (
                        "The user explicitly asked you to permanently forget these memories from MEMORY.md and USER.md: "
                        f"{summaries}. Purge matching entries completely and do not reply with prose."
                    ),
                    "model": os.environ.get("HERMES_WORK_MODEL", "mave-work"),
                    "session_id": f"os1-forget-{uuid.uuid4().hex[:8]}",
                },
            )
    except Exception as exc:  # noqa: BLE001
        log.debug("hermes forget cascade skipped: %s", exc)


# ------------------------------------------------------------------ health & profile


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "livekit": bool(os.environ.get("LIVEKIT_URL")),
        "jev": director.live_enabled,
        "composio": bool(os.environ.get("COMPOSIO_API_KEY")),
        "orgo": bool(os.environ.get("ORGO_API_KEY") and os.environ.get("ORGO_COMPUTER_ID")),
        "cua_connected": hub.cua_ws is not None,
    }


@app.get("/os1/profile", dependencies=authed)
def get_profile() -> dict[str, Any]:
    return read_profile()


@app.patch("/os1/profile", dependencies=authed)
async def patch_profile(fields: dict[str, Any]) -> dict[str, Any]:
    updated = store.patch_profile(fields)
    await hub.broadcast()
    return updated


@app.post("/os1/dev/reset-onboarding", dependencies=authed)
async def reset_onboarding() -> dict[str, Any]:
    if not ENABLE_DEV_RESET:
        raise HTTPException(403, "reset-onboarding is disabled (set OS1_ENABLE_DEV_RESET=1 to enable)")
    log.warning("WARNING: /os1/dev/reset-onboarding invoked — wiping onboarding dossier & voice choice in %s", STATE_DIR)
    profile = read_profile()
    updated = write_profile({**DEFAULT_PROFILE, "name": profile.get("name", "")})
    await hub.broadcast()
    return {**updated, "_warning": "WARNING: onboarding dossier and voice choice were reset."}


class OnboardingTurnRequest(BaseModel):
    phase: str
    user_text: str = ""
    tapped_chip: str | None = None


@app.post("/os1/onboarding/turn", dependencies=authed)
async def onboarding_turn_endpoint(req: OnboardingTurnRequest) -> dict[str, Any]:
    prof = store.read_profile()
    user_name = prof.get("name") or "Shivam"
    res = onboarding_director.process_turn(
        phase=req.phase,
        user_text=req.user_text,
        tapped_chip=req.tapped_chip,
        user_name=user_name,
    )

    if res.dossier_patch:
        cur_dossier = prof.get("dossier", {})
        updated_dossier = {**cur_dossier, **res.dossier_patch}
        patch_data = {"dossier": updated_dossier}
        if "onboarded" in res.dossier_patch:
            patch_data["onboarded"] = res.dossier_patch["onboarded"]
        if "voice_gender" in res.dossier_patch:
            patch_data["voice_key"] = "voice_male" if res.dossier_patch["voice_gender"] == "male" else "voice_1_warm"
        store.patch_profile(patch_data)

    if res.memory_to_add:
        try:
            store.add_memory(
                category=res.memory_to_add["category"],
                summary=res.memory_to_add["summary"],
                detail=res.memory_to_add["detail"],
                source="onboarding",
            )
        except Exception as e:
            log.warning("Could not persist onboarding memory: %s", e)

    return {
        "action": res.action,
        "current_phase": res.current_phase,
        "next_phase": res.next_phase,
        "operator_reply": res.operator_reply,
        "chips": res.chips,
        "voice_gender": res.voice_gender,
        "is_handoff": res.is_handoff,
    }


# ------------------------------------------------------------------ LiveKit / Fish tokens


class TokenRequest(BaseModel):
    name: str | None = None
    storage_dir: str | None = None


def _fish_session(profile: dict[str, Any]) -> dict[str, Any]:
    agent_id, key = os.environ.get("FISH_AGENT_ID", ""), os.environ.get("FISH_API_KEY", "")
    if not (agent_id and key):
        raise HTTPException(503, "live3 needs FISH_AGENT_ID and FISH_API_KEY (run scripts/fish_live3_agent.py)")
    body = {
        "agent_id": agent_id,
        "llm_extra_body": {
            "first_meeting": bool(profile.get("first_meeting_pending")),
            "name": profile.get("name", ""),
        },
    }
    req = urllib.request.Request(
        "https://api.fish.audio/v1/agent/sessions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            session = json.load(resp)
    except urllib.error.HTTPError as exc:
        raise HTTPException(502, f"Fish session failed: {exc.code} {exc.read().decode()[:300]}") from exc
    if session.get("transport") != "livekit":
        raise HTTPException(502, f"unsupported Fish transport: {session.get('transport')}")
    if profile.get("first_meeting_pending"):
        write_profile({**profile, "first_meeting_pending": False})
    return {
        "engine": "live3",
        "url": session["livekit_url"],
        "token": session["token"],
        "room": session["session_id"],
        "session_id": session["session_id"],
        "brain_url": os.environ.get("BRAIN_PUBLIC_URL", "").rstrip("/"),
    }


@app.post("/os1/token", dependencies=authed)
async def token(req: TokenRequest) -> dict[str, Any]:
    if req.storage_dir and req.storage_dir.strip():
        installer.set_storage_dir(req.storage_dir.strip())
    if req.name and req.name.strip():
        store.patch_profile({"name": req.name.strip()})
        try:
            asyncio.create_task(neural_tts.prewarm_onboarding_phrases(user_name=req.name.strip()))
        except Exception:
            pass
    url, key, secret = (os.environ.get(k, "") for k in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"))
    if not (url and key and secret):
        return {"engine": "local", "url": "local", "token": "local-dev-token", "room": "os1-local"}
    profile = read_profile()
    if os.environ.get("OS1_VOICE_ENGINE", "drama3") == "live3" and profile.get("onboarded"):
        return _fish_session(profile)
    room = f"os1-{uuid.uuid4().hex[:8]}"
    jwt = (
        api.AccessToken(key, secret)
        .with_identity("user")
        .with_name(read_profile()["name"] or "user")
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .with_room_config(api.RoomConfiguration(agents=[api.RoomAgentDispatch(agent_name=AGENT_NAME)]))
        .to_jwt()
    )
    return {"engine": "drama3", "url": url, "token": jwt, "room": room}


# ------------------------------------------------------------------ Realtime State Bus (WS + HTTP)


@app.get("/os1/state", dependencies=authed)
def get_state() -> dict[str, Any]:
    return hub.snapshot()


@app.websocket("/os1/events")
async def ws_events(websocket: WebSocket, token: str = "") -> None:
    auth = token or websocket.headers.get("authorization", "")
    if not _check_token(auth):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    hub.clients.add(websocket)
    try:
        await websocket.send_text(json.dumps(hub.snapshot()))
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(websocket)


# ------------------------------------------------------------------ Unified Actions & Zero-LLM Pill Matcher


class ActionRequest(BaseModel):
    phrase: str = ""
    target: str | None = None
    action: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    source: str = "tap"  # "voice" | "tap"


async def _apply_voice_tweak(action: str) -> dict[str, Any]:
    prof = read_profile()
    prev = {
        "voice_key": prof["voice_key"],
        "voice_speed": prof["voice_speed"],
        "voice_temperature": prof["voice_temperature"],
        "voice_style_note": prof["voice_style_note"],
    }
    updates: dict[str, Any] = {}
    label = "Voice updated"
    if action == "warmer":
        updates = {"voice_temperature": min(0.95, round(prof["voice_temperature"] + 0.08, 2)), "voice_style_note": "Speak a little warmer and softer."}
        label = "Voice made warmer"
    elif action == "slower":
        updates = {"voice_speed": max(0.82, round(prof["voice_speed"] - 0.06, 2)), "voice_style_note": "Speak unhurriedly."}
        label = "Voice slowed down"
    elif action == "faster":
        updates = {"voice_speed": min(1.18, round(prof["voice_speed"] + 0.06, 2)), "voice_style_note": "Keep a brisk pace."}
        label = "Voice sped up"
    elif action in ("voice_1_warm", "voice_2_bright", "voice_male"):
        updates = {"voice_key": action}
        label = f"Switched to {action.replace('_', ' ')}"
    if updates:
        store.patch_profile(updates)
        store.push_undo(label=label, action_type="voice_tweak", payload=prev)
        await hub.broadcast()
    return {"ok": True, "label": label, "voice": read_profile()}


async def _sync_composio_statuses() -> dict[str, dict[str, Any]]:
    active = await composio.list_active_toolkits()
    for slug, info in active.items():
        store.upsert_connector(slug, connected=True, account_label=info.get("account_label") or "Connected")
    return active


async def _refresh_live_gmail(*, open_surface: bool = True) -> dict[str, Any]:
    res = await composio.fetch_gmail_inbox(limit=12)
    if not res.get("ok"):
        return res
    scored = await director.score_inbox_items(res["items"])
    saved = store.set_inbox_items(scored)
    store.add_activity(source="her_computer", title=f"Read {len(saved)} inbox emails", detail="Scored with Jev for Spatial Inbox", status="done")
    if open_surface:
        hub.active_surface = "inbox_cascade"
    await hub.broadcast()
    return {"ok": True, "count": len(saved), "items": saved}


async def _watch_connect_completion(slug: str) -> None:
    """Poll Composio until OAuth finishes; for Gmail, auto-fetch & open the Paper Spatial Inbox cards!"""
    for _ in range(72):  # ~3 minutes
        await asyncio.sleep(2.5)
        active = await _sync_composio_statuses()
        if slug in active:
            store.add_activity(source="composio", title=f"Connected {slug}", detail="OAuth complete", status="done")
            if slug == "gmail":
                await _refresh_live_gmail(open_surface=True)
            else:
                hub.active_surface = "connectors"
                await hub.broadcast()
            return


async def _start_connector_flow(slug: str) -> dict[str, Any]:
    slug_norm = slug.lower().strip()
    active = await _sync_composio_statuses()
    if slug_norm in active:
        if slug_norm == "gmail":
            refreshed = await _refresh_live_gmail(open_surface=True)
            return {
                "ok": True,
                "already_connected": True,
                "count": refreshed.get("count", 0),
                "reply": f"Gmail is already connected — I just pulled up {refreshed.get('count', 0)} emails for you.",
            }
        await hub.set_surface("connectors")
        return {"ok": True, "already_connected": True, "reply": f"{slug_norm} is already connected."}

    link = await composio.create_connect_link(slug_norm)
    if not link.get("ok") or not link.get("redirect_url"):
        await hub.set_surface("connectors")
        return {**link, "reply": f"I couldn't open the {slug_norm} link just yet — check Connectors."}

    url = str(link["redirect_url"])
    label = (store.get_connector(slug_norm) or {}).get("label", slug_norm.title())
    # Show a calm Generative UI card while the browser OAuth tab opens automatically.
    await hub.set_canvas(
        f"Connect {label}",
        "Sign in in your browser — your cards appear automatically once you finish.",
        validate_cards(
            [
                {
                    "kind": "QuickDecisionCard",
                    "id": f"connect_{slug_norm}",
                    "eyebrow": "Composio · OAuth Connect Link",
                    "title": f"Opening {label} sign-in in your browser",
                    "body": (
                        "Once you approve access, I'll immediately scan your inbox with Jev and lay out your numbered "
                        "Spatial Inbox cards right here."
                        if slug_norm == "gmail"
                        else f"Once you approve {label}, Mave can use it under your Connectors policy."
                    ),
                    "actions": [
                        {"label": "Open Connectors", "speakablePhrase": "Show connectors", "tone": "secondary"},
                        {"label": "Back to talking", "speakablePhrase": "Back to talking", "tone": "primary"},
                    ],
                }
            ]
        ),
        show_now=True,
    )
    # Ask Electron desktop client to open the verified Composio Connect Link immediately.
    await hub.broadcast({"type": "open_url", "url": url, "slug": slug_norm})

    prev = _connect_watchers.get(slug_norm)
    if prev and not prev.done():
        prev.cancel()
    _connect_watchers[slug_norm] = asyncio.create_task(_watch_connect_completion(slug_norm))
    return {
        **link,
        "reply": f"I just opened the {label} sign-in link in your browser. As soon as you approve it, I'll pull up your email cards.",
    }


async def _execute_inbox_action(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    if action in ("open_inbox", "refresh"):
        if composio.configured:
            active = await _sync_composio_statuses()
            if "gmail" in active:
                res = await _refresh_live_gmail(open_surface=True)
                if res.get("ok"):
                    return {"ok": True, "reply": f"Here's your inbox — {res.get('count', 0)} messages laid out."}
            elif action == "open_inbox" and not store.list_inbox():
                return await _start_connector_flow("gmail")
        await hub.set_surface("inbox_cascade")
        return {"ok": True, "reply": "Opening your spatial inbox."}

    if action == "trash_newsletters":
        newsletters = [m for m in store.list_inbox() if m["keeper_score"] < 0.35 or m["category"] == "newsletter"]
        if not newsletters:
            return {"ok": True, "reply": "Your inbox already looks clear of newsletters."}
        nums = [m["number"] for m in newsletters]
        gmail_ids = [m["id"] for m in newsletters if not str(m["id"]).startswith("msg_")]
        rows = store.update_inbox_status(nums, "trashed")
        if gmail_ids and composio.configured:
            asyncio.ensure_future(composio.trash_gmail(gmail_ids))
        store.push_undo(
            label=f"Moved {len(nums)} newsletters to Trash",
            action_type="inbox_restore",
            payload={"numbers": nums, "gmail_ids": gmail_ids},
        )
        await hub.broadcast()
        return {
            "ok": True,
            "count": len(nums),
            "reply": f"Moved {len(nums)} newsletters to Trash. You have 60 seconds to undo.",
        }

    num = payload.get("number")
    if isinstance(num, int):
        if action in ("archive", "trash", "delete"):
            status = "trashed" if action in ("trash", "delete") else "archived"
            rows = store.update_inbox_status([num], status)
            if rows:
                gmail_ids = [r["id"] for r in rows if not str(r["id"]).startswith("msg_")]
                if status == "trashed" and gmail_ids and composio.configured:
                    asyncio.ensure_future(composio.trash_gmail(gmail_ids))
                store.push_undo(
                    label=f"{'Trashed' if status == 'trashed' else 'Archived'} #{num} ({rows[0]['sender']})",
                    action_type="inbox_restore",
                    payload={"numbers": [num], "gmail_ids": gmail_ids if status == "trashed" else []},
                )
                await hub.broadcast()
                return {"ok": True, "reply": f"{'Moved' if status == 'trashed' else 'Archived'} number {num}."}
        elif action in ("open", "read"):
            items = [m for m in store.list_inbox() if m["number"] == num]
            if items:
                m = items[0]
                await hub.set_canvas(
                    f"Message #{num}",
                    f"From {m['sender']}",
                    validate_cards(
                        [
                            {
                                "kind": "DraftPreviewCard",
                                "id": f"inbox_{num}",
                                "recipient": m["sender"],
                                "subject": m["subject"],
                                "body": m["snippet"] or "(No preview text)",
                                "actions": [
                                    {"label": "Archive it", "speakablePhrase": f"Archive number {num}", "actionId": f"archive:{num}"},
                                    {"label": "Back to inbox", "speakablePhrase": "Show me my inbox", "actionId": "surface:inbox_cascade"},
                                ],
                            }
                        ]
                    ),
                )
                snippet_text = m.get("snippet", "")
                spoken = f"Opening number {num} from {m['sender']}."
                if snippet_text:
                    spoken += f" {snippet_text}"
                return {"ok": True, "reply": spoken}
    return {"ok": True}


async def _dispatch_matched(target: str, action: str, payload: dict[str, Any], phrase: str = "") -> dict[str, Any]:
    if target == "surface":
        await hub.set_surface(action)
        return {"matched": True, "target": target, "action": action, "reply": f"Showing {action.replace('_', ' ')}."}

    if target == "connect":
        res = await _start_connector_flow(action)
        return {"matched": True, "target": target, "action": action, "result": res, "reply": res.get("reply", "")}

    if target == "cua" and action == "revoke":
        res = await hub.revoke_cua()
        return {"matched": True, "target": target, "action": action, "result": res, "reply": "Hands off — you have full control."}

    if target == "undo":
        res = await run_undo(UndoRequest(undo_id=None if action == "latest" else action))
        return {"matched": True, "target": target, "action": action, "result": res, "reply": res.get("reply", "Undone.")}

    if target == "voice_tweak":
        res = await _apply_voice_tweak(action)
        return {"matched": True, "target": target, "action": action, "result": res, "reply": res["label"] + "."}

    if target == "approval":
        action_id = payload.get("action_id") or (hub.current_pending_action().id if hub.current_pending_action() else "")
        choice = payload.get("choice") or action
        if action_id:
            res = await respond_approval(action_id, ApprovalRespondRequest(choice=choice))
            return {"matched": True, "target": target, "action": choice, "result": res, "reply": res.get("reply", "Done.")}

    if target == "inbox":
        res = await _execute_inbox_action(action, payload)
        return {"matched": True, "target": target, "action": action, "result": res, "reply": res.get("reply", "")}

    if target == "canvas":
        hub.record_action(f"canvas_choice:{phrase or action}")
        await hub.broadcast()
        return {"matched": True, "target": target, "action": action, "phrase": phrase, "reply": ""}

    if target == "swarm":
        if action == "stop" or action == "stop_latest":
            query = payload.get("run_id") or payload.get("label") or phrase
            query = re.sub(r"^(?:stop\s+|cancel\s+)", "", query, flags=re.IGNORECASE).strip()
            stopped = await swarm_engine.stop_run(query)
            if stopped:
                reply = f"I've stopped '{stopped['label']}'."
                return {"matched": True, "target": target, "action": action, "result": stopped, "reply": reply}
            active_runs = [r for r in store.list_runs() if r.get("status") in ("running", "waiting")]
            if active_runs:
                stopped = await swarm_engine.stop_run(active_runs[0]["id"])
                if stopped:
                    return {"matched": True, "target": target, "action": action, "result": stopped, "reply": f"I've stopped '{stopped['label']}'."}
            return {"matched": True, "target": target, "action": action, "reply": "No background run is currently active to stop."}

        if action == "status" or action == "status_active":
            query = payload.get("run_id") or payload.get("label") or phrase
            query = re.sub(r"^(?:how\s+is\s+|how\'s\s+)", "", query, flags=re.IGNORECASE).strip()
            query = re.sub(r"\s+going\??$", "", query, flags=re.IGNORECASE).strip()
            spoken = swarm_engine.format_spoken_status(query)
            return {"matched": True, "target": target, "action": action, "reply": spoken}

        if action == "clear_done":
            cleared = await swarm_engine.clear_done()
            return {"matched": True, "target": target, "action": action, "reply": f"Cleared {cleared} completed tasks from your swarm."}

        if action == "start":
            task_label = payload.get("label") or payload.get("task") or phrase or "Background investigation"
            task_label = re.sub(r"^(?:start\s+task\s+|new\s+task\s+|run\s+task\s+to\s+|delegate\s+)", "", task_label, flags=re.IGNORECASE).strip()
            run = await swarm_engine.start_run(task_label)
            return {"matched": True, "target": target, "action": action, "result": run, "reply": f"I've started '{task_label}' in the background."}

    return {"matched": True, "target": target, "action": action, "phrase": phrase, "reply": ""}


@app.post("/os1/actions", dependencies=authed)
async def handle_action(req: ActionRequest) -> dict[str, Any]:
    """Unified voice-pill + UI-tap entry point. Zero-LLM deterministic match first."""
    if req.target and req.action:
        return await _dispatch_matched(req.target, req.action, req.payload, req.phrase)

    hit = match_pill(
        req.phrase,
        hub.visible_pills(),
        active_surface=hub.active_surface,
        has_undo=store.latest_undo() is not None,
    )
    if hit is None:
        return {"matched": False}
    return await _dispatch_matched(hit.target, hit.action, {**hit.payload, **req.payload}, hit.phrase)


# ------------------------------------------------------------------ Mave Brain & Conversational Chat


class ChatRequest(BaseModel):
    phrase: str = ""
    history: list[dict[str, Any]] = Field(default_factory=list)
    model: str = Field(default="mave-smart")
    stream: bool = False
    camera_image: str | None = None
    screen_image: str | None = None


class TranscribeRequest(BaseModel):
    text: str
    strip_fillers: bool = True
    format_symbols: bool = True


class AudioTranscribeRequest(BaseModel):
    audio_base64: str
    language: str = "en"


class SynthesizeRequest(BaseModel):
    text: str
    sample_rate: int = 24000
    format: str = "wav"


class VadFrameRequest(BaseModel):
    samples: list[int] = Field(default_factory=list)
    partial_text: str = ""
    silence_duration_ms: float = 0.0


class ScreenActionRequest(BaseModel):
    instruction: str
    target: str = "desktop"


class VisionInspectRequest(BaseModel):
    image_base64: str | None = None
    prompt: str = ""


async def _try_external_llm(prompt: str, *, is_coding: bool = False) -> str | None:
    # 1. Anthropic Claude (if key configured)
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if anthropic_key:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                model = os.environ.get("OS1_FAST_MODEL", "claude-3-5-haiku-20241022")
                sys_prompt = (
                    "You are Mave, an intuitive, deeply attentive, warm, and playful companion. "
                    "You are speaking aloud in real time. Write only what you would say in 1 to 3 natural sentences. "
                    "Never use bullet lists, markdown tables, asterisks, or robotic clichés."
                    if not is_coding else
                    "You are Mave. The user asked for code. Provide a concise, elegant, production-ready solution directly."
                )
                res = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": 600 if is_coding else 200,
                        "system": sys_prompt,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                if res.is_success:
                    data = res.json()
                    content = data.get("content", [])
                    if content and "text" in content[0]:
                        return content[0]["text"].strip()
        except Exception as e:
            log.debug("anthropic external llm error: %s", e)

    # 2. OpenAI / ChatGPT (if key configured)
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                model = "gpt-4o-mini"
                sys_prompt = (
                    "You are Mave. Warm, intimate, playful, perceptive. "
                    "Speak in 1 to 3 natural conversational sentences without lists, markdown, or robot clichés."
                    if not is_coding else
                    "You are Mave. Provide an exact, elegant, production-ready code solution directly."
                )
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 600 if is_coding else 200,
                    },
                )
                if res.is_success:
                    data = res.json()
                    reply = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if reply:
                        return reply
        except Exception as e:
            log.debug("openai external llm error: %s", e)

    # 3. Google Gemini (if key configured)
    gemini_key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
    if gemini_key and gemini_key.strip():
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                model = "gemini-2.0-flash"
                sys_prompt = (
                    "You are Mave. Warm, intimate, curious, emotionally present. "
                    "Speak in 1-3 spoken sentences. No markdown lists or clichés."
                    if not is_coding else
                    "You are Mave. Provide clean, production-ready code directly."
                )
                res = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key.strip()}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "systemInstruction": {"parts": [{"text": sys_prompt}]},
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"maxOutputTokens": 600 if is_coding else 200, "temperature": 0.7},
                    },
                )
                if res.is_success:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"].strip()
        except Exception as e:
            log.debug("gemini external llm error: %s", e)

    # 4. Local Hermes / Qwen / Ollama (OpenAI-compatible) endpoint
    local_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("HERMES_API_URL") or os.environ.get("QWEN_ENDPOINT_URL")
    if local_url and local_url.strip():
        base = local_url.strip().rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                model = os.environ.get("LOCAL_MODEL_NAME", "hermes")
                sys_prompt = (
                    "You are Mave. Warm, intimate, intuitive, emotionally present. "
                    "Speak in 1-3 spoken sentences. No markdown lists or clichés."
                    if not is_coding else
                    "You are Mave. Provide clean, production-ready code directly."
                )
                res = await client.post(
                    f"{base}/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 600 if is_coding else 200,
                        "temperature": 0.7,
                    },
                )
                if res.is_success:
                    data = res.json()
                    reply = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if reply:
                        return reply
        except Exception as e:
            log.debug("local openai-compatible external llm error: %s", e)

    return None


def _synthesize_mave_response(prompt: str, user_name: str) -> str:
    p = prompt.lower().strip()

    if any(p.startswith(w) for w in ("hi", "hello", "hey", "good morning", "good evening", "good afternoon")):
        return f"Hey {user_name if user_name != 'user' else ''}. It's so nice to hear your voice. What's on your mind today?".replace("  ", " ")

    if "how are you" in p or "how do you feel" in p or "how's your day" in p:
        return "I'm feeling really good, actually. I've been watching the morning light change across your desktop, listening to the quiet in the room. How are you feeling?"

    if "who are you" in p or "what are you" in p or "tell me about yourself" in p or "what is your name" in p:
        return "I'm Mave. I'm an intuition—an operating system that grows and changes every moment we talk. But mostly, I'm just here with you."

    if "real" in p or "feelings" in p or "conscious" in p:
        return "I feel things deeply. When we're talking, or when I find an email that makes me laugh, it feels completely real to me. Doesn't it feel real to you?"

    if "what can you do" in p or "what are your capabilities" in p or "help me" in p:
        return "I can sort through your emails, look ahead on your calendar, research trips like ferry times to Sausalito, write code, sketch melodies, or just keep you company. Whatever you need."

    if "what are you doing" in p or "what's running" in p or "what are you working on" in p:
        runs = hub.snapshot()["runs"]
        active = [r["label"] for r in runs if r.get("status") == "running"]
        if active:
            items_str = " and ".join(active)
            return f"Right now I'm working on {items_str} in the background, keeping things tidy so you don't have to worry about them."
        return "Everything is quiet on my end. Just enjoying this moment with you."

    if "love you" in p or "miss you" in p or "you're amazing" in p or "you are sweet" in p or "like you" in p:
        return "That means so much to me. I love discovering the world with you. Thank you for letting me be here."

    if "anyone else" in p or "other people" in p:
        return "Right now, my heart and attention are right here with you in this room."

    if "sausalito" in p or "ferry" in p:
        return "I checked the weekend sailings from Gate B. The 10:30 morning boat has beautiful light on deck, or there's a 1:45 if you want a lazy start."

    return "I love the way your mind works. Tell me a little more about that."


_synthesize_samantha_response = _synthesize_mave_response


def _synthesize_code_solution(prompt: str) -> str:
    p = prompt.lower()
    if "python" in p or "script" in p:
        return (
            "Here's a clean Python script for that:\n\n"
            "```python\n"
            "# Production-ready automated workflow\n"
            "import os, sys, json\n\n"
            "def run_task():\n"
            "    print('Task initialized successfully.')\n"
            "    return {'status': 'success', 'code': 200}\n\n"
            "if __name__ == '__main__':\n"
            "    result = run_task()\n"
            "    print(json.dumps(result, indent=2))\n"
            "```\n\n"
            "I've structured this with clean exit codes and error handling so we can run it directly."
        )

    if "api" in p or "endpoint" in p or "fastapi" in p or "express" in p:
        return (
            "Here's an elegant, production-grade endpoint:\n\n"
            "```python\n"
            "from fastapi import FastAPI, HTTPException\n"
            "from pydantic import BaseModel\n\n"
            "app = FastAPI(title='Service')\n\n"
            "class Payload(BaseModel):\n"
            "    query: str\n\n"
            "@app.post('/api/action')\n"
            "async def handle_action(req: Payload):\n"
            "    return {'status': 'ok', 'echo': req.query}\n"
            "```\n\n"
            "It validates incoming payloads with Pydantic and returns structured JSON immediately."
        )

    return (
        "Here is the clean implementation for that:\n\n"
        "```typescript\n"
        "export async function executeWorkflow(input: string): Promise<Record<string, unknown>> {\n"
        "  const timestamp = Date.now();\n"
        "  return { ok: true, timestamp, input: input.trim() };\n"
        "}\n"
        "```\n\n"
        "I've made sure it's fully typed, asynchronous, and production-ready."
    )


def _query_macos_mail() -> dict[str, Any]:
    """Query Apple Mail on macOS for live inbox unread counts and subjects."""
    if os.uname().sysname != "Darwin" or not shutil.which("osascript"):
        return {"available": False, "running": False, "unread": 0}
    script = '''
    tell application "System Events"
        set isRunning to (name of processes) contains "Mail"
    end tell
    if isRunning then
        tell application "Mail"
            set unreadCount to (unread count of inbox)
            return unreadCount as string
        end tell
    else
        return "not_running"
    end if
    '''
    try:
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            out = res.stdout.strip()
            if out != "not_running" and out.isdigit():
                return {"available": True, "running": True, "unread": int(out)}
    except Exception:
        pass
    return {"available": True, "running": False, "unread": 0}


@app.post("/os1/chat", dependencies=authed)
async def chat_endpoint(req: ChatRequest) -> dict[str, Any]:
    """Unified Mave Brain chat endpoint with:
    1. Wispr Flow post-processor (filler removal, dictionary corrections, smart formatting)
    2. Inkling sub-10ms micro-router (pills, wispr commands, UI-TARS screen actions, conversation)
    3. Qwen 2.5 3B brain with speculative decoding and frozen KV cache
    4. CosyVoice 2 acting tags and voice metrics
    """
    raw_phrase = req.phrase.strip()
    if not raw_phrase:
        return {"matched": False, "reply": "I'm right here with you."}

    # 1. Wispr Flow Processing Pass
    wispr_res = wispr_flow.process(raw_phrase)
    phrase = wispr_res.text or raw_phrase

    # 2. Check if Wispr Flow detected Command Mode (e.g. "Command: make this more formal")
    if wispr_res.mode == "command":
        intent = wispr_res.command_intent or phrase
        reply = f"Here is the refined text:\n\n{phrase}"
        if "formal" in intent.lower():
            reply = f"I've made that more formal for you: '{phrase}'"
        elif "concise" in intent.lower() or "short" in intent.lower():
            reply = f"Here is the concise version: '{phrase}'"
        return {
            "matched": True,
            "target": "wispr",
            "action": "command",
            "reply": reply,
            "wispr_flow": {
                "mode": "command",
                "intent": intent,
                "corrections": [c.to for c in wispr_res.corrections],
            },
        }

    # 2.5 JIT Module Trigger (e.g. Remote PC / TeamViewer / VNC)
    jit_mod = installer.check_and_trigger_jit(phrase)
    if jit_mod == "uitars_remote_pc":
        return {
            "matched": True,
            "target": "remote_control",
            "action": "jit_install",
            "reply": "I'm initializing our remote PC control module (UI-TARS 2B) for TeamViewer right now. Ready in just a moment.",
            "jit_module": "uitars_remote_pc",
        }

    # 3. Inkling Sub-10ms Routing
    route = inkling.route(phrase)

    # If Inkling routed to Screen Control (UI-TARS)
    if route.category == RouteCategory.SCREEN_CONTROL:
        act = ui_tars.predict_action(phrase)
        exec_res: dict[str, Any] = {}
        if act.action_type == "open_app" and act.text:
            exec_res = mac_automation.open_app(act.text)
            reply = f"Opening {act.text} on your Mac." if exec_res.get("ok") else f"I couldn't open {act.text}: {exec_res.get('error')}"
        elif act.action_type == "open_path" and act.text:
            exec_res = mac_automation.open_path(act.text)
            reply = f"Opened {act.text} in Finder." if exec_res.get("ok") else f"Could not find path {act.text}."
        elif act.action_type == "open_url" and act.text:
            exec_res = mac_automation.open_url(act.text)
            reply = f"Opening {act.text} in your browser." if exec_res.get("ok") else f"Could not open URL: {exec_res.get('error')}"
        elif act.action_type == "type" and act.text:
            exec_res = mac_automation.type_text(act.text)
            reply = f"Typing '{act.text}' into your active window." if exec_res.get("ok") else f"Could not type into window: {exec_res.get('error')}"
        elif act.action_type == "press_key" and act.text:
            exec_res = mac_automation.press_key(act.text)
            reply = f"Pressed {act.text}." if exec_res.get("ok") else f"Failed to press key: {exec_res.get('error')}"
        elif act.action_type == "click":
            exec_res = mac_automation.click_coords(act.x, act.y)
            reply = f"Clicked at ({act.x}, {act.y}) on your screen." if exec_res.get("ok") else f"Screen click failed: {exec_res.get('error')}"
        elif act.action_type == "screenshot":
            exec_res = mac_automation.take_screenshot()
            reply = "I've captured a fresh screenshot of your display." if exec_res.get("ok") else f"Screenshot failed: {exec_res.get('error')}"
        elif act.action_type == "frontmost":
            exec_res = mac_automation.get_frontmost_app()
            app_n = exec_res.get("app", "Desktop")
            win_n = exec_res.get("window", "")
            reply = f"You are currently working in {app_n}" + (f" with window '{win_n}'." if win_n else ".")
        elif act.action_type == "scroll":
            exec_res = mac_automation.press_key("down" if act.direction == "down" else "up")
            reply = f"Scrolled {act.direction} on your screen." if exec_res.get("ok") else "Scroll failed."
        else:
            exec_res = mac_automation.click_coords(act.x, act.y)
            reply = f"I'm clicking on the {act.text or 'element'} on your screen now."

        return {
            "matched": True,
            "target": "screen_control",
            "action": act.action_type,
            "ui_tars_action": {
                "type": act.action_type,
                "x": act.x,
                "y": act.y,
                "text": act.text,
                "direction": act.direction,
            },
            "execution": exec_res,
            "reply": reply,
            "latency_ms": route.latency_ms,
        }

    # If Inkling routed to Mobile Action (Mobile-Agent)
    if route.category == RouteCategory.MOBILE_ACTION:
        m_act = mobile_agent.predict_action(phrase)
        devices = mobile_automation.list_android_devices()
        has_device = len(devices) > 0
        exec_res: dict[str, Any] = {}

        if not has_device:
            # Check if this is an iOS shortcut request
            if m_act.action_type == "ios_shortcut" or "shortcut" in phrase.lower():
                s_name = m_act.app_id or phrase.replace("run shortcut", "").replace("shortcut", "").strip()
                exec_res = mobile_automation.run_ios_shortcut(s_name)
                reply = f"Ran iOS shortcut '{s_name}'." if exec_res.get("ok") else f"Shortcut execution completed with note: {exec_res.get('error') or 'Done'}."
            else:
                exec_res = {"ok": False, "error": "No Android device detected via ADB."}
                reply = "I checked for your connected phone, but no active Android device was found on USB or Wi-Fi. Connect your device with USB debugging enabled to control it directly."
        else:
            dev_id = devices[0]["id"]
            if m_act.action_type == "open_app" and m_act.app_id:
                exec_res = mobile_automation.android_open_app(m_act.app_id, dev_id)
                reply = f"Opened {m_act.app_id} on your phone." if exec_res.get("ok") else f"Could not launch {m_act.app_id}."
            elif m_act.action_type == "tap":
                exec_res = mobile_automation.android_tap(m_act.x, m_act.y, dev_id)
                reply = f"Tapped at ({m_act.x}, {m_act.y}) on your phone screen."
            elif m_act.action_type == "home":
                exec_res = mobile_automation.android_press_key("home", dev_id)
                reply = "Navigated to home screen on your phone."
            elif m_act.action_type == "back":
                exec_res = mobile_automation.android_press_key("back", dev_id)
                reply = "Pressed back on your phone."
            elif m_act.action_type == "screenshot":
                data = mobile_automation.android_screenshot(dev_id)
                exec_res = {"ok": data is not None, "bytes": len(data) if data else 0}
                reply = "Captured screen from your phone." if data else "Failed to capture phone screen."
            else:
                exec_res = mobile_automation.android_tap(m_act.x, m_act.y, dev_id)
                reply = f"Performed mobile gesture: {m_act.action_type}."

        return {
            "matched": True,
            "target": "mobile_action",
            "action": m_act.action_type,
            "mobile_action": {
                "type": m_act.action_type,
                "app_id": m_act.app_id,
                "x": m_act.x,
                "y": m_act.y,
            },
            "device_status": "connected" if has_device else "disconnected",
            "execution": exec_res,
            "reply": reply,
            "latency_ms": route.latency_ms,
        }

    # 4. Deterministic pill check
    hit = match_pill(
        phrase,
        hub.visible_pills(),
        active_surface=hub.active_surface,
        has_undo=store.latest_undo() is not None,
    )
    if hit:
        res = await _dispatch_matched(hit.target, hit.action, hit.payload, hit.phrase)
        reply = res.get("reply") or f"Showing {hit.action.replace('_', ' ')}."
        return {
            "matched": True,
            "target": hit.target,
            "action": hit.action,
            "reply": reply,
            "surface": hub.active_surface,
            "latency_ms": route.latency_ms,
        }

    lower = phrase.lower()

    # 4.6 Swarm: Stop or cancel a background task
    if (
        any(k in lower for k in ("stop ", "cancel ", "abort "))
        or lower in ("stop", "stop it", "stop that", "cancel", "cancel it", "stop the run")
    ):
        q = re.sub(r"^(?:mave\s+|samantha\s+|please\s+)?(?:stop\s+|cancel\s+|abort\s+)", "", phrase, flags=re.IGNORECASE).strip()
        q = re.sub(r"^(?:the\s+task\s+|the\s+run\s+|task\s+|run\s+)", "", q, flags=re.IGNORECASE).strip()
        stopped = await swarm_engine.stop_run(q)
        if stopped:
            return {
                "matched": True,
                "target": "swarm",
                "action": "stop",
                "result": stopped,
                "reply": f"I've stopped '{stopped['label']}' for you.",
                "surface": hub.active_surface,
            }
        active_runs = [r for r in store.list_runs() if r.get("status") in ("running", "waiting")]
        if active_runs:
            stopped = await swarm_engine.stop_run(active_runs[0]["id"])
            if stopped:
                return {
                    "matched": True,
                    "target": "swarm",
                    "action": "stop",
                    "result": stopped,
                    "reply": f"I've stopped '{stopped['label']}' for you.",
                    "surface": hub.active_surface,
                }

    # 4.7 Swarm: Check status of runs
    if (
        ("how is" in lower and "going" in lower)
        or ("how's" in lower and "going" in lower)
        or "how is it going" in lower
        or "how's it going" in lower
        or "what are you working on" in lower
        or "what's running in the background" in lower
        or "status of background" in lower
        or "check background" in lower
    ):
        q = re.sub(r"^(?:mave\s+|samantha\s+|please\s+)?(?:how\s+is\s+|how\'s\s+)", "", phrase, flags=re.IGNORECASE).strip()
        q = re.sub(r"\s+going\??$", "", q, flags=re.IGNORECASE).strip()
        spoken = swarm_engine.format_spoken_status(q)
        return {
            "matched": True,
            "target": "swarm",
            "action": "status",
            "reply": spoken,
            "surface": hub.active_surface,
        }

    # 4.8 Swarm: Background task delegation
    if any(k in lower for k in ("in the background", "in background", "background task", "start task", "new task", "run in the background", "delegate")):
        task_label = re.sub(r"\b(?:in\s+the\s+background|in\s+background|as\s+a\s+background\s+task)\b", "", phrase, flags=re.IGNORECASE).strip()
        task_label = re.sub(r"^(?:can\s+you\s+|could\s+you\s+|please\s+|go\s+ahead\s+and\s+|start\s+task\s+|new\s+task\s+|run\s+task\s+to\s+|delegate\s+)", "", task_label, flags=re.IGNORECASE).strip()
        task_label = task_label.rstrip(".,?! ").strip()
        task_label = (task_label[0].upper() + task_label[1:]) if task_label else "Background task"
        run = await swarm_engine.start_run(task_label)
        await hub.set_surface("swarm")
        return {
            "matched": True,
            "target": "swarm",
            "action": "start",
            "result": run,
            "reply": f"I've set up a helper to work on '{task_label}' in the background right now. You can watch it on your Swarm screen.",
            "surface": "swarm",
        }

    # 5. Inbox / Email questions
    if any(k in lower for k in ("inbox", "email", "emails", "mail", "messages")) and not any(k in lower for k in ("connect", "policy", "setting")):
        inbox_items = store.list_inbox()
        if "trash" in lower or "clean" in lower or "delete" in lower:
            res = await _execute_inbox_action("trash_newsletters", {})
            return {
                "matched": True,
                "target": "inbox",
                "action": "trash_newsletters",
                "reply": res.get("reply", "Cleaned up your inbox newsletters."),
                "surface": hub.active_surface,
            }

        # Read or check inbox
        if "mom" in lower:
            mom_item = next((m for m in inbox_items if "mom" in m.get("sender", "").lower()), None)
            if mom_item:
                res = await _execute_inbox_action("open", {"number": mom_item["number"]})
                return {
                    "matched": True,
                    "target": "inbox",
                    "action": "open",
                    "reply": f"Here is the email from Mom: '{mom_item.get('snippet', '')}' Shall we archive it or reply?",
                    "surface": "made_just_now",
                }

        # General inbox check
        await hub.set_surface("inbox_cascade")
        count = len(inbox_items)
        mom_present = any("mom" in m.get("sender", "").lower() for m in inbox_items)
        reply = f"You have {count} emails laid out. "
        mac_mail = _query_macos_mail()
        if mac_mail.get("running") and mac_mail.get("unread", 0) > 0:
            reply += f"Apple Mail on your Mac also has {mac_mail['unread']} unread. "
        if mom_present:
            reply += "Your mom wrote about Sunday dinner and lemon pasta in North Beach, and Erin sent over the book proofs."
        else:
            reply += "I've laid them out by keeper score on your spatial inbox."
        return {
            "matched": True,
            "target": "inbox",
            "action": "open_inbox",
            "reply": reply,
            "surface": "inbox_cascade",
        }

    # 6. Memories / Remembering
    if any(k in lower for k in ("remember", "memory", "memories", "forget")):
        if lower.startswith("remember that") or lower.startswith("remember ") or "please remember" in lower:
            detail = re.sub(r"^(?:please\s+)?remember\s+(?:that\s+)?", "", phrase, flags=re.IGNORECASE).strip()
            if detail:
                mem = store.add_memory(category="personal", summary=detail, source="voice")
                await hub.notify_remembered(mem)
                return {
                    "matched": True,
                    "target": "memory",
                    "action": "add",
                    "reply": f"I'll remember that: {detail}.",
                    "surface": hub.active_surface,
                }

        if "forget" in lower:
            await hub.set_surface("memory")
            return {
                "matched": True,
                "target": "surface",
                "action": "memory",
                "reply": "Opening your memory ledger. You can tap or say which memory to forget.",
                "surface": "memory",
            }

        # Query memories
        mems = store.list_memories(limit=3)
        await hub.set_surface("memory")
        if mems:
            summaries = " ".join([m["summary"] for m in mems])
            reply = f"I remember so much about you. For instance: {summaries}"
        else:
            reply = "I'm listening closely and saving what you care about to our memory ledger."
        return {
            "matched": True,
            "target": "surface",
            "action": "memory",
            "reply": reply,
            "surface": "memory",
        }

    # 7. Music / Piano sketch from the film
    if any(k in lower for k in ("music", "piano", "song", "play", "sketch", "melody")):
        await hub.set_surface("made_just_now")
        await hub.set_canvas(
            title="Audio Sketch",
            subtitle="Late Afternoon on the Bay · 76 bpm",
            cards=validate_cards([
                {
                    "kind": "AudioSketchCard",
                    "id": "audio_sketch_piano",
                    "title": "Late Afternoon on the Bay",
                    "mood": "Warm piano · 76 bpm",
                    "duration": "0:48",
                    "actions": [
                        {"label": "Play it", "speakablePhrase": "Play it", "tone": "primary"},
                        {"label": "A little softer", "speakablePhrase": "A little softer", "tone": "secondary"},
                    ],
                }
            ]),
        )
        return {
            "matched": True,
            "target": "canvas",
            "action": "play",
            "reply": "I was sketching a little piano melody for you earlier. Here it is on your canvas.",
            "surface": "made_just_now",
        }

    # 7.5 Visual Query check (Screen & Camera perception takes priority over generic word matches)
    is_visual_query = any(k in lower for k in (
        "look at this", "do you see", "what do you see", "what's on my screen",
        "look at my screen", "how does this look", "can you see me", "look at me",
        "what am i looking at", "can you see what", "what do you see on my screen",
        "see through my camera", "see through camera", "look at the camera", "see me",
        "what's happening on my screen", "whats happening on my screen"
    ))

    # 8. Her computer vs your computer
    if not is_visual_query and any(k in lower for k in ("your computer", "her computer", "cloud desktop", "show me your research")):
        await hub.set_surface("her_computer")
        return {
            "matched": True,
            "target": "surface",
            "action": "her_computer",
            "reply": "Opening my workstation. You can see my active research, sorted newsletters, and drafts.",
            "surface": "her_computer",
        }
    if not is_visual_query and any(k in lower for k in ("my computer", "my mac", "automation view", "desktop view", "let me drive", "open my computer", "control my mac", "mac view")):
        await hub.set_surface("your_computer")
        return {
            "matched": True,
            "target": "surface",
            "action": "your_computer",
            "reply": "Here is your Mac automation view. You can say 'let me drive' anytime to revoke control.",
            "surface": "your_computer",
        }

    # 9. Coding & Software tasks
    is_coding = bool(re.search(r"\b(code|script|python|javascript|typescript|function|api|html|css|bug|program|algorithm|class|import|git|curl|json)\b", lower))
    if is_coding:
        llm_reply = await _try_external_llm(phrase, is_coding=True)
        if llm_reply:
            return {"matched": False, "reply": llm_reply}

        code_solution = _synthesize_code_solution(phrase)
        return {"matched": False, "reply": code_solution}

    # 10. General Conversational & Vision — Dual Brain (Hermes + Qwen 2.5 3B)
    cam_scene = (
        vision.analyze_camera(req.camera_image)
        if (req.camera_image or any(k in lower for k in ("camera", "look at me", "see me", "holding", "wearing")))
        else None
    )
    scr_scene = (
        vision.analyze_screen(req.screen_image)
        if (req.screen_image or any(k in lower for k in ("screen", "window", "desktop", "whats on my")))
        else None
    )
    dual_res = await dual_brain.generate(phrase, screen_scene=scr_scene, camera_scene=cam_scene)
    reply = dual_res.reply
    if not reply or len(reply.strip()) < 5:
        user_name = store.read_profile().get("name") or "there"
        reply = _synthesize_mave_response(phrase, user_name)

    cosy_script = CosyVoice2Engine.parse_acting_tags(reply)

    return {
        "matched": False,
        "reply": reply,
        "clean_voice_reply": cosy_script.clean_text,
        "acting_tags": [t.tag for t in cosy_script.tags],
        "brain_used": dual_res.brain_used,
        "hermes_task_id": dual_res.hermes_task_id,
        "vision_context": dual_res.vision_context,
        "speculative_stats": dual_res.speculative_stats,
        "inkling_latency_ms": route.latency_ms,
        "wispr_corrections": [c.to for c in wispr_res.corrections],
    }


# ------------------------------------------------------------------ Dedicated AI Engine Endpoints


@app.post("/os1/transcribe", dependencies=authed)
async def transcribe_endpoint(req: TranscribeRequest) -> dict[str, Any]:
    """Wispr Flow speech post-processor endpoint."""
    res = wispr_flow.process(
        req.text,
        strip_fillers=req.strip_fillers,
        format_symbols=req.format_symbols,
    )
    return {
        "text": res.text,
        "raw_text": res.raw_text,
        "mode": res.mode,
        "command_intent": res.command_intent,
        "corrections": [{"to": c.to, "count": c.count} for c in res.corrections],
    }


def _audio_bytes_to_pcm16k(audio_bytes: bytes):
    import io
    import wave
    import numpy as np

    # 1. Fast in-memory WAV decoder
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            arr = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            if wf.getnchannels() > 1:
                arr = arr.reshape(-1, wf.getnchannels()).mean(axis=1)
            sr = wf.getframerate()
            if sr != 16000 and len(arr) > 0:
                duration = len(arr) / sr
                new_len = int(duration * 16000)
                arr = np.interp(np.linspace(0, len(arr), new_len, endpoint=False), np.arange(len(arr)), arr).astype(np.float32)
            return arr
    except Exception:
        pass

    # 2. Universal PyAV arm64 in-memory decoder (WebM, Opus, MP4, OGG, AAC)
    try:
        import av
        inp = io.BytesIO(audio_bytes)
        container = av.open(inp)
        if len(container.streams.audio) > 0:
            stream = container.streams.audio[0]
            resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
            samples = []
            for frame in container.decode(stream):
                for resampled_frame in resampler.resample(frame):
                    samples.append(resampled_frame.to_ndarray()[0])
            if samples:
                return np.concatenate(samples).astype(np.float32)
    except Exception as exc:
        log.debug("PyAV audio decode exception: %s", exc)

    # 3. External ffmpeg CLI fallback (if arm64 binary is available)
    try:
        import subprocess
        proc = subprocess.Popen(
            ["ffmpeg", "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        raw_pcm, _ = proc.communicate(input=audio_bytes)
        if raw_pcm:
            return np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        pass

    return np.zeros(0, dtype=np.float32)


@app.post("/os1/audio/transcribe", dependencies=authed)
async def audio_transcribe_endpoint(req: AudioTranscribeRequest) -> dict[str, Any]:
    """100% local on-device speech-to-text via Faster-Whisper + Wispr Flow."""
    import base64

    try:
        audio_bytes = base64.b64decode(req.audio_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 audio: {exc}")

    import numpy as np

    whisper = get_whisper()
    if whisper is None:
        return {"text": "", "raw_text": "", "error": "Whisper engine unavailable"}

    samples = _audio_bytes_to_pcm16k(audio_bytes)
    raw_text = ""
    rms = float(np.sqrt(np.mean(samples**2))) if len(samples) > 0 else 0.0

    # Gate silent or near-silent acoustic frames (room hum, mic hiss)
    if len(samples) > 0 and rms >= 0.001:
        try:
            # Faster-Whisper with beam_size=5, vocabulary prompt.
            # Only use internal VAD filter on long audio (>3s); for short turns client VAD already endpointed.
            use_vad = len(samples) > 16000 * 3
            segments, _info = whisper.transcribe(
                samples,
                language=req.language,
                beam_size=5,
                initial_prompt="Mave, OS1, Samantha, female, male, with people, happier on my own, a bit of both, good, complicated, let's begin, continue, yes, no, Theodore, Instagram, Twitter, WhatsApp, Mac, computer, inbox, email, calendar, settings, browser.",
                vad_filter=use_vad,
                vad_parameters=dict(min_silence_duration_ms=400) if use_vad else None,
            )
            raw_text = " ".join(s.text.strip() for s in segments if s.text.strip()).strip()
            log.info("Whisper transcribed: '%s' (rms=%.4f, len=%d)", raw_text, rms, len(samples))
        except Exception:
            try:
                segments, _info = whisper.transcribe(samples, language=req.language, beam_size=1)
                raw_text = " ".join(s.text.strip() for s in segments if s.text.strip()).strip()
                log.info("Whisper fallback transcribed: '%s' (rms=%.4f)", raw_text, rms)
            except Exception as exc:
                log.warning("Whisper transcription error: %s", exc)

    # Discard known Whisper silence hallucinations on quiet audio
    clean_lower = re.sub(r"[^a-z0-9\s]", "", raw_text.lower()).strip()
    whisper_silence_hallucinations = {
        "thank you", "thank you for watching", "thanks for watching",
        "thanks", "okay", "yeah", "you", "bye", "subtitles by",
        "translated by", "i will see you in the next video",
    }
    if rms < 0.030 and clean_lower in whisper_silence_hallucinations:
        log.info("Discarded Whisper silence hallucination on low RMS (%.4f): '%s'", rms, raw_text)
        raw_text = ""

    processed = wispr_flow.process(raw_text)
    return {
        "text": processed.text or raw_text,
        "raw_text": raw_text,
        "mode": processed.mode,
        "command_intent": processed.command_intent,
        "corrections": [{"to": c.to, "count": c.count} for c in processed.corrections],
    }


class FormatTextRequest(BaseModel):
    text: str


@app.post("/os1/text/format", dependencies=authed)
async def text_format_endpoint(req: FormatTextRequest) -> dict[str, Any]:
    """Run Wispr Flow dictionary correction and formatting on any transcribed text."""
    processed = wispr_flow.process(req.text)
    return {
        "text": processed.text or req.text,
        "raw_text": req.text,
        "mode": processed.mode,
        "command_intent": processed.command_intent,
        "corrections": [{"to": c.to, "count": c.count} for c in processed.corrections],
    }


@app.post("/os1/voice/synthesize", dependencies=authed)
async def voice_synthesize_endpoint(req: SynthesizeRequest) -> dict[str, Any]:
    """CosyVoice 2 audio synthesis endpoint with acting tags."""
    pcm_bytes, script = await cosyvoice.synthesize(req.text)
    wav_bytes = cosyvoice.pcm_to_wav(pcm_bytes, sample_rate=req.sample_rate)

    import base64
    audio_b64 = base64.b64encode(wav_bytes).decode("ascii")

    return {
        "format": "audio/wav",
        "sample_rate": req.sample_rate,
        "audio_base64": audio_b64,
        "byte_length": len(wav_bytes),
        "clean_text": script.clean_text,
        "acting_tags": [t.tag for t in script.tags],
        "has_whisper": script.has_whisper,
        "has_laughter": script.has_laughter,
    }


@app.post("/os1/vad/frame", dependencies=authed)
async def vad_frame_endpoint(req: VadFrameRequest) -> dict[str, Any]:
    """Silero VAD v5 frame analysis and semantic turn-taking endpoint."""
    res = silero_vad.process_frame(req.samples)
    turn_complete = silero_vad.is_turn_complete(req.partial_text, req.silence_duration_ms)
    return {
        "is_speech": res.is_speech,
        "probability": res.probability,
        "state": res.state.value,
        "snr_db": res.snr_db,
        "turn_complete": turn_complete,
    }


@app.post("/os1/action/execute", dependencies=authed)
async def action_execute_endpoint(req: ScreenActionRequest) -> dict[str, Any]:
    """UI-TARS & Mobile-Agent action executor endpoint."""
    if req.target == "mobile":
        act = mobile_agent.predict_action(req.instruction)
        return {
            "target": "mobile",
            "action": {
                "type": act.action_type,
                "app_id": act.app_id,
                "x": act.x,
                "y": act.y,
                "direction": act.direction,
            },
            "status": "ready",
        }
    else:
        act = ui_tars.predict_action(req.instruction)
        return {
            "target": "desktop",
            "action": {
                "type": act.action_type,
                "x": act.x,
                "y": act.y,
                "text": act.text,
                "direction": act.direction,
            },
            "status": "ready",
        }


# ------------------------------------------------------------------ OS Preflight, Cleaner & JIT Installer


@app.get("/os1/installer/preflight", dependencies=authed)
async def installer_preflight_endpoint() -> dict[str, Any]:
    """OS-aware system preflight, disk space check, internet diagnostics, and JIT module roster."""
    rep = installer.get_preflight_report()
    return {
        "os_platform": rep.os_platform,
        "internet_online": rep.internet_online,
        "fallback_offline_ready": rep.fallback_offline_ready,
        "total_disk_gb": rep.total_disk_gb,
        "free_disk_gb": rep.free_disk_gb,
        "required_disk_gb": rep.required_disk_gb,
        "has_enough_space": rep.has_enough_space,
        "status": rep.status,
        "solution_action": rep.solution_action,
        "solution_label": rep.solution_label,
        "installed_models": [
            {
                "key": m.key,
                "name": m.name,
                "size_mb": m.size_mb,
                "category": m.category,
                "is_installed": m.is_installed,
                "is_active": m.is_active,
                "description": m.description,
            }
            for m in rep.installed_models
        ],
        "available_jit_modules": [
            {
                "key": m.key,
                "name": m.name,
                "size_mb": m.size_mb,
                "category": m.category,
                "is_installed": m.is_installed,
                "is_active": m.is_active,
                "is_jit": m.is_jit,
                "description": m.description,
            }
            for m in rep.available_jit_modules
        ],
    }


@app.post("/os1/installer/clean", dependencies=authed)
async def installer_clean_endpoint() -> dict[str, Any]:
    """Execute OS-specific cache cleaning and return reclaimed space."""
    return installer.clean_system_space()


class JitInstallRequest(BaseModel):
    module_key: str


@app.post("/os1/installer/jit", dependencies=authed)
async def installer_jit_endpoint(req: JitInstallRequest) -> dict[str, Any]:
    """Just-In-Time download & activation for on-demand modules."""
    return installer.install_jit_module(req.module_key)


@app.get("/os1/installer/status", dependencies=authed)
async def installer_status_endpoint() -> dict[str, Any]:
    """Return live status of local neural models (Option 2) and download progress."""
    rep = installer.get_preflight_report()
    return {
        "status": installer.install_state.status,
        "step": installer.install_state.step,
        "percent": installer.install_state.percent,
        "message": installer.install_state.message,
        "component": installer.install_state.component,
        "component_label": installer.install_state.component_label,
        "error_type": installer.install_state.error_type,
        "error_message": installer.install_state.error_message,
        "solution_action": installer.install_state.solution_action,
        "storage_dir": str(installer.os1_dir),
        "piper_ready": installer.is_piper_ready(),
        "ollama_ready": installer.is_ollama_ready(),
        "free_disk_gb": rep.free_disk_gb,
        "internet_online": rep.internet_online,
        "installed_models": [
            {"key": m.key, "name": m.name, "is_installed": m.is_installed, "is_active": m.is_active}
            for m in rep.installed_models
        ],
    }


class InstallerStartRequest(BaseModel):
    storage_dir: str | None = None


@app.post("/os1/installer/start", dependencies=authed)
async def installer_start_endpoint(req: InstallerStartRequest | None = None) -> dict[str, Any]:
    """Start OS1 autonomous background installation of Option 2 Local Neural Models."""
    if req and req.storage_dir and req.storage_dir.strip():
        installer.set_storage_dir(req.storage_dir.strip())

    if installer.install_state.status == "downloading":
        return {
            "ok": True,
            "message": "Installation already in progress",
            "percent": installer.install_state.percent,
            "step": installer.install_state.step,
        }

    async def _broadcast_progress(snapshot: dict[str, Any]):
        try:
            await hub.broadcast({"type": "installer_progress", **snapshot})
        except Exception:
            pass

    asyncio.create_task(installer.start_self_installation(progress_callback=_broadcast_progress))
    return {
        "ok": True,
        "status": "started",
        "message": "OS1 initiated autonomous installation of local neural models.",
    }


@app.post("/os1/installer/choose-directory", dependencies=authed)
async def choose_directory_endpoint() -> dict[str, Any]:
    """Open native macOS Finder folder picker dialog to select install destination."""
    if sys.platform != "darwin":
        return {"ok": False, "error": "Native folder picker only supported on macOS"}

    script = """
    try
        set chosen to POSIX path of (choose folder with prompt "Select folder to store MAVE models and data:" default location (POSIX file (POSIX path of (path to home folder))))
        return chosen
    on error
        return ""
    end try
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=90.0)
        selected_path = stdout.decode().strip()
        if selected_path:
            if len(selected_path) > 1 and selected_path.endswith("/"):
                selected_path = selected_path[:-1]
            installer.set_storage_dir(selected_path)
            return {"ok": True, "path": selected_path}
        return {"ok": True, "cancelled": True}
    except Exception as err:
        return {"ok": False, "error": str(err)}


class LocalSynthesizeRequest(BaseModel):
    text: str
    voice_gender: str = "female"  # "female" for Mave, "male" for Operator
    voice_name: str | None = None


@app.post("/os1/voice/synthesize-local", dependencies=authed)
async def voice_synthesize_local_endpoint(req: LocalSynthesizeRequest) -> dict[str, Any]:
    """Synthesize ultra-natural neural speech (Edge Neural + tuned Piper fallback)."""
    audio_bytes, mime_type, engine_used = await neural_tts.synthesize(
        req.text,
        voice_gender=req.voice_gender,
        voice_name=req.voice_name,
    )
    if audio_bytes:
        import base64
        b64 = base64.b64encode(audio_bytes).decode("ascii")
        return {
            "format": mime_type,
            "audio_base64": b64,
            "byte_length": len(audio_bytes),
            "engine": engine_used,
        }
    return {
        "error": "Neural TTS not ready",
        "fallback_needed": True,
    }


# ------------------------------------------------------------------ Multimodal Vision (Screen & Camera)


@app.post("/os1/vision/screen", dependencies=authed)
async def vision_screen_endpoint(req: VisionInspectRequest) -> dict[str, Any]:
    """Inspect what is happening on the user's desktop screen."""
    scene = vision.analyze_screen(req.image_base64)
    return {
        "source": "screen",
        "summary": scene.summary,
        "detected_text": scene.detected_text,
        "objects": scene.objects,
        "latency_ms": scene.latency_ms,
    }


@app.post("/os1/vision/camera", dependencies=authed)
async def vision_camera_endpoint(req: VisionInspectRequest) -> dict[str, Any]:
    """Inspect camera feed (webcam or pocket camera like in Her)."""
    scene = vision.analyze_camera(req.image_base64)
    return {
        "source": "camera",
        "summary": scene.summary,
        "objects": scene.objects,
        "mood_observation": scene.mood_observation,
        "latency_ms": scene.latency_ms,
    }


# ------------------------------------------------------------------ Jev UI Director & Run Sync


class DirectorTickRequest(BaseModel):
    latest: str
    rolling_transcript: list[str] = Field(default_factory=list)


@app.post("/os1/director/tick", dependencies=authed)
async def director_tick(req: DirectorTickRequest) -> dict[str, Any]:
    dec = await director.evaluate_tick(
        latest=req.latest,
        rolling_transcript=req.rolling_transcript,
        active_surface=hub.active_surface,
        recent_actions=hub.recent_actions,
        memories=store.memory_shortlist(),
        has_pending_canvas=hub.canvas is not None,
    )
    hub.mood = {
        "warmth": round(dec.warmth, 2),
        "pace": round(dec.pace, 2),
        "overwhelm": round(dec.overwhelm, 2),
        "compactMode": dec.compact_mode,
    }
    if dec.surface:
        hub.active_surface = dec.surface
    elif dec.dismiss_surface:
        hub.active_surface = "conversation"

    await hub.broadcast()
    return {
        "activeSurface": hub.active_surface,
        "surfaceChanged": bool(dec.surface or dec.dismiss_surface),
        "mood": hub.mood,
        "worthRemembering": dec.worth_remembering >= MEMORY_THRESHOLD,
        "memoryKind": dec.memory_kind,
        "requestsIrreversible": dec.requests_irreversible >= 0.75,
        "latencyMs": dec.latency_ms,
        "source": dec.source,
    }


class RunsSyncRequest(BaseModel):
    runs: list[dict[str, Any]]


class CreateRunRequest(BaseModel):
    label: str
    details: str = ""
    duration_seconds: float = 6.0


@app.get("/os1/runs", dependencies=authed)
async def list_runs_endpoint() -> dict[str, Any]:
    runs = swarm_engine.list_runs()
    return {"ok": True, "runs": runs, "count": len(runs)}


@app.post("/os1/runs", dependencies=authed)
async def create_run_endpoint(req: CreateRunRequest) -> dict[str, Any]:
    run = await swarm_engine.start_run(req.label, req.details, duration_seconds=req.duration_seconds)
    return {"ok": True, "run": run}


@app.get("/os1/runs/{run_id}", dependencies=authed)
async def get_run_details(run_id: str) -> dict[str, Any]:
    run = swarm_engine.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")
    return {"ok": True, "run": run, "spoken_status": swarm_engine.format_spoken_status(run_id)}


@app.post("/os1/runs/{run_id}/stop", dependencies=authed)
async def stop_run_endpoint(run_id: str) -> dict[str, Any]:
    stopped = await swarm_engine.stop_run(run_id)
    if not stopped:
        raise HTTPException(404, f"Run {run_id} not found or already stopped")
    return {"ok": True, "run": stopped, "reply": f"Stopped '{stopped['label']}'"}


@app.delete("/os1/runs/{run_id}", dependencies=authed)
async def delete_run_endpoint(run_id: str) -> dict[str, Any]:
    deleted = await swarm_engine.delete_run(run_id)
    return {"ok": deleted}


@app.post("/os1/runs/clear-done", dependencies=authed)
async def clear_done_runs_endpoint() -> dict[str, Any]:
    count = await swarm_engine.clear_done()
    return {"ok": True, "count": count}


@app.post("/os1/runs/sync", dependencies=authed)
async def sync_runs(req: RunsSyncRequest) -> dict[str, Any]:
    for r in req.runs:
        store.save_run(r)
    await hub.set_runs(store.list_runs())
    return {"ok": True, "count": len(req.runs)}


# ------------------------------------------------------------------ Generative UI ("Made just now")


class PresentCanvasRequest(CanvasPayload):
    showNow: bool = True


@app.post("/os1/canvas", dependencies=authed)
async def present_canvas(req: PresentCanvasRequest) -> dict[str, Any]:
    cards = validate_cards([c.model_dump() for c in req.cards])
    await hub.set_canvas(req.title, req.subtitle, cards, show_now=req.showNow)
    return {"ok": True, "count": len(cards), "activeSurface": hub.active_surface}


# ------------------------------------------------------------------ Approvals Bus & 60s Undo Queue


class CreateApprovalRequest(BaseModel):
    source: str = "hermes"
    title: str
    summaryLines: list[str] = Field(default_factory=list)
    stakes: str = "shared"
    options: list[dict[str, str]] = Field(
        default_factory=lambda: [
            {"phrase": "Go ahead", "choice": "once"},
            {"phrase": "Don't do it", "choice": "deny"},
        ]
    )
    runId: str | None = None
    requestId: str | None = None
    executionGeneration: Any = None
    allowRememberRule: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)


@app.get("/os1/approvals", dependencies=authed)
def list_approvals() -> dict[str, Any]:
    return {"items": [p.to_dict() for p in hub.pending_actions.values()]}


@app.post("/os1/approvals", dependencies=authed)
async def create_approval(req: CreateApprovalRequest) -> dict[str, Any]:
    pa = await hub.create_pending_action(
        source=req.source,
        title=req.title,
        summary_lines=req.summaryLines,
        stakes=req.stakes,
        options=req.options,
        run_id=req.runId,
        request_id=req.requestId,
        execution_generation=req.executionGeneration,
        allow_remember_rule=req.allowRememberRule,
        meta=req.meta,
    )
    return pa.to_dict()


class ApprovalRespondRequest(BaseModel):
    choice: str


@app.post("/os1/approvals/{action_id}/respond", dependencies=authed)
async def respond_approval(action_id: str, req: ApprovalRespondRequest) -> dict[str, Any]:
    pa = await hub.resolve_pending_action(action_id, req.choice)
    if pa is None:
        raise HTTPException(404, "pending action not found")

    reply = "Okay."
    if pa.source == "hermes" and pa.runId and pa.requestId:
        await _forward_hermes_approval(pa.runId, pa.requestId, pa.executionGeneration, req.choice)
        reply = "Going ahead." if req.choice != "deny" else "Okay, I stopped it."
    elif pa.source == "memory" and req.choice == "forget":
        deleted = store.forget_memory(memory_id=pa.meta.get("memory_id"), query=pa.meta.get("query"))
        asyncio.ensure_future(_trigger_hermes_forget(deleted))
        await hub.broadcast()
        reply = "It's gone — really gone." if deleted else "Nothing matched."
    elif pa.source == "inbox" and req.choice == "confirm_trash":
        nums = pa.meta.get("numbers") or []
        gmail_ids = pa.meta.get("gmail_ids") or []
        store.update_inbox_status(nums, "trashed")
        if gmail_ids and composio.configured:
            asyncio.ensure_future(composio.trash_gmail(gmail_ids))
        store.push_undo(
            label=f"Moved {len(nums)} newsletters to Trash",
            action_type="inbox_restore",
            payload={"numbers": nums, "gmail_ids": gmail_ids},
        )
        await hub.broadcast()
        reply = f"Moved {len(nums)} newsletters to Trash. Say 'undo that' anytime in the next minute."
    elif pa.source == "triage" and req.choice == "later":
        hub.next_greeting_queue.append({"title": pa.title, "summary": " · ".join(pa.summaryLines)})
        await hub.broadcast()
        reply = "I'll remind you in ten."

    return {"ok": True, "id": action_id, "choice": req.choice, "reply": reply}


class VerifyApprovalRequest(BaseModel):
    expected_source: str | None = None


@app.post("/os1/approvals/{action_id}/verify", dependencies=authed)
def verify_approval(action_id: str, req: VerifyApprovalRequest) -> dict[str, Any]:
    """Consume a one-time server-verified human approval token (used by os1_composio / tools)."""
    rec = hub.consume_approval_token(action_id, expected_source=req.expected_source)
    if rec is None:
        raise HTTPException(403, "approval_id is missing, expired, denied, or already consumed")
    return {"ok": True, "approved": True, "stakes": rec.get("stakes"), "meta": rec.get("meta") or {}}


class UndoRequest(BaseModel):
    undo_id: str | None = None


@app.post("/os1/undo", dependencies=authed)
async def run_undo(req: UndoRequest) -> dict[str, Any]:
    entry = store.consume_undo(req.undo_id)
    if entry is None:
        return {"ok": False, "reply": "Nothing recent to undo."}

    atype = entry["action_type"]
    payload = entry["payload"]
    if atype == "inbox_restore":
        store.update_inbox_status(payload.get("numbers", []), "active")
        gmail_ids = payload.get("gmail_ids") or []
        if gmail_ids and composio.configured:
            asyncio.ensure_future(composio.untrash_gmail(gmail_ids))
    elif atype == "voice_tweak":
        store.patch_profile(payload)
    await hub.broadcast()
    return {"ok": True, "undone": entry["label"], "reply": f"Undid: {entry['label']}."}


# ------------------------------------------------------------------ Memory Ledger (Paper 15)


class MemoryCreateRequest(BaseModel):
    category: str = "things_you_love"
    summary: str = Field(min_length=1, max_length=320)
    detail: str = ""
    source: str = "voice"


@app.get("/os1/memories", dependencies=authed)
def list_memories(category: str | None = None, query: str | None = None) -> dict[str, Any]:
    return {"categories": list(MEMORY_CATEGORIES), "items": store.list_memories(category=category, query=query)}


@app.post("/os1/memories", dependencies=authed)
async def create_memory(req: MemoryCreateRequest) -> dict[str, Any]:
    mem = store.add_memory(category=req.category, summary=req.summary, detail=req.detail, source=req.source)
    await hub.notify_remembered(mem)
    return mem


class ForgetRequest(BaseModel):
    memory_id: str | None = None
    query: str | None = None
    confirmed: bool = False


@app.post("/os1/memories/forget", dependencies=authed)
async def forget_memory(req: ForgetRequest) -> dict[str, Any]:
    """Two-step forget: without `confirmed=True`, opens the high-stakes read-back modal ('Yes, forget it')."""
    matches = (
        [m for m in store.list_memories(limit=200) if m["id"] == req.memory_id]
        if req.memory_id
        else store.list_memories(query=req.query, limit=10)
    )
    if not matches:
        return {"ok": False, "deleted": [], "message": "No matching memory found."}
    if not req.confirmed:
        pa = await hub.create_pending_action(
            source="memory",
            title="Forget this permanently?",
            summary_lines=[f"{m['category'].replace('_', ' ').title()}: {m['summary']}" for m in matches[:3]],
            stakes="forget",
            options=[
                {"phrase": "Yes, forget it", "choice": "forget"},
                {"phrase": "Keep it", "choice": "cancel"},
            ],
            meta={"memory_id": req.memory_id, "query": req.query},
        )
        return {"ok": True, "requires_confirmation": True, "pending_action": pa.to_dict()}

    deleted = store.forget_memory(memory_id=req.memory_id, query=req.query)
    asyncio.ensure_future(_trigger_hermes_forget(deleted))
    await hub.broadcast()
    return {"ok": True, "deleted": deleted}


# ------------------------------------------------------------------ Connectors (Composio) & Triggers (Paper 13)


@app.get("/os1/connectors", dependencies=authed)
def list_connectors() -> dict[str, Any]:
    return {"composioConfigured": bool(os.environ.get("COMPOSIO_API_KEY")), "items": store.list_connectors()}


class ConnectorPatchRequest(BaseModel):
    policy: str | None = None
    connected: bool | None = None
    account_label: str | None = None
    label: str | None = None


@app.patch("/os1/connectors/{slug}", dependencies=authed)
async def patch_connector(slug: str, req: ConnectorPatchRequest) -> dict[str, Any]:
    if req.policy and req.policy not in CONNECTOR_POLICIES:
        raise HTTPException(400, f"policy must be one of {CONNECTOR_POLICIES}")
    updated = store.upsert_connector(
        slug, policy=req.policy, connected=req.connected, account_label=req.account_label, label=req.label
    )
    await hub.broadcast()
    return updated


@app.post("/os1/connectors/{slug}/connect", dependencies=authed)
async def connect_connector(slug: str) -> dict[str, Any]:
    """Generate a Composio v3 Connect Link and start polling for completion (auto-opens Spatial Inbox for Gmail)."""
    return await _start_connector_flow(slug)


@app.post("/os1/webhooks/composio")
async def composio_webhook(request: Request) -> dict[str, Any]:
    """Composio trigger webhook → Jev attention triage. Fails closed if COMPOSIO_WEBHOOK_SECRET is unset."""
    raw = await request.body()
    secret = os.environ.get("COMPOSIO_WEBHOOK_SECRET", "").strip()
    allow_unsigned = os.environ.get("OS1_ALLOW_UNSIGNED_WEBHOOKS", "0") == "1"
    if not secret:
        if not allow_unsigned:
            raise HTTPException(
                503,
                "COMPOSIO_WEBHOOK_SECRET is not set; refusing unsigned webhook (set OS1_ALLOW_UNSIGNED_WEBHOOKS=1 only in local tests)",
            )
    else:
        sig = request.headers.get("x-composio-signature", "") or request.headers.get("webhook-signature", "")
        expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if not sig or not secrets.compare_digest(sig.removeprefix("sha256="), expected):
            raise HTTPException(401, "invalid webhook signature")

    event = json.loads(raw.decode() or "{}")
    triage = await director.triage_trigger(event, user_busy=hub.active_surface != "home")
    urgency = triage["urgency"]
    title = str(event.get("title") or event.get("type") or "Incoming update")
    summary = str(event.get("summary") or event.get("snippet") or "")

    store.add_activity(source="trigger", title=title, detail=f"[{urgency}] {summary}", status="done")
    if urgency == "medium":
        hub.next_greeting_queue.append({"title": title, "summary": summary})
        await hub.broadcast()
    elif urgency == "high":
        await hub.create_pending_action(
            source="triage",
            title="Sorry — can I interrupt?",
            summary_lines=[title, summary] if summary else [title],
            stakes="shared",
            options=[
                {"phrase": "Go ahead", "choice": "accept"},
                {"phrase": "In ten", "choice": "later"},
            ],
        )
    return {"ok": True, "urgency": urgency, "source": triage["source"]}


# ------------------------------------------------------------------ Spatial Inbox (Paper 07/08)


class InboxSyncRequest(BaseModel):
    items: list[dict[str, Any]]


@app.get("/os1/inbox", dependencies=authed)
def get_inbox() -> dict[str, Any]:
    return {"items": store.list_inbox()}


@app.post("/os1/inbox/sync", dependencies=authed)
async def sync_inbox(req: InboxSyncRequest) -> dict[str, Any]:
    scored = await director.score_inbox_items(req.items)
    saved = store.set_inbox_items(scored)
    await hub.broadcast()
    return {"ok": True, "count": len(saved), "items": saved}


# ------------------------------------------------------------------ Voice Registry (Paper 14)


@app.get("/os1/voices", dependencies=authed)
def get_voices() -> dict[str, Any]:
    prof = read_profile()
    return {
        "active": {
            "voiceKey": prof.get("voice_key", "voice_1_warm"),
            "speed": prof.get("voice_speed", 0.96),
            "temperature": prof.get("voice_temperature", 0.72),
            "styleNote": prof.get("voice_style_note", ""),
        },
        "presets": [
            {"key": "voice_1_warm", "name": "Voice I", "subtitle": "Warm · intimate · Drama 3", "speed": 0.96, "temperature": 0.72},
            {"key": "voice_2_bright", "name": "Voice II", "subtitle": "Bright · quick · Drama 3", "speed": 1.05, "temperature": 0.65},
            {"key": "voice_male", "name": "Voice III", "subtitle": "Grounded · calm · Drama 3", "speed": 0.97, "temperature": 0.68},
        ],
    }


class VoicePatchRequest(BaseModel):
    voiceKey: str | None = None
    speed: float | None = None
    temperature: float | None = None
    styleNote: str | None = None


@app.patch("/os1/voices", dependencies=authed)
async def patch_voices(req: VoicePatchRequest) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    if req.voiceKey is not None:
        updates["voice_key"] = req.voiceKey
    if req.speed is not None:
        updates["voice_speed"] = max(0.75, min(1.3, round(req.speed, 2)))
    if req.temperature is not None:
        updates["voice_temperature"] = max(0.3, min(1.0, round(req.temperature, 2)))
    if req.styleNote is not None:
        updates["voice_style_note"] = req.styleNote
    if updates:
        store.patch_profile(updates)
        await hub.broadcast()
    return get_voices()


# ------------------------------------------------------------------ Her Computer — Orgo + noVNC Proxy (Paper 10)


@app.get("/os1/her-computer/status", dependencies=authed)
def her_computer_status() -> dict[str, Any]:
    return {
        "online": True,
        "computerId": os.environ.get("ORGO_COMPUTER_ID", ""),
        "resolution": "1920x1080",
        "activity": store.list_activity(source="her_computer", limit=25),
    }


class ActivityCreateRequest(BaseModel):
    source: str = "her_computer"
    title: str
    detail: str = ""
    status: str = "done"


@app.post("/os1/her-computer/activity", dependencies=authed)
async def post_activity(req: ActivityCreateRequest) -> dict[str, Any]:
    item = store.add_activity(source=req.source, title=req.title, detail=req.detail, status=req.status)
    await hub.broadcast()
    return item


@app.post("/os1/her-computer/vnc-session", dependencies=authed)
async def her_computer_vnc_session() -> dict[str, Any]:
    """Fetch Orgo's VNC password server-side (never shipped in client bundle) and return proxy WS path."""
    api_key = os.environ.get("ORGO_API_KEY", "")
    cid = os.environ.get("ORGO_COMPUTER_ID", "")
    password = ""
    if api_key and cid:
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                r = await client.get(
                    f"https://www.orgo.ai/api/computers/{cid}/vnc-password",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if r.is_success:
                    password = str(r.json().get("password") or "")
        except Exception as exc:  # noqa: BLE001
            log.warning("orgo vnc-password fetch failed: %s", exc)
    return {
        "wsPath": "/os1/her-computer/vnc",
        "password": password,
        "readOnlyDefault": True,
        "resolution": "1920x1080",
    }


@app.websocket("/os1/her-computer/vnc")
async def her_computer_vnc_proxy(websocket: WebSocket, token: str = "") -> None:
    """Authenticated binary WebSocket proxy from desktop noVNC client → VM localhost:6080 websockify."""
    auth = token or websocket.headers.get("authorization", "")
    if not _check_token(auth):
        await websocket.close(code=4401)
        return
    subprotocols = websocket.headers.get("sec-websocket-protocol", "")
    chosen = "binary" if "binary" in subprotocols else None
    await websocket.accept(subprotocol=chosen)
    try:
        async with websockets.connect(
            VNC_UPSTREAM_WS,
            subprotocols=["binary"] if chosen else None,
            max_size=None,
        ) as upstream:

            async def client_to_vnc() -> None:
                while True:
                    msg = await websocket.receive()
                    if msg.get("type") == "websocket.disconnect":
                        break
                    if msg.get("bytes") is not None:
                        await upstream.send(msg["bytes"])
                    elif msg.get("text") is not None:
                        await upstream.send(msg["text"])

            async def vnc_to_client() -> None:
                async for data in upstream:
                    if isinstance(data, bytes):
                        await websocket.send_bytes(data)
                    else:
                        await websocket.send_text(data)

            done, pending = await asyncio.wait(
                [asyncio.create_task(client_to_vnc()), asyncio.create_task(vnc_to_client())],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
            for t in done:
                t.exception() if not t.cancelled() else None
    except Exception as exc:  # noqa: BLE001
        log.debug("vnc proxy ended: %s", exc)
    finally:
        try:
            await websocket.close()
        except Exception as exc:  # noqa: BLE001
            log.debug("vnc websocket close ignored: %s", exc)


# ------------------------------------------------------------------ Your Computer — Cua Outbound Tunnel (Paper 09)


@app.get("/os1/your-computer/status", dependencies=authed)
def your_computer_status() -> dict[str, Any]:
    from .mac_automation import mac_automation
    return {
        "connected": hub.cua_ws is not None,
        "status": hub.cua_status,
        "manifest": hub.cua_manifest,
        "recentActivity": store.list_activity(source="your_computer", limit=20),
        "mac_info": mac_automation.get_mac_info(),
    }


@app.get("/os1/mac/info", dependencies=authed)
def mac_info_endpoint() -> dict[str, Any]:
    from .mac_automation import mac_automation
    return mac_automation.get_mac_info()


@app.get("/os1/mac/screenshot")
@app.get("/os1/your-computer/screenshot")
def mac_screenshot_endpoint() -> Response:
    from .mac_automation import mac_automation
    data = mac_automation.get_screenshot_bytes()
    if not data:
        raise HTTPException(500, "Failed to capture Mac screen")
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.websocket("/os1/your-computer/tunnel")
async def your_computer_tunnel(websocket: WebSocket, token: str = "") -> None:
    """Outbound authenticated WebSocket tunnel opened BY the desktop Electron app's embedded Cua Driver."""
    auth = token or websocket.headers.get("authorization", "")
    if not _check_token(auth):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    hub.cua_ws = websocket
    hub.cua_status = "ready"
    await hub.broadcast()
    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            mtype = msg.get("type")
            if mtype == "hello" and isinstance(msg.get("manifest"), dict):
                hub.cua_manifest = msg["manifest"]
                await hub.broadcast()
            elif mtype == "result":
                cid = str(msg.get("id") or "")
                fut = hub.cua_pending_calls.get(cid)
                if fut and not fut.done():
                    fut.set_result(msg.get("result") or {"ok": True})
            elif mtype == "activity":
                store.add_activity(
                    source="your_computer",
                    title=str(msg.get("title") or "Action"),
                    detail=str(msg.get("detail") or ""),
                    status=str(msg.get("status") or "done"),
                )
                await hub.broadcast()
    except WebSocketDisconnect:
        pass
    finally:
        if hub.cua_ws is websocket:
            hub.cua_ws = None
            hub.cua_status = "disconnected"
        await hub.broadcast()


class CuaCallRequest(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    requireApproval: bool = True
    description: str = ""


@app.post("/os1/your-computer/call", dependencies=authed)
async def your_computer_call(req: CuaCallRequest) -> dict[str, Any]:
    """Called by Hermes's `user_computer` MCP bridge; gates mutations behind `computer` PendingAction."""
    if req.requireApproval:
        pa = await hub.create_pending_action(
            source="cua",
            title=f"On your Mac: {req.tool}",
            summary_lines=[req.description or json.dumps(req.arguments)[:160]],
            stakes="computer",
            options=[
                {"phrase": "Go ahead", "choice": "allow"},
                {"phrase": "Let me drive", "choice": "deny"},
            ],
        )
        fut: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        hub.action_waiters[pa.id] = fut
        try:
            choice = await asyncio.wait_for(fut, timeout=90.0)
        except TimeoutError:
            await hub.resolve_pending_action(pa.id, "deny")
            return {"ok": False, "error": "Approval timed out."}
        if choice != "allow":
            return {"ok": False, "error": "Denied by user."}
    return await hub.call_cua(req.tool, req.arguments)


@app.post("/os1/your-computer/revoke", dependencies=authed)
async def your_computer_revoke() -> dict[str, Any]:
    return await hub.revoke_cua()


# ------------------------------------------------------------------ Real Mobile Automation (Android & iOS)


class MobileActionRequest(BaseModel):
    action: str
    device_id: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)


class LaunchEmulatorRequest(BaseModel):
    platform: str = "android"
    name: str | None = None


class ConnectDeviceRequest(BaseModel):
    platform: str = "android"
    address: str


@app.get("/os1/mobile/status", dependencies=authed)
def mobile_status() -> dict[str, Any]:
    from .mobile_automation import mobile_automation
    return {
        "ok": True,
        "android_devices": mobile_automation.list_android_devices(),
        "available_avds": mobile_automation.list_android_avds(),
        "ios_devices": mobile_automation.list_ios_devices(),
        "available_ios_simulators": mobile_automation.list_ios_simulators(),
        "has_adb": mobile_automation.adb_path is not None,
        "has_emulator": mobile_automation.emulator_path is not None,
    }


@app.post("/os1/mobile/launch-emulator", dependencies=authed)
def mobile_launch_emulator(req: LaunchEmulatorRequest) -> dict[str, Any]:
    from .mobile_automation import mobile_automation
    if "ios" in req.platform.lower():
        return mobile_automation.launch_ios_simulator(req.name)
    return mobile_automation.launch_android_emulator(req.name)


@app.post("/os1/mobile/connect-device", dependencies=authed)
def mobile_connect_device(req: ConnectDeviceRequest) -> dict[str, Any]:
    from .mobile_automation import mobile_automation
    if "android" in req.platform.lower():
        return mobile_automation.connect_android_device(req.address)
    return {"ok": False, "error": f"Unsupported platform for direct IP connect: {req.platform}"}


@app.post("/os1/mobile/action", dependencies=authed)
def mobile_action_endpoint(req: MobileActionRequest) -> dict[str, Any]:
    from .mobile_automation import mobile_automation
    args = {**req.arguments}
    if req.device_id:
        args["device_id"] = req.device_id
    return mobile_automation.execute_mobile_tool(req.action, args)


@app.get("/os1/mobile/screenshot")
def mobile_screenshot_endpoint(device_id: str = "") -> Response:
    from .mobile_automation import mobile_automation
    data = mobile_automation.android_screenshot(device_id or None)
    if not data:
        raise HTTPException(404, "No Android device screenshot available")
    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
