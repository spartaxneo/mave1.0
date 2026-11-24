import { useState } from "react";
import { Presence, type PresenceState } from "../components/Presence";
import { SayChips } from "../components/SayChips";
import type { ActiveSurface, MoodState, WorkItem } from "../types";

type Levels = { current: { agent: number; user: number } };

const SHAPE_COLORS = ["#fffdf9", "#edd7bd", "#d9a53a", "#8fa88f", "#4a78c8", "#8a5866"];

/**
 * Paper 06 — Desktop Home: calm coral horizon with softly drifting translucent shapes,
 * one per active background run. Never cluttered; voice stays front and center.
 */
export function HomeSurface({
  runs,
  mood,
  presence,
  levels,
  onOpenSurface,
  onSay,
}: {
  runs: WorkItem[];
  mood: MoodState;
  presence: PresenceState;
  levels: Levels;
  onOpenSurface: (s: ActiveSurface) => void;
  onSay: (phrase: string) => void;
}) {
  const activeRuns = runs.filter((r) => r.status === "running" || r.status === "waiting");
  return (
    <div style={{ position: "fixed", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "clamp(54px, 8vh, 72px) clamp(16px, 4vw, 56px) clamp(72px, 11vh, 96px)", overflowY: "auto", boxSizing: "border-box" }}>
      {/* Soft warm horizon band */}
      <div
        style={{
          position: "fixed",
          left: 0,
          right: 0,
          top: "56%",
          height: 1,
          background: "linear-gradient(90deg, transparent 5%, rgba(255,253,249,0.22) 50%, transparent 95%)",
          pointerEvents: "none",
        }}
      />

      {/* Top corners */}
      <div className="os1-label os1-corner-tl" style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--paper)", flexShrink: 0 }} />
        <span>MAVE</span>
        <span style={{ color: "var(--on-coral-dim)" }}>
          {activeRuns.length > 0 ? `${activeRuns.length} running` : "Calm horizon"}
        </span>
      </div>
      <div className="os1-mono os1-corner-tr" style={{ color: "var(--on-coral-dim)" }}>
        Warmth {Math.round(mood.warmth * 100)}%
      </div>

      {/* Floating translucent shapes representing active work */}
      <div
        style={{
          position: "relative",
          width: "100%",
          maxWidth: 1080,
          display: "grid",
          justifyItems: "center",
          gap: 32,
        }}
      >
        <Presence
          state={presence}
          getLevel={presence === "speaking" ? () => levels.current.agent : () => levels.current.user}
          size={340}
        />

        {activeRuns.length > 0 ? (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              justifyContent: "center",
              gap: 20,
              maxWidth: 920,
            }}
          >
            {activeRuns.map((run, idx) => {
              const accent = SHAPE_COLORS[idx % SHAPE_COLORS.length];
              const isCircle = idx % 2 === 0;
              return (
                <button
                  key={run.id}
                  type="button"
                  onClick={() => onOpenSurface("swarm")}
                  className="os1-glass"
                  style={{
                    padding: "clamp(12px, 2.5vw, 16px) clamp(14px, 3vw, 22px)",
                    borderRadius: isCircle ? 999 : 24,
                    display: "flex",
                    alignItems: "center",
                    gap: 14,
                    cursor: "pointer",
                    animation: `os1-float ${4.2 + idx * 0.7}s ease-in-out infinite`,
                    textAlign: "left",
                    maxWidth: "100%",
                    boxSizing: "border-box",
                  }}
                >
                  <span
                    style={{
                      width: 12,
                      height: 12,
                      borderRadius: isCircle ? "50%" : 3,
                      background: accent,
                      boxShadow: `0 0 12px ${accent}`,
                      flexShrink: 0,
                    }}
                  />
                  <div>
                    <div style={{ font: "400 15px/1.25 var(--font-sans)", color: "var(--paper)" }}>{run.label}</div>
                    <div className="os1-mono" style={{ fontSize: 10, color: "var(--on-coral-dim)", marginTop: 3 }}>
                      {run.status === "waiting" ? "Needs your okay" : "Working in background"}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <p className="os1-lead" style={{ margin: 0, color: "var(--on-coral-dim)", textAlign: "center" }}>
            Everything is quiet. Just speak whenever you're ready.
          </p>
        )}

        <SayChips
          chips={
            mood.compactMode
              ? ["Show me my inbox", "Just talk"]
              : ["Show me my inbox", "Show me your computer", "Show me what you remember", "Just talk"]
          }
          onSay={onSay}
        />
      </div>
    </div>
  );
}

/**
 * Paper 11 — Swarm ("Many of her"): each parallel background agent run rendered as an orbital floating card
 * with live progress, real logs, result details, and speakable control chips.
 */
export function SwarmSurface({
  runs,
  onSay,
  onBack,
  onStartRun,
  onStopRun,
  onClearDone,
  onDeleteRun,
}: {
  runs: WorkItem[];
  onSay: (phrase: string) => void;
  onBack: () => void;
  onStartRun?: (label: string) => Promise<void> | void;
  onStopRun?: (runId: string) => Promise<void> | void;
  onClearDone?: () => Promise<void> | void;
  onDeleteRun?: (runId: string) => Promise<void> | void;
}) {
  const [expandedLogs, setExpandedLogs] = useState<Record<string, boolean>>({});
  const [taskInput, setTaskInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const activeCount = runs.filter((r) => r.status === "running" || r.status === "waiting").length;
  const doneCount = runs.filter((r) => r.status === "done" || r.status === "cancelled").length;

  const handleCreateTask = async (labelToStart?: string) => {
    const text = (labelToStart ?? taskInput).trim();
    if (!text || isSubmitting) return;
    setIsSubmitting(true);
    try {
      if (onStartRun) {
        await onStartRun(text);
      } else {
        onSay(`Can you ${text} in the background?`);
      }
      setTaskInput("");
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleLogs = (runId: string) => {
    setExpandedLogs((prev) => ({ ...prev, [runId]: !prev[runId] }));
  };

  return (
    <div className="os1-surface-container">
      <div className="os1-surface-header" style={{ flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="os1-label" style={{ color: "var(--on-coral-dim)" }}>
            11 · Swarm
          </div>
          <h2 className="os1-surface-title">
            Many of her{" "}
            <span style={{ fontSize: 14, fontWeight: 400, opacity: 0.65 }}>
              ({activeCount} running{doneCount > 0 ? `, ${doneCount} completed` : ""})
            </span>
          </h2>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {doneCount > 0 && (
            <button
              type="button"
              className="os1-pill"
              onClick={() => {
                if (onClearDone) void onClearDone();
                else onSay("Clear finished tasks");
              }}
            >
              Clear finished ({doneCount})
            </button>
          )}
          <button type="button" className="os1-pill" onClick={onBack}>
            Back to talking
          </button>
        </div>
      </div>

      {/* Quick Task Dispatch Bar */}
      <div
        className="os1-glass"
        style={{
          padding: "14px 18px",
          borderRadius: 16,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void handleCreateTask();
          }}
          style={{ display: "flex", gap: 10, alignItems: "center" }}
        >
          <input
            type="text"
            className="os1-input"
            value={taskInput}
            onChange={(e) => setTaskInput(e.target.value)}
            placeholder="Ask MAVE to research, clean up, or inspect something in the background..."
            style={{
              flex: 1,
              padding: "10px 14px",
              borderRadius: 10,
              border: "1px solid rgba(255, 253, 249, 0.25)",
              background: "rgba(255, 253, 249, 0.12)",
              color: "var(--paper)",
              font: "400 14px var(--font-sans)",
              outline: "none",
            }}
          />
          <button
            type="submit"
            className="os1-pill-ink primary"
            disabled={!taskInput.trim() || isSubmitting}
            style={{ whiteSpace: "nowrap", opacity: !taskInput.trim() || isSubmitting ? 0.6 : 1 }}
          >
            + Start background run
          </button>
        </form>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <span className="os1-mono" style={{ fontSize: 10, color: "var(--on-coral-dim)" }}>
            Quick start:
          </span>
          {[
            "Compare ferries to Sausalito",
            "Clean up inbox newsletters",
            "Check SF weather & bay tide",
            "Audit Mac system health",
          ].map((prompt) => (
            <button
              key={prompt}
              type="button"
              className="os1-pill"
              style={{ fontSize: 12, padding: "4px 10px" }}
              onClick={() => void handleCreateTask(prompt)}
            >
              + {prompt}
            </button>
          ))}
        </div>
      </div>

      {/* Grid of Active and Completed Runs */}
      <div
        className="os1-scroll"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(clamp(280px, 100%, 360px), 1fr))",
          gap: 18,
          alignContent: "start",
        }}
      >
        {runs.length === 0 ? (
          <div className="os1-glass" style={{ padding: 36, gridColumn: "1 / -1", textAlign: "center" }}>
            <p className="os1-lead" style={{ margin: 0, color: "var(--on-coral-dim)" }}>
              No background runs right now. Ask MAVE to look into something above and it will orbit here.
            </p>
          </div>
        ) : (
          runs.map((run, idx) => {
            const running = run.status === "running";
            const waiting = run.status === "waiting";
            const done = run.status === "done";
            const cancelled = run.status === "cancelled";
            const showLogs = Boolean(expandedLogs[run.id]);

            return (
              <div
                key={run.id}
                className="os1-paper-card"
                style={{
                  padding: 22,
                  display: "grid",
                  gap: 14,
                  animation: running ? `os1-float ${4.5 + (idx % 3) * 0.8}s ease-in-out infinite` : undefined,
                  border: waiting ? "1.5px solid var(--crimson)" : undefined,
                }}
              >
                {/* Header status */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
                  <span
                    className="os1-mono"
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: waiting ? "var(--crimson)" : running ? "var(--coral)" : done ? "var(--sage)" : "var(--ink-dim)",
                    }}
                  >
                    ● {run.status.toUpperCase()}
                  </span>
                  <span className="os1-mono" style={{ fontSize: 10, color: "var(--ink-dim)" }}>
                    {run.id}
                  </span>
                </div>

                {/* Title */}
                <div style={{ font: "500 18px/1.3 var(--font-sans)", color: "var(--ink)" }}>{run.label}</div>

                {/* Live progress and stage if running */}
                {running && (
                  <div style={{ display: "grid", gap: 6 }}>
                    <div
                      style={{
                        height: 5,
                        background: "rgba(56, 40, 30, 0.08)",
                        borderRadius: 3,
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          height: "100%",
                          width: `${Math.max(12, Math.min(100, run.progress ?? 45))}%`,
                          background: "var(--coral)",
                          borderRadius: 3,
                          transition: "width 0.4s ease-in-out",
                        }}
                      />
                    </div>
                    {run.stage && (
                      <div className="os1-mono" style={{ fontSize: 11, color: "var(--coral)" }}>
                        {run.stage}
                      </div>
                    )}
                  </div>
                )}

                {/* Result box if done */}
                {done && run.result && (
                  <div
                    style={{
                      font: "400 13px/1.45 var(--font-sans)",
                      color: "var(--ink)",
                      background: "rgba(143, 168, 143, 0.14)",
                      border: "1px solid rgba(143, 168, 143, 0.3)",
                      padding: "10px 14px",
                      borderRadius: 10,
                    }}
                  >
                    <div className="os1-mono" style={{ fontSize: 9, color: "var(--sage)", marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 }}>
                      Result
                    </div>
                    {run.result}
                  </div>
                )}

                {/* Cancelled notice */}
                {cancelled && (
                  <div className="os1-mono" style={{ fontSize: 11, color: "var(--ink-dim)", fontStyle: "italic" }}>
                    Stopped by user.
                  </div>
                )}

                {/* Live logs toggle & drawer */}
                {run.logs && run.logs.length > 0 && (
                  <div>
                    <button
                      type="button"
                      onClick={() => toggleLogs(run.id)}
                      style={{
                        background: "none",
                        border: "none",
                        color: "var(--coral)",
                        font: "500 12px var(--font-sans)",
                        cursor: "pointer",
                        padding: 0,
                      }}
                    >
                      {showLogs ? "Hide live logs ▲" : `View live logs (${run.logs.length}) ▼`}
                    </button>
                    {showLogs && (
                      <div
                        className="os1-mono"
                        style={{
                          fontSize: 10,
                          background: "rgba(56, 40, 30, 0.04)",
                          border: "1px solid rgba(56, 40, 30, 0.08)",
                          padding: 10,
                          borderRadius: 8,
                          marginTop: 8,
                          maxHeight: 140,
                          overflowY: "auto",
                          display: "grid",
                          gap: 4,
                          lineHeight: 1.4,
                        }}
                      >
                        {run.logs.map((line, logIdx) => (
                          <div key={logIdx} style={{ color: "var(--ink-dim)" }}>
                            {line}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Action buttons */}
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4 }}>
                  <button
                    type="button"
                    className="os1-pill-ink"
                    onClick={() => onSay(`How is ${run.label} going?`)}
                  >
                    “How's it going?”
                  </button>
                  {(running || waiting) && (
                    <button
                      type="button"
                      className="os1-pill-ink danger"
                      onClick={() => {
                        if (onStopRun) {
                          void onStopRun(run.id);
                        } else {
                          onSay(`Stop ${run.label}`);
                        }
                      }}
                    >
                      “Stop it”
                    </button>
                  )}
                  {(done || cancelled) && (
                    <button
                      type="button"
                      className="os1-pill-ink"
                      style={{ opacity: 0.7 }}
                      onClick={() => {
                        if (onDeleteRun) {
                          void onDeleteRun(run.id);
                        } else {
                          onSay("Clear finished tasks");
                        }
                      }}
                    >
                      Dismiss
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      <div style={{ display: "flex", justifyContent: "center" }}>
        <SayChips chips={["How's it going?", "Show me your computer", "Back to talking"]} onSay={onSay} />
      </div>
    </div>
  );
}
