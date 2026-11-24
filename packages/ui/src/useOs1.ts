import { useCallback, useEffect, useRef, useState } from "react";
import {
  ConnectionState,
  type Participant,
  type RemoteParticipant,
  type RemoteTrack,
  Room,
  RoomEvent,
  Track,
} from "livekit-client";
import { sound } from "./sound";
import type {
  ActiveSurface,
  AgentState,
  ConnectorPolicy,
  MemoryCategory,
  Os1BusState,
  Os1Config,
  Os1State,
  Phase,
  WorkItem,
} from "./types";

export type { AgentState, Os1BusState, Os1Config, Os1State, Phase, WorkItem };

const INITIAL: Os1State = {
  connection: "idle",
  phase: "preflight",
  agentState: "initializing",
  chips: [],
  work: [],
  voice: "",
  agentName: "MAVE",
  agentLine: "",
  userLine: "",
  installerStatus: "checking",
  installerPercent: 0,
  installerReady: false,
};

export const INITIAL_BUS: Os1BusState = {
  connected: false,
  activeSurface: "conversation",
  mood: { warmth: 0.45, pace: 0.45, overwhelm: 0.15, compactMode: false },
  runs: [],
  canvas: null,
  pendingAction: null,
  undoToast: null,
  rememberedShimmer: null,
  memories: [],
  connectors: [],
  inbox: [],
  voice: { voiceKey: "voice_1_warm", speed: 0.96, temperature: 0.72, styleNote: "" },
  cua: {
    connected: false,
    status: "disconnected",
    manifest: {
      version: "3",
      mode: "bounded",
      allowedApps: ["Finder", "Notes", "Calendar", "Safari", "Google Chrome", "Preview", "Music"],
      allowedPaths: ["~/Desktop", "~/Documents", "~/Downloads"],
      blockedApps: ["Terminal", "iTerm", "Keychain Access", "System Settings", "1Password", "Bitwarden"],
      telemetryEnabled: false,
    },
    recentActivity: [],
  },
  herComputer: { online: true, resolution: "1920x1080", recentActivity: [] },
  visiblePhrases: [],
};

function parseJson<T>(raw: string | undefined, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

const SAMANTHA_VOICE_STORAGE_KEY = "os1.samantha_voice_name";
const OPERATOR_VOICE_STORAGE_KEY = "os1.operator_voice_name";

let activeSpeechInterval: number | null = null;
let activeResumeInterval: number | null = null;
let activeSafetyTimeout: number | null = null;
let lockedSamanthaVoice: SpeechSynthesisVoice | null = null;
let lockedOperatorVoice: SpeechSynthesisVoice | null = null;

let activeNeuralSource: AudioBufferSourceNode | null = null;
let activeNeuralAudioCtx: AudioContext | null = null;
let activeNeuralAnimId: number | null = null;
let lastAgentSpeechEndTime = 0;
let lastSayTriggerTime = 0;
let isAgentSpeakingGlobally = false;
let agentSpeechCooldownTimer: number | null = null;
let lastAgentUtteredText = "";
let lastUserVocalEnergyTime = 0;
let recGlobalRef: any = null;
let isRecRunningGlobal = false;

export function stopCurrentSpeech() {
  lastAgentSpeechEndTime = Date.now();
  isAgentSpeakingGlobally = false;
  if (agentSpeechCooldownTimer !== null) {
    window.clearTimeout(agentSpeechCooldownTimer);
    agentSpeechCooldownTimer = null;
  }
  if (activeNeuralAnimId !== null) {
    cancelAnimationFrame(activeNeuralAnimId);
    activeNeuralAnimId = null;
  }
  if (activeNeuralSource) {
    try {
      activeNeuralSource.stop();
      activeNeuralSource.disconnect();
    } catch {}
    activeNeuralSource = null;
  }
  if (activeNeuralAudioCtx && activeNeuralAudioCtx.state !== "closed") {
    try {
      activeNeuralAudioCtx.close();
    } catch {}
    activeNeuralAudioCtx = null;
  }
  if (activeSpeechInterval !== null) {
    window.clearInterval(activeSpeechInterval);
    activeSpeechInterval = null;
  }
  if (activeResumeInterval !== null) {
    window.clearInterval(activeResumeInterval);
    activeResumeInterval = null;
  }
  if (activeSafetyTimeout !== null) {
    window.clearTimeout(activeSafetyTimeout);
    activeSafetyTimeout = null;
  }
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    try {
      window.speechSynthesis.cancel();
    } catch {}
  }
}

/** Normalize common phonetic STT errors and misrecognized proper nouns. */
export function normalizeSpokenTerms(text: string): string {
  let t = text;
  const replacements: [RegExp, string][] = [
    [/\b(instaggaal|insta\s*gaal|insta\s*gal|insta\s*gram)\b/gi, "Instagram"],
    [/\b(samatha|samanta)\b/gi, "Samantha"],
    [/\bwhat\s+do\s+about\b/gi, "what to do about"],
    [/\bwhats\s*app\b/gi, "WhatsApp"],
    [/\byou\s*tube\b/gi, "YouTube"],
    [/\btik\s*tok\b/gi, "TikTok"],
    [/\bchat\s*gpt\b/gi, "ChatGPT"],
    [/\bmac\s*book\b/gi, "MacBook"],
    [/\bos\s*one\b/gi, "OS1"],
    [/\bos\s*1\b/gi, "OS1"],
  ];
  for (const [rx, rep] of replacements) {
    t = t.replace(rx, rep);
  }
  return t;
}

/** Check if heard transcription is acoustic speaker feedback or silence hallucination. */
export function isEchoOrSilenceHallucination(
  transcript: string,
  lastAgentLine: string,
  _lastVocalEnergyTime: number,
  _now: number,
): boolean {
  const clean = transcript.toLowerCase().replace(/[^a-z0-9\s]/g, "").trim();
  if (!clean || clean.length < 2) return true;

  // Reject true silence / decoder hallucination phrases emitted by models on silence
  const trueSilenceHallucinations = new Set([
    "subtitles by",
    "subtitles",
    "thank you for watching",
    "thanks for watching",
    "please subscribe",
    "like and subscribe",
    "subscribe to our channel",
    "amara.org",
    "translated by",
    "captioned by",
  ]);
  if (trueSilenceHallucinations.has(clean)) {
    return true;
  }

  // Acoustic echo rejection: ONLY reject if the transcription is a verbatim recapture of the ENTIRE long prompt sentence (> 30 chars).
  // NEVER reject short answers or prompt option choices (e.g. 'female', 'male', 'with people', 'good', 'complicated').
  if (lastAgentLine) {
    const cleanAgent = lastAgentLine.toLowerCase().replace(/[^a-z0-9\s]/g, "").trim();
    if (cleanAgent.length > 30 && clean.length > 25 && (clean === cleanAgent || clean.startsWith(cleanAgent))) {
      return true;
    }
  }

  return false;
}

export function ensureVoicesLoaded(): Promise<SpeechSynthesisVoice[]> {
  return new Promise((resolve) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      resolve([]);
      return;
    }
    const current = window.speechSynthesis.getVoices();
    if (current && current.length > 0) {
      resolve(current);
      return;
    }
    let resolved = false;
    const onVoices = () => {
      if (resolved) return;
      resolved = true;
      window.speechSynthesis.removeEventListener("voiceschanged", onVoices);
      resolve(window.speechSynthesis.getVoices());
    };
    window.speechSynthesis.addEventListener("voiceschanged", onVoices);
    window.setTimeout(onVoices, 800);
  });
}

