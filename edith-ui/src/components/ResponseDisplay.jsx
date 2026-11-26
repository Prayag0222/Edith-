import { useEffect, useRef } from "react";

const FALLBACK_COPY = {
  READY: "Systems nominal. Standing by.",
  LISTENING: "Listening...",
  THINKING: "Analyzing request...",
};

export default function ResponseDisplay({ response, state, speechRange }) {
  const containerRef = useRef(null);
  const spokenRef = useRef(null);
  const followLatestRef = useRef(true);
  const userScrollUntilRef = useRef(0);
  const displayText = response || FALLBACK_COPY[state] || "";
  const responseChars = response ? Array.from(response) : [];
  const rangeStart =
    speechRange && Number.isInteger(speechRange.start)
      ? Math.min(responseChars.length, Math.max(0, speechRange.start))
      : 0;
  const rangeEnd =
    speechRange && Number.isInteger(speechRange.end)
      ? Math.min(responseChars.length, Math.max(rangeStart, speechRange.end))
      : 0;
  const hasSpokenRange = Boolean(
    response && rangeEnd > rangeStart
  );

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

      const maxScrollTop = Math.max(0, el.scrollHeight - el.clientHeight);
      let destination = maxScrollTop;
      const spokenElement = spokenRef.current;

      if (spokenElement) {
        const containerRect = el.getBoundingClientRect();
        const spokenRect = spokenElement.getBoundingClientRect();
        destination = Math.max(
          0,
          Math.min(
            maxScrollTop,
            el.scrollTop +
              spokenRect.top -
              containerRect.top -
              (el.clientHeight - spokenRect.height) * 0.45
          )
        );
      }

      const remaining = destination - el.scrollTop;

      if (Math.abs(remaining) <= 1) return;

      el.scrollTop +=
        Math.sign(remaining) * Math.max(0.5, Math.abs(remaining) * 0.14);
      frameId = requestAnimationFrame(followLatest);
    };

    frameId = requestAnimationFrame(followLatest);
    return () => cancelAnimationFrame(frameId);
  }, [response, speechRange]);

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
      {hasSpokenRange ? (
        <>
          {responseChars.slice(0, rangeStart).join("")}
          <span ref={spokenRef} className="transcript__spoken">
            {responseChars.slice(rangeStart, rangeEnd).join("")}
          </span>
          {responseChars.slice(rangeEnd).join("")}
        </>
      ) : (
        displayText
      )}
    </div>
  );
}