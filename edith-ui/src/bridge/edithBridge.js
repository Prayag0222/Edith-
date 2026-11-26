const VALID_STATES = new Set([
  "SLEEPING",
  "READY",
  "LISTENING",
  "THINKING",
  "SPEAKING",
]);

const DEFAULT_FADE_MS = 12000;

/**
 * Shared mutable store for 60fps Canvas reads (zero React re-renders).
 */
export const edithLiveStore = {
  state: "SLEEPING",
  audioLevel: 0,
  wakePulseAt: 0, // Timestamp of the last SLEEPING -> active transition
};

let uiListeners = new Set();
let fadeTimer = null;
let currentState = "SLEEPING";
let currentResponse = "";

function emitUI() {
  const snapshot = {
    state: currentState,
    response: currentResponse,
    visible: currentState !== "SLEEPING",
  };
  uiListeners.forEach((listener) => listener(snapshot));
}

function scheduleFadeClear() {
  clearTimeout(fadeTimer);
  fadeTimer = setTimeout(() => {
    currentResponse = "";
    emitUI();
  }, DEFAULT_FADE_MS);
}

export function setEdithState(nextState) {
  const normalized = String(nextState || "SLEEPING").toUpperCase();
  if (!VALID_STATES.has(normalized)) return;

  const wasSleeping = currentState === "SLEEPING";
  currentState = normalized;
  edithLiveStore.state = normalized;

  if (wasSleeping && normalized !== "SLEEPING") {
    edithLiveStore.wakePulseAt = performance.now();
  }

  if (normalized === "THINKING" || normalized === "SLEEPING") {
    clearTimeout(fadeTimer);
    currentResponse = "";
  }

  if (normalized === "SLEEPING") {
    edithLiveStore.audioLevel = 0;
  }

  emitUI();
}

export function setEdithResponse(text) {
  currentResponse = String(text ?? "");
  scheduleFadeClear();
  emitUI();
}

export function appendEdithResponse(chunk) {
  currentResponse += String(chunk ?? "");
  scheduleFadeClear();
  emitUI();
}

export function clearEdithResponse() {
  clearTimeout(fadeTimer);
  currentResponse = "";
  emitUI();
}

export function setEdithAudioLevel(level) {
  const value = Number(level);
  if (!Number.isFinite(value)) return;
  edithLiveStore.audioLevel = Math.max(0, Math.min(1, value));
}

export function subscribeEdithUI(listener) {
  uiListeners.add(listener);
  listener({
    state: currentState,
    response: currentResponse,
    visible: currentState !== "SLEEPING",
  });

  return () => {
    uiListeners.delete(listener);
  };
}

/**
 * Registers the exact pywebview bridge functions on window.
 * Safe to call inside a top-level useEffect.
 */
export function registerEdithBridge() {
  window.edithSetState = setEdithState;
  window.edithSetResponse = setEdithResponse;
  window.edithAppendResponse = appendEdithResponse;
  window.edithClearResponse = clearEdithResponse;
  window.edithSetAudioLevel = setEdithAudioLevel;

  return () => {
    clearTimeout(fadeTimer);
    delete window.edithSetState;
    delete window.edithSetResponse;
    delete window.edithAppendResponse;
    delete window.edithClearResponse;
    delete window.edithSetAudioLevel;
  };
}