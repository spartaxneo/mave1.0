import { type FormEvent, useEffect, useRef, useState } from "react";
import { InfinityLoader } from "../components/InfinityLoader";
import { Presence, type PresenceState } from "../components/Presence";
import { SayChips } from "../components/SayChips";
import { SpokenLyricsView } from "../components/SpokenLyricsView";
import { sound } from "../sound";
import type { AgentState, Os1State, WorkItem } from "../useOs1";

type Levels = { current: { agent: number; user: number } };

export function presenceFor(agent: AgentState, phase: Os1State["phase"], work: WorkItem[]): PresenceState {
  if (phase === "asleep") return "asleep";
  if (agent === "speaking") return "speaking";
  if (agent === "thinking") return "thinking";
  // In direct conversation or onboarding, prioritize listening to the user over background tasks
  if (phase === "active" || phase === "naming" || phase === "operator_welcome" || phase.startsWith("operator_q")) return "listening";
  if (work.some((w) => w.status === "running")) return "working";
  return "listening";
}

function levelGetter(levels: Levels, presence: PresenceState) {
  return () => (presence === "speaking" ? levels.current.agent : levels.current.user);
}

const corner = (_pos: "tl" | "tr" | "bl" | "br" | "bc"): React.CSSProperties => ({});

/* ------------------------------------------------------------------ preflight */

/** Before the scene starts: the name to greet, then the mic permission prompt. */
export function Preflight({
  onBegin,
  busy,
  error,
  installerStatus,
  installerPercent,
  installerMessage,
  installerReady = false,
  onCleanAndRetry,
}: {
  onBegin: (name: string, storageDir?: string) => void;
  busy: boolean;
  error?: string;
  installerStatus?: string;
  installerPercent?: number;
  installerMessage?: string;
  installerReady?: boolean;
  onCleanAndRetry?: () => void;
}) {
  const [name, setName] = useState("");
  const [storageDir, setStorageDir] = useState("~/.mave");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const canProceed = !busy;

  const handleChooseFolder = async () => {
    try {
      const res = await fetch("http://127.0.0.1:3008/os1/installer/choose-directory", {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        if (data.ok && data.path) {
          setStorageDir(data.path);
          return;
        }
        if (data.cancelled) return;
      }
    } catch {}
    fileInputRef.current?.click();
  };

  const onFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const file = files[0];
      const path = (file as any).path || (file as any).webkitRelativePath?.split("/")[0];
      if (path) {
        setStorageDir(path.startsWith("/") ? path : `~/${path}`);
      }
    }
  };

  const formatDisplayDir = (dir: string) => {
    if (!dir) return "~/.mave";
    return dir.replace(/^\/Users\/[^/]+/, "~");
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!canProceed) return;
    onBegin(name.trim(), storageDir.trim() || "~/.mave");
  };

  const handleCleanAndRetry = () => {
    if (onCleanAndRetry) {
      onCleanAndRetry();
    } else {
      void fetch("http://127.0.0.1:3008/os1/installer/clean", { method: "POST" });
      void fetch("http://127.0.0.1:3008/os1/installer/start", { method: "POST" });
    }
  };

  return (
    <form
      onSubmit={submit}
      style={{
        display: "grid",
        justifyItems: "center",
        gap: 24,
        width: "100%",
        maxWidth: 600,
        padding: "clamp(24px, 5vh, 48px) 20px",
        boxSizing: "border-box",
      }}
      className="os1-fade"
    >
      <input
        ref={fileInputRef}
        type="file"
        // @ts-expect-error webkitdirectory standard on desktop browsers
        webkitdirectory="true"
        directory="true"
        style={{ display: "none" }}
        onChange={onFileInputChange}
      />

      <div className="os1-display">
        MAVE<sup style={{ fontSize: "0.36em", verticalAlign: "top" }}>1.0</sup>
      </div>

      <label style={{ display: "grid", justifyItems: "center", gap: 14, width: "100%" }}>
        <span className="os1-label" style={{ color: "var(--on-coral-dim)" }}>
          What should it call you?
        </span>
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your first name"
          style={{
            width: "100%",
            maxWidth: 340,
            background: "transparent",
            border: "none",
            borderBottom: "1px solid var(--on-coral-faint)",
            color: "var(--on-coral)",
            font: "200 clamp(24px, 5vw, 34px) var(--font-sans)",
            textAlign: "center",
            padding: "6px 0",
            outline: "none",
          }}
        />
      </label>

      <button
        type="submit"
        disabled={!canProceed}
        style={{
          padding: "11px 28px",
          borderRadius: 999,
          border: "none",
          background: "var(--paper)",
          color: "var(--coral-deep)",
          font: "400 16px var(--font-sans)",
          cursor: canProceed ? "pointer" : "not-allowed",
          opacity: canProceed ? 1 : 0.45,
          transition: "opacity 160ms ease, transform 160ms ease",
          boxShadow: canProceed ? "0 2px 10px rgba(0, 0, 0, 0.08)" : "none",
          marginTop: 6,
        }}
      >
        {busy ? "Starting…" : "Begin"}
      </button>

      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10, marginTop: 4 }}>
        <p
          className="os1-label"
          style={{
            fontSize: 11,
            color: "var(--on-coral-dim)",
            textAlign: "center",
            lineHeight: 1.6,
            margin: 0,
          }}
        >
          MAVE 1.0 listens through your microphone.
          <br />
          You'll be asked to allow it.
        </p>

        <div
          className="os1-label"
          style={{
            fontSize: 11,
            color: "var(--on-coral-dim)",
            textAlign: "center",
            margin: 0,
            letterSpacing: "0.06em",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 5,
            whiteSpace: "nowrap",
          }}
        >
          <span>MAVE will be installed in</span>
          <button
            type="button"
            onClick={handleChooseFolder}
            title="Click to select folder in Finder"
            style={{
              background: "transparent",
              border: "none",
              padding: "0 2px",
              color: "var(--paper)",
              font: "400 11px var(--font-mono)",
              textDecoration: "underline",
              textUnderlineOffset: "3px",
              cursor: "pointer",
              letterSpacing: "0.02em",
              transition: "opacity 120ms ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.opacity = "0.75";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.opacity = "1";
            }}
          >
            "{formatDisplayDir(storageDir)}"
          </button>
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: "16px 22px",
            background: "rgba(0, 0, 0, 0.22)",
            border: "1px solid rgba(255, 255, 255, 0.22)",
            borderRadius: 14,
            color: "var(--paper)",
            fontSize: 13,
            maxWidth: 440,
            width: "100%",
            textAlign: "center",
            lineHeight: 1.45,
            boxShadow: "0 4px 18px rgba(0, 0, 0, 0.12)",
            marginTop: 4,
          }}
        >
          <div style={{ fontWeight: 500, fontSize: 14, marginBottom: 6, color: "var(--paper)" }}>System Notice</div>
          <div style={{ opacity: 0.95, wordBreak: "break-word" }}>{error}</div>
          <div style={{ display: "flex", gap: 10, justifyContent: "center", marginTop: 12 }}>
            <button
              type="button"
              onClick={handleCleanAndRetry}
              style={{
                fontSize: 12,
                padding: "6px 18px",
                borderRadius: 999,
                background: "var(--paper)",
                color: "var(--coral-deep)",
                border: "none",
                fontWeight: 500,
                cursor: "pointer",
                boxShadow: "0 2px 6px rgba(0, 0, 0, 0.12)",
              }}
            >
              Clean Caches &amp; Retry
            </button>
          </div>
        </div>
      )}
    </form>
  );
}

