from __future__ import annotations

import time
import numpy as np
from app.voice.wake_word import WakeWordDetector


class WakeWordAdapter:
    """Feed shared float32 microphone chunks into the frozen legacy ONNX detector."""

    def __init__(self, detector=None, check_interval_seconds: float = 0.25):
        if check_interval_seconds <= 0:
            raise ValueError("check_interval_seconds must be positive")
        self.detector = detector or WakeWordDetector()
        self.check_interval_samples = int(
            self.detector.sample_rate * check_interval_seconds
        )
        self._samples_since_check = 0

    def process(self, audio: np.ndarray) -> bool:
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return False
        if not np.all(np.isfinite(samples)):
            raise ValueError("Audio contains NaN or infinite values")

        pcm16 = np.clip(samples * 32768.0, -32768, 32767).astype(np.int16)
        self.detector._add_audio(pcm16)
        self._samples_since_check += pcm16.size

        if self.detector._samples_collected < self.detector.window_size:
            return False
        if self._samples_since_check < self.check_interval_samples:
            return False

        self._samples_since_check = 0
        window = self.detector._get_audio_window()
        if self.detector._calculate_rms(window) < self.detector.min_rms:
            return False

        score = self.detector._detect(window)
        if score < self.detector.threshold:
            return False

        now = time.monotonic()
        if now - self.detector.last_detection_time < self.detector.cooldown_seconds:
            return False

        self.detector.last_detection_time = now
        print(f"\\n[WAKE] Hey EDITH detected | Score: {score:.4f}")
        return True

    def reset(self) -> None:
        self.detector.reset()
        self._samples_since_check = 0