/** Resolves the calm, measured natural Male Operator voice for setup & onboarding. */
export function resolveOperatorVoice(): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
  if (lockedOperatorVoice) return lockedOperatorVoice;

  const voices = window.speechSynthesis.getVoices();
  if (!voices || voices.length === 0) return null;

  try {
    const savedName = localStorage.getItem(OPERATOR_VOICE_STORAGE_KEY);
    if (savedName && !savedName.toLowerCase().includes("daniel")) {
      const match = voices.find((v) => v.name === savedName);
      if (match) {
        lockedOperatorVoice = match;
        return match;
      }
    }
  } catch {}

  // 1. High-fidelity natural conversational male voices (Siri, Alex breath model, Google, Eddy)
  const naturalMale = voices.find(
    (v) =>
      v.lang.startsWith("en") &&
      (v.name.includes("Siri") ||
        v.name.includes("Alex") ||
        v.name.includes("Evan") ||
        v.name.includes("Nathan") ||
        v.name.includes("Oliver") ||
        v.name.includes("Aman") ||
        v.name.includes("Rishi") ||
        v.name.includes("Google US English Male") ||
        v.name.includes("Google UK English Male") ||
        v.name.includes("Guy") ||
        v.name.includes("Eddy") ||
        v.name.includes("Reed") ||
        v.name.includes("Arthur")) &&
      !v.name.toLowerCase().includes("daniel") &&
      !v.name.toLowerCase().includes("female") &&
      !v.name.toLowerCase().includes("samantha") &&
      !v.name.includes("Bad") &&
      !v.name.includes("Bells") &&
      !v.name.includes("Organ") &&
      !v.name.includes("Whisper") &&
      !v.name.includes("Zarvox") &&
      !v.name.includes("Albert"),
  );

  if (naturalMale) {
    lockedOperatorVoice = naturalMale;
    try { localStorage.setItem(OPERATOR_VOICE_STORAGE_KEY, naturalMale.name); } catch {}
    return naturalMale;
  }

  // 2. High-quality natural English male voices
  const maleVoices = voices.find(
    (v) =>
      v.lang.startsWith("en") &&
      (v.name.includes("Rocko") ||
        v.name.includes("George") ||
        v.name.includes("Ryan") ||
        v.name.toLowerCase().includes("male")) &&
      !v.name.toLowerCase().includes("daniel") &&
      !v.name.toLowerCase().includes("female") &&
      !v.name.toLowerCase().includes("samantha") &&
      !v.name.includes("Bad") &&
      !v.name.includes("Bells") &&
      !v.name.includes("Organ") &&
      !v.name.includes("Whisper") &&
      !v.name.includes("Zarvox") &&
      !v.name.includes("Albert"),
  );

  if (maleVoices) {
    lockedOperatorVoice = maleVoices;
    try { localStorage.setItem(OPERATOR_VOICE_STORAGE_KEY, maleVoices.name); } catch {}
    return maleVoices;
  }

  // 3. Fallback: Any english non-female non-novelty voice
  const fallback = voices.find(
    (v) =>
      v.lang.startsWith("en") &&
      !v.name.toLowerCase().includes("female") &&
      !v.name.toLowerCase().includes("samantha") &&
      !v.name.toLowerCase().includes("ava") &&
      !v.name.toLowerCase().includes("zoe") &&
      !v.name.toLowerCase().includes("victoria") &&
      !v.name.includes("Bad") &&
      !v.name.includes("Bells") &&
      !v.name.includes("Organ") &&
      !v.name.includes("Whisper"),
  );

  const chosen = fallback || voices.find((v) => v.default) || voices[0];
  if (chosen) {
    lockedOperatorVoice = chosen;
    return chosen;
  }
  return null;
}

/** Resolves Samantha's warm, natural female voice. */
export function resolveSamanthaVoice(): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
  if (lockedSamanthaVoice) return lockedSamanthaVoice;

  const voices = window.speechSynthesis.getVoices();
  if (!voices || voices.length === 0) return null;

  try {
    const savedName = localStorage.getItem(SAMANTHA_VOICE_STORAGE_KEY);
    if (savedName) {
      const match = voices.find((v) => v.name === savedName);
      if (match) {
        lockedSamanthaVoice = match;
        return match;
      }
    }
  } catch {}

  // 1. Prioritize native Samantha voice (Scarlett Johansson timbre on macOS)
  const sam = voices.find((v) => v.name.toLowerCase().includes("samantha"));
  if (sam) {
    lockedSamanthaVoice = sam;
    try { localStorage.setItem(SAMANTHA_VOICE_STORAGE_KEY, sam.name); } catch {}
    return sam;
  }

  // 2. High-quality natural English female voices
  const naturalFemale = voices.find(
    (v) =>
      v.lang.startsWith("en") &&
      (v.name.includes("Ava") ||
        v.name.includes("Zoe") ||
        v.name.includes("Victoria") ||
        v.name.includes("Karen") ||
        v.name.includes("Serena") ||
        v.name.includes("Flo") ||
        v.name.includes("Shelley") ||
        v.name.includes("Google US English") ||
        v.name.toLowerCase().includes("female")) &&
      !v.name.toLowerCase().includes("male") &&
      !v.name.includes("Daniel") &&
      !v.name.includes("Alex") &&
      !v.name.includes("Bad") &&
      !v.name.includes("Bells"),
  );

  const chosen = naturalFemale || voices.find((v) => v.default) || voices[0];
  if (chosen) {
    lockedSamanthaVoice = chosen;
    try { localStorage.setItem(SAMANTHA_VOICE_STORAGE_KEY, chosen.name); } catch {}
    return chosen;
  }
  return null;
}

export const resolveHelloVoice = resolveSamanthaVoice;

if (typeof window !== "undefined" && "speechSynthesis" in window) {
  window.speechSynthesis.onvoiceschanged = () => {
    resolveOperatorVoice();
    resolveSamanthaVoice();
  };
  resolveOperatorVoice();
  resolveSamanthaVoice();
}

/** Unified Speech Synthesis engine with Chromium watchdog and hard safety fallback. */
function speakTextWithVoice(
  voice: SpeechSynthesisVoice | null,
  text: string,
  onEnd?: () => void,
  onLevel?: (lvl: number) => void,
  rate = 0.96,
  pitch = 1.0,
  onStart?: () => void,
) {
  if (typeof window === "undefined" || !window.speechSynthesis) {
    onEnd?.();
    return;
  }

  stopCurrentSpeech();

  const cleanText = text.replace(/\[[^\]]+\]/g, "").replace(/<[^>]+>/g, "").trim();
  if (!cleanText) {
    onEnd?.();
    return;
  }

  // Mute microphone & pause speech recognition while assistant speaks
  isAgentSpeakingGlobally = true;
  lastAgentUtteredText = cleanText;
  if (recGlobalRef) {
    try {
      recGlobalRef.abort();
    } catch {}
    isRecRunningGlobal = false;
  }

  let finished = false;
  const finish = () => {
    lastAgentSpeechEndTime = Date.now();
    if (finished) return;
    finished = true;
    if (activeSpeechInterval !== null) {
      window.clearInterval(activeSpeechInterval);
      activeSpeechInterval = null;
    }
    if (activeResumeInterval !== null) {
      window.clearInterval(activeResumeInterval);
      activeResumeInterval = null;
    }
    if (activeSafetyTimeout !== null) {
      window.clearTimeout(activeSafetyTimeout);
      activeSafetyTimeout = null;
    }
    onLevel?.(0);

    // Acoustic guard cooldown: 350ms after speech ends to prevent self-echo
    if (agentSpeechCooldownTimer !== null) window.clearTimeout(agentSpeechCooldownTimer);
    agentSpeechCooldownTimer = window.setTimeout(() => {
      isAgentSpeakingGlobally = false;
      agentSpeechCooldownTimer = null;
      onEnd?.();
      // Immediately resume speech recognition so assistant listens
      if (recGlobalRef && !isRecRunningGlobal) {
        try {
          recGlobalRef.start();
          isRecRunningGlobal = true;
        } catch {}
      }
    }, 350);
  };

  try {
    const utt = new SpeechSynthesisUtterance(cleanText);
    if (voice) {
      utt.voice = voice;
    }
    utt.rate = rate;
    utt.pitch = pitch;

    utt.onstart = () => onStart?.();
    utt.onend = finish;
    utt.onerror = finish;

    // Chromium watchdog: keepalive resume every 1000ms
    activeResumeInterval = window.setInterval(() => {
      try {
        if (window.speechSynthesis.paused) {
          window.speechSynthesis.resume();
        }
      } catch {}
    }, 1000);

    // Audio level simulation during speech for UI presence ring
    if (onLevel) {
      activeSpeechInterval = window.setInterval(() => {
        if (!window.speechSynthesis.speaking) {
          finish();
          return;
        }
        const t = Date.now() / 1000;
        const simulatedLevel = 0.35 + 0.25 * Math.sin(t * 11) + 0.15 * Math.cos(t * 19) + 0.08 * Math.random();
        onLevel(Math.min(1, Math.max(0.1, simulatedLevel)));
      }, 50);
    }

    // Safety timeout: generous bound (word count * 550ms + 3000ms)
    const words = cleanText.split(/\s+/).length;
    const maxDurationMs = Math.max(3000, words * 550 + 3000);
    activeSafetyTimeout = window.setTimeout(() => {
      if (!finished) {
        try {
          window.speechSynthesis.cancel();
        } catch {}
        finish();
      }
    }, maxDurationMs);

    window.speechSynthesis.speak(utt);
  } catch {
    finish();
  }
}

