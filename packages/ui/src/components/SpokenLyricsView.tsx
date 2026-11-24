import React, { useEffect, useMemo, useRef, useState } from "react";

interface SpokenLyricsViewProps {
  text: string;
  isSpeaking?: boolean;
  className?: string;
  maxLinesPerChunk?: number;
}

/** Split long speech into natural, readable sentence-based lyric chunks (~2-4 lines each). */
function chunkSpeechText(rawText: string): string[] {
  const clean = rawText.replace(/\[[^\]]+\]/g, "").replace(/<[^>]+>/g, "").trim();
  if (!clean) return [];

  // Short responses stay as a single cohesive statement
  if (clean.length <= 110) {
    return [clean];
  }

  // Split into sentences preserving punctuation
  const sentenceRegex = /[^.!?]+[.!?]+(?:\s+|$)|[^.!?]+$/g;
  const rawSentences = clean.match(sentenceRegex) || [clean];
  const sentences = rawSentences.map((s) => s.trim()).filter(Boolean);

  if (sentences.length <= 1) {
    // If it's one very long sentence, chunk by clauses/commas or length
    if (clean.length > 200) {
      const words = clean.split(/\s+/);
      const chunks: string[] = [];
      let current: string[] = [];
      for (const w of words) {
        current.push(w);
        if (current.join(" ").length >= 130 && w.endsWith(",")) {
          chunks.push(current.join(" "));
          current = [];
        } else if (current.join(" ").length >= 170) {
          chunks.push(current.join(" "));
          current = [];
        }
      }
      if (current.length > 0) chunks.push(current.join(" "));
      return chunks.length > 0 ? chunks : [clean];
    }
    return [clean];
  }

  // Group sentences into compact chunks of at most ~150 characters (2-4 lines)
  const chunks: string[] = [];
  let currentChunk = "";

  for (const sentence of sentences) {
    if (!currentChunk) {
      currentChunk = sentence;
    } else if ((currentChunk + " " + sentence).length <= 150) {
      currentChunk += " " + sentence;
    } else {
      chunks.push(currentChunk);
      currentChunk = sentence;
    }
  }
  if (currentChunk) {
    chunks.push(currentChunk);
  }

  return chunks.length > 0 ? chunks : [clean];
}

/** Determine responsive font styling dynamically according to active chunk length. */
function getResponsiveFontStyle(chunkLength: number): {
  fontSize: string;
  lineHeight: number;
  letterSpacing: string;
} {
  if (chunkLength <= 45) {
    return {
      fontSize: "clamp(24px, 4.4vw, 40px)",
      lineHeight: 1.32,
      letterSpacing: "-0.015em",
    };
  }
  if (chunkLength <= 110) {
    return {
      fontSize: "clamp(19px, 3.2vw, 29px)",
      lineHeight: 1.36,
      letterSpacing: "-0.01em",
    };
  }
  if (chunkLength <= 200) {
    return {
      fontSize: "clamp(16px, 2.3vw, 22px)",
      lineHeight: 1.42,
      letterSpacing: "-0.005em",
    };
  }
  return {
    fontSize: "clamp(14px, 1.8vw, 18px)",
    lineHeight: 1.48,
    letterSpacing: "0em",
  };
}

