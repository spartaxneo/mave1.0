import { useEffect, useRef } from "react";

/** Presence states from the component kit (Paper S1 · 01). */
export type PresenceState = "asleep" | "listening" | "thinking" | "speaking" | "working";

interface Props {
  state: PresenceState;
  /** 0..1, sampled every frame: her voice while speaking, the user's while listening. */
  getLevel: () => number;
  /** Ribbon width in px. */
  size?: number;
}

const FIBERS = 9;

/**
 * Her presence: a ring when listening/asleep, a three-lobe ribbon of fine fibers with
 * pointed ends when thinking/speaking, an arc while working elsewhere.
 * Drawn on canvas so amplitude can follow audio at 60 fps without React re-renders.
 */
export function Presence({ state, getLevel, size = 440 }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const levelRef = useRef(getLevel);
  const stateRef = useRef(state);
  levelRef.current = getLevel;
  stateRef.current = state;

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const ctx = el.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const w = size;
    // Expansive vertical headroom (0.85) gives the living ribbon full space to animate, undulate, and flow without any clipping
    const h = size * 0.85;
    el.width = w * dpr;
    el.height = h * dpr;
    ctx.scale(dpr, dpr);

    let frame = 0;
    let smooth = 0;
    let ribbon = 0; // 0 = ring, 1 = ribbon (morph)
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const draw = (t: number) => {
      const s = stateRef.current;
      const rawLevel = levelRef.current();
      // Continuous organic vocal/presence breathing so the ribbon always moves with silky fluidity
      const naturalBreathing = 0.09 + 0.05 * Math.sin((t / 1000) * 2.2) + 0.03 * Math.cos((t / 1000) * 3.7);
      const voiceMod =
        rawLevel > 0.04
          ? rawLevel
          : s === "speaking"
            ? 0.38 + 0.22 * Math.sin((t / 1000) * 9.2) + 0.14 * Math.cos((t / 1000) * 15.7) + 0.08 * Math.sin((t / 1000) * 23.4)
            : naturalBreathing;

      smooth += (Math.min(1, voiceMod * 2.2) - smooth) * 0.18;
      // The ribbon represents Samantha's living consciousness — active whenever awake
      const wantRibbon = s === "asleep" ? 0 : 1;
      ribbon += (wantRibbon - ribbon) * 0.08;
      ctx.clearRect(0, 0, w, h);
      ctx.lineCap = "round";
      const cx = w / 2;
      const cy = h / 2;
      // Continuous smooth time progression
      const time = t / 950;

      if (ribbon < 0.98) {
        // Ring (asleep)
        const alpha = (1 - ribbon) * (s === "asleep" ? 0.45 : 1);
        const breathe = 1 + Math.sin(time * 1.2) * 0.02;
        const r = h * 0.3 * breathe;
        ctx.save();
        ctx.globalAlpha = alpha;
        ctx.strokeStyle = "#fffdf9";
        ctx.lineWidth = 1.6;
        ctx.shadowColor = "rgba(255,253,249,0.85)";
        ctx.shadowBlur = 10;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }

      if (ribbon > 0.02) {
        // Ribbon: three-lobe living ribbon with pointed ends
        const span = w * (s === "thinking" ? 0.6 : s === "listening" ? 0.78 : 0.84);
        // Calibrated amplitude: silky, graceful motion that breathes dynamically with ample breathing space
        const amp = h * (s === "thinking" ? 0.11 : s === "listening" ? 0.13 + naturalBreathing * 0.05 : 0.15 + smooth * 0.13);
        const phase = time * (s === "speaking" ? 2.8 : s === "thinking" ? 1.4 : 2.0);
        const maxExcursion = h * 0.35; // Guarantee at least 15% clearance from top and bottom boundaries

        ctx.save();
        ctx.globalAlpha = ribbon;
        ctx.strokeStyle = "#fffdf9";
        for (let f = 0; f < FIBERS; f++) {
          const jitter = (f - FIBERS / 2) / FIBERS;
          for (const sign of [1, -1]) {
            ctx.beginPath();
            ctx.lineWidth = f === Math.floor(FIBERS / 2) ? 1.8 : 0.75;
            ctx.globalAlpha = ribbon * (0.35 + 0.65 * (1 - Math.abs(jitter) * 1.6));
            for (let i = 0; i <= 120; i++) {
              const u = i / 120;
              const x = cx - span / 2 + u * span;
              const envelope = Math.pow(Math.sin(Math.PI * u), 0.72);
              const wobble = 1 + jitter * 0.22 * Math.sin(time * 1.8 + f * 0.8);
              const wave =
                Math.sin(3 * Math.PI * u - phase + jitter * 0.25) +
                0.12 * Math.sin(6 * Math.PI * u - phase * 1.4 + f * 0.5);
              const rawDy = sign * amp * wobble * envelope * wave;
              // Smooth hyperbolic tangent soft-limiting: strictly prevents clipping while retaining 100% natural fluidity
              const dy = Math.tanh(rawDy / maxExcursion) * maxExcursion;
              const y = cy + dy;
              if (i === 0) ctx.moveTo(x, y);
              else ctx.lineTo(x, y);
            }
            ctx.stroke();
          }
        }
        ctx.restore();
      }
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [size]);

  return (
    <canvas
      ref={canvas}
      role="img"
      aria-label={`MAVE is ${state}`}
      style={{
        width: "100%",
        maxWidth: size,
        height: "auto",
        aspectRatio: "100 / 85",
        display: "block",
      }}
    />
  );
}
