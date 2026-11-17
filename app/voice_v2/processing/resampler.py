from __future__ import annotations

import numpy as np

try:
    import soxr
except ImportError:
    soxr = None


class AudioResampler:
    """High-quality streaming/offline resampling using python-soxr."""

    def __init__(self, quality: str = "HQ"):
        if soxr is None:
            raise ImportError(
                "python-soxr is required. Install it with: pip install soxr"
            )
        self.quality = quality

    def resample(
        self,
        audio: np.ndarray,
        input_rate: int,
        output_rate: int,
    ) -> np.ndarray:
        if input_rate <= 0 or output_rate <= 0:
            raise ValueError("Sample rates must be positive")
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if samples.size == 0 or input_rate == output_rate:
            return samples.copy()
        converted = soxr.resample(
            samples,
            input_rate,
            output_rate,
            quality=self.quality,
        )
        return np.asarray(converted, dtype=np.float32).reshape(-1)

    def create_stream(self, input_rate: int, output_rate: int):
        if input_rate <= 0 or output_rate <= 0:
            raise ValueError("Sample rates must be positive")
        if input_rate == output_rate:
            return None
        return soxr.ResampleStream(
            input_rate,
            output_rate,
            num_channels=1,
            dtype="float32",
            quality=self.quality,
        )
