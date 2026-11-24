"""live3 engine: Mave's brain as an OpenAI-compatible endpoint for Fish Live 3.

Fish Live 3 owns listening, turn-taking, backchannels and the voice; on every reply it
calls our `POST /v1/chat/completions` (verified 2026-11-22: greeting + every user turn).
We answer with the same TurnEngine + Brain the drama3 worker uses.

    uv run uvicorn os1_voice.brain_server:app --host 0.0.0.0 --port 8788

Must be public HTTPS (Fish rejects private hosts). Fish targets: TTFT < 800 ms, 10 s cap,
one retry; three failed generations end the call.

Fish can't be pushed into mid-call, so run results go to the app over
`GET /os1/sessions/{id}/events` (SSE); the app relays them back as a `user.message`
wrapped in <background-update>, and the brain narrates.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from .brain import Brain
from .config import Settings
from .hermes import HermesRuns
from .jev import Jev
from .onboarding import load_script
from .orchestrator_client import OrchestratorClient
from .router import TurnRouter
from .turns import TurnEngine, WorkManager

log = logging.getLogger("os1.brain_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

BRAIN_TOKEN = os.environ.get("OS1_BRAIN_TOKEN", "")  # what Fish sends as Bearer (llm.custom.api_key)
CLIENT_TOKEN = os.environ.get("OS1_CLIENT_TOKEN", "")  # what the app sends for the events stream
SESSION_TTL_S = 3 * 3600
# Proxies/tunnels (Cloudflare) buffer or compress SSE unless told not to.
SSE_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


def sse(body: AsyncIterator[bytes]) -> StreamingResponse:
    return StreamingResponse(body, media_type="text/event-stream", headers=SSE_HEADERS)


app = FastAPI(title="OS1 brain (live3)")
settings = Settings()
jev = Jev(settings)
runs = HermesRuns(settings)
orch = OrchestratorClient()
brain = Brain("live3")
router = TurnRouter(jev)


class SessionEvents:
    """UiPort for live3: screen state the app reads over SSE."""

    def __init__(self) -> None:
        self.phase: str = "active"
        self._chips: list[str] = []
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    @property
    def chips(self) -> list[str]:
        return self._chips

    async def set_phase(self, phase: Any) -> None:
        self.phase = str(getattr(phase, "value", phase))
        await self.queue.put({"type": "phase", "phase": self.phase})

    async def set_chips(self, chips: list[str]) -> None:
        self._chips = chips
        await self.queue.put({"type": "chips", "chips": chips})

    async def set_work(self, items: list[dict]) -> None:
        await self.queue.put({"type": "work", "items": items})


@dataclass
class Session:
    engine: TurnEngine
    ui: SessionEvents
    first_meeting: bool
    greeted: bool = False
    touched: float = field(default_factory=time.monotonic)


SESSIONS: dict[str, Session] = {}


def _session(session_id: str, extra: dict[str, Any]) -> Session:
    now = time.monotonic()
    for sid in [s for s, v in SESSIONS.items() if now - v.touched > SESSION_TTL_S]:
        SESSIONS.pop(sid, None)
    if session_id not in SESSIONS:
        ui = SessionEvents()
        first = bool(extra.get("first_meeting"))
        work = WorkManager(runs, ui, orch=orch)

        async def narrate(update: str, how: str) -> None:
            await ui.queue.put({"type": "narrate", "text": update})

        work.narrate = narrate
        engine = TurnEngine(
            router=router,
            work=work,
            ui=ui,
            orch=orch,
            user_name=str(extra.get("name") or ""),
            first_meeting=first,
            asleep_phase="asleep",
            active_phase="active",
        )
        SESSIONS[session_id] = Session(engine=engine, ui=ui, first_meeting=first)
        ui._chips = [] if first else engine.chips()
    s = SESSIONS[session_id]
    s.touched = now
    return s


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""


def _sse(chunk_id: str, delta: dict[str, Any], finish: str | None = None) -> bytes:
    payload = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": "mave",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return f"data: {json.dumps(payload)}\n\n".encode()


async def _reply(words: AsyncIterator[str]) -> AsyncIterator[bytes]:
    cid = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    yield _sse(cid, {"role": "assistant", "content": ""})
    async for text in words:
        if text:
            yield _sse(cid, {"content": text})
    yield _sse(cid, {}, "stop")
    yield b"data: [DONE]\n\n"


async def _fixed(text: str) -> AsyncIterator[str]:
    yield text


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "engine": "live3", "model": brain.settings.model, "sessions": len(SESSIONS)}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, authorization: str = Header(default="")) -> StreamingResponse:
    if BRAIN_TOKEN and not secrets.compare_digest(authorization, f"Bearer {BRAIN_TOKEN}"):
        raise HTTPException(401, "unauthorized")
    body = await request.json()
    session_id = str(body.get("session_id") or "anonymous")
    extra = body.get("fishaudio_extra_body") or {}
    s = _session(session_id, extra)
    messages = body.get("messages") or []

    history = [
        {"role": m["role"], "content": _text(m.get("content"))}
        for m in messages
        if m.get("role") in ("user", "assistant") and _text(m.get("content")).strip()
    ]
    last_user = next((h for h in reversed(history) if h["role"] == "user"), None)
    replying_to_user = bool(history) and history[-1]["role"] == "user"

    if not replying_to_user:
        # Fish asks for the opening line (or a re-engagement) with no new user turn.
        if not s.greeted:
            s.greeted = True
            if s.first_meeting:
                script = load_script()
                first_words = (script.get("mave") or script.get("samantha", {}))["first_words"]
                return StreamingResponse(
                    _reply(_fixed(first_words)), media_type="text/event-stream"
                )
            note = "The call just connected. Greet them as yourself, warmly and briefly, like picking up where you left off."
        else:
            note = "They've gone quiet. Say something short and natural, or simply check in."
        return sse(_reply(brain.stream(history, note)))

    result = await s.engine.decide((last_user or {}).get("content", "").strip())
    if result.note is None:
        # Not said to her / "hold on": Live 3 handles the silence. Return an empty turn.
        return sse(_reply(_fixed("")))

    async def words() -> AsyncIterator[str]:
        said = ""
        async for chunk in brain.stream(history, result.note):
            said += chunk
            yield chunk
        s.engine.heard_her(said)
        if s.engine.first_meeting and ("Mave" in said or "Samantha" in said):
            await s.ui.set_chips(load_script()["chips"]["naming"])

    return sse(_reply(words()))


@app.get("/os1/sessions/{session_id}/poll")
async def session_poll(session_id: str, authorization: str = Header(default="")) -> dict[str, Any]:
    """Queued screen events + run results for the app. Polling works through any proxy;
    Cloudflare quick tunnels hold long-lived SSE bodies (measured 2026-11-22)."""
    if CLIENT_TOKEN and not secrets.compare_digest(authorization, f"Bearer {CLIENT_TOKEN}"):
        raise HTTPException(401, "unauthorized")
    s = _session(session_id, {})
    events: list[dict[str, Any]] = []
    while not s.ui.queue.empty():
        events.append(s.ui.queue.get_nowait())
    return {"chips": s.ui.chips, "phase": s.ui.phase, "events": events}


@app.get("/os1/sessions/{session_id}/events")
async def session_events(session_id: str, token: str = "") -> StreamingResponse:
    """Screen state + run results for the app (EventSource can't send headers, so the token is a query param)."""
    if CLIENT_TOKEN and not secrets.compare_digest(token, CLIENT_TOKEN):
        raise HTTPException(401, "unauthorized")
    s = _session(session_id, {})

    async def stream() -> AsyncIterator[bytes]:
        yield b": " + b" " * 2048 + b"\n\n"  # padding: pushes the stream past proxy buffers right away
        yield f"data: {json.dumps({'type': 'chips', 'chips': s.ui.chips})}\n\n".encode()
        while True:
            try:
                ev = await asyncio.wait_for(s.ui.queue.get(), timeout=15)
                yield f"data: {json.dumps(ev)}\n\n".encode()
            except TimeoutError:
                yield b": keepalive\n\n"

    return sse(stream())
