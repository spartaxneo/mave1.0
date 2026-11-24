import { useEffect, useRef } from "react";
import { InfinityLoader } from "../components/InfinityLoader";
import { sound } from "../sound";

// Optional local boot audio: bundled when present locally, gracefully falls back to synthesized sound.boot() in public builds.
const _localBootAudio = import.meta.glob<string>("../assets/init_sound.{mp3,m4a,wav}", { eager: true, import: "default" });
const initSoundUrl: string | null = Object.values(_localBootAudio)[0] ?? null;

/**
 * OS1 Startup Sequence — continuous 3D infinity-helix → ring WebGL animation
 * driven directly by `init_sound.m4a` / `init_sound.mp3` (14.2 s) via WebAudio
 * `AudioBufferSourceNode` + live `AnalyserNode` energy so visuals and sound stay sample-locked:
 *   -0.90–0.00 s  coral field warms up; 3D infinity helix emerges and spins calmly
 *    0.00–5.20 s  accelerating pulses; gossamer echo filament trails the ribbon
 *    5.20–10.75 s 90° turn into depth + continuous parametric morph ∞ → O (zero swap)
 *   10.75–12.15 s locked radiant ring breathes across the resolving chord climax
 *   12.15–13.38 s graceful contraction to a warm point of light + silky dissolve
 *   13.38–14.20 s awaits `init_sound.m4a`'s natural reverb tail before handoff
 *
 * Press Escape to skip.
 */
