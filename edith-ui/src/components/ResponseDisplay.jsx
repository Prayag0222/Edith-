import { useEffect, useRef } from "react";

const FALLBACK_COPY = {
  READY: "Systems nominal. Standing by.",
  LISTENING: "Listening...",
  THINKING: "Analyzing request...",
};

export default function ResponseDisplay({ response, state }) {
  const containerRef = useRef(null);
  const displayText = response || FALLBACK_COPY[state] || "";

  // Auto-scroll to latest streamed lines
  useEffect(() => {
    const el = containerRef.current;
    if (el && response) {
      el.scrollTop = el.scrollHeight;
    }
  }, [response]);

  return (
    <div
      ref={containerRef}
      className={`transcript ${displayText ? "has-text" : ""} ${!response ? "is-subtle" : ""}`}
      aria-live="polite"
    >
      {displayText}
    </div>
  );
}