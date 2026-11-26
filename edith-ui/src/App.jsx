import { useEffect, useState } from "react";
import {
  registerEdithBridge,
  setEdithAudioLevel,
  setEdithResponse,
  setEdithState,
  subscribeEdithUI,
} from "./bridge/edithBridge.js";
import EdithInterface from "./components/EdithInterface.jsx";

export default function App() {
  const [ui, setUi] = useState({
    state: "SLEEPING",
    response: "",
    visible: false,
  });

  const preview = new URLSearchParams(window.location.search).has("preview");

  useEffect(() => {
    const unregisterBridge = registerEdithBridge();
    const unsubscribe = subscribeEdithUI(setUi);

    return () => {
      unsubscribe();
      unregisterBridge();
    };
  }, []);

  // Optional ?preview mode for testing all 5 states + simulated voice levels in browser
  useEffect(() => {
    if (!preview) return;

    const sequence = [
      ["READY", ""],
      ["LISTENING", ""],
      ["THINKING", ""],
      [
        "SPEAKING",
        "All systems are online. Telemetry is nominal and ready for your command.",
      ],
    ];

    let idx = 0;
    const step = () => {
      const [nextState, text] = sequence[idx % sequence.length];
      setEdithState(nextState);
      if (text) setEdithResponse(text);
      idx++;
    };

    step();
    const stateTimer = setInterval(step, 5500);
    const audioTimer = setInterval(() => {
      const t = performance.now() / 180;
      const simulated = 0.25 + 0.55 * Math.abs(Math.sin(t) * Math.cos(t * 0.6));
      setEdithAudioLevel(simulated);
    }, 60);

    return () => {
      clearInterval(stateTimer);
      clearInterval(audioTimer);
    };
  }, [preview]);

  return (
    <div className="relative h-full w-full bg-transparent">
      <EdithInterface
        state={ui.state}
        response={ui.response}
        visible={ui.visible}
      />

      {preview && (
        <nav className="preview-controls absolute bottom-1 left-5 z-20 flex gap-1.5">
          {["SLEEPING", "READY", "LISTENING", "THINKING", "SPEAKING"].map(
            (item) => (
              <button
                key={item}
                onClick={() => {
                  setEdithState(item);
                  if (item === "SPEAKING") {
                    setEdithResponse(
                      "Your systems are ready. What shall we work on next?"
                    );
                  }
                }}
              >
                {item}
              </button>
            )
          )}
        </nav>
      )}
    </div>
  );
}