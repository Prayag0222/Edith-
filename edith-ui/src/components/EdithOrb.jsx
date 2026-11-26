import { useEffect, useRef } from "react";
import { edithLiveStore } from "../bridge/edithBridge.js";
import { damp } from "../engine/lerp.js";
import { ORB_STATES, createParticlePool } from "../engine/orbConfig.js";
import {
  drawAtmosphericGlow,
  drawCoreAndSphere,
  drawEnergyPulses,
  drawOrbitalParticles,
  drawOrbitalPaths,
  drawScanningLines,
  drawTechnicalRings,
} from "../engine/orbLayers.js";

export default function EdithOrb({ state }) {
  const canvasRef = useRef(null);
  const wakeLoopRef = useRef(null);

  // Trigger loop restart whenever state leaves SLEEPING
  useEffect(() => {
    if (state !== "SLEEPING" && wakeLoopRef.current) {
      wakeLoopRef.current();
    }
  }, [state]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d", { alpha: true });
    let rafId = 0;
    let running = false;
    let lastTs = 0;
    let width = 0;
    let height = 0;

    // Continuous motion accumulators (never reset on state change)
    let elapsed = 0;
    let ringAngle = 0;
    let scanAngle = 0;
    let particleTime = 0;
    let smoothedAudio = 0;

    // Current interpolated visual parameters
    const cur = { ...ORB_STATES.SLEEPING };
    const particles = createParticlePool(22);

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const stopLoop = () => {
      running = false;
      cancelAnimationFrame(rafId);
    };

    const draw = (now) => {
      if (!running) return;

      const dt = lastTs ? Math.min((now - lastTs) / 1000, 0.05) : 0.016;
      lastTs = now;
      elapsed += dt;

      const activeState = edithLiveStore.state;
      const target = ORB_STATES[activeState] || ORB_STATES.SLEEPING;

      // Smoothly interpolate all state parameters
      const speed = 5.5;
      cur.opacity = damp(cur.opacity, target.opacity, 4.5, dt);
      cur.scale = damp(cur.scale, target.scale, 4.5, dt);
      cur.ringSpeed = damp(cur.ringSpeed, target.ringSpeed, speed, dt);
      cur.particleSpeed = damp(cur.particleSpeed, target.particleSpeed, speed, dt);
      cur.coreIntensity = damp(cur.coreIntensity, target.coreIntensity, speed, dt);
      cur.auraIntensity = damp(cur.auraIntensity, target.auraIntensity, speed, dt);
      cur.breathSpeed = damp(cur.breathSpeed, target.breathSpeed, 4.0, dt);
      cur.breathAmp = damp(cur.breathAmp, target.breathAmp, 4.0, dt);
      cur.scanAlpha = damp(cur.scanAlpha, target.scanAlpha, 4.0, dt);
      cur.audioWeight = damp(cur.audioWeight, target.audioWeight, 6.0, dt);
      cur.hue = damp(cur.hue, target.hue, 4.0, dt);
      cur.accentHue = damp(cur.accentHue, target.accentHue, 4.0, dt);
      cur.accentAlpha = damp(cur.accentAlpha, target.accentAlpha, 4.0, dt);

      // Pause loop completely once dissolved into SLEEPING
      if (activeState === "SLEEPING" && cur.opacity < 0.01) {
        ctx.clearRect(0, 0, width, height);
        stopLoop();
        return;
      }

      // Smooth real-time audio reactivity (fast attack, gentle release)
      const rawAudio = edithLiveStore.audioLevel * cur.audioWeight;
      const audioLambda = rawAudio > smoothedAudio ? 18 : 7;
      smoothedAudio = damp(smoothedAudio, rawAudio, audioLambda, dt);

      // Advance continuous motion accumulators
      ringAngle += dt * cur.ringSpeed;
      scanAngle += dt * (0.65 + cur.ringSpeed * 0.75);
      particleTime += dt * cur.particleSpeed;

      const breath = Math.sin(elapsed * cur.breathSpeed) * cur.breathAmp;
      const baseRadius = Math.min(width, height) * 0.255 * (1 + breath + smoothedAudio * 0.06);

      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalAlpha = cur.opacity;
      ctx.translate(width / 2, height / 2);
      ctx.scale(cur.scale, cur.scale);

      drawAtmosphericGlow(ctx, baseRadius, cur, smoothedAudio);
      drawOrbitalPaths(ctx, baseRadius, cur, ringAngle);
      drawTechnicalRings(ctx, baseRadius, cur, ringAngle, smoothedAudio);
      drawScanningLines(ctx, baseRadius, cur, scanAngle);
      drawOrbitalParticles(ctx, baseRadius, cur, particles, particleTime, smoothedAudio);
      drawEnergyPulses(
        ctx,
        baseRadius,
        cur,
        now,
        edithLiveStore.wakePulseAt,
        smoothedAudio,
        activeState === "SPEAKING",
        elapsed
      );
      drawCoreAndSphere(ctx, baseRadius, cur, smoothedAudio);

      ctx.restore();
      rafId = requestAnimationFrame(draw);
    };

    const startLoop = () => {
      if (running || document.hidden) return;
      running = true;
      lastTs = 0;
      rafId = requestAnimationFrame(draw);
    };

    wakeLoopRef.current = startLoop;

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);

    const onVisibility = () => {
      if (document.hidden) {
        stopLoop();
      } else if (edithLiveStore.state !== "SLEEPING") {
        startLoop();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    if (edithLiveStore.state !== "SLEEPING") {
      startLoop();
    }

    return () => {
      stopLoop();
      wakeLoopRef.current = null;
      observer.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="orb-canvas"
      aria-label={`EDITH ${state.toLowerCase()} intelligence core`}
    />
  );
}