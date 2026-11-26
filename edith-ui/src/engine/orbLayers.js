import { easeOutCubic } from "./lerp.js";

/**
 * Layer 1: Outer atmospheric glow (replaces heavy CSS filter: blur).
 */
export function drawAtmosphericGlow(ctx, baseRadius, cur, audio) {
  const glowRadius = baseRadius * (2.05 + audio * 0.22);
  const alpha = cur.auraIntensity * (1 + audio * 0.45);

  const grad = ctx.createRadialGradient(0, 0, baseRadius * 0.18, 0, 0, glowRadius);
  grad.addColorStop(0, `hsla(${cur.hue}, 96%, 72%, ${alpha})`);
  grad.addColorStop(0.45, `hsla(${cur.hue + 8}, 90%, 54%, ${alpha * 0.38})`);
  grad.addColorStop(1, "rgba(0, 0, 0, 0)");

  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(0, 0, glowRadius, 0, Math.PI * 2);
  ctx.fill();

  // Subtle secondary accent bloom (turquoise or faint violet in THINKING)
  if (cur.accentAlpha > 0.01) {
    const accent = ctx.createRadialGradient(0, 0, baseRadius * 0.2, 0, 0, glowRadius * 0.85);
    accent.addColorStop(0, `hsla(${cur.accentHue}, 85%, 68%, ${cur.accentAlpha})`);
    accent.addColorStop(0.6, `hsla(${cur.accentHue}, 80%, 50%, ${cur.accentAlpha * 0.25})`);
    accent.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = accent;
    ctx.beginPath();
    ctx.arc(0, 0, glowRadius * 0.85, 0, Math.PI * 2);
    ctx.fill();
  }
}

/**
 * Layer 2: Hairline orbital tracks.
 */
