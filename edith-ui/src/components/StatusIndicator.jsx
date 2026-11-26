const STATUS_LABELS = {
  SLEEPING: "SLEEPING",
  READY: "READY",
  LISTENING: "LISTENING",
  THINKING: "THINKING",
  SPEAKING: "SPEAKING",
};

export default function StatusIndicator({ state }) {
  const label = STATUS_LABELS[state] || "READY";

  return (
    <header className="identity-header">
      <div className="flex items-center gap-2.5 whitespace-nowrap">
        <span className="identity-mark" />
        <span className="identity-name">EDITH</span>
        <span className="identity-divider" />
        <span className="identity-status">{label}</span>
      </div>
      <div className="identity-subtitle">PERSONAL INTELLIGENCE SYSTEM</div>
    </header>
  );
}