export function SpokenLyricsView({
  text,
  isSpeaking = false,
  className = "",
}: SpokenLyricsViewProps) {
  const chunks = useMemo(() => chunkSpeechText(text), [text]);
  const [activeIndex, setActiveIndex] = useState(0);
  const touchStartX = useRef<number | null>(null);

  // Reset to first chunk whenever spoken text changes
  useEffect(() => {
    setActiveIndex(0);
  }, [text]);

  // Spotify-style auto-swipe: advance smoothly while assistant is speaking
  useEffect(() => {
    if (!isSpeaking || chunks.length <= 1) return;

    const currentText = chunks[activeIndex] || "";
    const words = currentText.split(/\s+/).length;
    // Natural speaking pace: ~320ms per word + 1200ms base reading pause
    const durationMs = Math.min(8000, Math.max(3800, words * 320 + 1200));

    const timer = window.setTimeout(() => {
      setActiveIndex((prev) => (prev + 1) % chunks.length);
    }, durationMs);

    return () => window.clearTimeout(timer);
  }, [isSpeaking, activeIndex, chunks]);

  if (!text || chunks.length === 0) return null;

  const activeChunk = chunks[activeIndex] || chunks[0];
  const { fontSize, lineHeight, letterSpacing } = getResponsiveFontStyle(activeChunk.length);
  const hasMultiplePages = chunks.length > 1;

  const handlePrev = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setActiveIndex((prev) => (prev > 0 ? prev - 1 : chunks.length - 1));
  };

  const handleNext = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setActiveIndex((prev) => (prev < chunks.length - 1 ? prev + 1 : 0));
  };

  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartX.current === null) return;
    const diff = touchStartX.current - e.changedTouches[0].clientX;
    if (Math.abs(diff) > 40) {
      if (diff > 0) handleNext();
      else handlePrev();
    }
    touchStartX.current = null;
  };

  return (
    <div
      className={`os1-lyrics-container ${className}`}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
      style={{
        width: "100%",
        maxWidth: "min(780px, 92vw)",
        minHeight: "clamp(88px, 15vh, 130px)",
        maxHeight: "clamp(160px, 25vh, 220px)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        margin: "clamp(8px, 2vh, 18px) auto",
        userSelect: "none",
        boxSizing: "border-box",
      }}
    >
      {/* Active lyric card with smooth fade/slide in */}
      <div
        key={`${text.slice(0, 16)}-${activeIndex}`}
        className="os1-fade"
        style={{
          color: "var(--paper)",
          fontWeight: 200,
          fontSize,
          lineHeight,
          letterSpacing,
          textAlign: "center",
          textWrap: "balance" as any,
          transition: "font-size 250ms ease, line-height 250ms ease",
          maxWidth: "100%",
          padding: "0 14px",
        }}
      >
        {activeChunk}
      </div>

      {/* Spotify Lyrics Swiping Dots & Navigation Controls */}
      {hasMultiplePages && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 12,
            marginTop: 14,
            opacity: 0.85,
            transition: "opacity 200ms ease",
          }}
        >
          {/* Previous arrow */}
          <button
            type="button"
            onClick={handlePrev}
            aria-label="Previous lyric lines"
            style={{
              background: "transparent",
              border: "none",
              color: "var(--on-coral)",
              cursor: "pointer",
              fontSize: 16,
              padding: "2px 6px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              opacity: 0.6,
              transition: "opacity 150ms ease, transform 150ms ease",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = "0.6")}
          >
            ‹
          </button>

          {/* Interactive lyric page pills */}
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            {chunks.map((_, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setActiveIndex(i)}
                aria-label={`Jump to lines ${i + 1}`}
                style={{
                  width: i === activeIndex ? 18 : 6,
                  height: 6,
                  borderRadius: 3,
                  background: i === activeIndex ? "var(--paper)" : "var(--on-coral-faint)",
                  border: "none",
                  padding: 0,
                  cursor: "pointer",
                  transition: "all 300ms cubic-bezier(0.16, 1, 0.3, 1)",
                  boxShadow: i === activeIndex ? "0 0 8px rgba(255,255,255,0.4)" : "none",
                }}
              />
            ))}
          </div>

          {/* Next arrow */}
          <button
            type="button"
            onClick={handleNext}
            aria-label="Next lyric lines"
            style={{
              background: "transparent",
              border: "none",
              color: "var(--on-coral)",
              cursor: "pointer",
              fontSize: 16,
              padding: "2px 6px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              opacity: 0.6,
              transition: "opacity 150ms ease, transform 150ms ease",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = "0.6")}
          >
            ›
          </button>

          {/* Subtle page counter indicator */}
          <span
            style={{
              fontSize: 10,
              fontFamily: "var(--font-mono)",
              color: "var(--on-coral-dim)",
              marginLeft: 4,
              letterSpacing: "0.08em",
            }}
          >
            {activeIndex + 1}/{chunks.length}
          </span>
        </div>
      )}
    </div>
  );
}