export function drawOrbitalPaths(ctx, baseRadius, cur, angleBase) {
  ctx.save();
  ctx.rotate(angleBase * 0.12);

  const tracks = [
    { rx: baseRadius + 24, ry: (baseRadius + 24) * 0.84, rot: 0.35, alpha: 0.16 },
    { rx: baseRadius + 38, ry: (baseRadius + 38) * 0.88, rot: -0.52, alpha: 0.11 },
  ];

  for (const track of tracks) {
    ctx.save();
    ctx.rotate(track.rot);
    ctx.beginPath();
    ctx.setLineDash([2, 6]);
    ctx.lineWidth = 0.75;
    ctx.strokeStyle = `hsla(${cur.hue}, 95%, 82%, ${track.alpha})`;
    ctx.ellipse(0, 0, track.rx, track.ry, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  ctx.restore();
}

/**
 * Layer 3: Precision rotating technical rings + tick marks.
 */
export function drawTechnicalRings(ctx, baseRadius, cur, ringAngle, audio) {
  const expand = audio * 6;
  const rings = [
    { r: baseRadius + 15 + expand * 0.5, dir: 1, mult: 0.55, w: 1.15, dash: [24, 7, 3, 7], a: 0.58 },
    { r: baseRadius + 25 + expand * 0.8, dir: -1, mult: 0.38, w: 0.85, dash: [2, 6], a: 0.36 },
    { r: baseRadius + 36 + expand, dir: 1, mult: 0.24, w: 1.0, dash: [42, 12, 6, 12], a: 0.44 },
  ];

  rings.forEach((ring, idx) => {
    ctx.save();
    ctx.rotate(ringAngle * ring.dir * ring.mult);
    ctx.beginPath();
    ctx.setLineDash(ring.dash);
    ctx.lineWidth = ring.w;
    ctx.strokeStyle = `hsla(${cur.hue + idx * 6}, 95%, ${idx === 1 ? 82 : 74}%, ${ring.a})`;
    ctx.arc(0, 0, ring.r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  });

  // Precision radial ticks around the inner engineering ring
  const tickCount = 24;
  ctx.save();
  ctx.rotate(-ringAngle * 0.14);
  for (let i = 0; i < tickCount; i++) {
    const theta = (i / tickCount) * Math.PI * 2;
    const major = i % 6 === 0;
    const r0 = baseRadius + 8;
    const r1 = baseRadius + (major ? 14 : 11) + audio * (major ? 4 : 2);
    ctx.beginPath();
    ctx.moveTo(Math.cos(theta) * r0, Math.sin(theta) * r0);
    ctx.lineTo(Math.cos(theta) * r1, Math.sin(theta) * r1);
    ctx.lineWidth = major ? 1.2 : 0.65;
    ctx.strokeStyle = `hsla(${cur.hue}, 100%, 86%, ${major ? 0.52 : 0.22})`;
    ctx.stroke();
  }
  ctx.restore();
}

/**
 * Layer 4: Subtle sweeping scan arcs (prominent in THINKING).
 */
export function drawScanningLines(ctx, baseRadius, cur, scanAngle) {
  if (cur.scanAlpha <= 0.02) return;

  const r = baseRadius + 30;
  for (let i = 0; i < 2; i++) {
    ctx.save();
    ctx.rotate(scanAngle * (i === 0 ? 1 : -0.68) + i * Math.PI);
    ctx.beginPath();
    ctx.setLineDash([]);
    ctx.lineWidth = i === 0 ? 2.0 : 1.2;
    ctx.strokeStyle = `hsla(${i === 0 ? cur.hue : cur.accentHue}, 100%, 80%, ${cur.scanAlpha * (i === 0 ? 0.85 : 0.55)})`;
    ctx.arc(0, 0, r + i * 7, -0.45, 0.45);
    ctx.stroke();
    ctx.restore();
  }
}

/**
 * Layer 5: Low-count orbital particles (no per-particle shadowBlur for speed).
 */
export function drawOrbitalParticles(ctx, baseRadius, cur, particles, particleTime, audio) {
  for (let i = 0; i < particles.length; i++) {
    const p = particles[i];
    const theta = p.angle + particleTime * p.speed;
    const r = baseRadius + p.radiusOffset + Math.sin(particleTime * 0.9 + p.phase) * 3 + audio * 6;
    const x = Math.cos(theta) * r;
    const y = Math.sin(theta) * r * p.tilt;
    const alpha = 0.28 + 0.35 * (0.5 + 0.5 * Math.sin(particleTime * 1.4 + p.phase));

    // Soft halo dot
    ctx.fillStyle = `hsla(${cur.hue + (i % 4) * 6}, 100%, 78%, ${alpha * 0.28})`;
    ctx.beginPath();
    ctx.arc(x, y, p.size * 2.4, 0, Math.PI * 2);
    ctx.fill();

    // Crisp center point
    ctx.fillStyle = `hsla(${cur.hue}, 100%, 92%, ${alpha})`;
    ctx.beginPath();
    ctx.arc(x, y, p.size, 0, Math.PI * 2);
    ctx.fill();
  }
}

/**
 * Layer 6: Wake-word activation ripple & rhythmic speaking pulses.
 */
export function drawEnergyPulses(ctx, baseRadius, cur, now, wakePulseAt, audio, isSpeaking, time) {
  // Activation ripple on wake word (900ms expansion)
  if (wakePulseAt > 0) {
    const elapsed = (now - wakePulseAt) / 900;
    if (elapsed >= 0 && elapsed < 1) {
      const eased = easeOutCubic(elapsed);
      const r = baseRadius * 0.9 + eased * 56;
      ctx.beginPath();
      ctx.setLineDash([]);
      ctx.lineWidth = 1.6 * (1 - eased);
      ctx.strokeStyle = `hsla(${cur.hue}, 100%, 84%, ${(1 - eased) * 0.65})`;
      ctx.arc(0, 0, r, 0, Math.PI * 2);
      ctx.stroke();
    }
  }

  // Smooth outward energy pulses while SPEAKING
  if (isSpeaking && audio > 0.03) {
    for (let i = 0; i < 2; i++) {
      const progress = (time * 0.75 + i * 0.5) % 1;
      const r = baseRadius + 20 + progress * 36;
      const alpha = (1 - progress) * audio * 0.48;
      ctx.beginPath();
      ctx.setLineDash([]);
      ctx.lineWidth = 1.1;
      ctx.strokeStyle = `hsla(${cur.hue}, 100%, 82%, ${alpha})`;
      ctx.arc(0, 0, r, 0, Math.PI * 2);
      ctx.stroke();
    }
  }
}

/**
 * Layer 7 & 8: Inner translucent energy sphere + central glowing core.
 */
export function drawCoreAndSphere(ctx, baseRadius, cur, audio) {
  const shellR = baseRadius * (0.94 + audio * 0.08);

  // Layer 7: Inner glowing sphere
  const shell = ctx.createRadialGradient(-shellR * 0.24, -shellR * 0.26, 2, 0, 0, shellR);
  shell.addColorStop(0, `rgba(240, 252, 255, ${0.34 * cur.coreIntensity})`);
  shell.addColorStop(0.32, `hsla(${cur.hue}, 98%, 68%, ${0.28 * cur.coreIntensity})`);
  shell.addColorStop(0.75, `hsla(${cur.hue + 10}, 92%, 42%, ${0.12 * cur.coreIntensity})`);
  shell.addColorStop(1, "rgba(0, 0, 0, 0)");

  ctx.fillStyle = shell;
  ctx.beginPath();
  ctx.arc(0, 0, shellR, 0, Math.PI * 2);
  ctx.fill();

  // Thin containment ring around the inner sphere
  ctx.beginPath();
  ctx.setLineDash([]);
  ctx.lineWidth = 0.85;
  ctx.strokeStyle = `rgba(214, 246, 255, ${0.42 * cur.coreIntensity + audio * 0.2})`;
  ctx.arc(0, 0, shellR * 0.72, 0, Math.PI * 2);
  ctx.stroke();

  // Layer 8: Central high-luminance energy core
  const coreR = shellR * (0.48 + audio * 0.14);
  const core = ctx.createRadialGradient(-coreR * 0.12, -coreR * 0.14, 1, 0, 0, coreR);
  core.addColorStop(0, `rgba(255, 255, 255, ${0.98 * cur.coreIntensity})`);
  core.addColorStop(0.18, `hsla(${cur.hue}, 100%, 88%, ${0.82 * cur.coreIntensity})`);
  core.addColorStop(0.5, `hsla(${cur.hue}, 100%, 62%, ${0.26 * cur.coreIntensity})`);
  core.addColorStop(1, "rgba(0, 0, 0, 0)");

  ctx.fillStyle = core;
  ctx.beginPath();
  ctx.arc(0, 0, coreR, 0, Math.PI * 2);
  ctx.fill();
}