/* ------------------------------------------------------------------ 01 boot */

export function Boot({
  levels,
  installerStatus,
  installerPercent,
  installerComponent,
  installerComponentLabel,
  installerMessage,
  error,
  onCleanAndRetry,
}: {
  levels: Levels;
  installerStatus?: string;
  installerPercent?: number;
  installerComponent?: string;
  installerComponentLabel?: string;
  installerMessage?: string;
  error?: string;
  onCleanAndRetry?: () => void;
}) {
  const fraction = error
    ? 0.08
    : installerStatus === "ready"
    ? 1
    : Math.max(0.08, Math.min(1, (installerPercent ?? 8) / 100));

  return (
    <>
      <div className="os1-corner-tl" style={{ display: "flex", alignItems: "baseline", gap: 14, color: "var(--on-coral)" }}>
        <span style={{ font: "200 clamp(22px, 4vw, 30px) var(--font-sans)" }}>
          MAVE<sup style={{ fontSize: 13 }}>1.0</sup>
        </span>
        <span className="os1-mono">Build 1.0</span>
      </div>
      <div className="os1-mono os1-corner-tr">
        Voice-first core
      </div>
      <div className="os1-screen-center os1-fade" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 20 }}>
        <Presence state="listening" getLevel={() => levels.current.agent * 0.4} size={360} />
        <Progress fraction={fraction} animate seconds={0.8} />
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
          <span className="os1-label" style={{ fontSize: 11, letterSpacing: "0.14em" }}>
            Initializing your MAVE 1.0
          </span>
          {installerMessage && (
            <span
              className="os1-mono"
              style={{
                fontSize: 12,
                color: error ? "var(--paper)" : "var(--on-coral-dim)",
                opacity: 0.9,
                maxWidth: 420,
                textAlign: "center",
              }}
            >
              {installerMessage} {installerPercent != null && installerPercent > 0 && installerPercent < 100 ? `(${installerPercent}%)` : ""}
            </span>
          )}
        </div>

        {error && (
          <div
            style={{
              padding: "16px 24px",
              background: "rgba(0, 0, 0, 0.22)",
              border: "1px solid rgba(255, 255, 255, 0.22)",
              borderRadius: 14,
              color: "var(--paper)",
              maxWidth: 460,
              width: "100%",
              textAlign: "center",
              lineHeight: 1.45,
              boxShadow: "0 4px 18px rgba(0, 0, 0, 0.16)",
              marginTop: 10,
              animation: "os1FadeIn 220ms ease",
            }}
          >
            <div style={{ fontWeight: 500, fontSize: 14, marginBottom: 6, color: "var(--paper)" }}>System Notice</div>
            <div style={{ fontSize: 13, opacity: 0.95, wordBreak: "break-word" }}>{error}</div>
            <div style={{ display: "flex", gap: 10, justifyContent: "center", marginTop: 12 }}>
              <button
                type="button"
                onClick={onCleanAndRetry}
                style={{
                  fontSize: 12,
                  padding: "6px 18px",
                  borderRadius: 999,
                  background: "var(--paper)",
                  color: "var(--coral-deep)",
                  border: "none",
                  fontWeight: 500,
                  cursor: "pointer",
                  boxShadow: "0 2px 6px rgba(0, 0, 0, 0.12)",
                }}
              >
                Clean Caches &amp; Retry
              </button>
            </div>
          </div>
        )}
      </div>
      <div className="os1-mono os1-corner-bl">
        Audio · full-duplex ready
      </div>
      <div className="os1-mono os1-corner-br">
        Mic on · camera off
      </div>
    </>
  );
}