const HELIX_START_MS = 180;
const PRE_ROLL_MS = 1350;
const SAFETY_TIMEOUT_MS = 22_000;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function StartupSequence({ onDone }: { onDone: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const auraRef = useRef<HTMLDivElement>(null);
  const veilRef = useRef<HTMLDivElement>(null);
  const markRef = useRef<HTMLDivElement>(null);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    let cancelled = false;
    let finished = false;
    let audioCtx: AudioContext | null = null;
    let bufferSource: AudioBufferSourceNode | null = null;
    let gainNode: GainNode | null = null;
    let analyser: AnalyserNode | null = null;
    let freqBuf: Uint8Array<ArrayBuffer> | null = null;
    let audioStartTime: number | null = null;
    let audioPlaying = false;
    let loader: InfinityLoader | null = null;

    if (sound.muted) {
      sound.muted = false;
    }

    const cleanupAudio = () => {
      audioPlaying = false;
      if (bufferSource) {
        try {
          bufferSource.stop();
          bufferSource.disconnect();
        } catch {
          /* ignore */
        }
        bufferSource = null;
      }
      if (audioCtx) {
        void audioCtx.close().catch(() => undefined);
        audioCtx = null;
      }
      analyser = null;
      freqBuf = null;
      gainNode = null;
    };

    const finish = () => {
      if (finished) return;
      finished = true;
      cancelled = true;
      cleanupAudio();
      loader?.destroy();
      loader = null;
      onDoneRef.current();
    };

    let resolveAudioEnded!: () => void;
    const audioEnded = new Promise<void>((resolve) => {
      resolveAudioEnded = resolve;
    });

    // Start pre-decoding audio immediately on mount so it's ready by the end of pre-roll
    const preparedAudioPromise = (async (): Promise<AudioBuffer | null> => {
      if (!initSoundUrl) return null;
      try {
        const resp = await fetch(initSoundUrl);
        const arrayBuf = await resp.arrayBuffer();
        if (cancelled) return null;
        const tempCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
        const decoded = await tempCtx.decodeAudioData(arrayBuf);
        void tempCtx.close().catch(() => undefined);
        return decoded;
      } catch {
        return null;
      }
    })();

    const unlockAudio = () => {
      if (audioCtx && audioCtx.state === "suspended") {
        void audioCtx.resume().then(() => {
          if (audioStartTime === null && audioCtx) {
            audioStartTime = audioCtx.currentTime;
          }
        });
      }
    };
    window.addEventListener("pointerdown", unlockAudio, { passive: true });
    window.addEventListener("keydown", unlockAudio, { passive: true });
    window.addEventListener("click", unlockAudio, { passive: true });
    window.addEventListener("touchstart", unlockAudio, { passive: true });

    const unsubMute = sound.onMuteChange((muted) => {
      if (gainNode) gainNode.gain.value = muted ? 0 : 1;
    });

    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "m") return;
      if (e.key === "Escape") {
        finish();
      }
    };
    window.addEventListener("keydown", onKeyDown);

    const safetyTimer = window.setTimeout(finish, SAFETY_TIMEOUT_MS);

    requestAnimationFrame(() => {
      if (veilRef.current) veilRef.current.style.opacity = "0";
    });

    const getAudioTime = (): number | null => {
      if (!audioCtx || !audioPlaying || audioCtx.state !== "running" || audioStartTime === null) return null;
      return Math.max(0, audioCtx.currentTime - audioStartTime);
    };

    const getAudioEnergy = (): number => {
      if (!analyser || !freqBuf || !audioPlaying || sound.muted || audioCtx?.state !== "running") return 0;
      analyser.getByteFrequencyData(freqBuf);
      let sum = 0;
      const start = 2;
      const end = Math.min(48, freqBuf.length);
      for (let i = start; i < end; i++) sum += freqBuf[i];
      return Math.min(1, sum / ((end - start) * 185));
    };

    const run = async () => {
      const canvas = canvasRef.current;
      if (!canvas) {
        finish();
        return;
      }

      try {
        loader = new InfinityLoader(canvas, {
          mode: "startup",
          getAudioTime,
          getAudioEnergy,
          onGlowChange: (intensity) => {
            if (!auraRef.current) return;
            auraRef.current.style.opacity = String(0.18 + intensity * 0.65);
            auraRef.current.style.transform = `scale(${0.86 + intensity * 0.34})`;
          },
        });
      } catch {
        finish();
        return;
      }

      loader.onRingLocked = () => {
        if (!markRef.current) return;
        window.setTimeout(() => {
          if (cancelled || !markRef.current) return;
          markRef.current.style.transition = "opacity 650ms ease";
          markRef.current.style.opacity = "0";
        }, 550);
      };

      const visualComplete = new Promise<void>((resolve) => {
        if (loader) loader.onComplete = resolve;
      });

      await delay(HELIX_START_MS);
      if (cancelled || !loader) return;

      loader.start();
      if (markRef.current) markRef.current.style.opacity = "0.74";

      await delay(PRE_ROLL_MS);
      if (cancelled || !loader) return;

      // Audio playback setup
      try {
        audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
        gainNode = audioCtx.createGain();
        gainNode.gain.value = sound.muted ? 0 : 1;
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.78;
        freqBuf = new Uint8Array(new ArrayBuffer(analyser.frequencyBinCount));

        gainNode.connect(analyser);
        analyser.connect(audioCtx.destination);

        const preloadedBuffer = await preparedAudioPromise;
        if (cancelled || !audioCtx) return;

        if (preloadedBuffer) {
          bufferSource = audioCtx.createBufferSource();
          bufferSource.buffer = preloadedBuffer;
          bufferSource.connect(gainNode);

          bufferSource.onended = () => {
            audioPlaying = false;
            resolveAudioEnded();
          };

          void audioCtx.resume().catch(() => undefined);
          bufferSource.start(0);
          audioStartTime = audioCtx.currentTime;
          audioPlaying = true;
        } else {
          sound.boot();
          resolveAudioEnded();
        }
      } catch {
        // Safe fallback to WebAudio synthesized boot sound
        sound.boot();
        resolveAudioEnded();
      }

      if (cancelled || !loader) return;
      loader.triggerTransition();

      await Promise.all([visualComplete, audioEnded]);
      if (cancelled) return;

      finish();
    };

    void run();

    return () => {
      cancelled = true;
      window.clearTimeout(safetyTimer);
      unsubMute();
      window.removeEventListener("pointerdown", unlockAudio);
      window.removeEventListener("keydown", unlockAudio);
      window.removeEventListener("click", unlockAudio);
      window.removeEventListener("touchstart", unlockAudio);
      window.removeEventListener("keydown", onKeyDown);
      cleanupAudio();
      loader?.destroy();
      loader = null;
    };
  }, []);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Subtle sunlit warm coral bloom behind the 3D filament */}
      <div
        ref={auraRef}
        style={{
          position: "fixed",
          width: "min(62vw, 680px)",
          height: "min(62vw, 680px)",
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(255, 224, 198, 0.34) 0%, rgba(236, 126, 92, 0.16) 38%, transparent 70%)",
          opacity: 0.18,
          transform: "scale(0.86)",
          pointerEvents: "none",
          willChange: "transform, opacity",
        }}
      />
      <canvas
        ref={canvasRef}
        style={{
          position: "relative",
          display: "block",
          pointerEvents: "none",
        }}
      />
      <div
        ref={markRef}
        aria-label="MAVE1.0"
        style={{
          position: "fixed",
          left: 0,
          right: 0,
          bottom: "clamp(24px, 6vh, 58px)",
          textAlign: "center",
          font: "200 32px/1 var(--font-sans)",
          letterSpacing: "0.04em",
          color: "var(--paper)",
          opacity: 0,
          transition: "opacity 900ms var(--ease-soft) 350ms",
          pointerEvents: "none",
        }}
      >
        MAVE<sup style={{ fontSize: 13, verticalAlign: "top", marginLeft: 1 }}>1.0</sup>
      </div>
      <div
        ref={veilRef}
        style={{
          position: "fixed",
          inset: 0,
          background: "#1d0a05",
          opacity: 1,
          transition: "opacity 600ms var(--ease-soft)",
          pointerEvents: "none",
        }}
      />
    </div>
  );
}
