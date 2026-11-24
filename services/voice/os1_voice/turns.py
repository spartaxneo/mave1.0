"""Engine-independent turn logic: Jev routing, say-chips, background work, narration.

Both voice engines use this:
- drama3: SamanthaAgent (LiveKit worker) — UI via participant attributes (Bus).
- live3:  brain_server.py (Fish Live 3 custom LLM) — UI via an SSE event stream to the app.

    text ─▶ TurnEngine.decide() ─▶ Jev router ─▶ note for the brain (or None = stay quiet)
                                    ├ work    → Hermes run on Opus (WorkManager)
                                    ├ control → status / steer / stop / approve / deny
                                    ├ chip    → deterministic say-chip action
                                    └ chat    → just talk
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from .hermes import HermesRuns
from .onboarding import first_meeting_overlay, load_script
from .orchestrator_client import OrchestratorClient
from .router import Route, RunRef, TurnRouter

log = logging.getLogger("os1.turns")

ACTIVE_CHIPS = ["Show me", "Hold on a sec", "Goodnight, Mave"]
WORK_CHIP = "How's it going?"

ROUTE_NOTES = {
    "work": "You've just asked your helpers to take care of this in the background. Acknowledge it in one "
    "short, natural sentence (no results yet, no promises about timing), then stop.",
    "chat": "Answer from what you know and what you remember about them. If this actually needs looking "
    "something up or doing something, say you'll have it taken care of.",
}


def tone(warmth: float | None) -> str:
    if warmth is None:
        return ""
    if warmth >= 0.66:
        return " This moment is personal: slow down and be gentle."
    if warmth <= 0.2:
        return " They're being brisk: be quick and light."
    return ""


class UiPort(Protocol):
    """What the turn engine can do to the screen. Implemented by Bus (drama3) and SessionEvents (live3)."""

    @property
    def phase(self) -> Any: ...
    @property
    def chips(self) -> list[str]: ...
    async def set_phase(self, phase: Any) -> None: ...
    async def set_chips(self, chips: list[str]) -> None: ...
    async def set_work(self, items: list[dict]) -> None: ...


@dataclass
class Task:
    run_id: str
    label: str
    status: str = "running"
    pending_approval: dict[str, Any] | None = None


NarrateFn = Callable[[str, str], Awaitable[None]]  # (background-update text, how-to-say-it note)


class WorkManager:
    """Background Hermes runs on Opus, and narration when they finish or need approval."""

    def __init__(
        self,
        runs: HermesRuns,
        ui: UiPort,
        narrate: NarrateFn | None = None,
        orch: OrchestratorClient | None = None,
    ) -> None:
        self._runs = runs
        self._ui = ui
        self._orch = orch
        self.narrate: NarrateFn | None = narrate
        self.tasks: dict[str, Task] = {}

    def refs(self) -> list[RunRef]:
        return [RunRef(t.run_id, t.label) for t in self.tasks.values() if t.status in ("running", "waiting")]

    def pending(self) -> Task | None:
        return next((t for t in self.tasks.values() if t.pending_approval), None)

    async def _publish(self) -> None:
        items = [{"id": t.run_id, "label": t.label, "status": t.status} for t in self.tasks.values()]
        await self._ui.set_work(items)
        if self._orch is not None:
            await self._orch.sync_runs(items)

    async def start(self, request: str) -> Task:
        run_id = await self._runs.start(
            request,
            instructions="The user asked for this out loud. Finish with a short plain-language result someone "
            "could say in two sentences. Ask before anything irreversible.",
        )
        label = " ".join(request.split()[:7]).rstrip(".,?!")
        task = self.tasks[run_id] = Task(run_id=run_id, label=label)
        await self._publish()
        asyncio.ensure_future(self._watch(task))
        return task

    async def _watch(self, task: Task) -> None:
        output = ""
        try:
            async for ev in self._runs.events(task.run_id):
                if ev.event == "approval.request":
                    task.status, task.pending_approval = "waiting", ev.data
                    await self._publish()
                    desc = str(ev.data.get("description") or ev.data)
                    if self._orch is not None:
                        await self._orch.create_approval(
                            run_id=task.run_id,
                            request_id=str(ev.data.get("request_id", "")),
                            generation=ev.data.get("execution_generation"),
                            title=f"Approve: {task.label}",
                            summary_lines=[desc[:200]],
                            stakes=str(ev.data.get("stakes") or "shared"),
                        )
                    await self._say(
                        task,
                        f"Your helper needs permission to continue: {desc}",
                        "Ask them, in one sentence, whether it's okay to go ahead.",
                    )
                elif ev.event == "message.delta":
                    output += str(ev.data.get("delta") or ev.data.get("text") or "")
                elif ev.event == "run.completed":
                    output = str(ev.data.get("output") or output)
                    task.status = "done"
                    break
                elif ev.event in ("run.failed", "run.cancelled", "run.interrupted"):
                    task.status = ev.event.split(".")[1]
                    break
        except Exception as exc:  # noqa: BLE001
            log.warning("run %s stream failed: %s", task.run_id, exc)
            task.status = "failed"
        await self._publish()
        if self._orch is not None and task.status in ("done", "failed"):
            await self._orch.log_activity(task.label, output[-220:] if output else task.status, status=task.status)
        if task.status == "done":
            await self._say(task, output[-4000:], "Tell them the result in your own words, briefly and naturally.")
        elif task.status == "failed":
            await self._say(task, "It failed.", "Tell them gently that it didn't work and offer to try again.")

    async def _say(self, task: Task, update: str, how: str) -> None:
        if self.narrate is not None:
            await self.narrate(f'<background-update task="{task.label}">\n{update}\n</background-update>', how)

    async def control(self, route: Route, text: str) -> str:
        task = self.tasks.get(route.run_id or "") or (self.pending() if route.control in ("approve", "deny") else None)
        if task is None and self.tasks:
            task = list(self.tasks.values())[-1]
        if task is None:
            return "Nothing is running in the background right now; say so lightly."
        match route.control:
            case "stop":
                await self._runs.stop(task.run_id)
                task.status = "cancelled"
                await self._publish()
                return f'You just stopped "{task.label}". Confirm in a few words.'
            case "change":
                await self._runs.steer(task.run_id, text)
                return f'You passed their change on to "{task.label}". Confirm in a few words.'
            case "approve" | "deny" if task.pending_approval:
                req = task.pending_approval
                await self._runs.approve(
                    task.run_id,
                    str(req.get("request_id", "")),
                    req.get("execution_generation"),
                    "once" if route.control == "approve" else "deny",
                )
                task.pending_approval, task.status = None, "running"
                await self._publish()
                return "Acknowledge their answer in a few words and carry on."
            case _:
                info = await self._runs.status(task.run_id)
                latest = str(info.get("output") or "")[-600:]
                return f'"{task.label}" is {info.get("status")}. Latest: {latest or "nothing yet"}. Tell them briefly.'


@dataclass
class TurnResult:
    note: str | None  # None = stay quiet
    interrupt: bool = False


class TurnEngine:
    def __init__(
        self,
        *,
        router: TurnRouter,
        work: WorkManager,
        ui: UiPort,
        orch: OrchestratorClient | None = None,
        user_name: str = "",
        first_meeting: bool = False,
        asleep_phase: Any = None,
        active_phase: Any = None,
    ) -> None:
        self._router = router
        self.work = work
        self._ui = ui
        self._orch = orch
        self._script = load_script()
        self.recent: list[str] = []
        self.first_meeting = first_meeting
        self._overlay = first_meeting_overlay(user_name) if first_meeting else ""
        self._asleep, self._active = asleep_phase, active_phase

    def chips(self) -> list[str]:
        return ACTIVE_CHIPS + ([WORK_CHIP] if self.work.refs() else [])

    def heard_her(self, said: str) -> None:
        self.recent.append(f"mave: {said}")

    async def decide(self, text: str) -> TurnResult:
        if not text:
            return TurnResult(None)
        if text.startswith("<background-update"):
            return TurnResult(self._with_overlay("Your helpers just reported back (below). Tell them what matters."))
        if self._asleep is not None and self._ui.phase == self._asleep:
            await self._ui.set_phase(self._active)

        # Tier 0: deterministic zero-LLM pill/safety/undo/surface match on the orchestrator.
        if self._orch is not None:
            hit = await self._orch.try_action(text)
            if hit is not None:
                self.recent.append(f"user: {text}")
                reply = str(hit.get("reply") or "")
                if reply:
                    return TurnResult(
                        self._with_overlay(
                            f'An on-screen action just happened: "{reply}". Acknowledge it naturally in one short sentence.'
                        )
                    )
                if hit.get("target") == "canvas":
                    return TurnResult(
                        self._with_overlay(f'They chose "{hit.get("phrase")}" from the card on screen. React naturally.')
                    )

        pending = self.work.pending()
        route = await self._router.route(
            text,
            recent=self.recent,
            chips=self._ui.chips,
            runs=self.work.refs(),
            pending_approval=str(pending.pending_approval.get("description", "")) if pending else None,
        )
        log.info("route %s (%.2f via %s) %r", route.kind, route.confidence, route.source, text[:80])
        self.recent.append(f"user: {text}")

        # Fire non-blocking Jev UI Director tick so surfaces/mood evolve in parallel with speech.
        if self._orch is not None and route.kind != "ignore":
            asyncio.ensure_future(self._orch.director_tick(text, self.recent))

        if route.kind == "ignore":
            return TurnResult(None)
        note: str | None = ROUTE_NOTES["chat"]
        if route.kind == "chip":
            result = await self._chip(route.chip or "")
            if result.note is None:
                return result
            note = result.note
        elif route.kind == "control":
            note = await self.work.control(route, text)
        elif route.kind == "work":
            try:
                await self.work.start(text)
                await self._ui.set_chips(self.chips())
                note = ROUTE_NOTES["work"]
            except Exception as exc:  # noqa: BLE001
                log.warning("could not start run: %s", exc)
                note = "Your helpers can't be reached right now. Say so honestly and briefly."
        return TurnResult(self._with_overlay(note + tone(route.warmth)))

    def _with_overlay(self, note: str) -> str:
        return f"{self._overlay}\n\n{note}".strip() if self._overlay else note

    async def _chip(self, chip: str) -> TurnResult:
        match chip:
            case "Hold on a sec":
                return TurnResult(None, interrupt=True)
            case "Goodnight, Mave" | "Goodnight, Samantha":
                if self._asleep is not None:
                    await self._ui.set_phase(self._asleep)
                return TurnResult("Say a warm, brief goodnight.")
            case "How's it going?":
                return TurnResult(await self.work.control(Route(kind="control", control="status"), chip))
            case "I love it":
                self.first_meeting, self._overlay = False, ""
                await self._ui.set_chips(self.chips())
                return TurnResult("They love the name. React with real delight, briefly.")
            case "Let's pick another":
                return TurnResult("They'd like a different name. Play along and offer one or two you'd like.")
            case "Show me":
                if self._orch is not None:
                    await self._orch.show_surface("her_computer")
                return TurnResult("You just pulled up your computer screen for them to watch. Mention it warmly in a few words.")
        return TurnResult(ROUTE_NOTES["chat"])