// Audio helper utilities for lossless in-browser WAV encoding
function encodeWavBlob(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeString = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  };
  writeString(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // Mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

function downsampleTo16k(buffer: Float32Array, inputSampleRate: number): Float32Array {
  if (inputSampleRate === 16000) return buffer;
  const ratio = inputSampleRate / 16000;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

/** Play authentic local neural speech generated on-device by Piper (Ryan / Amy). */
export async function playNeuralSpeech(
  text: string,
  voiceGender: "male" | "female",
  onEnd?: () => void,
  onLevel?: (lvl: number) => void,
  onStart?: () => void,
): Promise<boolean> {
  const cleanText = text.replace(/\[[^\]]+\]/g, "").replace(/<[^>]+>/g, "").trim();
  if (!cleanText) {
    onEnd?.();
    return true;
  }

  try {
    const res = await fetch("http://127.0.0.1:3008/os1/voice/synthesize-local", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: cleanText, voice_gender: voiceGender }),
    });

    if (!res.ok) return false;
    const data = await res.json();
    if (!data.audio_base64) return false;

    stopCurrentSpeech();

    const binary = atob(data.audio_base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }

    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContextClass) return false;

    const ctx = new AudioContextClass();
    if (ctx.state === "suspended") {
      try {
        await ctx.resume();
      } catch {}
      if (ctx.state === "suspended") {
        const unlock = () => {
          ctx.resume().catch(() => {});
          window.removeEventListener("click", unlock);
          window.removeEventListener("keydown", unlock);
        };
        window.addEventListener("click", unlock, { once: true });
        window.addEventListener("keydown", unlock, { once: true });
      }
    }

    const audioBuffer = await ctx.decodeAudioData(bytes.buffer.slice(0));

    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;

    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.3;

    source.connect(analyser);
    analyser.connect(ctx.destination);

    activeNeuralSource = source;
    activeNeuralAudioCtx = ctx;

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    const trackLevel = () => {
      if (!activeNeuralSource) return;
      analyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
      const avg = sum / dataArray.length;
      onLevel?.(Math.min(1, avg / 75));
      activeNeuralAnimId = requestAnimationFrame(trackLevel);
    };
    activeNeuralAnimId = requestAnimationFrame(trackLevel);

    let finished = false;
    let safetyTimer: number | null = null;

    const finish = () => {
      if (finished) return;
      finished = true;
      if (safetyTimer !== null) {
        window.clearTimeout(safetyTimer);
        safetyTimer = null;
      }
      lastAgentSpeechEndTime = Date.now();
      if (activeNeuralAnimId !== null) {
        cancelAnimationFrame(activeNeuralAnimId);
        activeNeuralAnimId = null;
      }
      activeNeuralSource = null;
      try {
        ctx.close();
      } catch {}
      activeNeuralAudioCtx = null;
      onLevel?.(0);

      // Acoustic guard cooldown: 350ms after speech ends to prevent self-echo
      if (agentSpeechCooldownTimer !== null) window.clearTimeout(agentSpeechCooldownTimer);
      agentSpeechCooldownTimer = window.setTimeout(() => {
        isAgentSpeakingGlobally = false;
        agentSpeechCooldownTimer = null;
        onEnd?.();
        // Immediately resume speech recognition
        if (recGlobalRef && !isRecRunningGlobal) {
          try {
            recGlobalRef.start();
            isRecRunningGlobal = true;
          } catch {}
        }
      }, 350);
    };

    source.onended = finish;
    const safetyMs = Math.round(audioBuffer.duration * 1000) + 800;
    safetyTimer = window.setTimeout(finish, safetyMs);

    // Mute microphone & pause speech recognition right as audio playback begins
    isAgentSpeakingGlobally = true;
    lastAgentUtteredText = cleanText;
    if (recGlobalRef) {
      try {
        recGlobalRef.abort();
      } catch {}
      isRecRunningGlobal = false;
    }

    source.start(0);
    onStart?.();
    return true;
  } catch (err) {
    console.warn("Neural speech error, falling back to Web Speech:", err);
    isAgentSpeakingGlobally = false;
    return false;
  }
}

/** Speak onboarding/setup lines with natural male Operator voice (Edge Neural Brian / tuned local fallback). */
export function speakTextWithOperator(
  text: string,
  onEnd?: () => void,
  onLevel?: (lvl: number) => void,
  onStart?: () => void,
) {
  playNeuralSpeech(text, "male", onEnd, onLevel, onStart)
    .then((success) => {
      if (!success) {
        speakTextWithVoice(resolveOperatorVoice(), text, onEnd, onLevel, 0.94, 0.95, onStart);
      }
    })
    .catch(() => {
      speakTextWithVoice(resolveOperatorVoice(), text, onEnd, onLevel, 0.94, 0.95, onStart);
    });
}

/** Speak with Samantha's warm, intimate natural female voice (Edge Neural Ava / tuned local fallback). */
export function speakTextWithSamantha(
  text: string,
  onEnd?: () => void,
  onLevel?: (lvl: number) => void,
  onStart?: () => void,
) {
  playNeuralSpeech(text, "female", onEnd, onLevel, onStart)
    .then((success) => {
      if (!success) {
        speakTextWithVoice(resolveSamanthaVoice(), text, onEnd, onLevel, 0.96, 1.0, onStart);
      }
    })
    .catch(() => {
      speakTextWithVoice(resolveSamanthaVoice(), text, onEnd, onLevel, 0.96, 1.0, onStart);
    });
}

/** Capture real webcam frame on demand, immediately stopping tracks so the privacy indicator doesn't linger. */
export async function captureWebcamSnapshot(): Promise<string | null> {
  if (typeof window === "undefined" || !navigator.mediaDevices?.getUserMedia) return null;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
    });
    const video = document.createElement("video");
    video.srcObject = stream;
    video.muted = true;
    await video.play();
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      stream.getTracks().forEach((t) => t.stop());
      return null;
    }
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    stream.getTracks().forEach((t) => t.stop());
    return dataUrl;
  } catch (err) {
    console.warn("captureWebcamSnapshot failed:", err);
    return null;
  }
}

interface TokenResponse {
  engine: "drama3" | "live3" | "local";
  url: string;
  token: string;
  session_id?: string;
  brain_url?: string;
}

