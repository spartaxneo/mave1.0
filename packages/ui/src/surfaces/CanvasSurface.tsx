import { useEffect, useRef, useState } from "react";
import type { AudioSketchCard, CanvasState, Os1Card, SpeakableAction } from "../types";

/**
 * Paper 12 — Generative UI ("Made just now"): renders all 7 validated OS1 card types
 * with tactile warm paper styling and speakable phrases on every action.
 */
export function CanvasSurface({
  canvas,
  compact,
  onSay,
  onBack,
}: {
  canvas: CanvasState | null;
  compact?: boolean;
  onSay: (phrase: string) => void;
  onBack: () => void;
}) {
  const cards = canvas?.cards ?? [];
  return (
    <div className="os1-surface-container" style={{ gridTemplateRows: "auto 1fr" }}>
      <div className="os1-surface-header">
        <div>
          <div className="os1-label" style={{ color: "var(--on-coral-dim)" }}>
            12 · Made just now
          </div>
          <h2 className="os1-surface-title">
            {canvas?.title || "Made just now"}
          </h2>
          {canvas?.subtitle && (
            <div style={{ marginTop: 6, color: "var(--on-coral-dim)", font: "300 16px var(--font-sans)" }}>
              {canvas.subtitle}
            </div>
          )}
        </div>
        <button type="button" className="os1-pill" onClick={onBack}>
          Back to talking
        </button>
      </div>

      <div
        className="os1-scroll"
        style={{
          display: "grid",
          gridTemplateColumns: cards.length > 1 ? "repeat(auto-fit, minmax(min(100%, 340px), 1fr))" : "minmax(0, 760px)",
          justifyContent: "center",
          gap: 20,
          alignContent: "start",
        }}
      >
        {cards.length === 0 ? (
          <div className="os1-glass" style={{ padding: 36, textAlign: "center" }}>
            <p className="os1-lead" style={{ margin: 0 }}>
              Nothing laid out yet.
            </p>
            <p style={{ margin: "8px 0 0", color: "var(--on-coral-dim)" }}>
              When comparing choices, drafting a letter, or reviewing a plan, MAVE sketches cards here automatically.
            </p>
          </div>
        ) : (
          cards.map((card, i) => <CardRenderer key={`${card.id}-${i}`} card={card} compact={compact} onSay={onSay} />)
        )}
      </div>
    </div>
  );
}

function ActionRow({ actions, compact, onSay }: { actions: SpeakableAction[]; compact?: boolean; onSay: (p: string) => void }) {
  const visible = compact ? actions.slice(0, 2) : actions;
  return (
    <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 6 }}>
      {visible.map((act) => (
        <button
          key={act.speakablePhrase}
          type="button"
          className={`os1-pill-ink ${act.tone === "primary" ? "primary" : act.tone === "danger" ? "danger" : ""}`}
          onClick={() => onSay(act.speakablePhrase)}
        >
          “{act.speakablePhrase}”
        </button>
      ))}
    </div>
  );
}

