from __future__ import annotations

import time
import numpy as np
from app.voice.wake_word import WakeWordDetector


class WakeWordAdapter:
    """Feed shared float32 microphone chunks into the frozen legacy ONNX detector."""

    def __init__(
        self,
        detector=None,
        check_interval_seconds: float = 0.25,
        *,
        vad=None,
        wake_threshold: float = 0.94,
        vad_threshold: float = 0.55,
        required_consecutive_hits: int = 2,
        vad_speech_timeout_seconds: float = 1.0,
    ):
        if check_interval_seconds <= 0:
            raise ValueError("check_interval_seconds must be positive")
        if not 0 <= wake_threshold <= 1:
            raise ValueError("wake_threshold must be between 0 and 1")
        if not 0 <= vad_threshold <= 1:
            raise ValueError("vad_threshold must be between 0 and 1")
        if required_consecutive_hits < 1:
            raise ValueError("required_consecutive_hits must be positive")
        if vad_speech_timeout_seconds <= 0:
            raise ValueError("vad_speech_timeout_seconds must be positive")
        self.detector = detector or WakeWordDetector()
        self.vad = vad
        self.check_interval_samples = int(
            self.detector.sample_rate * check_interval_seconds
        )
        self.wake_threshold = wake_threshold
        self.vad_threshold = vad_threshold
        self.required_consecutive_hits = required_consecutive_hits
        self.vad_speech_timeout_seconds = vad_speech_timeout_seconds
        self._samples_since_check = 0
        self._last_vad_speech_time = None
        self._consecutive_hits = 0

    def _contains_speech(self, result) -> bool:
        if result is None:
            return False
        if isinstance(result, (bool, np.bool_)):
            return bool(result)
        probabilities = np.asarray(result, dtype=np.float32).reshape(-1)
        return bool(
            probabilities.size
            and np.any(probabilities >= self.vad_threshold)
        )

    def process(self, audio: np.ndarray) -> bool:
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return False
        if not np.all(np.isfinite(samples)):
            raise ValueError("Audio contains NaN or infinite values")

        if self.vad is not None:
            if self._contains_speech(self.vad.process(samples)):
                self._last_vad_speech_time = time.monotonic()

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
            self._consecutive_hits = 0
            return False

        now = time.monotonic()
        vad_speech = (
            self.vad is None
            or (
                self._last_vad_speech_time is not None
                and now - self._last_vad_speech_time
                <= self.vad_speech_timeout_seconds
            )
        )
        score = self.detector._detect(window)
        if not vad_speech or score < self.wake_threshold:
            self._consecutive_hits = 0
            return False

        if now - self.detector.last_detection_time < self.detector.cooldown_seconds:
            self._consecutive_hits = 0
            return False

        self._consecutive_hits += 1
        if self._consecutive_hits < self.required_consecutive_hits:
            return False

        self._consecutive_hits = 0
        self.detector.last_detection_time = now
        print(f"\\n[WAKE] Hey EDITH detected | Score: {score:.4f}")
        return True

    def reset(self) -> None:
        self.detector.reset()
        if self.vad is not None:
            self.vad.reset()
        self._samples_since_check = 0
        self._last_vad_speech_time = None
        self._consecutive_hits = 0
