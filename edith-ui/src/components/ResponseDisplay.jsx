import { useEffect, useRef } from "react";

const FALLBACK_COPY = {
  READY: "Systems nominal. Standing by.",
  LISTENING: "Listening...",
  THINKING: "Analyzing request...",
};

export default function ResponseDisplay({ response, state }) {
  const containerRef = useRef(null);
  const followLatestRef = useRef(true);
  const userScrollUntilRef = useRef(0);
  const displayText = response || FALLBACK_COPY[state] || "";

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    if (!response) {
      followLatestRef.current = true;
      el.scrollTop = 0;
      return;
    }

    if (!followLatestRef.current) return;

    let frameId;
    const followLatest = () => {
      if (!followLatestRef.current) return;

      const remaining =
        el.scrollHeight - el.clientHeight - el.scrollTop;

      if (remaining <= 1) return;

      el.scrollTop += Math.max(0.5, remaining * 0.14);
      frameId = requestAnimationFrame(followLatest);
    };

    frameId = requestAnimationFrame(followLatest);
    return () => cancelAnimationFrame(frameId);
  }, [response]);

  const handleScroll = () => {
    const el = containerRef.current;
    if (!el || performance.now() > userScrollUntilRef.current) return;

    followLatestRef.current =
      el.scrollHeight - el.clientHeight - el.scrollTop <= 24;
  };

  const markUserScroll = () => {
    userScrollUntilRef.current = performance.now() + 300;
  };

  const handleKeyDown = (event) => {
    if (
      ["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "]
        .includes(event.key)
    ) {
      markUserScroll();
    }
  };

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      onWheel={markUserScroll}
      onTouchMove={markUserScroll}
      onPointerDown={markUserScroll}
      onPointerMove={(event) => {
        if (event.buttons > 0) markUserScroll();
      }}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      className={`transcript ${displayText ? "has-text" : ""} ${!response ? "is-subtle" : ""}`}
      aria-live="polite"
      aria-label="Assistant response"
    >
      {displayText}
    </div>
  );
}