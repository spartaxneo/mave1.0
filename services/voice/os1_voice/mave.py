"""Mave on the drama3 engine: LiveKit turn-taking + our brain + Fish Drama 3 voice.

The words come from Brain (one fast Claude call, cached persona), not from Hermes.
Turn decisions come from TurnEngine (shared with the live3 brain server).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterable
from typing import Any

from livekit.agents import Agent, ModelSettings, StopResponse, llm

from .brain import Brain
from .bus import Bus, Phase
from .cues import strip_cues_stream
from .onboarding import load_script
from .turns import TurnEngine

log = logging.getLogger("mave.voice")


class MaveAgent(Agent):
    def __init__(self, *, engine: TurnEngine, brain: Brain, bus: Bus, tts: Any, voice_key: str) -> None:
        super().__init__(instructions="(persona lives in os1_voice.brain)", tts=tts)
        self._engine = engine
        self._brain = brain
        self._bus = bus
        self._voice_key = voice_key
        self._script = load_script()
        self._spoke_since_hello = False
        self._next_note: str | None = None
        engine.work.narrate = self._narrate

    async def on_enter(self) -> None:
        await self._bus.set_voice(self._voice_key)
        if self._engine.first_meeting:
            await self._bus.set_phase(Phase.SAMANTHA_FIRST_MEETING)
            await self._bus.set_chips([])
            first_words = (
                self._script.get("mave", {}).get("first_words")
                or self._script.get("samantha", {}).get("first_words", "Hello, I'm here.")
            )
            self.session.say(first_words)
            asyncio.ensure_future(self._nudge_if_silent())
        else:
            await self._bus.set_phase(Phase.ACTIVE)
            await self._bus.set_chips(self._engine.chips())

    async def _nudge_if_silent(self) -> None:
        nudge_delay = float(
            self._script.get("mave", {}).get("nudge_after_s")
            or self._script.get("samantha", {}).get("nudge_after_s", 3.5)
        ) + 1.5
        await asyncio.sleep(nudge_delay)
        if not self._spoke_since_hello:
            nudge = (
                self._script.get("mave", {}).get("nudge_after_silence")
                or self._script.get("samantha", {}).get("nudge_after_silence", "[softly] Hi. Can you hear me okay?")
            )
            self.session.say(nudge)

    async def _narrate(self, update: str, how: str) -> None:
        self._next_note = how
        self.session.generate_reply(user_input=update)

    # --- turn entry points (spoken turns + typed/tapped input share one path) ---

    async def on_user_turn_completed(self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage) -> None:
        if await self.handle_text((new_message.text_content or "").strip()) is None:
            raise StopResponse()

    async def handle_text(self, text: str) -> str | None:
        self._spoke_since_hello = True
        result = await self._engine.decide(text)
        if result.interrupt:
            self.session.interrupt()
        self._next_note = result.note
        return result.note

    # --- the words: our brain instead of an LLM plugin ---

    async def llm_node(
        self, chat_ctx: llm.ChatContext, tools: list[llm.FunctionTool], model_settings: ModelSettings
    ) -> AsyncIterable[str]:
        history = [
            {"role": m.role, "content": m.text_content or ""}
            for m in chat_ctx.items
            if isinstance(m, llm.ChatMessage) and m.role in ("user", "assistant")
        ]
        note, self._next_note = self._next_note, None
        async for chunk in self._brain.stream(history, note):
            yield chunk

    async def transcription_node(self, text: AsyncIterable[str], model_settings: ModelSettings) -> AsyncIterable[str]:
        said = ""
        async for chunk in strip_cues_stream(text):
            said += chunk
            yield chunk
        if said:
            self._engine.heard_her(said)
            if self._engine.first_meeting and ("Mave" in said or "Samantha" in said) and self._bus.phase in (Phase.SAMANTHA_FIRST_MEETING, getattr(Phase, "MAVE_FIRST_MEETING", Phase.SAMANTHA_FIRST_MEETING)):
                # She just named herself.
                await self._bus.set_chips(self._script["chips"]["naming"])
                await self._bus.set_phase(Phase.ACTIVE)


SamanthaAgent = MaveAgent
