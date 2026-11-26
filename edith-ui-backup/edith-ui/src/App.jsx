import { useEffect, useState } from "react";
import { Mic, Brain, Volume2, Power } from "lucide-react";

const STATES = {
  READY: {
    label: "READY",
    description: "Waiting for your command",
    icon: Mic,
  },
  LISTENING: {
    label: "LISTENING",
    description: "I'm listening to you",
    icon: Mic,
  },
  THINKING: {
    label: "THINKING",
    description: "Processing your request",
    icon: Brain,
  },
  SPEAKING: {
    label: "SPEAKING",
    description: "Preparing a response",
    icon: Volume2,
  },
  SLEEPING: {
    label: "SLEEPING",
    description: "Waiting for wake word",
    icon: Power,
  },
};

// Fixed waveform heights: predictable across React renders.
const WAVEFORM_BARS = Array.from({ length: 25 }, (_, index) => ({
  id: index,
  height: 8 + ((index * 17 + 11) % 22),
  opacity: 0.4 + ((index * 13 + 7) % 60) / 100,
}));

export default function App() {
  const [status, setStatus] = useState("READY");

  const current = STATES[status] || STATES.READY;
  const Icon = current.icon;

  useEffect(() => {
    // Python can update the interface through this function.
    window.edithSetState = (newState) => {
      if (STATES[newState]) {
        setStatus(newState);
      }
    };

    return () => {
      delete window.edithSetState;
    };
  }, []);

  const isActive = status === "LISTENING" || status === "SPEAKING";

  return (
    <main className="min-h-screen flex items-center justify-center bg-transparent p-5">
      <section className="relative w-[340px] rounded-3xl border border-cyan-400/20 bg-[#080e19]/95 p-7 text-white shadow-[0_0_60px_rgba(0,180,255,0.12)]">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-[0.3em] text-cyan-300">
              EDITH
            </h1>

            <p className="mt-1 text-[10px] tracking-[0.25em] text-slate-500">
              PERSONAL AI ASSISTANT
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="h-2 w-2 animate-pulse rounded-full bg-cyan-400" />
            <span className="text-[10px] tracking-widest text-cyan-300">
              ONLINE
            </span>
          </div>
        </div>

        {/* Animated Orb */}
        <div className="relative flex h-44 items-center justify-center">
          <div className="absolute h-36 w-36 animate-ping rounded-full border border-cyan-400/10" />

          <div className="absolute h-28 w-28 rounded-full border border-cyan-400/30" />

          <div className="absolute h-24 w-24 rounded-full bg-cyan-400/10 blur-2xl" />

          <div className="relative flex h-20 w-20 items-center justify-center rounded-full border border-cyan-300/60 bg-cyan-400/10 shadow-[0_0_35px_rgba(0,200,255,0.35)]">
            <Icon size={30} className="text-cyan-300" />
          </div>
        </div>

        {/* Current State */}
        <div className="text-center">
          <h2 className="text-sm font-semibold tracking-[0.35em] text-cyan-300">
            {current.label}
          </h2>

          <p className="mt-2 text-xs text-slate-400">
            {current.description}
          </p>
        </div>

        {/* Decorative Waveform */}
        <div className="mt-7 flex h-8 items-center justify-center gap-1">
          {WAVEFORM_BARS.map((bar) => (
            <div
              key={bar.id}
              className={`w-1 rounded-full bg-cyan-400 ${
                isActive ? "animate-pulse" : ""
              }`}
              style={{
                height: isActive ? `${bar.height}px` : "5px",
                opacity: bar.opacity,
              }}
            />
          ))}
        </div>

        {/* Footer */}
        <div className="mt-6 flex items-center justify-between border-t border-white/10 pt-4">
          <span className="text-[10px] tracking-widest text-slate-500">
            LOCAL AI SYSTEM
          </span>

          <span className="text-[10px] text-cyan-400">
            v0.1
          </span>
        </div>

      </section>
    </main>
  );
}