function Progress({ fraction, animate = false, seconds = 6 }: { fraction: number; animate?: boolean; seconds?: number }) {
  const [f, setF] = useState(fraction);
  useEffect(() => {
    if (!animate) return;
    const started = performance.now();
    let frame = 0;
    const tick = (t: number) => {
      setF(Math.min(1, fraction + ((t - started) / (seconds * 1000)) * (1 - fraction)));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [animate, fraction, seconds]);
  return (
    <div style={{ width: "min(240px, 78vw)", height: 1, background: "var(--on-coral-faint)", position: "relative" }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          width: `${f * 100}%`,
          background: "var(--paper)",
          boxShadow: "0 0 8px rgba(255,253,249,0.8)",
          height: 2,
          top: -0.5,
        }}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ 02 setup */

const SETUP_STEP: Partial<Record<Os1State["phase"], number>> = {
  operator_welcome: 1,
  operator_q1: 2,
  operator_q1_hesitance: 2,
  operator_q2: 3,
  operator_q3: 4,
};

export function Setup({ state, levels, onSay }: { state: Os1State; levels: Levels; onSay: (p: string) => void }) {
  const step = SETUP_STEP[state.phase] ?? 1;
  const presence = state.agentState === "speaking" ? "speaking" : "listening";
  return (
    <>
      <div className="os1-corner-tl" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {[1, 2, 3, 4, 5].map((i) => (
          <span
            key={i}
            style={{ width: "clamp(16px, 3.5vw, 28px)", height: 2, background: i <= step ? "var(--paper)" : "var(--on-coral-faint)" }}
          />
        ))}
        <span className="os1-label" style={{ fontSize: 11, marginLeft: 10, color: "var(--on-coral)" }}>
          Setup {step} / 5
        </span>
      </div>
      <div className="os1-screen-center">
        <Presence state={presence} getLevel={levelGetter(levels, presence)} size={320} />
        <SpokenLyricsView
          text={state.agentLine}
          isSpeaking={state.agentState === "speaking"}
        />
        <div className="os1-heard" style={{ minHeight: 22 }}>
          {state.userLine && `“${state.userLine}”`}
        </div>
        <SayChips chips={state.chips} onSay={onSay} />
      </div>
      <div className="os1-label os1-corner-bc" style={{ fontSize: 11 }}>
        {state.agentState === "speaking"
          ? (state.phase.startsWith("operator_") ? "● Operator is speaking" : `● ${state.agentName || "MAVE"} is speaking`)
          : state.speechWarning
          ? `● ${state.speechWarning}`
          : "● Listening — just speak"}
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ 03 waking */

export function Waking({ levels }: { levels: Levels }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [webglFailed, setWebglFailed] = useState(false);

  useEffect(() => {
    sound.wake();
    const canvas = canvasRef.current;
    if (!canvas) return;
    let loader: InfinityLoader | null = null;
    try {
      // ~5.5 s continuous helix → breathing ring morph, matching the ~6 s server initiation window.
      loader = new InfinityLoader(canvas, { mode: "waking", fixedSize: 340 });
      loader.start();
      loader.triggerTransition();
    } catch {
      setWebglFailed(true);
    }
    return () => {
      loader?.destroy();
    };
  }, []);

  return (
    <>
      <div className="os1-corner-tl" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {[1, 2, 3, 4, 5].map((i) => (
          <span
            key={i}
            style={{ width: "clamp(16px, 3.5vw, 28px)", height: 2, background: "var(--paper)" }}
          />
        ))}
        <span className="os1-label" style={{ fontSize: 11, marginLeft: 10, color: "var(--on-coral)" }}>
          Setup 5 / 5
        </span>
      </div>
      <div className="os1-screen-center os1-fade">
        {webglFailed ? (
          <Presence state="thinking" getLevel={() => levels.current.agent} size={340} />
        ) : (
          <canvas
            ref={canvasRef}
            aria-label="Initiating MAVE 1.0"
            style={{
              width: "min(340px, 85vw)",
              height: "min(340px, 85vw)",
              display: "block",
              marginTop: -28,
              marginBottom: -28,
            }}
          />
        )}
        <Progress fraction={0.1} animate />
        <p className="os1-lead" style={{ textAlign: "center", margin: 0, color: "var(--on-coral)" }}>
          Please wait while your operating system
          <br />
          becomes someone.
        </p>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ 04 conversation */

export function Conversation({
  state,
  levels,
  onSay,
}: {
  state: Os1State;
  levels: Levels;
  onSay: (p: string) => void;
}) {
  const presence = presenceFor(state.agentState, state.phase, state.work);
  const running = state.work.filter((w) => w.status === "running" || w.status === "waiting").length;
  const [clock, setClock] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setClock(new Date()), 15_000);
    return () => clearInterval(id);
  }, []);
  const statusWord = { asleep: "Asleep", listening: "Listening", thinking: "Thinking", speaking: "Speaking", working: "Working" }[
    presence
  ];
  return (
    <>
      <div className="os1-label os1-corner-tl" style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--paper)", flexShrink: 0 }} />
        <span style={{ color: "var(--on-coral)" }}>{state.agentName || "MAVE"}</span>
        <span>{statusWord}</span>
      </div>
      <div className="os1-label os1-corner-tr">
        {clock.toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" })}
      </div>
      <div className="os1-screen-center">
        <Presence state={presence} getLevel={levelGetter(levels, presence)} size={360} />
        <div className="os1-heard" style={{ minHeight: 22 }}>
          {state.userLine && `You — “${state.userLine}”`}
        </div>
        <SpokenLyricsView
          text={state.agentLine}
          isSpeaking={state.agentState === "speaking"}
        />
        <SayChips chips={state.chips} onSay={onSay} />
      </div>
      {running > 0 && (
        <div className="os1-label os1-corner-bl" style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span
            style={{
              width: 14,
              height: 14,
              borderRadius: "50%",
              border: "1.5px solid var(--on-coral-faint)",
              borderTopColor: "var(--paper)",
              flexShrink: 0,
            }}
          />
          {running} {running === 1 ? "thing" : "things"} in background
        </div>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ 05 naming */

export function Naming({ state, onSay }: { state: Os1State; onSay: (p: string) => void }) {
  return (
    <div className="os1-screen-center os1-fade" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
      {state.userLine && (
        <div className="os1-lead" style={{ color: "var(--on-coral-dim)", fontSize: "clamp(18px, 4vw, 26px)" }}>
          “{state.userLine}”
        </div>
      )}
      <div
        style={{
          font: "200 clamp(54px, 14vw, 140px)/1.0 var(--font-sans)",
          color: "var(--paper)",
          letterSpacing: "-0.02em",
          textAlign: "center",
          userSelect: "none",
        }}
      >
        MAVE<sup style={{ fontSize: "0.36em", verticalAlign: "top", marginLeft: 4 }}>1.0</sup>
      </div>

      <div style={{ marginTop: "clamp(24px, 5vh, 44px)" }}>
        <button
          type="button"
          onClick={() => onSay("Continue")}
          style={{
            padding: "12px 36px",
            borderRadius: 999,
            border: "none",
            background: "var(--paper)",
            color: "var(--coral-deep)",
            font: "400 16px/1 var(--font-sans)",
            cursor: "pointer",
            boxShadow: "0 2px 12px rgba(0, 0, 0, 0.08)",
            transition: "transform 140ms ease, opacity 140ms ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = "scale(1.04)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "scale(1)";
          }}
        >
          Continue
        </button>
      </div>
    </div>
  );
}
