import { type FormEvent, useState } from "react";
import { SayChips } from "../components/SayChips";
import type { ConnectorItem, ConnectorPolicy, MemoryCategory, MemoryItem, VoiceSettings } from "../types";
import { resolveHelloVoice } from "../useOs1";

const POLICY_CYCLE: ConnectorPolicy[] = ["full_access", "ask_before_write", "read_only", "ask_every_time"];

/**
 * Paper 13 — Connectors: spoken status ("Mail · asks before sending") instead of toggle clutter,
 * plus live policy changes and Composio Connect Link flow.
 */
export function ConnectorsSurface({
  connectors,
  onUpdate,
  onConnect,
  onBack,
}: {
  connectors: ConnectorItem[];
  onUpdate: (slug: string, patch: { policy?: ConnectorPolicy; connected?: boolean }) => void;
  onConnect: (slug: string) => Promise<{ ok: boolean; redirect_url?: string; message?: string }>;
  onBack: () => void;
}) {
  const [notice, setNotice] = useState<string | null>(null);

  const cyclePolicy = (c: ConnectorItem) => {
    const next = POLICY_CYCLE[(POLICY_CYCLE.indexOf(c.policy) + 1) % POLICY_CYCLE.length];
    onUpdate(c.slug, { policy: next });
  };

  const handleConnect = async (slug: string) => {
    const res = await onConnect(slug);
    if (res.ok && res.redirect_url) {
      window.open(res.redirect_url, "_blank", "noopener");
      setNotice(`Opened Connect Link for ${slug}.`);
    } else {
      setNotice(res.message || `Composio not yet linked for ${slug}.`);
    }
    window.setTimeout(() => setNotice(null), 4000);
  };

  return (
    <div className="os1-surface-container">
      <div className="os1-surface-header">
        <div>
          <div className="os1-label" style={{ color: "var(--on-coral-dim)" }}>
            13 · Connectors · Composio
          </div>
          <h2 className="os1-surface-title">What she can reach</h2>
        </div>
        <button type="button" className="os1-pill" onClick={onBack}>
          Back to talking
        </button>
      </div>

      <div className="os1-paper-card os1-scroll" style={{ padding: "12px 26px", display: "grid", alignContent: "start" }}>
        {connectors.map((c, idx) => (
          <div
            key={c.slug}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 16,
              flexWrap: "wrap",
              padding: "18px 0",
              borderBottom: idx < connectors.length - 1 ? "1px solid var(--ink-faint)" : "none",
            }}
          >
            <div>
              <div style={{ font: "400 20px/1.2 var(--font-sans)", color: "var(--ink)" }}>{c.spoken_status}</div>
              <div className="os1-mono" style={{ fontSize: 11, color: "var(--ink-dim)", marginTop: 4 }}>
                {c.slug} {c.account_label ? `· ${c.account_label}` : ""}
              </div>
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <button type="button" className="os1-pill-ink" onClick={() => cyclePolicy(c)}>
                Change rule
              </button>
              {!c.connected ? (
                <button type="button" className="os1-pill-ink primary" onClick={() => void handleConnect(c.slug)}>
                  Connect
                </button>
              ) : (
                <button type="button" className="os1-pill-ink" onClick={() => onUpdate(c.slug, { connected: false })}>
                  Disconnect
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <div style={{ textAlign: "center", color: "var(--on-coral-dim)", fontSize: 14 }}>
        {notice ?? "Policy changes apply immediately at runtime. Composio Firewall is enabled."}
      </div>
    </div>
  );
}

/**
 * Paper 14 — Voice: two-voice presets (Warm / Bright / Grounded Drama 3) + spoken warmth & pace tweaks.
 */
export function VoiceSurface({
  voice,
  onUpdate,
  onSay,
  onBack,
}: {
  voice: VoiceSettings;
  onUpdate: (patch: Partial<VoiceSettings>) => void;
  onSay: (phrase: string) => void;
  onBack: () => void;
}) {
  const presets = [
    { key: "voice_1_warm", name: "Voice I", desc: "Warm · unhurried · Fish Drama 3", speed: 0.96, temperature: 0.72 },
    { key: "voice_2_bright", name: "Voice II", desc: "Bright · lively · Fish Drama 3", speed: 1.05, temperature: 0.65 },
    { key: "voice_male", name: "Voice III", desc: "Grounded · calm · Fish Drama 3", speed: 0.97, temperature: 0.68 },
  ];

  const playVoiceSample = (name: string, speed: number, _temp: number) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(`This is ${name}. I'm right here with you.`);
    const voice = resolveHelloVoice();
    if (voice) utt.voice = voice;
    utt.rate = Math.max(0.75, Math.min(1.3, speed));
    utt.pitch = 1.0;
    window.speechSynthesis.speak(utt);
  };

  const handleSelectPreset = (p: (typeof presets)[0]) => {
    onUpdate({ voiceKey: p.key, speed: p.speed, temperature: p.temperature });
    playVoiceSample(p.name, p.speed, p.temperature);
  };

  return (
    <div className="os1-surface-container">
      <div className="os1-surface-header">
        <div>
          <div className="os1-label" style={{ color: "var(--on-coral-dim)" }}>
            14 · Voice
          </div>
          <h2 className="os1-surface-title">How she sounds</h2>
        </div>
        <button type="button" className="os1-pill" onClick={onBack}>
          Back to talking
        </button>
      </div>

      <div style={{ display: "grid", gap: 20, alignContent: "start" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 200px), 1fr))", gap: 14 }}>
          {presets.map((p) => {
            const active = voice.voiceKey === p.key;
            return (
              <button
                key={p.key}
                type="button"
                onClick={() => handleSelectPreset(p)}
                className={active ? "os1-paper-card" : "os1-glass"}
                style={{
                  padding: 24,
                  textAlign: "left",
                  cursor: "pointer",
                  display: "grid",
                  gap: 8,
                  border: active ? "2px solid var(--paper)" : undefined,
                }}
              >
                <div className="os1-mono" style={{ fontSize: 11, color: active ? "var(--coral)" : "var(--on-coral-dim)" }}>
                  {active ? "● ACTIVE" : "PRESET"}
                </div>
                <div style={{ font: "300 28px var(--font-sans)" }}>{p.name}</div>
                <div style={{ font: "300 14px var(--font-sans)", opacity: 0.78 }}>{p.desc}</div>
              </button>
            );
          })}
        </div>

        <div className="os1-paper-card" style={{ padding: 26, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))", gap: 24 }}>
          <label style={{ display: "grid", gap: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span className="os1-label" style={{ color: "var(--ink-dim)" }}>
                Pace
              </span>
              <span className="os1-mono">{voice.speed.toFixed(2)}×</span>
            </div>
            <input
              type="range"
              min={0.82}
              max={1.18}
              step={0.02}
              value={voice.speed}
              onChange={(e) => onUpdate({ speed: Number(e.target.value) })}
              style={{ accentColor: "var(--coral)" }}
            />
          </label>
          <label style={{ display: "grid", gap: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span className="os1-label" style={{ color: "var(--ink-dim)" }}>
                Warmth / expressiveness
              </span>
              <span className="os1-mono">{Math.round(voice.temperature * 100)}%</span>
            </div>
            <input
              type="range"
              min={0.45}
              max={0.95}
              step={0.02}
              value={voice.temperature}
              onChange={(e) => onUpdate({ temperature: Number(e.target.value) })}
              style={{ accentColor: "var(--coral)" }}
            />
          </label>
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "center" }}>
        <SayChips chips={["A little warmer", "Slow down", "A little faster", "Back to talking"]} onSay={onSay} />
      </div>
    </div>
  );
}

const MEMORY_META: { key: MemoryCategory; label: string; color: string }[] = [
  { key: "people", label: "People", color: "var(--coral)" },
  { key: "places", label: "Places", color: "var(--teal)" },
  { key: "things_you_love", label: "Things you love", color: "var(--mustard)" },
  { key: "things_that_hurt", label: "Things that hurt", color: "var(--plum)" },
  { key: "promises", label: "Promises", color: "var(--cobalt)" },
];

/**
 * Paper 15 — Memory Ledger: 5 warm categories with real hard-delete ("Yes, forget it" cascade).
 */
export function MemorySurface({
  memories,
  onAdd,
  onForget,
  onBack,
}: {
  memories: MemoryItem[];
  onAdd: (category: MemoryCategory, summary: string) => void;
  onForget: (memoryId: string) => void;
  onBack: () => void;
}) {
  const [cat, setCat] = useState<MemoryCategory | "all">("all");
  const [draft, setDraft] = useState("");
  const [draftCat, setDraftCat] = useState<MemoryCategory>("things_you_love");

  const filtered = cat === "all" ? memories : memories.filter((m) => m.category === cat);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    onAdd(draftCat, draft.trim());
    setDraft("");
  };

  return (
    <div className="os1-surface-container" style={{ gridTemplateRows: "auto auto 1fr auto", gap: 16 }}>
      <div className="os1-surface-header">
        <div>
          <div className="os1-label" style={{ color: "var(--on-coral-dim)" }}>
            15 · Memory · Really gone when forgotten
          </div>
          <h2 className="os1-surface-title">What she remembers</h2>
        </div>
        <button type="button" className="os1-pill" onClick={onBack}>
          Back to talking
        </button>
      </div>

      {/* Category filter pills */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          className="os1-pill"
          style={{ background: cat === "all" ? "var(--paper)" : undefined, color: cat === "all" ? "var(--coral-deep)" : undefined }}
          onClick={() => setCat("all")}
        >
          All ({memories.length})
        </button>
        {MEMORY_META.map((m) => (
          <button
            key={m.key}
            type="button"
            className="os1-pill"
            style={{ background: cat === m.key ? "var(--paper)" : undefined, color: cat === m.key ? "var(--coral-deep)" : undefined }}
            onClick={() => setCat(m.key)}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Ledger list */}
      <div
        className="os1-scroll"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(clamp(260px, 100%, 340px), 1fr))",
          gap: 14,
          alignContent: "start",
        }}
      >
        {filtered.length === 0 ? (
          <div className="os1-glass" style={{ gridColumn: "1 / -1", padding: 32, textAlign: "center" }}>
            <p className="os1-lead" style={{ margin: 0 }}>
              Nothing saved here yet.
            </p>
            <p style={{ margin: "6px 0 0", color: "var(--on-coral-dim)" }}>
              Moments worth keeping appear here automatically as you talk — or add one below.
            </p>
          </div>
        ) : (
          filtered.map((mem) => {
            const meta = MEMORY_META.find((m) => m.key === mem.category) ?? MEMORY_META[2];
            const dateStr = new Date(mem.created_at * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" });
            return (
              <div key={mem.id} className="os1-paper-card" style={{ padding: "18px 20px", display: "grid", gap: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="os1-mono" style={{ fontSize: 10, color: meta.color }}>
                    ● {meta.label}
                  </span>
                  <span className="os1-mono" style={{ fontSize: 10, color: "var(--ink-dim)" }}>
                    {dateStr}
                  </span>
                </div>
                <div style={{ font: "400 16px/1.4 var(--font-sans)", color: "var(--ink)" }}>{mem.summary}</div>
                {mem.detail && <div style={{ font: "300 13px/1.45 var(--font-sans)", color: "var(--ink-dim)" }}>{mem.detail}</div>}
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <button
                    type="button"
                    className="os1-pill-ink"
                    style={{ fontSize: 12, padding: "5px 12px" }}
                    onClick={() => onForget(mem.id)}
                  >
                    Forget…
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Add a moment directly */}
      <form onSubmit={submit} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <select
          value={draftCat}
          onChange={(e) => setDraftCat(e.target.value as MemoryCategory)}
          style={{
            padding: "10px 14px",
            borderRadius: 999,
            border: "1px solid rgba(255,253,249,0.34)",
            background: "rgba(56,20,10,0.28)",
            color: "var(--paper)",
            font: "400 13px var(--font-sans)",
          }}
        >
          {MEMORY_META.map((m) => (
            <option key={m.key} value={m.key} style={{ color: "#38281e" }}>
              {m.label}
            </option>
          ))}
        </select>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add something you want her to remember…"
          style={{
            flex: "1 1 200px",
            minWidth: 160,
            padding: "10px 18px",
            borderRadius: 999,
            border: "1px solid rgba(255,253,249,0.34)",
            background: "rgba(255,253,249,0.12)",
            color: "var(--paper)",
            font: "300 15px var(--font-sans)",
            outline: "none",
          }}
        />
        <button type="submit" className="os1-pill">
          Remember
        </button>
      </form>
    </div>
  );
}