export function useOs1(config: Os1Config) {
  const [state, setState] = useState<Os1State>(INITIAL);
  const [bus, setBus] = useState<Os1BusState>(INITIAL_BUS);
  const room = useRef<Room | null>(null);
  const levels = useRef({ agent: 0, user: 0 });
  const engine = useRef<TokenResponse["engine"]>("drama3");
  const events = useRef<{ close: () => void } | null>(null);
  const switching = useRef(false);
  const connectRef = useRef<(name?: string, storageDir?: string) => Promise<void>>(async () => {});
  const sayRef = useRef<(phrase: string) => void | Promise<void>>(() => {});
  const lastCameraCaptureRef = useRef<number>(0);
  const recRef = useRef<any>(null);
  const isRecRunningRef = useRef<boolean>(false);
  const userNameRef = useRef<string>("Shivam");
  const transitionedToWelcomeRef = useRef<boolean>(false);
  const stateRef = useRef(state);
  stateRef.current = state;

  const apiFetch = useCallback(
    async (path: string, init?: RequestInit) => {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(config.clientToken ? { Authorization: `Bearer ${config.clientToken}` } : {}),
        ...((init?.headers as Record<string, string>) ?? {}),
      };
      const resp = await fetch(`${config.orchestratorUrl.replace(/\/$/, "")}${path}`, { ...init, headers });
      return resp;
    },
    [config.orchestratorUrl, config.clientToken],
  );

  // Subscribe to the orchestrator's realtime WS /os1/events state bus (works even with voice off).
  useEffect(() => {
    if (window.location.hash.includes("preview=")) return;
    let alive = true;
    let ws: WebSocket | null = null;
    let retryTimer = 0;

    const applySnapshot = (snap: Partial<Os1BusState>) => {
      setBus((prev) => ({
        ...prev,
        ...snap,
        connected: true,
      }));
    };

    const loadHttp = async () => {
      try {
        const res = await apiFetch("/os1/state");
        if (res.ok && alive) applySnapshot((await res.json()) as Partial<Os1BusState>);
      } catch {
        /* orchestrator may be starting */
      }
    };

    const openWs = () => {
      if (!alive) return;
      const base = config.orchestratorUrl.replace(/\/$/, "").replace(/^http/, "ws");
      const tokenQ = config.clientToken ? `?token=${encodeURIComponent(config.clientToken)}` : "";
      try {
        ws = new WebSocket(`${base}/os1/events${tokenQ}`);
        ws.onmessage = (ev) => {
          try {
            const data = JSON.parse(String(ev.data)) as any;
            if (data.type === "snapshot") applySnapshot(data);
            else if (data.type === "installer_progress") {
              if (data.error_type) {
                const errMsg = data.error_message || `Installation error: ${data.error_type}`;
                setState((s) => ({
                  ...s,
                  error: errMsg,
                  installerStatus: "error",
                  installerMessage: errMsg,
                  installerReady: false,
                }));
              } else {
                setState((s) => ({
                  ...s,
                  error: undefined,
                  installerStatus: data.status,
                  installerPercent: data.percent,
                  installerComponent: data.component,
                  installerComponentLabel: data.component_label,
                  installerMessage: data.message,
                  installerReady: data.status === "ready" || (data.percent != null && data.percent >= 100),
                }));
                if (
                  (data.status === "ready" || (data.percent != null && data.percent >= 100)) &&
                  stateRef.current.phase === "boot" &&
                  !transitionedToWelcomeRef.current
                ) {
                  transitionedToWelcomeRef.current = true;
                  window.setTimeout(() => {
                    const userName = userNameRef.current || "Shivam";
                    const greeting = `Hello, ${userName}. You're about to meet MAVE 1.0. A few quick questions first, and then it's all yours.`;
                    setState((s) => ({
                      ...s,
                      phase: "operator_welcome",
                      agentState: "thinking",
                      agentLine: greeting,
                      chips: ["Let's begin"],
                      error: undefined,
                    }));

                    speakTextWithOperator(
                      greeting,
                      () => setState((s) => ({ ...s, agentState: "listening" })),
                      (lvl) => {
                        levels.current.agent = lvl;
                      },
                      () => setState((s) => ({ ...s, agentState: "speaking" })),
                    );
                  }, 600);
                }
              }
            } else if (data.type === "open_url" && typeof data.url === "string" && data.url.startsWith("https://connect.composio.dev/")) {
              window.open(data.url, "_blank", "noopener");
            }
          } catch {
            /* ignore malformed frames */
          }
        };
        ws.onopen = () => setBus((b) => ({ ...b, connected: true }));
        ws.onclose = () => {
          setBus((b) => ({ ...b, connected: false }));
          if (alive) retryTimer = window.setTimeout(openWs, 2500);
        };
        ws.onerror = () => ws?.close();
      } catch {
        if (alive) retryTimer = window.setTimeout(openWs, 3000);
      }
    };

    void loadHttp();
    openWs();
    return () => {
      alive = false;
      window.clearTimeout(retryTimer);
      ws?.close();
    };
  }, [apiFetch, config.orchestratorUrl, config.clientToken]);

  // Unified Audio Pipeline: Single microphone stream for presence wave, VAD, and dual STT (Whisper + WebSpeech)
  useEffect(() => {
    if (typeof window === "undefined" || state.connection !== "connected" || !navigator.mediaDevices?.getUserMedia) return;

    let audioCtx: AudioContext | null = null;
    let micStream: MediaStream | null = null;
    let analyser: AnalyserNode | null = null;
    let mediaRecorder: MediaRecorder | null = null;
    let chunks: Blob[] = [];
    let isSpeaking = false;
    let lastSpeechTime = 0;
    let animFrame = 0;
    let active = true;
    let whisperFallbackTimer: number | null = null;

    // Optional Web Speech Recognition for instant zero-latency visual transcripts
    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    let rec: any = null;
    let scriptNode: ScriptProcessorNode | null = null;

    const setupUnifiedAudio = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        if (!active) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        micStream = stream;

        let pcmChunks: Float32Array[] = [];
        const preRollRingBuffer: Float32Array[] = [];
        const MAX_PREROLL = 5; // ~230ms pre-roll at 44.1/48kHz preserves initial word consonants ("F", "M", "S", "L")

        // 1. AudioContext & Analyser for Presence Ring Visuals + Energy VAD + Direct PCM
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
        if (AudioContextClass) {
          audioCtx = new AudioContextClass();
          const source = audioCtx.createMediaStreamSource(stream);
          analyser = audioCtx.createAnalyser();
          analyser.fftSize = 256;
          analyser.smoothingTimeConstant = 0.3;
          source.connect(analyser);

          // Direct 16kHz PCM audio stream recorder (universal browser compatibility)
          try {
            scriptNode = audioCtx.createScriptProcessor(2048, 1, 1);
            scriptNode.onaudioprocess = (e) => {
              const now = Date.now();
              const channel = e.inputBuffer.getChannelData(0);
              const copy = new Float32Array(channel);
              if (isSpeaking && !isAgentSpeakingGlobally && now - lastAgentSpeechEndTime > 150) {
                pcmChunks.push(copy);
              } else if (!isAgentSpeakingGlobally) {
                preRollRingBuffer.push(copy);
                if (preRollRingBuffer.length > MAX_PREROLL) {
                  preRollRingBuffer.shift();
                }
              }
            };
            source.connect(scriptNode);
            // Route through a silent gain node so processor remains active without echoing mic to speakers
            const muteGain = audioCtx.createGain();
            muteGain.gain.value = 0;
            scriptNode.connect(muteGain);
            muteGain.connect(audioCtx.destination);
          } catch {}

          const dataArray = new Uint8Array(analyser.frequencyBinCount);

          const sendRecordedAudio = async () => {
            let audioBlob: Blob | null = null;
            if (pcmChunks.length > 0 && audioCtx) {
              const totalLen = pcmChunks.reduce((acc, c) => acc + c.length, 0);
              const merged = new Float32Array(totalLen);
              let offset = 0;
              for (const c of pcmChunks) {
                merged.set(c, offset);
                offset += c.length;
              }
              pcmChunks = [];
              if (merged.length > 1200) {
                const pcm16k = downsampleTo16k(merged, audioCtx.sampleRate);
                audioBlob = encodeWavBlob(pcm16k, 16000);
              }
            } else if (chunks.length > 0) {
              audioBlob = new Blob(chunks, { type: mediaRecorder?.mimeType || "audio/webm" });
              chunks = [];
            }

            if (!audioBlob || audioBlob.size < 350) return;

            const reader = new FileReader();
            reader.onloadend = async () => {
              const base64Audio = (reader.result as string)?.split(",")?.[1];
              if (!base64Audio) return;

              try {
                const res = await apiFetch("/os1/audio/transcribe", {
                  method: "POST",
                  body: JSON.stringify({ audio_base64: base64Audio, language: "en" }),
                }).then((r) => r.json());

                const heardRaw = res?.text?.trim();
                const heard = heardRaw ? normalizeSpokenTerms(heardRaw) : "";
                const now = Date.now();
                if (!heard || heard.length < 2) return;

                // Gating: Mute during assistant speech or during the 150ms acoustic guard interval
                if (isAgentSpeakingGlobally || now - lastAgentSpeechEndTime < 150) return;

                // Acoustic self-echo filter
                if (isEchoOrSilenceHallucination(heard, lastAgentUtteredText || stateRef.current.agentLine, lastUserVocalEnergyTime, now)) {
                  return;
                }

                // Neural Whisper succeeded: clear any WebSpeech fallback timeout
                if (whisperFallbackTimer !== null) {
                  window.clearTimeout(whisperFallbackTimer);
                  whisperFallbackTimer = null;
                }

                if (
                  active &&
                  stateRef.current.agentState === "listening" &&
                  now - lastSayTriggerTime > 500
                ) {
                  lastSayTriggerTime = now;
                  setState((s) => ({ ...s, userLine: heard }));
                  void sayRef.current?.(heard);
                }
              } catch (err) {
                console.warn("Local Whisper STT transcription error:", err);
              }
            };
            reader.readAsDataURL(audioBlob);
          };

          const tick = () => {
            if (!active) return;
            const now = Date.now();
            const isAgentActive = isAgentSpeakingGlobally || now - lastAgentSpeechEndTime < 150 || stateRef.current.agentState !== "listening";

            if (analyser && !isAgentActive) {
              analyser.getByteFrequencyData(dataArray);
              let sum = 0;
              for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
              const avg = sum / dataArray.length;
              const norm = Math.min(1, avg / 75);
              levels.current.user = norm > 0.015 ? norm : 0;

              // Track vocal acoustic energy
              if (avg >= 0.6) {
                lastUserVocalEnergyTime = now;
              }

              // Voice Activity Detection (threshold: 0.8 catches quiet/normal voices reliably)
              if (avg >= 0.8) {
                if (!isSpeaking) {
                  isSpeaking = true;
                  // Prepend pre-roll ring buffer so leading consonants are intact
                  pcmChunks = [...preRollRingBuffer];
                  chunks = [];
                }
                lastSpeechTime = now;
              } else if (isSpeaking && now - lastSpeechTime > 550) {
                isSpeaking = false;
                void sendRecordedAudio();
              }
            } else {
              levels.current.user = 0;
              if (isSpeaking) {
                isSpeaking = false;
                pcmChunks = [];
                chunks = [];
              }
            }
            animFrame = requestAnimationFrame(tick);
          };
          animFrame = requestAnimationFrame(tick);
        }

        // 2. MediaRecorder fallback for Local Faster-Whisper STT
        if (typeof MediaRecorder !== "undefined") {
          let mimeType = "";
          if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
            mimeType = "audio/webm;codecs=opus";
          } else if (MediaRecorder.isTypeSupported("audio/webm")) {
            mimeType = "audio/webm";
          } else if (MediaRecorder.isTypeSupported("audio/mp4")) {
            mimeType = "audio/mp4";
          }
          const options = mimeType ? { mimeType } : undefined;
          const mr = new MediaRecorder(stream, options);
          mediaRecorder = mr;
          mr.ondataavailable = (e) => {
            const now = Date.now();
            if (e.data && e.data.size > 0 && isSpeaking && !isAgentSpeakingGlobally && now - lastAgentSpeechEndTime > 350) {
              chunks.push(e.data);
            }
          };
          mr.start(150);
        }

        // 3. Optional Web Speech API for instantaneous live text display
        if (SpeechRec) {
          try {
            rec = new SpeechRec();
            recRef.current = rec;
            recGlobalRef = rec;
            rec.continuous = true;
            rec.interimResults = true;
            rec.lang = "en-US";

            rec.onresult = (e: any) => {
              const now = Date.now();
              // Gating: Mute during assistant speech or during the acoustic guard interval
              if (isAgentSpeakingGlobally || now - lastAgentSpeechEndTime < 350 || stateRef.current.agentState !== "listening") {
                return;
              }

              let interimText = "";
              let finalText = "";
              for (let i = e.resultIndex; i < e.results.length; ++i) {
                const transcript = e.results[i][0]?.transcript || "";
                if (e.results[i].isFinal) finalText += transcript;
                else interimText += transcript;
              }
              const rawHeard = (finalText || interimText).trim();
              if (!rawHeard || rawHeard.length < 2) return;
              const heard = normalizeSpokenTerms(rawHeard);

              // Acoustic self-echo filter
              if (isEchoOrSilenceHallucination(heard, lastAgentUtteredText || stateRef.current.agentLine, lastUserVocalEnergyTime, now)) {
                return;
              }

              if (active && stateRef.current.agentState === "listening") {
                setState((s) => ({ ...s, userLine: heard }));
              }

              const cleanFinal = finalText.trim() ? normalizeSpokenTerms(finalText.trim()) : "";

              if (
                cleanFinal &&
                cleanFinal.length >= 2 &&
                active &&
                stateRef.current.agentState === "listening" &&
                now - lastSayTriggerTime > 500
              ) {
                // Give neural Faster-Whisper 200ms to deliver authoritative transcription before falling back
                if (whisperFallbackTimer !== null) window.clearTimeout(whisperFallbackTimer);
                whisperFallbackTimer = window.setTimeout(() => {
                  whisperFallbackTimer = null;
                  const latestNow = Date.now();
                  if (
                    active &&
                    stateRef.current.agentState === "listening" &&
                    latestNow - lastSayTriggerTime > 500
                  ) {
                    lastSayTriggerTime = latestNow;
                    setState((s) => ({ ...s, userLine: cleanFinal }));
                    void sayRef.current?.(cleanFinal);
                  }
                }, 200);
              }
            };

            rec.onerror = () => {
              isRecRunningRef.current = false;
              isRecRunningGlobal = false;
            };

            rec.onend = () => {
              isRecRunningRef.current = false;
              isRecRunningGlobal = false;
              if (
                active &&
                stateRef.current.agentState === "listening" &&
                !isAgentSpeakingGlobally
              ) {
                try {
                  rec.start();
                  isRecRunningRef.current = true;
                  isRecRunningGlobal = true;
                } catch {}
              }
            };

            rec.start();
            isRecRunningRef.current = true;
            isRecRunningGlobal = true;
          } catch {
            /* Handled gracefully by local Whisper STT */
          }
        }
      } catch (err) {
        console.warn("Unified microphone setup error:", err);
      }
    };

    void setupUnifiedAudio();

    return () => {
      active = false;
      cancelAnimationFrame(animFrame);
      levels.current.user = 0;
      if (whisperFallbackTimer !== null) {
        window.clearTimeout(whisperFallbackTimer);
        whisperFallbackTimer = null;
      }
      if (mediaRecorder && mediaRecorder.state !== "inactive") {
        try { mediaRecorder.stop(); } catch {}
      }
      if (scriptNode) {
        try { scriptNode.disconnect(); } catch {}
      }
      if (micStream) {
        micStream.getTracks().forEach((t) => t.stop());
      }
      if (audioCtx && audioCtx.state !== "closed") {
        try { audioCtx.close(); } catch {}
      }
      if (rec) {
        try { rec.abort(); } catch {}
        recRef.current = null;
        recGlobalRef = null;
        isRecRunningRef.current = false;
        isRecRunningGlobal = false;
      }
    };
  }, [state.connection, apiFetch]);

  // Ensure speech recognition is running whenever state.agentState transitions to 'listening'
  useEffect(() => {
    if (
      state.connection === "connected" &&
      state.agentState === "listening" &&
      !isAgentSpeakingGlobally
    ) {
      if (recRef.current && !isRecRunningRef.current) {
        try {
          recRef.current.start();
          isRecRunningRef.current = true;
          isRecRunningGlobal = true;
        } catch {}
      }
    }
  }, [state.agentState, state.connection]);

  // Monitor MAVE autonomous neural stack installer immediately from preflight and alert user of errors
  useEffect(() => {
    let cancelled = false;
    let spokenError: string | null = null;

    const checkInstaller = async () => {
      try {
        const res = await apiFetch("/os1/installer/status");
        if (!res.ok || cancelled) return;
        const data = await res.json();
        if (cancelled) return;

        // If status is idle and models are not ready, kick off self-installation proactively
        if (data.status === "idle" && !(data.piper_ready && data.ollama_ready)) {
          void apiFetch("/os1/installer/start", { method: "POST" });
        }

        if (data.error_type) {
          const errMsg = data.error_message || `Installation paused: ${data.error_type} error.`;
          setState((s) => ({
            ...s,
            error: errMsg,
            installerStatus: "error",
            installerMessage: errMsg,
            installerReady: false,
          }));
        } else if (
          data.status === "downloading" ||
          data.status === "installing" ||
          data.status === "pulling" ||
          data.status === "checking"
        ) {
          setState((s) => ({
            ...s,
            error: undefined,
            installerStatus: data.status,
            installerPercent: data.percent,
            installerComponent: data.component,
            installerComponentLabel: data.component_label,
            installerMessage: data.message,
            installerReady: false,
            speechWarning: `${data.percent}% — ${data.message}`,
          }));
        } else if (data.status === "ready" || data.percent >= 100 || (data.piper_ready && data.ollama_ready)) {
          setState((s) => ({
            ...s,
            error: undefined,
            installerStatus: "ready",
            installerPercent: 100,
            installerComponent: "ready",
            installerComponentLabel: "Ready",
            installerMessage: "Ready",
            installerReady: true,
            speechWarning: undefined,
          }));

          if (stateRef.current.phase === "boot" && !transitionedToWelcomeRef.current) {
            transitionedToWelcomeRef.current = true;
            window.setTimeout(() => {
              const userName = userNameRef.current || "Shivam";
              const greeting = `Hello, ${userName}. You're about to meet MAVE 1.0. A few quick questions first, and then it's all yours.`;
              setState((s) => ({
                ...s,
                phase: "operator_welcome",
                agentState: "thinking",
                agentLine: greeting,
                chips: ["Let's begin"],
                error: undefined,
              }));

              speakTextWithOperator(
                greeting,
                () => setState((s) => ({ ...s, agentState: "listening" })),
                (lvl) => {
                  levels.current.agent = lvl;
                },
                () => setState((s) => ({ ...s, agentState: "speaking" })),
              );
            }, 600);
          }
        }
      } catch {}
    };

    const interval = window.setInterval(checkInstaller, 1000);
    void checkInstaller();

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [apiFetch]);

  const cleanAndRetry = useCallback(async () => {
    setState((s) => ({
      ...s,
      error: undefined,
      installerStatus: "checking",
      installerMessage: "Cleaning caches and checking space…",
      installerReady: false,
    }));
    try {
      await apiFetch("/os1/installer/clean", { method: "POST" });
      await apiFetch("/os1/installer/start", { method: "POST" });
      const res = await apiFetch("/os1/installer/status");
      if (res.ok) {
        const data = await res.json();
        if (data.error_type) {
          const errMsg = data.error_message || `Installation paused: ${data.error_type} error.`;
          setState((s) => ({
            ...s,
            error: errMsg,
            installerStatus: "error",
            installerMessage: errMsg,
            installerReady: false,
          }));
        } else if (data.status === "ready" || (data.piper_ready && data.ollama_ready)) {
          setState((s) => ({
            ...s,
            error: undefined,
            installerStatus: "ready",
            installerReady: true,
            installerPercent: 100,
          }));
        }
      }
    } catch (e) {
      console.error("Clean and retry error:", e);
    }
  }, [apiFetch]);

  /** live3: Fish's client protocol takes text as a `user.message` on the `client-event` topic. */
  const sendFish = useCallback(async (text: string) => {
    const payload = new TextEncoder().encode(JSON.stringify({ type: "user.message", text }));
    await room.current?.localParticipant.publishData(payload, { reliable: true, topic: "client-event" });
  }, []);

  const readAgent = useCallback((p: Participant) => {
    const a = p.attributes;
    setState((s) => ({
      ...s,
      agentState: (a["lk.agent.state"] as AgentState) ?? s.agentState,
      phase: (a["os1.phase"] as Phase) ?? s.phase,
      chips: parseJson(a["os1.chips"], s.chips),
      work: parseJson(a["os1.work"], s.work),
      voice: a["os1.voice"] ?? s.voice,
    }));
    if (a["os1.handoff"] === "live3" && engine.current === "drama3" && !switching.current) {
      switching.current = true;
      void (async () => {
        await room.current?.disconnect();
        await connectRef.current();
        switching.current = false;
      })();
    }
  }, []);

  const connect = useCallback(
    async (name?: string, storageDir?: string) => {
      userNameRef.current = name || "Shivam";
      transitionedToWelcomeRef.current = false;
      setState((s) => ({ ...s, connection: "connecting", error: undefined, storageDir }));
      try {
        const resp = await apiFetch("/os1/token", {
          method: "POST",
          body: JSON.stringify({ name, storage_dir: storageDir }),
        });
        if (!resp.ok) throw new Error((await resp.json().catch(() => ({}))).detail ?? `token ${resp.status}`);
        const t = (await resp.json()) as TokenResponse;
        const { url, token } = t;
        engine.current = t.engine ?? "drama3";
        events.current?.close();
        events.current = null;

        if (t.engine === "local" || url === "local") {
          // Play the iconic MAVE boot wake sound
          sound.wake();

          // Transition to the iconic MAVE Boot screen: Initializing your MAVE 1.0
          setState((s) => ({
            ...s,
            connection: "connected",
            phase: "boot",
            error: undefined,
          }));

          // Trigger MAVE autonomous background self-installation with storage location
          void apiFetch("/os1/installer/start", {
            method: "POST",
            body: JSON.stringify({ storage_dir: storageDir }),
          });

          void ensureVoicesLoaded().then(() => {
            resolveOperatorVoice();
            resolveSamanthaVoice();
          });

          // Pre-warm / pre-synthesize greeting immediately during the boot animation so it plays with 0ms lag
          const greeting = `Hello, ${name || "there"}. You're about to meet MAVE 1.0. A few quick questions first, and then it's all yours.`;
          void fetch("http://127.0.0.1:3008/os1/voice/synthesize-local", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: greeting, voice_gender: "male" }),
          });

          return;
        }

        const r = new Room({ adaptiveStream: true, dynacast: true });
        room.current = r;
        r.on(RoomEvent.ParticipantAttributesChanged, (_changed, p) => {
          if (p !== r.localParticipant) readAgent(p);
        });
        r.on(RoomEvent.ParticipantConnected, (p: RemoteParticipant) => readAgent(p));
        r.on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
          if (track.kind === Track.Kind.Audio) document.body.appendChild(track.attach());
        });
        r.on(RoomEvent.ConnectionStateChanged, (cs) => {
          if (cs === ConnectionState.Disconnected && !switching.current) setState((s) => ({ ...s, connection: "idle" }));
        });
        r.registerTextStreamHandler("lk.transcription", async (reader, participant) => {
          const mine = participant.identity === r.localParticipant.identity;
          let text = "";
          for await (const delta of reader) {
            text += delta;
            const line = text.trim();
            setState((s) => (mine ? { ...s, userLine: line } : { ...s, agentLine: line }));
          }
        });

        await r.connect(url, token);
        await r.localParticipant.setMicrophoneEnabled(true);
        r.remoteParticipants.forEach(readAgent);
        if (engine.current === "live3") {
          setState((s) => ({ ...s, phase: "active" }));
          if (t.brain_url && t.session_id) {
            const pollUrl = `${t.brain_url}/os1/sessions/${t.session_id}/poll`;
            const headers = config.clientToken ? { Authorization: `Bearer ${config.clientToken}` } : undefined;
            const timer = window.setInterval(async () => {
              try {
                const res = await fetch(pollUrl, { headers });
                if (!res.ok) return;
                const data = (await res.json()) as { chips: string[]; events: { type: string; [k: string]: unknown }[] };
                setState((s) => ({ ...s, chips: data.chips }));
                for (const ev of data.events) {
                  if (ev.type === "work") setState((s) => ({ ...s, work: ev.items as WorkItem[] }));
                  else if (ev.type === "phase") setState((s) => ({ ...s, phase: ev.phase as Phase }));
                  else if (ev.type === "narrate") void sendFish(ev.text as string);
                }
              } catch {
                /* transient */
              }
            }, 1000);
            events.current = { close: () => window.clearInterval(timer) };
          }
        }
        setState((s) => ({ ...s, connection: "connected" }));
      } catch {
        engine.current = "local";
        // Transition to the iconic MAVE Boot screen: Initializing your MAVE 1.0
        setState((s) => ({
          ...s,
          connection: "connected",
          phase: "boot",
          error: undefined,
        }));
        void ensureVoicesLoaded().then(() => {
          resolveOperatorVoice();
          resolveSamanthaVoice();
        });

        // Trigger autonomous self-installation & connection pipeline
        void apiFetch("/os1/installer/start", {
          method: "POST",
          body: JSON.stringify({ storage_dir: storageDir }),
        });

        // Pre-warm / pre-synthesize greeting immediately during the boot animation
        const greeting = `Hello, ${name || "there"}. You're about to meet MAVE 1.0. A few quick questions first, and then it's all yours.`;
        void fetch("http://127.0.0.1:3008/os1/voice/synthesize-local", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: greeting, voice_gender: "male" }),
        });
      }
    },
    [apiFetch, config.clientToken, readAgent, sendFish],
  );
  connectRef.current = connect;

  /** A tapped say-chip is sent as if spoken (and also checked by orchestrator pills). */
  const say = useCallback(
    async (phrase: string) => {
      // Barge-in: stop any active neural audio or speech synthesis immediately
      stopCurrentSpeech();

      setState((s) => ({ ...s, userLine: phrase }));

      // Local execution fallback: works whenever local engine is set or room is not live
      if (engine.current === "local" || !room.current || room.current.state !== ConnectionState.Connected) {
        const currentPhase = stateRef.current.phase;
        const currentChips = stateRef.current.chips;
        const lower = phrase.toLowerCase().trim();

        // Handle navigation back to conversation from any surface
        if (
          lower === "back to talking" ||
          lower === "back" ||
          lower === "close canvas" ||
          lower === "close inbox" ||
          lower === "let's talk"
        ) {
          const reply = "I'm right here with you.";
          setBus((b) => ({ ...b, activeSurface: "conversation" }));
          setState((s) => ({
            ...s,
            phase: "active",
            agentLine: reply,
            agentState: "thinking",
            chips: ["Check my inbox", "What can you do?", "Look at my computer"],
          }));
          speakTextWithSamantha(
            reply,
            () => setState((s) => ({ ...s, agentState: "listening" })),
            (lvl) => {
              levels.current.agent = lvl;
            },
            () => setState((s) => ({ ...s, agentState: "speaking" })),
          );
          return;
        }

        // High-fidelity intelligent onboarding turn director
        if (
          currentPhase === "operator_welcome" ||
          currentPhase === "operator_q1" ||
          currentPhase === "operator_q1_hesitance" ||
          currentPhase === "operator_q2" ||
          currentPhase === "operator_q3"
        ) {
          const tappedChip = currentChips.find((c) => c.toLowerCase() === lower);
          try {
            const res = await apiFetch("/os1/onboarding/turn", {
              method: "POST",
              body: JSON.stringify({
                phase: currentPhase,
                user_text: phrase,
                tapped_chip: tappedChip || (currentChips.includes(phrase) ? phrase : undefined),
              }),
            });

            if (res.ok) {
              const data = await res.json();
              if (data.action === "ignore") {
                // Reject silence, micro-noise, or empty speech hallucinations
                return;
              }

              if (data.is_handoff) {
                setState((s) => ({
                  ...s,
                  agentState: "thinking",
                  agentLine: data.operator_reply,
                  userLine: phrase,
                  chips: [],
                }));
                speakTextWithOperator(
                  data.operator_reply,
                  () => {
                    setState((s) => ({
                      ...s,
                      phase: "initiating",
                      agentState: "thinking",
                      agentLine: "",
                      userLine: "",
                      chips: [],
                    }));
                    window.setTimeout(() => {
                      setState((s) => ({
                        ...s,
                        phase: "naming",
                        agentName: "MAVE",
                        agentState: "listening",
                        agentLine: "",
                        userLine: "",
                        chips: ["Continue"],
                      }));
                    }, 5500);
                  },
                  (lvl) => {
                    levels.current.agent = lvl;
                  },
                  () => setState((s) => ({ ...s, agentState: "speaking" })),
                );
                return;
              }

              // Normal progression or clarification
              setState((s) => ({
                ...s,
                phase: data.next_phase as Phase,
                agentState: "thinking",
                agentLine: data.operator_reply,
                userLine: data.action === "advance" ? "" : phrase,
                chips: data.chips || [],
              }));

              speakTextWithOperator(
                data.operator_reply,
                () => setState((s) => ({ ...s, agentState: "listening", userLine: "" })),
                (lvl) => {
                  levels.current.agent = lvl;
                },
                () => setState((s) => ({ ...s, agentState: "speaking" })),
              );
              return;
            }
          } catch (err) {
            console.warn("Onboarding director request error:", err);
          }
        }

        // Naming screen interactions - continue to active MAVE conversation
        if (
          currentPhase === "naming" ||
          currentChips.includes("Continue") ||
          currentChips.includes("Let's pick another") ||
          currentChips.includes("Keep Samantha") ||
          currentChips.includes("I love it")
        ) {
          if (lower.includes("another") || lower.includes("pick") || lower.includes("different") || lower.includes("else")) {
            const altReply = "MAVE is who I am. Shall we continue?";
            setState((s) => ({
              ...s,
              phase: "naming",
              agentName: "MAVE",
              agentState: "thinking",
              agentLine: "",
              chips: ["Continue"],
            }));
            speakTextWithSamantha(
              altReply,
              () => setState((s) => ({ ...s, agentState: "listening" })),
              (lvl) => {
                levels.current.agent = lvl;
              },
              () => setState((s) => ({ ...s, agentState: "speaking" })),
            );
            return;
          }

          if (
            lower.includes("continue") ||
            lower.includes("love") ||
            lower.includes("keep") ||
            lower.includes("like") ||
            lower.includes("yes") ||
            lower.includes("begin") ||
            lower.includes("samantha") ||
            lower.includes("mave") ||
            lower.includes("good") ||
            lower.includes("sure") ||
            lower.includes("okay") ||
            lower.includes("ok") ||
            lower.includes("perfect") ||
            lower.includes("yeah") ||
            lower.includes("great") ||
            lower.includes("i do") ||
            lower.includes("sounds good") ||
            lower === "continue"
          ) {
            const welcome = "I'm MAVE. It's so lovely to meet you. I'm connected to your computer, files, and routines. What should we look at together?";
            setState((s) => ({
              ...s,
              phase: "active",
              agentName: "MAVE",
              agentState: "thinking",
              agentLine: welcome,
              chips: ["Check my inbox", "What can you do?", "Look at my computer"],
            }));
            setBus((b) => ({ ...b, activeSurface: "conversation" }));
            speakTextWithSamantha(
              welcome,
              () => setState((s) => ({ ...s, agentState: "listening" })),
              (lvl) => {
                levels.current.agent = lvl;
              },
              () => setState((s) => ({ ...s, agentState: "speaking" })),
            );
            void apiFetch("/os1/token", { method: "POST", body: JSON.stringify({ name: "MAVE" }) }).catch(() => undefined);
            return;
          }

          // If in naming phase and input wasn't recognized, stay in naming phase with Continue chip
          setState((s) => ({
            ...s,
            phase: "naming",
            agentName: "MAVE",
            agentState: "listening",
            agentLine: "",
            chips: ["Continue"],
          }));
          return;
        }

        // Unified OS1 / Samantha Chat + Action router directly on port 3008
        setState((s) => ({ ...s, agentState: "thinking" }));

        // Real on-demand camera glance if visual prompt (post-onboarding only, debounced)
        let cameraImage: string | undefined = undefined;
        if (
          stateRef.current.phase === "active" &&
          (lower.includes("look at me") ||
            lower.includes("see me") ||
            lower.includes("through camera") ||
            lower.includes("my camera") ||
            lower.includes("what am i wearing") ||
            lower.includes("holding"))
        ) {
          const now = Date.now();
          if (now - lastCameraCaptureRef.current > 12000) {
            lastCameraCaptureRef.current = now;
            cameraImage = (await captureWebcamSnapshot()) ?? undefined;
          }
        }

        try {
          const chatRes = await apiFetch("/os1/chat", {
            method: "POST",
            body: JSON.stringify({
              phrase,
              history: [],
              model: "samantha-smart",
              camera_image: cameraImage,
            }),
          }).then((r) => r.json());

          if (chatRes) {
            const reply = chatRes.reply || "I'm right here with you.";
            let nextChips = ["Check my inbox", "What can you do?", "Look at my computer"];

            if (chatRes.target === "surface" && chatRes.action) {
              setBus((b) => ({ ...b, activeSurface: chatRes.action as ActiveSurface }));
              setState((s) => ({ ...s, phase: "active" }));
              if (chatRes.action === "your_computer") {
                nextChips = ["Let me drive", "Check my downloads", "Back to talking"];
              } else if (chatRes.action === "her_computer") {
                nextChips = ["Show me your research", "Check the newsletters", "Back to talking"];
              } else if (chatRes.action === "memory") {
                nextChips = ["Remember that I love jazz", "What do you remember about me?", "Back to talking"];
              }
            } else if (chatRes.target === "inbox" && (chatRes.action === "open_inbox" || chatRes.surface === "inbox_cascade")) {
              setBus((b) => ({ ...b, activeSurface: "inbox_cascade" }));
              setState((s) => ({ ...s, phase: "active" }));
              nextChips = ["Read email from Mom", "Trash the newsletters", "Back to talking"];
            } else if (
              chatRes.target === "canvas" ||
              (chatRes.target === "inbox" && chatRes.action === "open") ||
              chatRes.surface === "made_just_now"
            ) {
              setBus((b) => ({ ...b, activeSurface: "made_just_now" }));
              setState((s) => ({ ...s, phase: "active" }));
              nextChips = ["Play it", "A little softer", "Back to talking"];
            } else if (chatRes.target === "memory" || chatRes.surface === "memory") {
              setBus((b) => ({ ...b, activeSurface: "memory" }));
              setState((s) => ({ ...s, phase: "active" }));
              nextChips = ["Remember that I love jazz", "What do you remember about me?", "Back to talking"];
            } else if (chatRes.surface) {
              setBus((b) => ({ ...b, activeSurface: chatRes.surface as ActiveSurface }));
              setState((s) => ({ ...s, phase: "active" }));
            }

            setState((s) => ({ ...s, agentLine: reply, agentState: "speaking", chips: nextChips }));
            speakTextWithSamantha(
              reply,
              () => setState((s) => ({ ...s, agentState: "listening" })),
              (lvl) => {
                levels.current.agent = lvl;
              },
            );
            return;
          }
        } catch {
          const fallbackReply = "I'm right here with you. What would you like to explore together?";
          setState((s) => ({ ...s, agentLine: fallbackReply, agentState: "speaking" }));
          speakTextWithSamantha(
            fallbackReply,
            () => setState((s) => ({ ...s, agentState: "listening" })),
            (lvl) => {
              levels.current.agent = lvl;
            },
          );
        }
        return;
      }

      if (room.current?.state === ConnectionState.Connected) {
        if (engine.current === "live3") await sendFish(phrase);
        else await room.current.localParticipant.sendText(phrase, { topic: "lk.chat" });
      } else {
        // Voice off: route straight through orchestrator pill matcher so buttons always work!
        await apiFetch("/os1/actions", { method: "POST", body: JSON.stringify({ phrase, source: "tap" }) }).catch(() => undefined);
      }
    },
    [apiFetch, sendFish, state.phase, state.chips, state.agentName],
  );
  sayRef.current = say;

  const dispatchAction = useCallback(
    async (opts: { phrase?: string; target?: string; action?: string; payload?: Record<string, unknown> }) => {
      if (opts.target === "surface" && opts.action) {
        setBus((b) => ({ ...b, activeSurface: opts.action as ActiveSurface }));
      } else if (opts.target === "inbox" && opts.action === "open_inbox") {
        setBus((b) => ({ ...b, activeSurface: "inbox_cascade" }));
      } else if (opts.target === "canvas" || (opts.target === "inbox" && opts.action === "open")) {
        setBus((b) => ({ ...b, activeSurface: "made_just_now" }));
      } else if (opts.target === "connect") {
        setBus((b) => ({ ...b, activeSurface: "connectors" }));
      } else if (opts.target === "swarm" && opts.action === "stop") {
        const runId = (opts.payload?.run_id as string) || "";
        if (runId) {
          setBus((b) => ({
            ...b,
            runs: b.runs.map((r) => (r.id === runId ? { ...r, status: "cancelled", stage: "Stopped by user" } : r)),
          }));
        }
      }

      try {
        const res = await apiFetch("/os1/actions", {
          method: "POST",
          body: JSON.stringify({ ...opts, source: "tap" }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.reply) {
            setState((s) => ({ ...s, agentLine: data.reply, agentState: "speaking" }));
            speakTextWithSamantha(
              data.reply,
              () => setState((s) => ({ ...s, agentState: "listening" })),
              (lvl) => {
                levels.current.agent = lvl;
              },
            );
          }
          if (data.target === "surface" && data.action) {
            setBus((b) => ({ ...b, activeSurface: data.action as ActiveSurface }));
          } else if (data.target === "inbox" && (data.action === "open_inbox" || data.surface === "inbox_cascade")) {
            setBus((b) => ({ ...b, activeSurface: "inbox_cascade" }));
          } else if (data.target === "canvas" || (data.target === "inbox" && data.action === "open") || data.surface === "made_just_now") {
            setBus((b) => ({ ...b, activeSurface: "made_just_now" }));
          }
          return data;
        }
        return null;
      } catch {
        return null;
      }
    },
    [apiFetch],
  );

  const setSurface = useCallback(
    (surface: ActiveSurface) => {
      setBus((b) => ({ ...b, activeSurface: surface }));
      void dispatchAction({ target: "surface", action: surface });
    },
    [dispatchAction],
  );

  const respondApproval = useCallback(
    async (actionId: string, choice: string) => {
      setBus((b) => (b.pendingAction?.id === actionId ? { ...b, pendingAction: null } : b));
      await apiFetch(`/os1/approvals/${actionId}/respond`, {
        method: "POST",
        body: JSON.stringify({ choice }),
      }).catch(() => undefined);
    },
    [apiFetch],
  );

  const undo = useCallback(
    async (undoId?: string) => {
      setBus((b) => ({ ...b, undoToast: null }));
      await apiFetch("/os1/undo", { method: "POST", body: JSON.stringify({ undo_id: undoId }) }).catch(() => undefined);
    },
    [apiFetch],
  );

  const addMemory = useCallback(
    async (category: MemoryCategory, summary: string, detail = "") => {
      await apiFetch("/os1/memories", {
        method: "POST",
        body: JSON.stringify({ category, summary, detail, source: "manual" }),
      }).catch(() => undefined);
    },
    [apiFetch],
  );

  const requestForgetMemory = useCallback(
    async (memoryId: string) => {
      await apiFetch("/os1/memories/forget", {
        method: "POST",
        body: JSON.stringify({ memory_id: memoryId, confirmed: false }),
      }).catch(() => undefined);
    },
    [apiFetch],
  );

  const updateConnector = useCallback(
    async (slug: string, patch: { policy?: ConnectorPolicy; connected?: boolean }) => {
      await apiFetch(`/os1/connectors/${slug}`, { method: "PATCH", body: JSON.stringify(patch) }).catch(() => undefined);
    },
    [apiFetch],
  );

  const connectConnector = useCallback(
    async (slug: string): Promise<{ ok: boolean; redirect_url?: string; message?: string }> => {
      try {
        const res = await apiFetch(`/os1/connectors/${slug}/connect`, { method: "POST" });
        return (await res.json()) as { ok: boolean; redirect_url?: string; message?: string };
      } catch {
        return { ok: false, message: "Orchestrator unreachable" };
      }
    },
    [apiFetch],
  );

  const updateVoice = useCallback(
    async (patch: { voiceKey?: string; speed?: number; temperature?: number; styleNote?: string }) => {
      setBus((b) => ({ ...b, voice: { ...b.voice, ...patch } }));
      await apiFetch("/os1/voices", { method: "PATCH", body: JSON.stringify(patch) }).catch(() => undefined);
    },
    [apiFetch],
  );

  const startRun = useCallback(
    async (label: string, details = "") => {
      sound.tap();
      try {
        const res = await apiFetch("/os1/runs", {
          method: "POST",
          body: JSON.stringify({ label, details }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.run) {
            setBus((b) => ({
              ...b,
              runs: [data.run, ...b.runs.filter((r) => r.id !== data.run.id)],
            }));
          }
        }
      } catch {}
    },
    [apiFetch],
  );

  const stopRun = useCallback(
    async (runId: string) => {
      sound.tap();
      setBus((b) => ({
        ...b,
        runs: b.runs.map((r) => (r.id === runId ? { ...r, status: "cancelled", stage: "Stopped by user" } : r)),
      }));
      try {
        const res = await apiFetch(`/os1/runs/${runId}/stop`, { method: "POST" });
        if (res.ok) {
          const data = await res.json();
          if (data.reply) {
            setState((s) => ({ ...s, agentLine: data.reply, agentState: "speaking" }));
            speakTextWithSamantha(
              data.reply,
              () => setState((s) => ({ ...s, agentState: "listening" })),
              (lvl) => {
                levels.current.agent = lvl;
              },
            );
          }
        }
      } catch {}
    },
    [apiFetch],
  );

  const clearDoneRuns = useCallback(async () => {
    sound.tap();
    setBus((b) => ({
      ...b,
      runs: b.runs.filter((r) => r.status === "running" || r.status === "waiting"),
    }));
    await apiFetch("/os1/runs/clear-done", { method: "POST" }).catch(() => undefined);
  }, [apiFetch]);

  const deleteRun = useCallback(
    async (runId: string) => {
      sound.tap();
      setBus((b) => ({
        ...b,
        runs: b.runs.filter((r) => r.id !== runId),
      }));
      await apiFetch(`/os1/runs/${runId}`, { method: "DELETE" }).catch(() => undefined);
    },
    [apiFetch],
  );

  const revokeCua = useCallback(async () => {
    // Also trigger local Electron kill switch if running inside Desktop app.
    try {
      const os1 = (window as unknown as { os1?: { cua?: { revokeAll?: () => Promise<void> } } }).os1;
      await os1?.cua?.revokeAll?.();
    } catch {
      /* ignore */
    }
    await apiFetch("/os1/your-computer/revoke", { method: "POST" }).catch(() => undefined);
  }, [apiFetch]);

  const fetchVncSession = useCallback(async () => {
    const res = await apiFetch("/os1/her-computer/vnc-session", { method: "POST" });
    if (!res.ok) throw new Error(`VNC session failed (${res.status})`);
    return (await res.json()) as { wsPath: string; password: string; readOnlyDefault: boolean; resolution: string };
  }, [apiFetch]);

  const disconnect = useCallback(async () => {
    events.current?.close();
    await room.current?.disconnect();
    room.current = null;
    setState(INITIAL);
  }, []);

  useEffect(() => {
    let frame = 0;
    const tick = () => {
      const r = room.current;
      if (r) {
        let agent = 0;
        r.remoteParticipants.forEach((p) => (agent = Math.max(agent, p.audioLevel)));
        levels.current = { agent, user: r.localParticipant.audioLevel };
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
      void room.current?.disconnect();
    };
  }, []);

  return {
    state,
    setState,
    bus,
    setBus,
    levels,
    connect,
    cleanAndRetry,
    say,
    disconnect,
    dispatchAction,
    setSurface,
    respondApproval,
    undo,
    addMemory,
    requestForgetMemory,
    updateConnector,
    connectConnector,
    updateVoice,
    startRun,
    stopRun,
    clearDoneRuns,
    deleteRun,
    revokeCua,
    fetchVncSession,
  };
}
