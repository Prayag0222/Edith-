from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True, slots=True)
class AudioMetrics:
    rms: float
    peak: float
    clipping_ratio: float
    is_silent: bool


class AudioProcessor:
    """Lightweight measurement and validation; does not destructively denoise."""

    def __init__(self, silence_rms_threshold: float = 0.002,
                 clipping_threshold: float = 0.999):
        if silence_rms_threshold < 0:
            raise ValueError("silence_rms_threshold cannot be negative")
        if not 0 < clipping_threshold <= 1:
            raise ValueError("clipping_threshold must be in (0, 1]")
        self.silence_rms_threshold = silence_rms_threshold
        self.clipping_threshold = clipping_threshold

    @staticmethod
    def normalize_input(audio: np.ndarray) -> np.ndarray:
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if not np.all(np.isfinite(samples)):
            raise ValueError("Audio contains NaN or infinite values")
        return samples

    def analyze(self, audio: np.ndarray) -> AudioMetrics:
        samples = self.normalize_input(audio)
        if samples.size == 0:
            return AudioMetrics(0.0, 0.0, 0.0, True)

        # float64 accumulation avoids unnecessary precision loss for long clips.
        rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
        peak = float(np.max(np.abs(samples)))
        clipping_ratio = float(np.count_nonzero(
            np.abs(samples) >= self.clipping_threshold
        ) / samples.size)

        return AudioMetrics(
            rms=rms,
            peak=peak,
            clipping_ratio=clipping_ratio,
            is_silent=rms < self.silence_rms_threshold,
        )