function CardRenderer({ card, compact, onSay }: { card: Os1Card; compact?: boolean; onSay: (p: string) => void }) {
  switch (card.kind) {
    case "ComparisonCard":
      return (
        <div className="os1-paper-card" style={{ padding: 26, display: "grid", gap: 18 }}>
          <div>
            <div className="os1-mono" style={{ fontSize: 11, color: "var(--coral)" }}>
              Comparison
            </div>
            <h3 style={{ margin: "4px 0 0", font: "300 24px/1.2 var(--font-sans)" }}>{card.title}</h3>
            {card.subtitle && <p style={{ margin: "4px 0 0", color: "var(--ink-dim)", fontSize: 14 }}>{card.subtitle}</p>}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: `repeat(${card.options.length}, 1fr)`, gap: 14 }}>
            {card.options.map((opt) => (
              <div
                key={opt.title}
                style={{
                  padding: 16,
                  borderRadius: 16,
                  background: "rgba(237, 215, 189, 0.42)",
                  display: "grid",
                  gap: 10,
                  alignContent: "space-between",
                }}
              >
                <div>
                  <div style={{ font: "500 17px var(--font-sans)" }}>{opt.title}</div>
                  {opt.subtitle && <div style={{ fontSize: 13, color: "var(--ink-dim)", marginTop: 2 }}>{opt.subtitle}</div>}
                  {opt.meta && (
                    <div className="os1-mono" style={{ fontSize: 11, color: "var(--coral)", marginTop: 6 }}>
                      {opt.meta}
                    </div>
                  )}
                  {(opt.highlights ?? []).length > 0 && (
                    <ul style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 13, color: "var(--ink-dim)", lineHeight: 1.55 }}>
                      {(opt.highlights ?? []).map((h) => (
                        <li key={h}>{h}</li>
                      ))}
                    </ul>
                  )}
                </div>
                <button type="button" className="os1-pill-ink primary" onClick={() => onSay(opt.speakablePhrase)}>
                  “{opt.speakablePhrase}”
                </button>
              </div>
            ))}
          </div>
        </div>
      );

    case "ChoicePairCard":
      return (
        <div className="os1-paper-card" style={{ padding: "clamp(18px, 3.5vw, 28px)", display: "grid", gap: 18 }}>
          <div style={{ font: "300 24px/1.3 var(--font-sans)", textAlign: "center" }}>{card.prompt}</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 200px), 1fr))", gap: 14 }}>
            {[card.left, card.right].map((item) => (
              <button
                key={item.speakablePhrase}
                type="button"
                onClick={() => onSay(item.speakablePhrase)}
                style={{
                  padding: "24px 20px",
                  borderRadius: 18,
                  border: "1px solid var(--ink-faint)",
                  background: "rgba(237, 215, 189, 0.35)",
                  color: "var(--ink)",
                  cursor: "pointer",
                  textAlign: "left",
                  display: "grid",
                  gap: 8,
                }}
              >
                <div style={{ font: "300 28px/1.1 var(--font-sans)" }}>{item.title}</div>
                {item.detail && <div style={{ font: "300 14px var(--font-sans)", color: "var(--ink-dim)" }}>{item.detail}</div>}
                <div className="os1-mono" style={{ fontSize: 11, color: "var(--coral)", marginTop: 6 }}>
                  Say “{item.speakablePhrase}”
                </div>
              </button>
            ))}
          </div>
        </div>
      );

    case "QuickDecisionCard":
      return (
        <div className="os1-paper-card" style={{ padding: 26, display: "grid", gap: 14 }}>
          {card.eyebrow && (
            <div className="os1-mono" style={{ fontSize: 11, color: "var(--coral)" }}>
              {card.eyebrow}
            </div>
          )}
          <h3 style={{ margin: 0, font: "300 26px/1.25 var(--font-sans)" }}>{card.title}</h3>
          {card.body && <p style={{ margin: 0, font: "300 16px/1.55 var(--font-sans)", color: "var(--ink-dim)" }}>{card.body}</p>}
          <ActionRow actions={card.actions} compact={compact} onSay={onSay} />
        </div>
      );

    case "ReadbackConfirmCard":
      return (
        <div
          className="os1-paper-card"
          style={{
            padding: 26,
            display: "grid",
            gap: 16,
            border: card.stakes === "money" || card.stakes === "forget" ? "2px solid var(--crimson)" : undefined,
          }}
        >
          <div className="os1-mono" style={{ fontSize: 11, color: "var(--crimson)" }}>
            Read-back confirmation · {card.stakes}
          </div>
          <h3 style={{ margin: 0, font: "400 24px/1.25 var(--font-sans)" }}>{card.title}</h3>
          <div style={{ display: "grid", gap: 8, padding: 14, borderRadius: 14, background: "rgba(56,40,30,0.05)" }}>
            {card.summaryLines.map((line) => (
              <div key={line} style={{ font: "400 15px/1.4 var(--font-sans)" }}>
                {line}
              </div>
            ))}
          </div>
          <ActionRow actions={[card.confirmAction, card.cancelAction]} onSay={onSay} />
        </div>
      );

    case "DraftPreviewCard":
      return (
        <div className="os1-paper-card" style={{ padding: 26, display: "grid", gap: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span className="os1-mono" style={{ fontSize: 11, color: "var(--coral)" }}>
              Draft · To {card.recipient}
            </span>
          </div>
          {card.subject && <div style={{ font: "500 18px var(--font-sans)" }}>{card.subject}</div>}
          <div
            style={{
              padding: 18,
              borderRadius: 14,
              background: "rgba(237, 215, 189, 0.34)",
              font: "300 16px/1.65 var(--font-sans)",
              whiteSpace: "pre-wrap",
            }}
          >
            {card.body}
          </div>
          <ActionRow actions={card.actions} compact={compact} onSay={onSay} />
        </div>
      );

    case "TimelineCard":
      return (
        <div className="os1-paper-card" style={{ padding: 26, display: "grid", gap: 16 }}>
          <h3 style={{ margin: 0, font: "300 24px var(--font-sans)" }}>{card.title}</h3>
          <div style={{ display: "grid", gap: 12 }}>
            {card.steps.map((step) => (
              <div
                key={`${step.time}-${step.title}`}
                style={{
                  display: "grid",
                  gridTemplateColumns: "78px 1fr",
                  gap: 14,
                  alignItems: "baseline",
                  paddingLeft: 12,
                  borderLeft: `2px solid ${step.status === "now" ? "var(--coral)" : step.status === "done" ? "var(--sage)" : "var(--ink-faint)"}`,
                }}
              >
                <span className="os1-mono" style={{ fontSize: 12, color: "var(--coral)" }}>
                  {step.time}
                </span>
                <div>
                  <div style={{ font: "500 15px var(--font-sans)" }}>{step.title}</div>
                  {step.detail && <div style={{ fontSize: 13, color: "var(--ink-dim)", marginTop: 2 }}>{step.detail}</div>}
                </div>
              </div>
            ))}
          </div>
          {card.actions && card.actions.length > 0 && <ActionRow actions={card.actions} compact={compact} onSay={onSay} />}
        </div>
      );

    case "AudioSketchCard":
      return <AudioSketchRenderer card={card} compact={compact} onSay={onSay} />;
  }
}

