from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .audio_input import AudioChunk


class AudioRingBuffer:
    """Thread-safe fixed-duration rolling buffer for pre-roll and recent audio."""

    def __init__(self, capacity_seconds: float, sample_rate: int = 16000):
        if capacity_seconds <= 0:
            raise ValueError("capacity_seconds must be positive")
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")

        self.sample_rate = sample_rate
        self.capacity_samples = max(1, int(round(capacity_seconds * sample_rate)))
        self._buffer = np.zeros(self.capacity_samples, dtype=np.float32)
        self._write_pos = 0
        self._size = 0
        self._lock = threading.RLock()

    @property
    def size(self) -> int:
        with self._lock:
            return self._size

    @property
    def duration_seconds(self) -> float:
        with self._lock:
            return self._size / self.sample_rate

    def append(self, audio: np.ndarray | AudioChunk) -> None:
        if isinstance(audio, AudioChunk):
            if audio.sample_rate != self.sample_rate:
                raise ValueError(
                    f"Expected {self.sample_rate} Hz, received {audio.sample_rate} Hz"
                )
            samples = audio.samples
        else:
            samples = audio

        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return
        if not np.all(np.isfinite(samples)):
            raise ValueError("Audio contains NaN or infinite values")

        with self._lock:
            if samples.size >= self.capacity_samples:
                self._buffer[:] = samples[-self.capacity_samples:]
                self._write_pos = 0
                self._size = self.capacity_samples
                return

            first = min(samples.size, self.capacity_samples - self._write_pos)
            self._buffer[self._write_pos:self._write_pos + first] = samples[:first]
            remaining = samples.size - first
            if remaining:
                self._buffer[:remaining] = samples[first:]

            self._write_pos = (self._write_pos + samples.size) % self.capacity_samples
            self._size = min(self.capacity_samples, self._size + samples.size)

    def get_audio(self, copy: bool = True) -> np.ndarray:
        """Return buffered samples oldest-to-newest."""
        with self._lock:
            if self._size == 0:
                result = np.empty(0, dtype=np.float32)
            elif self._size < self.capacity_samples:
                result = self._buffer[:self._size]
            elif self._write_pos == 0:
                result = self._buffer
            else:
                result = np.concatenate((
                    self._buffer[self._write_pos:],
                    self._buffer[:self._write_pos],
                ))
            return result.copy() if copy else result

    def clear(self) -> None:
        with self._lock:
            self._buffer.fill(0)
            self._write_pos = 0
            self._size = 0


class AudioAccumulator:
    """
    Accumulates a complete utterance across many microphone chunks.

    Unlike AudioRingBuffer, this does not discard old samples. Default maximum
    duration is 10 minutes, allowing 5-minute speech with headroom.
    """

    def __init__(self, sample_rate: int = 16000, max_duration_seconds: float = 600):
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if max_duration_seconds <= 0:
            raise ValueError("max_duration_seconds must be positive")
        self.sample_rate = sample_rate
        self.max_samples = int(sample_rate * max_duration_seconds)
        self._parts: list[np.ndarray] = []
        self._sample_count = 0
        self._lock = threading.RLock()

    @property
    def sample_count(self) -> int:
        with self._lock:
            return self._sample_count

    @property
    def duration_seconds(self) -> float:
        with self._lock:
            return self._sample_count / self.sample_rate

    @property
    def is_full(self) -> bool:
        with self._lock:
            return self._sample_count >= self.max_samples

    def append(self, audio: np.ndarray | AudioChunk) -> int:
        if isinstance(audio, AudioChunk):
            if audio.sample_rate != self.sample_rate:
                raise ValueError(
                    f"Expected {self.sample_rate} Hz, received {audio.sample_rate} Hz"
                )
            samples = audio.samples
        else:
            samples = audio

        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return 0
        if not np.all(np.isfinite(samples)):
            raise ValueError("Audio contains NaN or infinite values")

        with self._lock:
            remaining = self.max_samples - self._sample_count
            if remaining <= 0:
                return 0
            accepted = min(samples.size, remaining)
            # Own the memory: incoming callback buffers may be reused elsewhere.
            self._parts.append(samples[:accepted].copy())
            self._sample_count += accepted
            return accepted

    def get_audio(self) -> np.ndarray:
        with self._lock:
            if not self._parts:
                return np.empty(0, dtype=np.float32)
            if len(self._parts) == 1:
                return self._parts[0].copy()
            return np.concatenate(self._parts).astype(np.float32, copy=False)

    def clear(self) -> None:
        with self._lock:
            self._parts.clear()
            self._sample_count = 0


@dataclass(frozen=True, slots=True)
class AudioFrame:
    samples: np.ndarray
    sample_rate: int
    start_sample: int
    end_sample: int


def iter_audio_frames(
    audio: np.ndarray,
    sample_rate: int = 16000,
    frame_duration_ms: int = 20,
    include_partial: bool = False,
):
    """Yield contiguous frames; final short frame is optional."""
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if frame_duration_ms <= 0:
        raise ValueError("frame_duration_ms must be positive")

    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    frame_size = int(sample_rate * frame_duration_ms / 1000)
    if frame_size <= 0:
        raise ValueError("Frame duration is too small for this sample rate")

    for start in range(0, samples.size, frame_size):
        end = min(start + frame_size, samples.size)
        if end - start < frame_size and not include_partial:
            break
        frame = samples[start:end].copy()
        frame.setflags(write=False)
        yield AudioFrame(frame, sample_rate, start, end)
