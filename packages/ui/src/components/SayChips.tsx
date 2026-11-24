interface Props {
  chips: string[];
  /** Taps behave exactly like saying the phrase. */
  onSay?: (phrase: string) => void;
}

/** "Say" chips: hints of what you can say. The likeliest phrase is filled. */
export function SayChips({ chips, onSay }: Props) {
  if (!chips.length) return null;
  return (
    <div className="os1-say-container os1-fade">
      <span className="os1-label" style={{ fontSize: 11, color: "var(--on-coral-dim)", marginRight: 2 }}>
        Say
      </span>
      {chips.map((chip, i) => (
        <button
          key={chip}
          type="button"
          onClick={() => onSay?.(chip)}
          className="os1-say-chip"
          style={{
            border: `1px solid ${i === 0 ? "transparent" : "var(--on-coral-faint)"}`,
            background: i === 0 ? "var(--paper)" : "rgba(255,253,249,0.08)",
            color: i === 0 ? "var(--coral-deep)" : "var(--on-coral)",
          }}
        >
          <span
            aria-hidden
            style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              flexShrink: 0,
              border: `1.6px solid ${i === 0 ? "var(--coral)" : "var(--on-coral)"}`,
            }}
          />
          “{chip}”
        </button>
      ))}
    </div>
  );
}
