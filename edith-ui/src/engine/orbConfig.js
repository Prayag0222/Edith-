export const ORB_STATES = {
  SLEEPING: {
    opacity: 0,
    scale: 0.86,
    ringSpeed: 0.15,
    particleSpeed: 0.2,
    coreIntensity: 0.15,
    auraIntensity: 0.05,
    breathSpeed: 0.8,
    breathAmp: 0.005,
    scanAlpha: 0,
    audioWeight: 0,
    hue: 196,
    accentHue: 235,
    accentAlpha: 0,
  },
  READY: {
    opacity: 1,
    scale: 1.0,
    ringSpeed: 0.65,
    particleSpeed: 0.7,
    coreIntensity: 0.72,
    auraIntensity: 0.24,
    breathSpeed: 1.25,
    breathAmp: 0.018,
    scanAlpha: 0.14,
    audioWeight: 0.15,
    hue: 196, // Electric cyan / ice blue
    accentHue: 180, // Light turquoise
    accentAlpha: 0.08,
  },
  LISTENING: {
    opacity: 1,
    scale: 1.03,
    ringSpeed: 0.95,
    particleSpeed: 1.05,
    coreIntensity: 0.92,
    auraIntensity: 0.34,
    breathSpeed: 1.8,
    breathAmp: 0.022,
    scanAlpha: 0.25,
    audioWeight: 0.85, // Mic reactivity
    hue: 191,
    accentHue: 174,
    accentAlpha: 0.12,
  },
  THINKING: {
    opacity: 1,
    scale: 1.0,
    ringSpeed: 1.85,
    particleSpeed: 2.1,
    coreIntensity: 0.88,
    auraIntensity: 0.32,
    breathSpeed: 2.6,
    breathAmp: 0.015,
    scanAlpha: 0.68, // Sweeping computational scan arc
    audioWeight: 0,
    hue: 202, // Deep electric cyan
    accentHue: 248, // Subtle violet accent (<15%)
    accentAlpha: 0.14,
  },
  SPEAKING: {
    opacity: 1,
    scale: 1.04,
    ringSpeed: 1.15,
    particleSpeed: 1.25,
    coreIntensity: 1.0,
    auraIntensity: 0.38,
    breathSpeed: 3.1,
    breathAmp: 0.028,
    scanAlpha: 0.22,
    audioWeight: 1.0, // Full TTS reactivity
    hue: 188,
    accentHue: 172,
    accentAlpha: 0.12,
  },
};

export function createParticlePool(count = 22) {
  return Array.from({ length: count }, (_, i) => ({
    angle: (i / count) * Math.PI * 2,
    radiusOffset: 18 + (i % 5) * 9,
    speed: (i % 2 === 0 ? 1 : -1) * (0.22 + (i % 4) * 0.09),
    size: 0.9 + (i % 3) * 0.45,
    tilt: 0.78 + (i % 3) * 0.08,
    phase: i * 1.37,
  }));
}