function playPianoSketch(): () => void {
  const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  if (!AudioCtx) return () => {};
  const ctx = new AudioCtx();

  // Gentle warm piano progression (Fmaj7 -> Am7 -> Cmaj7 -> G)
  const chords: { time: number; notes: number[] }[] = [
    { time: 0.1, notes: [174.61, 261.63, 329.63, 440.0] },
    { time: 2.2, notes: [110.0, 164.81, 220.0, 261.63, 329.63] },
    { time: 4.4, notes: [130.81, 196.0, 246.94, 329.63] },
    { time: 6.6, notes: [98.0, 146.83, 196.0, 246.94, 293.66] },
    { time: 8.8, notes: [174.61, 220.0, 261.63, 329.63, 440.0] },
  ];

  const master = ctx.createGain();
  master.gain.setValueAtTime(0.32, ctx.currentTime);
  master.connect(ctx.destination);

  chords.forEach(({ time, notes }) => {
    notes.forEach((freq, noteIdx) => {
      const noteTime = ctx.currentTime + time + noteIdx * 0.04;
      const osc = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "triangle";
      osc.frequency.setValueAtTime(freq, noteTime);

      osc2.type = "sine";
      osc2.frequency.setValueAtTime(freq * 2, noteTime);

      gain.gain.setValueAtTime(0.0001, noteTime);
      gain.gain.linearRampToValueAtTime(0.22 / Math.sqrt(notes.length), noteTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, noteTime + 2.6);

      osc.connect(gain);
      osc2.connect(gain);
      gain.connect(master);

      osc.start(noteTime);
      osc2.start(noteTime);
      osc.stop(noteTime + 2.8);
      osc2.stop(noteTime + 2.8);
    });
  });

  return () => {
    try {
      master.gain.linearRampToValueAtTime(0.0001, ctx.currentTime + 0.08);
      setTimeout(() => ctx.close(), 100);
    } catch {}
  };
}

function AudioSketchRenderer({
  card,
  compact,
  onSay,
}: {
  card: AudioSketchCard;
  compact?: boolean;
  onSay: (p: string) => void;
}) {
  const [playing, setPlaying] = useState(false);
  const stopRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => {
      stopRef.current?.();
    };
  }, []);

  const togglePlay = () => {
    if (playing) {
      stopRef.current?.();
      stopRef.current = null;
      setPlaying(false);
    } else {
      setPlaying(true);
      const stop = playPianoSketch();
      stopRef.current = stop;
      // Piano sketch runs ~11 seconds
      setTimeout(() => {
        setPlaying(false);
        stopRef.current = null;
      }, 11500);
    }
  };

  const handleAction = (act: SpeakableAction) => {
    if (/play|listen/i.test(act.speakablePhrase) || /play|listen/i.test(act.label)) {
      togglePlay();
    }
    onSay(act.speakablePhrase);
  };

  const bars = card.bars ?? [
    0.28, 0.45, 0.72, 0.54, 0.88, 0.64, 0.94, 0.5, 0.76, 0.42, 0.84, 0.62, 0.92, 0.48, 0.7, 0.55, 0.82,
    0.38, 0.66, 0.44, 0.58, 0.34, 0.48, 0.25,
  ];

  return (
    <div className="os1-studio-card" style={{ padding: 26, display: "grid", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div>
          <div className="os1-mono" style={{ fontSize: 11, color: "var(--coral)" }}>
            Audio sketch {card.mood ? `· ${card.mood}` : ""}
          </div>
          <h3 style={{ margin: "4px 0 0", font: "300 24px var(--font-sans)" }}>{card.title}</h3>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            type="button"
            className="os1-pill-ink primary"
            style={{ fontSize: 12, padding: "4px 10px", display: "inline-flex", alignItems: "center", gap: 4 }}
            onClick={togglePlay}
          >
            {playing ? "❚❚ Pause" : "▶ Play"}
          </button>
          <span className="os1-mono" style={{ color: "var(--ink-dim)" }}>
            {card.duration || "0:42"}
          </span>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 5, height: 56 }}>
        {bars.map((h: number, i: number) => (
          <span
            key={i}
            style={{
              flex: "0 0 5px",
              height: `${Math.max(16, Math.round((playing ? (h * (0.6 + 0.4 * Math.sin(Date.now() / 150 + i))) : h) * 100))}%`,
              borderRadius: 999,
              background: playing ? "var(--coral)" : i % 4 === 0 ? "var(--coral)" : "rgba(56,40,30,0.28)",
              transition: "height 0.2s ease, background 0.3s ease",
            }}
          />
        ))}
      </div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 6 }}>
        {(compact ? card.actions.slice(0, 2) : card.actions).map((act: SpeakableAction) => (
          <button
            key={act.speakablePhrase}
            type="button"
            className={`os1-pill-ink ${act.tone === "primary" ? "primary" : act.tone === "danger" ? "danger" : ""}`}
            onClick={() => handleAction(act)}
          >
            “{act.speakablePhrase}”
          </button>
        ))}
      </div>
    </div>
  );
}
