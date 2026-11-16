from __future__ import annotations

from dataclasses import dataclass
import time

import numpy as np

from app.voice_v2.core.audio_buffer import AudioRingBuffer, AudioAccumulator
from .silero_vad import SileroVAD


@dataclass(frozen=True, slots=True)
class EndpointConfig:
    sample_rate: int = 16000

    pre_roll_seconds: float = 0.5

    start_threshold: float = 0.55
    continue_threshold: float = 0.35

    start_confirm_ms: int = 64

    # Short commands should finish relatively quickly.
    end_silence_ms: int = 1000

    # Longer speech should tolerate natural thinking/breathing pauses.
    long_speech_end_silence_ms: int = 3500

    # Switch to long-speech endpointing after this much actual speech.
    adaptive_after_speech_ms: int = 1200

    min_utterance_ms: int = 120

    max_utterance_seconds: float = 600.0

    adaptive_endpointing: bool = True

    def __post_init__(self):
        if self.sample_rate not in (8000, 16000):
            raise ValueError("Endpoint detector supports 8 kHz or 16 kHz")

        if self.pre_roll_seconds < 0:
            raise ValueError("pre_roll_seconds cannot be negative")

        if not 0 < self.continue_threshold <= self.start_threshold < 1:
            raise ValueError("Invalid VAD thresholds")

        if self.start_confirm_ms < 0:
            raise ValueError("start_confirm_ms cannot be negative")

        if self.end_silence_ms <= 0:
            raise ValueError("end_silence_ms must be positive")

        if self.long_speech_end_silence_ms <= 0:
            raise ValueError("long_speech_end_silence_ms must be positive")

        if self.adaptive_after_speech_ms < 0:
            raise ValueError("adaptive_after_speech_ms cannot be negative")

        if self.max_utterance_seconds <= 0:
            raise ValueError("max_utterance_seconds must be positive")


@dataclass(frozen=True, slots=True)
class SpeechSegment:
    audio: np.ndarray
    sample_rate: int
    started_at: float
    ended_at: float
    speech_duration_seconds: float
    ended_by: str

    @property
    def duration_seconds(self) -> float:
        return self.audio.size / self.sample_rate


class AdaptiveEndpointDetector:

    def __init__(
        self,
        vad: SileroVAD,
        config: EndpointConfig | None = None,
    ):
        self.vad = vad
        self.config = config or EndpointConfig()

        if vad.config.sample_rate != self.config.sample_rate:
            raise ValueError("VAD and endpoint sample rates must match")

        self.pre_roll = AudioRingBuffer(
            capacity_seconds=max(self.config.pre_roll_seconds, 0.032),
            sample_rate=self.config.sample_rate,
        )

        self._pending_audio = np.empty(0, dtype=np.float32)

        self._active = False
        self._utterance: AudioAccumulator | None = None

        self._start_confirm_samples = 0
        self._silence_samples = 0
        self._speech_samples = 0

        self._started_at = 0.0

    @property
    def is_speaking(self) -> bool:
        return self._active

    def reset(self):
        self.pre_roll.clear()

        self._pending_audio = np.empty(0, dtype=np.float32)

        self._active = False
        self._utterance = None

        self._start_confirm_samples = 0
        self._silence_samples = 0
        self._speech_samples = 0

        self._started_at = 0.0

        self.vad.reset()

    def _effective_end_silence_samples(self) -> int:

        duration_ms = self.config.end_silence_ms

        if (
            self.config.adaptive_endpointing
            and self._speech_samples >= (
                self.config.sample_rate
                * self.config.adaptive_after_speech_ms
                / 1000
            )
        ):
            duration_ms = self.config.long_speech_end_silence_ms

        return int(
            self.config.sample_rate * duration_ms / 1000
        )

    def process(self, audio: np.ndarray) -> SpeechSegment | None:

        samples = np.asarray(
            audio,
            dtype=np.float32,
        ).reshape(-1)

        if samples.size == 0:
            return None

        if not np.all(np.isfinite(samples)):
            raise ValueError("Audio contains NaN or infinite values")

        if self._pending_audio.size:
            combined = np.concatenate(
                (self._pending_audio, samples)
            )
        else:
            combined = samples

        frame_size = self.vad.frame_size

        complete_samples = (
            combined.size // frame_size
        ) * frame_size

        if complete_samples == 0:
            self._pending_audio = combined.copy()
            return None

        frames = combined[:complete_samples].reshape(
            -1,
            frame_size,
        )

        # Preserve unprocessed audio instead of discarding it.
        self._pending_audio = combined[complete_samples:].copy()

        for index, frame in enumerate(frames):

            probabilities = self.vad.process(frame)

            if not probabilities:
                continue

            probability = probabilities[0]

            frame = frame.copy()
            frame_samples = frame.size

            self.pre_roll.append(frame)

            is_speech_start = (
                probability >= self.config.start_threshold
            )

            is_speech_continue = (
                probability >= self.config.continue_threshold
            )

            # WAITING FOR SPEECH
            if not self._active:

                if is_speech_start:
                    self._start_confirm_samples += frame_samples
                else:
                    self._start_confirm_samples = 0

                required_samples = int(
                    self.config.sample_rate
                    * self.config.start_confirm_ms
                    / 1000
                )

                if self._start_confirm_samples >= required_samples:

                    self._begin_utterance()

                    if self._utterance is not None:
                        self._utterance.append(
                            self.pre_roll.get_audio()
                        )

                    self._speech_samples = frame_samples

                continue

            # ACTIVE SPEECH
            if self._utterance is not None:
                self._utterance.append(frame)

            if is_speech_continue:

                self._silence_samples = 0
                self._speech_samples += frame_samples

            else:

                self._silence_samples += frame_samples

            # Maximum recording duration
            if self._utterance and self._utterance.is_full:

                self._pending_audio = combined[
                    (index + 1) * frame_size:
                ].copy()

                return self._finish("max_duration")

            # Adaptive endpointing
            if (
                self._silence_samples
                >= self._effective_end_silence_samples()
            ):

                if (
                    self._utterance
                    and self._utterance.duration_seconds * 1000
                    >= self.config.min_utterance_ms
                ):

                    self._pending_audio = combined[
                        (index + 1) * frame_size:
                    ].copy()

                    return self._finish("silence")

                self._reset_after_short_noise()

        return None

    def _begin_utterance(self):

        self._active = True

        self._started_at = time.monotonic()

        self._utterance = AudioAccumulator(
            sample_rate=self.config.sample_rate,
            max_duration_seconds=self.config.max_utterance_seconds,
        )

        self._silence_samples = 0
        self._speech_samples = 0

    def _finish(self, reason: str) -> SpeechSegment:

        assert self._utterance is not None

        audio = self._utterance.get_audio()

        ended_at = time.monotonic()

        segment = SpeechSegment(
            audio=audio,
            sample_rate=self.config.sample_rate,
            started_at=self._started_at,
            ended_at=ended_at,
            speech_duration_seconds=(
                self._speech_samples / self.config.sample_rate
            ),
            ended_by=reason,
        )

        self._active = False
        self._utterance = None

        self._start_confirm_samples = 0
        self._silence_samples = 0
        self._speech_samples = 0

        self._started_at = 0.0

        self.vad.reset()
        self.pre_roll.clear()

        return segment

    def _reset_after_short_noise(self):

        self._active = False
        self._utterance = None

        self._start_confirm_samples = 0
        self._silence_samples = 0
        self._speech_samples = 0

        self._started_at = 0.0

        self.vad.reset()
        self.pre_roll.clear()