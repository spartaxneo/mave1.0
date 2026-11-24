"""OS1 voice worker entry point.

    uv run python -m os1_voice.worker dev      # local development (auto-reload)
    uv run python -m os1_voice.worker start    # production

One AgentSession per room. First run: OperatorAgent -> (initiating) -> SamanthaAgent
(first meeting). Afterwards: SamanthaAgent directly. Agent handoffs keep the room and
swap TTS voices.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import os

from livekit.agents import AgentServer, AgentSession, JobContext, JobProcess, cli, inference, room_io
from livekit.plugins import fishaudio, silero

from .brain import Brain
from .bus import Bus, Phase
from .config import Settings, Voice, voices
from .hermes import HermesRuns, new_session_id, voice_llm
from .jev import Jev
from .onboarding import Dossier, OperatorAgent
from .orchestrator_client import OrchestratorClient
from .profile import ProfileStore
from .router import TurnRouter
from .mave import MaveAgent, SamanthaAgent
from .turns import TurnEngine, WorkManager

log = logging.getLogger("os1.worker")
INITIATION_S = float(os.environ.get("OS1_INITIATION_S", "6"))
AGENT_NAME = os.environ.get("MAVE_AGENT_NAME", os.environ.get("OS1_AGENT_NAME", "mave"))
# drama3: Samantha speaks through this worker (exact Drama 3 voice).
# live3:  onboarding runs here, then the app hands off to a Fish Live 3 session (brain_server.py).
VOICE_ENGINE = os.environ.get("OS1_VOICE_ENGINE", "drama3")

server = AgentServer()


async def on_text_input(sess: AgentSession, ev: room_io.TextInputEvent) -> None:
    """Typed text and tapped say-chips take the same path as a spoken turn
    (LiveKit's default would call generate_reply and skip our turn logic)."""
    agent = sess.current_agent
    handle = getattr(agent, "handle_text", None)
    if handle is None:
        await sess.interrupt()
        sess.generate_reply(user_input=ev.text)
        return
    await sess.interrupt()
    if await handle(ev.text.strip()) is not None:
        sess.generate_reply(user_input=ev.text)


def make_tts(voice: Voice) -> fishaudio.TTS:
    if not voice.reference_id:
        log.warning("Fish voice %s has no reference_id; Fish will use its default voice", voice.key)
    return fishaudio.TTS(
        model=voice.model,
        voice_id=voice.reference_id or fishaudio.tts.DEFAULT_VOICE_ID,
        output_format="pcm",
        sample_rate=24000,
        latency_mode="balanced",
        speed=voice.speed,
        temperature=voice.temperature,
    )


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    settings = Settings()
    registry = voices()
    jev = Jev(settings)
    runs = HermesRuns(settings)
    profiles = ProfileStore(
        os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8787"), os.environ.get("OS1_CLIENT_TOKEN", "")
    )
    profile = await profiles.get()

    await ctx.connect()
    bus = Bus(ctx.room)
    orch = OrchestratorClient()
    router = TurnRouter(jev)
    work = WorkManager(runs, bus, orch=orch)
    brain = Brain("drama3")
    engines: list[TurnEngine] = []

    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        stt=fishaudio.STT(),
        # Unused for Samantha (SamanthaAgent.llm_node streams from Brain); kept so the session has an LLM.
        llm=voice_llm(settings, new_session_id("voice")),
        tts=make_tts(registry[profile.get("voice_key") or settings.default_voice]),
        turn_handling={"turn_detection": inference.TurnDetector()},
    )

    def mave(voice_key: str, *, first_meeting: bool) -> MaveAgent:
        voice = registry.get(voice_key) or registry[settings.default_voice]
        engine = TurnEngine(
            router=router,
            work=work,
            ui=bus,
            orch=orch,
            user_name=profile.get("name", ""),
            first_meeting=first_meeting,
            asleep_phase=Phase.ASLEEP,
            active_phase=Phase.ACTIVE,
        )
        engines.append(engine)
        return MaveAgent(engine=engine, brain=brain, bus=bus, tts=make_tts(voice), voice_key=voice.key)

    samantha = mave

    async def onboarding_complete(dossier: Dossier) -> None:
        await profiles.patch(
            onboarded=True,
            voice_key=dossier.voice_key,
            dossier=dataclasses.asdict(dossier),
            first_meeting_pending=VOICE_ENGINE == "live3",
        )
        # Seed Hermes memory so she wakes up knowing what the interview revealed.
        memory = dossier.as_memory_text()
        if memory:
            try:
                await runs.start(
                    "Save these facts about the user to your long-term user memory (USER.md). "
                    "Do not reply with anything else.\n\n" + memory
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("could not seed Hermes memory: %s", exc)
        await asyncio.sleep(INITIATION_S)  # the client plays the waking loop + chime (Paper 03)
        if VOICE_ENGINE == "live3":
            await bus.set_handoff("live3")  # the app leaves this room and joins the Fish Live 3 session
        else:
            session.update_agent(mave(dossier.voice_key, first_meeting=True))

    if profile.get("onboarded"):
        agent = mave(profile.get("voice_key", settings.default_voice), first_meeting=False)
    else:
        agent = OperatorAgent(
            jev=jev,
            bus=bus,
            tts=make_tts(registry["operator"]),
            voices=registry,
            user_name=profile.get("name", ""),
            on_complete=onboarding_complete,
        )

    async def cleanup() -> None:
        # Hermes isn't in the per-turn path, so hand it the conversation for long-term memory.
        lines = [line for e in engines for line in e.recent]
        if sum(1 for line in lines if line.startswith("user:")) >= 2:
            try:
                await runs.start(
                    "This is a transcript of a voice conversation you just had with the user. Save anything worth "
                    "remembering about them to long-term memory. Do not reply with anything else.\n\n"
                    + "\n".join(lines[-80:])
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("could not send transcript to Hermes: %s", exc)
        await runs.aclose()
        await jev.aclose()
        await orch.aclose()

    ctx.add_shutdown_callback(cleanup)
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(text_input=room_io.TextInputOptions(text_input_cb=on_text_input)),
    )


if __name__ == "__main__":
    cli.run_app(server)
