import { SayChips } from "../components/SayChips";
import type { InboxItem } from "../types";

/**
 * Paper 07/08 — Spatial Inbox: numbered tactile paper/studio tiles ranked by Jev keeper score.
 * Everything on screen can be named aloud ("open number two", "archive number four", "trash the newsletters").
 */
export function InboxSurface({
  items,
  compact,
  onAction,
  onBack,
}: {
  items: InboxItem[];
  compact?: boolean;
  onAction: (action: string, payload?: Record<string, unknown>) => void;
  onBack: () => void;
}) {
  const shown = compact ? items.slice(0, 4) : items;
  const newsletterCount = items.filter((m) => m.keeper_score < 0.35 || m.category === "newsletter").length;

  return (
    <div className="os1-surface-container">
      <div className="os1-surface-header">
        <div>
          <div className="os1-label" style={{ color: "var(--on-coral-dim)" }}>
            07 · Spatial Inbox
          </div>
          <h2 className="os1-surface-title">
            {items.length} waiting
            {newsletterCount > 0 ? ` · ${newsletterCount} ${newsletterCount === 1 ? "newsletter" : "newsletters"}` : ""}
          </h2>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {newsletterCount > 0 && (
            <button type="button" className="os1-pill" onClick={() => onAction("trash_newsletters")}>
              “Trash newsletters”
            </button>
          )}
          <button type="button" className="os1-pill" onClick={() => onAction("refresh")}>
            Refresh mail
          </button>
          <button type="button" className="os1-pill" onClick={onBack}>
            Back to talking
          </button>
        </div>
      </div>

      <div
        className="os1-scroll"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(clamp(260px, 100%, 340px), 1fr))",
          gap: 16,
          alignContent: "start",
        }}
      >
        {shown.length === 0 ? (
          <div className="os1-glass" style={{ gridColumn: "1 / -1", padding: 36, textAlign: "center" }}>
            <p className="os1-lead" style={{ margin: 0 }}>
              Your inbox is clear.
            </p>
            <p style={{ margin: "8px 0 0", color: "var(--on-coral-dim)", fontSize: 15 }}>
              Connect Mail in Connectors or ask MAVE “look through my email” to populate your spatial inbox.
            </p>
          </div>
        ) : (
          shown.map((msg) => {
            const isKeeper = msg.keeper_score >= 0.7;
            const isJunk = msg.keeper_score < 0.35;
            return (
              <div
                key={msg.id}
                className={isKeeper ? "os1-paper-card" : "os1-studio-card"}
                style={{
                  padding: "18px 20px",
                  display: "grid",
                  gap: 10,
                  opacity: isJunk ? 0.84 : 1,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      className="os1-mono"
                      style={{
                        fontSize: 12,
                        padding: "2px 8px",
                        borderRadius: 999,
                        background: isKeeper ? "var(--coral)" : "rgba(56,40,30,0.12)",
                        color: isKeeper ? "var(--paper)" : "var(--ink)",
                      }}
                    >
                      {String(msg.number).padStart(2, "0")}
                    </span>
                    {msg.is_vip && (
                      <span className="os1-mono" style={{ fontSize: 10, color: "var(--coral)" }}>
                        ★ VIP
                      </span>
                    )}
                  </div>
                  <span className="os1-mono" style={{ fontSize: 10, color: "var(--ink-dim)" }}>
                    {msg.category}
                  </span>
                </div>

                <div>
                  <div style={{ font: "500 14px/1.3 var(--font-sans)", color: "var(--ink-dim)" }}>{msg.sender}</div>
                  <div style={{ font: "400 17px/1.3 var(--font-sans)", color: "var(--ink)", marginTop: 2 }}>
                    {msg.subject}
                  </div>
                </div>

                {msg.snippet && (
                  <p
                    style={{
                      margin: 0,
                      font: "300 14px/1.45 var(--font-sans)",
                      color: "var(--ink-dim)",
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}
                  >
                    {msg.snippet}
                  </p>
                )}

                {/* Jev keeper score bar */}
                <div style={{ height: 2, background: "rgba(56,40,30,0.10)", borderRadius: 2, overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${Math.round(msg.keeper_score * 100)}%`,
                      height: "100%",
                      background: isKeeper ? "var(--coral)" : isJunk ? "var(--ink-dim)" : "var(--mustard)",
                    }}
                  />
                </div>

                <div style={{ display: "flex", gap: 8, marginTop: 2 }}>
                  <button
                    type="button"
                    className="os1-pill-ink primary"
                    style={{ fontSize: 12, padding: "6px 12px" }}
                    onClick={() => onAction("open", { number: msg.number })}
                  >
                    “Open {msg.number}”
                  </button>
                  <button
                    type="button"
                    className="os1-pill-ink"
                    style={{ fontSize: 12, padding: "6px 12px" }}
                    onClick={() => onAction("archive", { number: msg.number })}
                  >
                    Archive
                  </button>
                  <button
                    type="button"
                    className="os1-pill-ink"
                    style={{ fontSize: 12, padding: "6px 12px" }}
                    onClick={() => onAction("trash", { number: msg.number })}
                  >
                    Trash
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div style={{ display: "flex", justifyContent: "center" }}>
        <SayChips
          chips={
            items.length > 0
              ? [`Open number ${items[0].number}`, "Trash the newsletters", "Back to talking"]
              : ["Show connectors", "Back to talking"]
          }
          onSay={(phrase) => {
            if (phrase.toLowerCase().includes("trash")) onAction("trash_newsletters");
            else if (phrase.toLowerCase().includes("open")) onAction("open", { number: items[0]?.number ?? 1 });
            else onBack();
          }}
        />
      </div>
    </div>
  );
}
