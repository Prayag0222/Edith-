import { useEffect, useRef } from "react";
import { edithLiveStore } from "../bridge/edithBridge.js";
import { damp } from "../engine/lerp.js";

export default function AudioVisualizer({ state }) {
  const canvasRef = useRef(null);
  const active = state === "LISTENING" || state === "SPEAKING";

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    const width = 92;
    const height = 14;
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    let rafId = 0;
    let lastTs = 0;
    let phase = 0;
    let amp = 0;

    const draw = (now) => {
      const dt = lastTs ? Math.min((now - lastTs) / 1000, 0.05) : 0.016;
      lastTs = now;

      const isReactive =
        edithLiveStore.state === "LISTENING" || edithLiveStore.state === "SPEAKING";
      const targetAmp = isReactive ? Math.max(0.08, edithLiveStore.audioLevel) : 0;
      amp = damp(amp, targetAmp, 10, dt);
      phase += dt * (isReactive ? 7.5 : 2.0);

      ctx.clearRect(0, 0, width, height);

      const midY = height / 2;
      ctx.beginPath();
      for (let x = 0; x <= width; x += 2) {
        const norm = x / width;
        const envelope = Math.sin(norm * Math.PI); // Taper cleanly at both ends
        const wave =
          Math.sin(norm * 14 + phase) * 0.65 +
          Math.sin(norm * 24 - phase * 1.3) * 0.35;
        const y = midY + wave * envelope * amp * (midY - 1.5);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }

      const grad = ctx.createLinearGradient(0, 0, width, 0);
      grad.addColorStop(0, "rgba(56, 189, 248, 0)");
      grad.addColorStop(0.2, `rgba(186, 230, 253, ${0.45 + amp * 0.45})`);
      grad.addColorStop(0.8, `rgba(45, 212, 191, ${0.45 + amp * 0.45})`);
      grad.addColorStop(1, "rgba(56, 189, 248, 0)");

      ctx.strokeStyle = grad;
      ctx.lineWidth = 1.25;
      ctx.stroke();

      if (isReactive || amp > 0.01) {
        rafId = requestAnimationFrame(draw);
      }
    };

    rafId = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafId);
  }, [active]);

  const caption =
    state === "SPEAKING"
      ? "VOICE OUTPUT"
      : state === "LISTENING"
        ? "VOICE INPUT"
        : state === "THINKING"
          ? "LOCAL INFERENCE"
          : "STANDBY LINK";

  return (
    <div className="micro-line flex items-center gap-3">
      <canvas ref={canvasRef} className="audio-line-canvas" />
      <span className="micro-caption">{caption}</span>
    </div>
  );
}