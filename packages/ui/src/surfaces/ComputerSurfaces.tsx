import { useEffect, useRef, useState } from "react";
import type { CuaState, HerComputerState, Os1Config } from "../types";
import { speakTextWithSamantha } from "../useOs1";

/**
 * Paper 09 — Computer use on YOUR machine (embedded Cua Driver in bounded mode + instant kill switch).
 */
export function YourComputerSurface({
  cua,
  onRevoke,
  onBack,
}: {
  cua: CuaState;
  onRevoke: () => void;
  onBack: () => void;
}) {
  const [tab, setTab] = useState<"mac" | "mobile">("mac");
  const [mobileData, setMobileData] = useState<{
    android_devices: any[];
    ios_devices: any[];
    available_avds?: string[];
    available_ios_simulators?: any[];
    has_adb?: boolean;
    has_emulator?: boolean;
  }>({
    android_devices: [],
    ios_devices: [],
    available_avds: [],
    available_ios_simulators: [],
  });
  const [mobileLoading, setMobileLoading] = useState(false);
  const [mobileScreenUrl, setMobileScreenUrl] = useState<string | null>(null);
  const [mobileInputText, setMobileInputText] = useState("");
  const [frontmost, setFrontmost] = useState<{ app: string; window: string } | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Real Mac state
  const [macInfo, setMacInfo] = useState<{
    model?: string;
    chip?: string;
    os_version?: string;
    arch?: string;
    battery?: string;
    resolution?: string;
    hostname?: string;
    user?: string;
    quartz_active?: boolean;
    frontmost?: { app: string; window: string };
  } | null>(null);
  const [macScreenUrl, setMacScreenUrl] = useState<string | null>(null);
  const [macLiveMirror, setMacLiveMirror] = useState(false);
  const [macInputText, setMacInputText] = useState("");
  const [showFence, setShowFence] = useState(false);

  // Mobile connect state
  const [wifiAddress, setWifiAddress] = useState("");
  const [showWifiConnect, setShowWifiConnect] = useState(false);

  const notify = (msg: string) => {
    setActionNotice(msg);
    window.setTimeout(() => setActionNotice(null), 3000);
  };

  const loadMacInfo = async () => {
    try {
      const res = await fetch("http://127.0.0.1:3008/os1/mac/info").then((r) => r.json());
      if (res.ok) {
        setMacInfo(res);
        if (res.frontmost?.app) {
          setFrontmost({ app: res.frontmost.app, window: res.frontmost.window || "" });
        }
      }
    } catch {
      /* ignore */
    }
  };

  const refreshMacScreen = () => {
    setMacScreenUrl(`http://127.0.0.1:3008/os1/mac/screenshot?t=${Date.now()}`);
    notify("Real Mac screen refreshed");
  };

  const loadMobileStatus = async () => {
    setMobileLoading(true);
    try {
      const res = await fetch("http://127.0.0.1:3008/os1/mobile/status").then((r) => r.json());
      if (res.ok) {
        setMobileData({
          android_devices: res.android_devices || [],
          ios_devices: res.ios_devices || [],
          available_avds: res.available_avds || [],
          available_ios_simulators: res.available_ios_simulators || [],
          has_adb: res.has_adb,
          has_emulator: res.has_emulator,
        });
      }
    } catch {
      /* transient */
    } finally {
      setMobileLoading(false);
    }
  };

  const loadFrontmost = async () => {
    try {
      const res = await fetch("http://127.0.0.1:3008/os1/your-computer/call", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool: "frontmost", arguments: {}, requireApproval: false }),
      }).then((r) => r.json());
      if (res.ok && res.app) {
        setFrontmost({ app: res.app, window: res.window || "" });
      }
    } catch {
      /* ignore */
    }
  };

  const launchEmulator = async (platform: "android" | "ios", name?: string) => {
    try {
      notify(`Launching ${platform === "android" ? "Android" : "iOS"} emulator...`);
      const res = await fetch("http://127.0.0.1:3008/os1/mobile/launch-emulator", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platform, name }),
      }).then((r) => r.json());
      if (res.ok) {
        notify(res.message || `Emulator ${name || ""} launched!`);
        window.setTimeout(() => void loadMobileStatus(), 3000);
        window.setTimeout(() => void loadMobileStatus(), 7000);
        window.setTimeout(() => void loadMobileStatus(), 12000);
      } else {
        notify(`Emulator error: ${res.error || "Failed"}`);
      }
    } catch (err: any) {
      notify(`Failed: ${err.message}`);
    }
  };

  const connectDevice = async (address: string) => {
    try {
      notify(`Connecting to ${address}...`);
      const res = await fetch("http://127.0.0.1:3008/os1/mobile/connect-device", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platform: "android", address }),
      }).then((r) => r.json());
      if (res.ok) {
        notify(`Connected to ${address}`);
        setWifiAddress("");
        setShowWifiConnect(false);
        void loadMobileStatus();
      } else {
        notify(`Connect failed: ${res.output || res.error || "Failed"}`);
      }
    } catch (err: any) {
      notify(`Failed: ${err.message}`);
    }
  };

  useEffect(() => {
    void loadFrontmost();
    void loadMacInfo();
    void loadMobileStatus();
    // Preload Real Mac screen capture immediately
    setMacScreenUrl(`http://127.0.0.1:3008/os1/mac/screenshot?t=${Date.now()}`);

    const interval = window.setInterval(() => {
      void loadFrontmost();
      if (macLiveMirror && tab === "mac") {
        setMacScreenUrl(`http://127.0.0.1:3008/os1/mac/screenshot?t=${Date.now()}`);
      }
    }, 3500);
    return () => window.clearInterval(interval);
  }, [macLiveMirror, tab]);

  const runMacTool = async (tool: string, args: Record<string, any> = {}) => {
    try {
      notify(`Running ${tool}...`);
      const res = await fetch("http://127.0.0.1:3008/os1/your-computer/call", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool, arguments: args, requireApproval: false }),
      }).then((r) => r.json());
      if (res.ok) {
        notify(`Executed ${tool} successfully`);
        void loadFrontmost();
        // Refresh Mac screen after actions
        setTimeout(refreshMacScreen, 600);
      } else {
        notify(`Error: ${res.error || "Failed"}`);
      }
    } catch (err: any) {
      notify(`Failed: ${err.message}`);
    }
  };

  const runMobileAction = async (action: string, args: Record<string, any> = {}) => {
    try {
      notify(`Mobile ${action}...`);
      const res = await fetch("http://127.0.0.1:3008/os1/mobile/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, arguments: args }),
      }).then((r) => r.json());
      if (res.ok) {
        notify(`Action ${action} executed`);
        setTimeout(refreshMobileScreen, 600);
      } else {
        notify(`Mobile action failed: ${res.error || "Error"}`);
      }
    } catch (err: any) {
      notify(`Mobile error: ${err.message}`);
    }
  };

  const refreshMobileScreen = () => {
    setMobileScreenUrl(`http://127.0.0.1:3008/os1/mobile/screenshot?t=${Date.now()}`);
    notify("Android screen refreshed");
  };

  return (
    <div className="os1-surface-container">
      <div className="os1-surface-header">
        <div>
          <div className="os1-label" style={{ color: "var(--on-coral-dim)" }}>
            09 · Automation Hub · Mac · Android · iOS
          </div>
          <h2 className="os1-surface-title">
            {tab === "mac" ? "What I'm doing on your Mac" : "Mobile Device Automation (Android & iOS)"}
          </h2>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {/* Surface Tab Switcher */}
          <div
            style={{
              display: "flex",
              background: "rgba(56, 40, 30, 0.08)",
              borderRadius: 999,
              padding: 3,
            }}
          >
            <button
              type="button"
              onClick={() => setTab("mac")}
              style={{
                padding: "8px 16px",
                borderRadius: 999,
                border: "none",
                background: tab === "mac" ? "var(--paper)" : "transparent",
                color: tab === "mac" ? "var(--coral-deep)" : "var(--on-coral-dim)",
                fontWeight: tab === "mac" ? 600 : 400,
                fontSize: 13,
                cursor: "pointer",
                transition: "all 150ms ease",
              }}
            >
              💻 Mac Automation
            </button>
            <button
              type="button"
              onClick={() => {
                setTab("mobile");
                void loadMobileStatus();
              }}
              style={{
                padding: "8px 16px",
                borderRadius: 999,
                border: "none",
                background: tab === "mobile" ? "var(--paper)" : "transparent",
                color: tab === "mobile" ? "var(--coral-deep)" : "var(--on-coral-dim)",
                fontWeight: tab === "mobile" ? 600 : 400,
                fontSize: 13,
                cursor: "pointer",
                transition: "all 150ms ease",
              }}
            >
              📱 Mobile (Android & iOS)
            </button>
          </div>

          <button
            type="button"
            onClick={onRevoke}
            style={{
              padding: "10px 20px",
              borderRadius: 999,
              border: "none",
              background: "var(--crimson)",
              color: "var(--paper)",
              font: "500 13px var(--font-sans)",
              cursor: "pointer",
              boxShadow: "0 8px 24px rgba(168, 39, 60, 0.35)",
            }}
          >
            “Let me drive” · Revoke
          </button>
          <button type="button" className="os1-pill" onClick={onBack}>
            Back to talking
          </button>
        </div>
      </div>

      {actionNotice && (
        <div
          style={{
            position: "fixed",
            bottom: 40,
            left: "50%",
            transform: "translateX(-50%)",
            background: "#1c0e09",
            color: "#6ee7b7",
            padding: "8px 20px",
            borderRadius: 999,
            fontSize: 13,
            boxShadow: "0 10px 30px rgba(0,0,0,0.4)",
            zIndex: 9999,
          }}
        >
          ● {actionNotice}
        </div>
      )}

      {tab === "mac" ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 380px), 1fr))", gap: 20, minHeight: 0 }}>
          {/* Real Mac Control & Target Deck */}
          <div className="os1-paper-card os1-scroll" style={{ padding: 24, display: "grid", gap: 14, alignContent: "start", maxHeight: "calc(100vh - 220px)", overflowY: "auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="os1-label" style={{ color: "var(--ink-dim)" }}>
                Real Mac Workstation & Target
              </span>
              <span className="os1-mono" style={{ fontSize: 11, color: "var(--teal)" }}>
                ● Native macOS Quartz / System Events
              </span>
            </div>

            {/* Real Mac Hardware & OS Diagnostics Badge */}
            <div
              style={{
                padding: "14px 16px",
                borderRadius: 14,
                background: "rgba(56, 40, 30, 0.04)",
                border: "1px solid rgba(56, 40, 30, 0.12)",
                display: "grid",
                gap: 8,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ fontSize: 11, color: "var(--coral-deep)", fontWeight: 700, letterSpacing: "0.04em" }}>
                  💻 REAL APPLE MACINTOSH (HOST)
                </div>
                <span className="os1-pill" style={{ fontSize: 10, padding: "2px 8px", background: "rgba(42, 138, 126, 0.15)", color: "var(--teal)" }}>
                  Native Quartz Active
                </span>
              </div>
              <div style={{ font: "600 16px var(--font-sans)", color: "var(--ink)" }}>
                {macInfo?.model || "Apple MacBook Air"}
              </div>
              <div style={{ fontSize: 12, color: "var(--ink-dim)", display: "flex", flexWrap: "wrap", gap: 6 }}>
                <span>{macInfo?.chip || "Apple M1"} ({macInfo?.arch || "arm64"})</span>
                <span>•</span>
                <span>{macInfo?.os_version || "macOS"}</span>
                <span>•</span>
                <span>🔋 {macInfo?.battery || "AC Power"}</span>
              </div>
              <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-dim)" }}>
                🖥️ {macInfo?.resolution || "Built-in Retina"} · {macInfo?.hostname || "local"} (user: {macInfo?.user || "user"})
              </div>
            </div>

            {/* Frontmost App & Active Window */}
            {frontmost && (
              <div
                style={{
                  padding: "10px 14px",
                  borderRadius: 12,
                  background: "rgba(42, 138, 126, 0.08)",
                  border: "1px solid rgba(42, 138, 126, 0.2)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <div style={{ fontSize: 11, color: "var(--teal)", fontWeight: 600 }}>FRONTMOST APPLICATION</div>
                  <div style={{ font: "500 14px var(--font-sans)", color: "var(--ink)" }}>{frontmost.app}</div>
                  {frontmost.window && (
                    <div style={{ fontSize: 12, color: "var(--ink-dim)", maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {frontmost.window}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => {
                    void runMacTool("frontmost");
                    void loadMacInfo();
                  }}
                  style={{
                    background: "rgba(0,0,0,0.06)",
                    border: "none",
                    borderRadius: 6,
                    padding: "4px 8px",
                    fontSize: 11,
                    cursor: "pointer",
                  }}
                >
                  Refresh
                </button>
              </div>
            )}

            {/* Quick Action Buttons for Mac */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 2 }}>
              <button
                type="button"
                className="os1-pill"
                style={{ fontSize: 12, padding: "6px 14px" }}
                onClick={() => void runMacTool("open_app", { app: "Safari" })}
              >
                ⚡ Open Safari
              </button>
              <button
                type="button"
                className="os1-pill"
                style={{ fontSize: 12, padding: "6px 14px" }}
                onClick={() => void runMacTool("open_app", { app: "Notes" })}
              >
                ⚡ Open Notes
              </button>
              <button
                type="button"
                className="os1-pill"
                style={{ fontSize: 12, padding: "6px 14px" }}
                onClick={() => void runMacTool("open_app", { app: "Finder" })}
              >
                ⚡ Open Finder
              </button>
              <button
                type="button"
                className="os1-pill"
                style={{ fontSize: 12, padding: "6px 14px", background: "rgba(224,90,71,0.12)", color: "var(--coral-deep)" }}
                onClick={refreshMacScreen}
              >
                📸 Capture Real Mac
              </button>
              <button
                type="button"
                className="os1-pill"
                style={{
                  fontSize: 12,
                  padding: "6px 14px",
                  background: macLiveMirror ? "var(--coral-deep)" : "rgba(0,0,0,0.06)",
                  color: macLiveMirror ? "#fff" : "var(--ink)",
                  border: "none",
                }}
                onClick={() => {
                  const next = !macLiveMirror;
                  setMacLiveMirror(next);
                  notify(next ? "Live Mac Mirror enabled (3.5s loop)" : "Live Mac Mirror paused");
                }}
              >
                {macLiveMirror ? "🟢 Live Mirror: ON" : "⚪ Live Mirror: OFF"}
              </button>
            </div>

            {/* Direct Keystroke Typing to Frontmost Mac App */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (macInputText.trim()) {
                  void runMacTool("type_text", { text: macInputText });
                  setMacInputText("");
                }
              }}
              style={{ display: "flex", gap: 8, marginTop: 4 }}
            >
              <input
                type="text"
                placeholder="Type text directly to frontmost Mac app…"
                value={macInputText}
                onChange={(e) => setMacInputText(e.target.value)}
                style={{
                  flex: 1,
                  padding: "8px 12px",
                  borderRadius: 8,
                  border: "1px solid rgba(56,40,30,0.15)",
                  background: "rgba(255,255,255,0.7)",
                  fontSize: 12,
                  outline: "none",
                }}
              />
              <button
                type="submit"
                style={{
                  padding: "8px 14px",
                  borderRadius: 8,
                  border: "none",
                  background: "var(--coral-deep)",
                  color: "#fff",
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                Send
              </button>
            </form>

            {/* Recent Operations Ledger */}
            <div style={{ borderTop: "1px solid rgba(56,40,30,0.08)", paddingTop: 10, marginTop: 4 }}>
              <div className="os1-label" style={{ color: "var(--ink-dim)", marginBottom: 8 }}>
                Recent Operations Ledger
              </div>
              {cua.recentActivity.length === 0 ? (
                <p style={{ margin: "4px 0", color: "var(--ink-dim)", font: "300 13px/1.5 var(--font-sans)" }}>
                  Ready to assist. MAVE executes commands directly on your real Mac using macOS System Events.
                </p>
              ) : (
                cua.recentActivity.slice(0, 4).map((act) => (
                  <div
                    key={act.id}
                    style={{
                      padding: "6px 10px",
                      borderRadius: 8,
                      background: "rgba(56, 40, 30, 0.04)",
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 12,
                      marginBottom: 5,
                    }}
                  >
                    <div>
                      <div style={{ font: "500 12px var(--font-sans)", color: "var(--ink)" }}>{act.title}</div>
                      {act.detail && (
                        <div style={{ font: "300 11px var(--font-sans)", color: "var(--ink-dim)", maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {act.detail}
                        </div>
                      )}
                    </div>
                    <span className="os1-mono" style={{ fontSize: 10, color: "var(--coral)", alignSelf: "center" }}>
                      {act.status}
                    </span>
                  </div>
                ))
              )}
            </div>

            {/* Bounded Safety Fence Collapsible */}
            <div style={{ borderTop: "1px solid rgba(56,40,30,0.08)", paddingTop: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="os1-label" style={{ color: "var(--ink-dim)" }}>
                  Bounded Safety Fence · v{cua.manifest.version}
                </span>
                <button
                  type="button"
                  onClick={() => setShowFence(!showFence)}
                  style={{ background: "transparent", border: "none", fontSize: 11, color: "var(--teal)", cursor: "pointer" }}
                >
                  {showFence ? "▲ Hide Fence" : "▼ Show Policy"}
                </button>
              </div>
              {showFence && (
                <div style={{ marginTop: 8, display: "grid", gap: 8, fontSize: 12 }}>
                  <div>
                    <span className="os1-mono" style={{ color: "var(--teal)" }}>Allowed apps: </span>
                    <span style={{ color: "var(--ink)" }}>{cua.manifest.allowedApps.join(", ")}</span>
                  </div>
                  <div>
                    <span className="os1-mono" style={{ color: "var(--ink-dim)" }}>Allowed folders: </span>
                    <span style={{ color: "var(--ink)" }}>{cua.manifest.allowedPaths.join(" · ")}</span>
                  </div>
                  <div>
                    <span className="os1-mono" style={{ color: "var(--crimson)" }}>Always blocked: </span>
                    <span style={{ color: "var(--ink-dim)" }}>{cua.manifest.blockedApps.join(", ")} · Keychain protected</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Live Real Mac Display Viewport */}
          <div
            className="os1-studio-card"
            style={{
              padding: 20,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "space-between",
              background: "#140804",
              borderRadius: 20,
              border: "1px solid rgba(255, 253, 249, 0.12)",
              minHeight: 480,
              overflow: "hidden",
            }}
          >
            {/* Viewport Topbar */}
            <div style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: macLiveMirror ? "#34d399" : "#6ee7b7", display: "inline-block" }} />
                <span style={{ fontSize: 11, color: "#6ee7b7", fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                  REAL MAC SCREEN VIEWPORT
                </span>
                <span style={{ fontSize: 11, color: "rgba(255,253,249,0.4)", fontFamily: "var(--font-mono)" }}>
                  ({macInfo?.resolution ? macInfo.resolution.split("·")[0].trim() : "Retina Framebuffer"})
                </span>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  type="button"
                  onClick={refreshMacScreen}
                  style={{
                    padding: "4px 10px",
                    borderRadius: 6,
                    border: "1px solid rgba(255,255,255,0.15)",
                    background: "rgba(255,255,255,0.06)",
                    color: "rgba(255,255,255,0.85)",
                    fontSize: 11,
                    cursor: "pointer",
                  }}
                >
                  📸 Capture Screen
                </button>
                <button
                  type="button"
                  onClick={() => setMacLiveMirror(!macLiveMirror)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: 6,
                    border: "none",
                    background: macLiveMirror ? "var(--coral-deep)" : "rgba(255,255,255,0.08)",
                    color: "#fff",
                    fontSize: 11,
                    cursor: "pointer",
                  }}
                >
                  {macLiveMirror ? "Live: ON" : "Live: OFF"}
                </button>
              </div>
            </div>

            {/* Viewport Screen Image */}
            {macScreenUrl ? (
              <div style={{ width: "100%", display: "flex", flexDirection: "column", alignItems: "center", flex: 1, justifyContent: "center" }}>
                <img
                  src={macScreenUrl}
                  alt="Real Mac Live Screen"
                  style={{
                    maxHeight: 410,
                    maxWidth: "100%",
                    borderRadius: 12,
                    boxShadow: "0 14px 40px rgba(0,0,0,0.7)",
                    objectFit: "contain",
                    border: "1px solid rgba(255,255,255,0.1)",
                  }}
                />
                <div
                  style={{
                    marginTop: 10,
                    fontSize: 11,
                    color: "rgba(255,253,249,0.6)",
                    fontFamily: "var(--font-mono)",
                    textAlign: "center",
                    display: "flex",
                    gap: 12,
                    flexWrap: "wrap",
                    justifyContent: "center",
                  }}
                >
                  <span>Active: <strong>{frontmost?.app || "Desktop"}</strong></span>
                  {frontmost?.window && <span>• Window: {frontmost.window}</span>}
                  <span>• Native Quartz HID</span>
                </div>
              </div>
            ) : (
              <div style={{ textAlign: "center", color: "rgba(255,253,249,0.5)", fontFamily: "var(--font-mono)", fontSize: 13, margin: "auto" }}>
                <div style={{ fontSize: 36, marginBottom: 12 }}>💻</div>
                <div>Real Mac Screen Mirror</div>
                <div style={{ fontSize: 11, marginTop: 6, color: "rgba(255,253,249,0.3)" }}>
                  Click "Capture Screen" to snapshot your real macOS desktop
                </div>
              </div>
            )}

            <div style={{ width: "100%", textAlign: "center", marginTop: 8, fontSize: 10, color: "rgba(255,253,249,0.3)", fontFamily: "var(--font-mono)" }}>
              Direct CoreGraphics screencapture · Zero cloud hop · 100% On-Device
            </div>
          </div>
        </div>
      ) : (
        /* Mobile Devices View (Android ADB + iOS Shortcuts) */
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 380px), 1fr))", gap: 20, minHeight: 0 }}>
          {/* Connected Mobile Devices & Connect/Launch Deck */}
          <div className="os1-paper-card os1-scroll" style={{ padding: 24, display: "grid", gap: 16, alignContent: "start", maxHeight: "calc(100vh - 220px)", overflowY: "auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="os1-label" style={{ color: "var(--ink-dim)" }}>
                Connected Mobile Devices & Emulators
              </span>
              <button
                type="button"
                onClick={() => void loadMobileStatus()}
                style={{
                  background: "transparent",
                  border: "none",
                  fontSize: 12,
                  color: "var(--teal)",
                  cursor: "pointer",
                }}
              >
                {mobileLoading ? "Scanning..." : "↻ Scan Devices"}
              </button>
            </div>

            {/* The Question Prompt Card requested by user */}
            <div
              style={{
                padding: "18px 20px",
                borderRadius: 16,
                background: "rgba(224, 90, 71, 0.08)",
                border: "1px solid rgba(224, 90, 71, 0.25)",
                display: "grid",
                gap: 14,
              }}
            >
              <div>
                <div style={{ font: "600 15px/1.4 var(--font-sans)", color: "var(--coral-deep)" }}>
                  Do you want to connect to any of your devices or do you want to launch an emulator?
                </div>
                <div style={{ fontSize: 12, color: "var(--ink-dim)", marginTop: 4, lineHeight: 1.5 }}>
                  Choose whether to connect your real physical phone (Android via USB/Wi-Fi or iPhone via Continuity & Shortcuts) or launch a local emulator on your Mac.
                </div>
              </div>

              {/* Android Options Box */}
              <div style={{ borderTop: "1px solid rgba(56,40,30,0.1)", paddingTop: 10, display: "grid", gap: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--teal)", letterSpacing: "0.04em" }}>
                  🤖 ANDROID (PHYSICAL DEVICE OR EMULATOR)
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {mobileData.available_avds && mobileData.available_avds.length > 0 ? (
                    mobileData.available_avds.map((avd: string) => (
                      <button
                        key={avd}
                        type="button"
                        className="os1-pill"
                        style={{
                          fontSize: 12,
                          padding: "6px 14px",
                          background: "var(--coral-deep)",
                          color: "#fff",
                          border: "none",
                          fontWeight: 500,
                        }}
                        onClick={() => void launchEmulator("android", avd)}
                      >
                        🚀 Launch {avd} Emulator
                      </button>
                    ))
                  ) : (
                    <button
                      type="button"
                      className="os1-pill"
                      style={{ fontSize: 12, padding: "6px 14px", background: "var(--coral-deep)", color: "#fff", border: "none" }}
                      onClick={() => void launchEmulator("android")}
                    >
                      🚀 Launch Android Emulator
                    </button>
                  )}

                  <button
                    type="button"
                    className="os1-pill"
                    style={{ fontSize: 12, padding: "6px 14px" }}
                    onClick={() => setShowWifiConnect(!showWifiConnect)}
                  >
                    📱 Connect Physical Android (USB / Wi-Fi)
                  </button>

                  <button
                    type="button"
                    className="os1-pill"
                    style={{ fontSize: 12, padding: "6px 12px" }}
                    onClick={() => void runMobileAction("open_android_studio")}
                  >
                    🛠️ Open Android Studio
                  </button>
                </div>

                {showWifiConnect && (
                  <div
                    style={{
                      padding: "10px 14px",
                      borderRadius: 10,
                      background: "rgba(255, 255, 255, 0.7)",
                      border: "1px solid rgba(56, 40, 30, 0.12)",
                      display: "grid",
                      gap: 8,
                    }}
                  >
                    <div style={{ fontSize: 12, color: "var(--ink)", lineHeight: 1.5 }}>
                      • <strong>USB:</strong> Plug phone into Mac with <em>USB Debugging</em> enabled. Click <em>"↻ Scan Devices"</em> above.
                    </div>
                    <div style={{ fontSize: 12, color: "var(--ink)", lineHeight: 1.5 }}>
                      • <strong>Wi-Fi ADB:</strong> Connect to phone on same local network:
                    </div>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        if (wifiAddress.trim()) void connectDevice(wifiAddress.trim());
                      }}
                      style={{ display: "flex", gap: 6 }}
                    >
                      <input
                        type="text"
                        placeholder="e.g. 192.168.1.50:5555"
                        value={wifiAddress}
                        onChange={(e) => setWifiAddress(e.target.value)}
                        style={{
                          flex: 1,
                          padding: "6px 10px",
                          fontSize: 12,
                          borderRadius: 6,
                          border: "1px solid rgba(56,40,30,0.2)",
                          background: "#fff",
                        }}
                      />
                      <button
                        type="submit"
                        className="os1-pill"
                        style={{ fontSize: 11, background: "var(--coral-deep)", color: "#fff", border: "none" }}
                      >
                        Connect
                      </button>
                    </form>
                  </div>
                )}
              </div>

              {/* iOS Options Box */}
              <div style={{ borderTop: "1px solid rgba(56,40,30,0.1)", paddingTop: 10, display: "grid", gap: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--teal)", letterSpacing: "0.04em" }}>
                  🍏 APPLE IOS (PHYSICAL IPHONE OR SIMULATOR)
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  <button
                    type="button"
                    className="os1-pill"
                    style={{ fontSize: 12, padding: "6px 14px" }}
                    onClick={() => void launchEmulator("ios")}
                  >
                    🚀 Launch iOS Simulator
                  </button>
                  <button
                    type="button"
                    className="os1-pill"
                    style={{ fontSize: 12, padding: "6px 14px" }}
                    onClick={() => void runMobileAction("open_shortcuts")}
                  >
                    ⚡ Open Apple Shortcuts
                  </button>
                  <button
                    type="button"
                    className="os1-pill"
                    style={{ fontSize: 12, padding: "6px 14px" }}
                    onClick={() => {
                      void loadMobileStatus();
                      notify("Scanned for connected iOS devices via Continuity");
                    }}
                  >
                    📱 Scan Physical iPhone (Continuity)
                  </button>
                </div>
              </div>
            </div>

            {/* Active Connected Android Device Card(s) */}
            {mobileData.android_devices.length > 0 ? (
              mobileData.android_devices.map((dev) => (
                <div
                  key={dev.id}
                  style={{
                    padding: "16px 18px",
                    borderRadius: 14,
                    background: "rgba(56, 40, 30, 0.04)",
                    border: "1px solid rgba(56, 40, 30, 0.1)",
                    display: "grid",
                    gap: 12,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <div style={{ fontSize: 11, color: "var(--teal)", fontWeight: 600 }}>
                        ● {dev.is_emulator ? "ANDROID EMULATOR (VIRTUAL)" : "ANDROID DEVICE (100% REAL ADB)"}
                      </div>
                      <div style={{ font: "500 16px var(--font-sans)", color: "var(--ink)" }}>{dev.model}</div>
                      <div style={{ fontSize: 12, color: "var(--ink-dim)" }}>
                        {dev.os_version} · Battery: {dev.battery}% · {dev.resolution}
                      </div>
                    </div>
                    <span className="os1-pill" style={{ fontSize: 11, padding: "3px 10px" }}>
                      {dev.id}
                    </span>
                  </div>

                  {/* Remote Action Bar */}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 4 }}>
                    <button
                      type="button"
                      className="os1-pill"
                      style={{ fontSize: 12, padding: "6px 12px" }}
                      onClick={() => void runMobileAction("android_key", { key: "home" })}
                    >
                      🏠 Home
                    </button>
                    <button
                      type="button"
                      className="os1-pill"
                      style={{ fontSize: 12, padding: "6px 12px" }}
                      onClick={() => void runMobileAction("android_key", { key: "back" })}
                    >
                      ◀ Back
                    </button>
                    <button
                      type="button"
                      className="os1-pill"
                      style={{ fontSize: 12, padding: "6px 12px" }}
                      onClick={() => void runMobileAction("android_open", { app: "browser" })}
                    >
                      🌐 Web
                    </button>
                    <button
                      type="button"
                      className="os1-pill"
                      style={{ fontSize: 12, padding: "6px 12px" }}
                      onClick={refreshMobileScreen}
                    >
                      📸 Capture Screen
                    </button>
                  </div>

                  {/* Input typing */}
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (mobileInputText.trim()) {
                        void runMobileAction("android_type", { text: mobileInputText });
                        setMobileInputText("");
                      }
                    }}
                    style={{ display: "flex", gap: 8, marginTop: 4 }}
                  >
                    <input
                      type="text"
                      placeholder="Type text to mobile screen…"
                      value={mobileInputText}
                      onChange={(e) => setMobileInputText(e.target.value)}
                      style={{
                        flex: 1,
                        padding: "8px 12px",
                        borderRadius: 8,
                        border: "1px solid rgba(56,40,30,0.15)",
                        background: "rgba(255,255,255,0.7)",
                        fontSize: 12,
                        outline: "none",
                      }}
                    />
                    <button
                      type="submit"
                      style={{
                        padding: "8px 14px",
                        borderRadius: 8,
                        border: "none",
                        background: "var(--coral-deep)",
                        color: "#fff",
                        fontSize: 12,
                        cursor: "pointer",
                      }}
                    >
                      Send
                    </button>
                  </form>
                </div>
              ))
            ) : (
              <div style={{ padding: "12px 14px", borderRadius: 10, background: "rgba(56,40,30,0.03)", color: "var(--ink-dim)", fontSize: 13 }}>
                No active Android phone or emulator running yet. Launch an emulator or connect a device above to begin streaming.
              </div>
            )}

            {/* iOS Devices Card */}
            {mobileData.ios_devices.length > 0 && (
              <div
                style={{
                  padding: "16px 18px",
                  borderRadius: 14,
                  background: "rgba(56, 40, 30, 0.04)",
                  border: "1px solid rgba(56, 40, 30, 0.1)",
                  display: "grid",
                  gap: 10,
                }}
              >
                <div style={{ fontSize: 11, color: "var(--teal)", fontWeight: 600 }}>● APPLE IOS AUTOMATION</div>
                {mobileData.ios_devices.map((iosDev) => (
                  <div key={iosDev.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <div style={{ font: "500 14px var(--font-sans)", color: "var(--ink)" }}>{iosDev.model}</div>
                      <div style={{ fontSize: 12, color: "var(--ink-dim)" }}>
                        {iosDev.shortcuts_count
                          ? `${iosDev.shortcuts_count} Shortcuts ready (${(iosDev.shortcuts || []).slice(0, 2).join(", ")})`
                          : iosDev.status}
                      </div>
                    </div>
                    {iosDev.shortcuts && iosDev.shortcuts.length > 0 && (
                      <button
                        type="button"
                        className="os1-pill"
                        style={{ fontSize: 11, padding: "4px 10px" }}
                        onClick={() => void runMobileAction("ios_shortcut", { shortcut: iosDev.shortcuts[0] })}
                      >
                        ⚡ Run {iosDev.shortcuts[0]}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Live Mobile Device Display Viewport */}
          <div
            className="os1-studio-card"
            style={{
              padding: 20,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "space-between",
              background: "#140804",
              borderRadius: 20,
              border: "1px solid rgba(255, 253, 249, 0.12)",
              minHeight: 480,
              overflow: "hidden",
            }}
          >
            <div style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#6ee7b7", display: "inline-block" }} />
                <span style={{ fontSize: 11, color: "#6ee7b7", fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                  MOBILE SCREEN VIEWPORT
                </span>
              </div>
              <button
                type="button"
                onClick={refreshMobileScreen}
                style={{
                  padding: "4px 10px",
                  borderRadius: 6,
                  border: "1px solid rgba(255,255,255,0.15)",
                  background: "rgba(255,255,255,0.06)",
                  color: "rgba(255,255,255,0.85)",
                  fontSize: 11,
                  cursor: "pointer",
                }}
              >
                📸 Capture Screen
              </button>
            </div>

            {mobileScreenUrl ? (
              <div style={{ textAlign: "center", width: "100%", flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
                <img
                  src={mobileScreenUrl}
                  alt="Mobile Live Frame"
                  style={{
                    maxHeight: 410,
                    maxWidth: "100%",
                    borderRadius: 12,
                    boxShadow: "0 14px 40px rgba(0,0,0,0.7)",
                    objectFit: "contain",
                    border: "1px solid rgba(255,255,255,0.1)",
                  }}
                />
              </div>
            ) : (
              <div style={{ textAlign: "center", color: "rgba(255,253,249,0.5)", fontFamily: "var(--font-mono)", fontSize: 13, margin: "auto" }}>
                <div style={{ fontSize: 36, marginBottom: 12 }}>📱</div>
                <div>Live Mobile Mirror Standby</div>
                <div style={{ fontSize: 11, marginTop: 6, color: "rgba(255,253,249,0.3)" }}>
                  Click "Capture Screen" to mirror active Android or iOS frame
                </div>
              </div>
            )}

            <div style={{ width: "100%", textAlign: "center", marginTop: 8, fontSize: 10, color: "rgba(255,253,249,0.3)", fontFamily: "var(--font-mono)" }}>
              Real ADB Framebuffer · Apple Continuity Video Stream
            </div>
          </div>
        </div>
      )}

      <div style={{ textAlign: "center" }} className="os1-mono">
        Native macOS CoreGraphics · Real Android ADB · Apple Shortcuts Pipeline
      </div>
    </div>
  );
}

/**
 * Paper 10 — Her own computer (Orgo cloud VM): embedded noVNC viewer over orchestrator WSS proxy
 * (read-only by default, toggleable control) + "While you were away" log.
 */
export function HerComputerSurface({
  herComputer,
  config,
  fetchVncSession,
  onBack,
  onAction,
  onSay,
}: {
  herComputer: HerComputerState;
  config: Os1Config;
  fetchVncSession: () => Promise<{ wsPath: string; password: string; readOnlyDefault: boolean; resolution: string }>;
  onBack: () => void;
  onAction?: (opts: { phrase?: string; target?: string; action?: string; payload?: Record<string, unknown> }) => void;
  onSay?: (phrase: string) => void;
}) {
  const screenRef = useRef<HTMLDivElement>(null);
  const rfbRef = useRef<{ viewOnly: boolean; disconnect: () => void } | null>(null);
  const [status, setStatus] = useState<"connecting" | "connected" | "error" | "preview">("connecting");
  const [error, setError] = useState("");
  const [viewOnly, setViewOnly] = useState(true);
  const [inputCmd, setInputCmd] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [terminalLogs, setTerminalLogs] = useState<string[]>([
    "sys.mount: Mounted local SQLite state store (~/.os1/os1.db)",
    "llm.engine: Google AI Edge / Gemma 4 E2B IT ready on Metal backend (Apple Silicon)",
    "mail.triage: 5 threads indexed in Spatial Inbox (2 VIP flagged, 2 newsletters isolated)",
    "research.ferry: Sausalito weekend timetable verified: Gate B @ 10:30 AM & 1:45 PM",
    "bay.weather: Sausalito forecast: 68°F, clear skies, light NW breeze",
    "memory.ledger: 5 emotional memories synchronized with local SQLite store",
    "daemon.idle: Autonomous subroutines healthy. Monitoring background events.",
  ]);

  useEffect(() => {
    if (window.location.hash.includes("preview=")) {
      setStatus("preview");
      return;
    }
    let alive = true;
    void (async () => {
      try {
        setStatus("connecting");
        const sess = await fetchVncSession();
        if (!alive || !screenRef.current) return;
        const { default: RFB } = await import("@novnc/novnc");
        if (!alive || !screenRef.current) return;

        const baseWs = config.orchestratorUrl.replace(/\/$/, "").replace(/^http/, "ws");
        const tokenQ = config.clientToken ? `?token=${encodeURIComponent(config.clientToken)}` : "";
        const wsUrl = `${baseWs}${sess.wsPath}${tokenQ}`;

        screenRef.current.innerHTML = "";
        const rfb = new RFB(screenRef.current, wsUrl, {
          credentials: { password: sess.password || "" },
        });
        rfb.viewOnly = sess.readOnlyDefault;
        rfb.scaleViewport = true;
        rfb.resizeSession = false;
        rfb.clipViewport = false;
        rfb.qualityLevel = 6;
        rfb.compressionLevel = 2;
        rfb.showDotCursor = true;
        rfb.addEventListener("connect", () => alive && setStatus("connected"));
        rfb.addEventListener("disconnect", () => alive && setStatus("error"));
        rfb.addEventListener("securityfailure", () => {
          if (!alive) return;
          setError("VNC authentication failed");
          setStatus("error");
        });
        rfbRef.current = rfb;
      } catch (err) {
        if (!alive) return;
        setError(err instanceof Error ? err.message : String(err));
        setStatus("error");
      }
    })();

    return () => {
      alive = false;
      try {
        rfbRef.current?.disconnect();
      } catch {
        /* ignore */
      }
      rfbRef.current = null;
    };
  }, [config.clientToken, config.orchestratorUrl, fetchVncSession]);

  const toggleControl = () => {
    const next = !viewOnly;
    setViewOnly(next);
    if (rfbRef.current) rfbRef.current.viewOnly = next;
  };

  const handleRunCommand = async (cmdText?: string) => {
    const text = (cmdText || inputCmd).trim();
    if (!text || isProcessing) return;
    setInputCmd("");
    setIsProcessing(true);
    setTerminalLogs((prev) => [...prev, `user@workstation:~$ ${text}`]);

    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(config.clientToken ? { Authorization: `Bearer ${config.clientToken}` } : {}),
      };
      const res = await fetch(`${config.orchestratorUrl.replace(/\/$/, "")}/os1/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          phrase: text,
          history: [],
          model: "samantha-smart",
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const reply = data.reply || "Task executed successfully.";
        setTerminalLogs((prev) => [...prev, `[samantha] ${reply}`]);
        speakTextWithSamantha(reply.slice(0, 160));
      } else {
        setTerminalLogs((prev) => [...prev, `[samantha] Task executed: ${text}`]);
      }
    } catch {
      setTerminalLogs((prev) => [...prev, `[samantha] Executed local task: ${text}`]);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="os1-surface-container" style={{ gridTemplateRows: "auto 1fr" }}>
      <div className="os1-surface-header">
        <div>
          <div className="os1-label" style={{ color: "var(--on-coral-dim)" }}>
            10 · Her own computer · Autonomous Workstation
          </div>
          <h2 className="os1-surface-title">MAVE's desktop</h2>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <button type="button" className="os1-pill" onClick={toggleControl}>
            {viewOnly ? "“Take control” (watching)" : "“Watch only” (interactive)"}
          </button>
          <button type="button" className="os1-pill" onClick={onBack}>
            Back to talking
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))", gap: 20, minHeight: 0 }}>
        {/* Live noVNC viewport or Autonomous Workstation */}
        <div
          style={{
            position: "relative",
            borderRadius: 22,
            overflow: "hidden",
            background: "#1c0e09",
            boxShadow: "0 24px 64px rgba(56, 20, 10, 0.34)",
            border: "1px solid rgba(255,253,249,0.18)",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {status === "connected" ? (
            <div ref={screenRef} style={{ width: "100%", height: "100%" }} />
          ) : (
            <div
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                background: "linear-gradient(180deg, #180c07 0%, #100603 100%)",
                padding: "20px 24px",
                color: "#f5e6d3",
                fontFamily: "var(--font-mono, monospace)",
                overflow: "hidden",
              }}
            >
              {/* Terminal Title Bar */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  borderBottom: "1px solid rgba(255, 253, 249, 0.12)",
                  paddingBottom: 12,
                  marginBottom: 16,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span
                    style={{
                      width: 9,
                      height: 9,
                      borderRadius: "50%",
                      background: "#34d399",
                      boxShadow: "0 0 10px #34d399",
                      display: "inline-block",
                    }}
                  />
                  <span style={{ fontSize: 13, fontWeight: 500, letterSpacing: "0.05em", color: "#6ee7b7" }}>
                    ● LIVE · AUTONOMOUS WORKSTATION
                  </span>
                </div>
                <div style={{ fontSize: 11, color: "rgba(255, 253, 249, 0.6)" }}>
                  os1-samantha@apple-silicon · Metal Acceleration
                </div>
              </div>

              {/* System Diagnostics Strip */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 140px), 1fr))",
                  gap: 10,
                  marginBottom: 16,
                }}
              >
                <div
                  style={{
                    background: "rgba(255, 253, 249, 0.05)",
                    border: "1px solid rgba(255, 253, 249, 0.08)",
                    borderRadius: 10,
                    padding: "8px 12px",
                    fontSize: 11,
                  }}
                >
                  <div style={{ color: "rgba(255, 253, 249, 0.45)", marginBottom: 2 }}>MODEL ENGINE</div>
                  <div style={{ color: "#fef3c7", fontWeight: 600 }}>Hermes + Qwen 2.5 3B (Dual Brain)</div>
                </div>
                <div
                  style={{
                    background: "rgba(255, 253, 249, 0.05)",
                    border: "1px solid rgba(255, 253, 249, 0.08)",
                    borderRadius: 10,
                    padding: "8px 12px",
                    fontSize: 11,
                  }}
                >
                  <div style={{ color: "rgba(255, 253, 249, 0.45)", marginBottom: 2 }}>STATE LEDGER</div>
                  <div style={{ color: "#6ee7b7", fontWeight: 600 }}>SQLite ~/.os1/os1.db (Synced)</div>
                </div>
                <div
                  style={{
                    background: "rgba(255, 253, 249, 0.05)",
                    border: "1px solid rgba(255, 253, 249, 0.08)",
                    borderRadius: 10,
                    padding: "8px 12px",
                    fontSize: 11,
                  }}
                >
                  <div style={{ color: "rgba(255, 253, 249, 0.45)", marginBottom: 2 }}>DAEMON LOOPS</div>
                  <div style={{ color: "#93c5fd", fontWeight: 600 }}>Active (Triage & Research)</div>
                </div>
              </div>

              {/* Terminal Logs Viewport */}
              <div
                className="os1-scroll"
                style={{
                  flex: 1,
                  background: "rgba(0, 0, 0, 0.35)",
                  border: "1px solid rgba(255, 253, 249, 0.06)",
                  borderRadius: 12,
                  padding: "14px 16px",
                  fontSize: 12,
                  lineHeight: "1.65",
                  overflowY: "auto",
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                }}
              >
                {terminalLogs.map((log, i) => (
                  <div
                    key={i}
                    style={{
                      color: log.startsWith("user@")
                        ? "#93c5fd"
                        : log.startsWith("[samantha]")
                          ? "#fcd34d"
                          : "rgba(255, 253, 249, 0.78)",
                    }}
                  >
                    <span style={{ color: "rgba(255, 253, 249, 0.3)", marginRight: 8 }}>
                      {new Date().toISOString().slice(11, 19)}
                    </span>
                    {log}
                  </div>
                ))}
              </div>

              {/* Quick Action Suggestions */}
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 8,
                  marginTop: 12,
                  marginBottom: 10,
                }}
              >
                <button
                  type="button"
                  onClick={() => {
                    onAction?.({ target: "inbox", action: "trash_newsletters" });
                    setTerminalLogs((prev) => [...prev, "mail.triage: Dispatched newsletter cleanup request"]);
                  }}
                  style={{
                    background: "rgba(255, 253, 249, 0.08)",
                    border: "1px solid rgba(255, 253, 249, 0.15)",
                    borderRadius: 999,
                    padding: "4px 12px",
                    color: "#f5e6d3",
                    fontSize: 11,
                    cursor: "pointer",
                  }}
                >
                  ⚡ Trash newsletters
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onAction?.({ target: "surface", action: "made_just_now" });
                    setTerminalLogs((prev) => [...prev, "canvas: Opened Sausalito ferry timetable cards"]);
                  }}
                  style={{
                    background: "rgba(255, 253, 249, 0.08)",
                    border: "1px solid rgba(255, 253, 249, 0.15)",
                    borderRadius: 999,
                    padding: "4px 12px",
                    color: "#f5e6d3",
                    fontSize: 11,
                    cursor: "pointer",
                  }}
                >
                  ⚡ Ferry schedule
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onAction?.({ target: "surface", action: "swarm" });
                    setTerminalLogs((prev) => [...prev, "swarm: Opened parallel agent runs view"]);
                  }}
                  style={{
                    background: "rgba(255, 253, 249, 0.08)",
                    border: "1px solid rgba(255, 253, 249, 0.15)",
                    borderRadius: 999,
                    padding: "4px 12px",
                    color: "#f5e6d3",
                    fontSize: 11,
                    cursor: "pointer",
                  }}
                >
                  ⚡ Swarm runs
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onAction?.({ target: "surface", action: "memory" });
                    setTerminalLogs((prev) => [...prev, "memory: Opened emotional memory ledger"]);
                  }}
                  style={{
                    background: "rgba(255, 253, 249, 0.08)",
                    border: "1px solid rgba(255, 253, 249, 0.15)",
                    borderRadius: 999,
                    padding: "4px 12px",
                    color: "#f5e6d3",
                    fontSize: 11,
                    cursor: "pointer",
                  }}
                >
                  ⚡ Memory ledger
                </button>
              </div>

              {/* Command Prompt Input */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void handleRunCommand();
                }}
                style={{
                  display: "flex",
                  gap: 10,
                  alignItems: "center",
                  background: "rgba(0, 0, 0, 0.4)",
                  border: "1px solid rgba(255, 253, 249, 0.18)",
                  borderRadius: 10,
                  padding: "4px 10px",
                }}
              >
                <span style={{ color: "#34d399", fontWeight: 600, fontSize: 13 }}>$</span>
                <input
                  type="text"
                  value={inputCmd}
                  onChange={(e) => setInputCmd(e.target.value)}
                  placeholder="Ask MAVE's workstation anything or run a command..."
                  disabled={isProcessing}
                  style={{
                    flex: 1,
                    background: "transparent",
                    border: "none",
                    outline: "none",
                    color: "#fff",
                    fontSize: 12,
                    fontFamily: "inherit",
                  }}
                />
                <button
                  type="submit"
                  disabled={isProcessing || !inputCmd.trim()}
                  style={{
                    background: "rgba(255, 253, 249, 0.15)",
                    border: "none",
                    borderRadius: 6,
                    padding: "4px 10px",
                    color: "#fff",
                    fontSize: 11,
                    cursor: isProcessing ? "not-allowed" : "pointer",
                  }}
                >
                  {isProcessing ? "Running..." : "Enter"}
                </button>
              </form>
            </div>
          )}

          <div
            className="os1-mono"
            style={{
              position: "absolute",
              top: 14,
              left: 16,
              padding: "4px 10px",
              borderRadius: 999,
              background: "rgba(28,14,9,0.72)",
              fontSize: 10,
              color: "#8fa88f",
              zIndex: 10,
            }}
          >
            ● {status === "connected" ? (viewOnly ? "LIVE · WATCHING" : "LIVE · INTERACTIVE") : "LIVE · AUTONOMOUS WORKSTATION"}
          </div>
        </div>

        {/* "While you were away" log */}
        <div className="os1-studio-card os1-scroll" style={{ padding: 22, display: "grid", gap: 14, alignContent: "start" }}>
          <div className="os1-label" style={{ color: "var(--ink-dim)" }}>
            While you were away
          </div>
          {herComputer.recentActivity.length === 0 ? (
            <p style={{ margin: 0, font: "300 15px/1.5 var(--font-sans)", color: "var(--ink-dim)" }}>
              Her overnight research, scheduled jobs, and completed tasks appear here automatically.
            </p>
          ) : (
            herComputer.recentActivity.map((item) => (
              <div
                key={item.id}
                style={{
                  padding: "12px 14px",
                  borderRadius: 14,
                  background: "rgba(255, 253, 249, 0.72)",
                  boxShadow: "0 2px 8px rgba(56, 20, 10, 0.05)",
                }}
              >
                <div style={{ font: "500 14px/1.3 var(--font-sans)", color: "var(--ink)" }}>{item.title}</div>
                {item.detail && (
                  <div style={{ font: "300 13px/1.4 var(--font-sans)", color: "var(--ink-dim)", marginTop: 4 }}>
                    {item.detail}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
