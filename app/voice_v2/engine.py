from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.voice_v2.core.audio_input import (
    AudioInputConfig,
    AudioInputService,
)
from app.voice_v2.detection.endpoint_detector import (
    AdaptiveEndpointDetector,
    EndpointConfig,
)
from app.voice_v2.detection.silero_vad import (
    SileroVAD,
    SileroVADConfig,
)
from app.voice_v2.recognition.config import STTConfig
from app.voice_v2.recognition.stt_engine import SpeechToTextEngine
from app.voice_v2.integration.wake_word_adapter import WakeWordAdapter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VoiceEngineConfig:
    sample_rate: int = 16000
    block_duration_ms: int = 20
    subscriber_queue_blocks: int = 100
    wake_queue_timeout: float = 0.5
    speech_start_timeout_seconds: float = 15.0
    max_utterance_seconds: float = 600.0


class VoiceEngine:
    """
    EDITH Voice Engine v2.

    Public interface:
        wait_for_wake_word() -> bool
        listen() -> dict | None
        close()

    A single AudioInputService owns the microphone.
    """

    def __init__(
        self,
        config: VoiceEngineConfig | None = None,
        *,
        audio_service: AudioInputService | None = None,
        wake_adapter: WakeWordAdapter | None = None,
        vad: SileroVAD | None = None,
        stt: SpeechToTextEngine | None = None,
    ):
        self.config = config or VoiceEngineConfig()

        self._audio_service = audio_service
        self._owns_audio_service = audio_service is None

        self._wake_adapter = wake_adapter
        self._vad = vad
        self._stt = stt

        self._endpoint: AdaptiveEndpointDetector | None = None
        self._subscription = None

        self._started = False
        self._wake_detected = False
        self._closed = False

    # --------------------------------------------------
    # INITIALIZATION
    # --------------------------------------------------

    def start(self) -> None:

        if self._closed:
            raise RuntimeError("VoiceEngine is closed")

        if self._started:
            return

        if self._audio_service is None:

            audio_config = AudioInputConfig(
                sample_rate=self.config.sample_rate,
                channels=1,
                block_duration_ms=self.config.block_duration_ms,
                dtype="float32",
                subscriber_queue_blocks=self.config.subscriber_queue_blocks,
                start=False,
            )

            self._audio_service = AudioInputService(audio_config)

        if self._wake_adapter is None:
            self._wake_adapter = WakeWordAdapter()

        if self._vad is None:
            self._vad = SileroVAD(
                SileroVADConfig(
                    sample_rate=self.config.sample_rate
                )
            )

        self._endpoint = AdaptiveEndpointDetector(
            self._vad,
            EndpointConfig(
                sample_rate=self.config.sample_rate,
                max_utterance_seconds=self.config.max_utterance_seconds,
            ),
        )

        if self._stt is None:
            self._stt = SpeechToTextEngine(
                STTConfig(
                    sample_rate=self.config.sample_rate
                )
            )

        self._subscription = self._audio_service.subscribe(
            max_blocks=self.config.subscriber_queue_blocks
        )

        if not self._audio_service.is_running:
            self._audio_service.start()

        self._started = True

        logger.info("EDITH Voice Engine v2 started")

    # --------------------------------------------------
    # WAKE WORD
    # --------------------------------------------------

    def wait_for_wake_word(self) -> bool:

        self.start()

        subscription = self._subscription
        wake_adapter = self._wake_adapter

        if subscription is None or wake_adapter is None:
            raise RuntimeError("VoiceEngine initialization incomplete")

        if self._wake_detected:
            return True

        # --------------------------------------------------
        # PREPARE FRESH WAKE DETECTION SESSION
        # --------------------------------------------------

        # Discard audio captured during the previous conversation
        # and Piper playback. We don't want EDITH hearing itself.
        discarded = subscription.discard_pending()

        # Reset the detector's rolling audio buffer and check timer.
        # This prevents previous conversation audio from affecting
        # the next wake-word detection session.
        wake_adapter.reset()

        if discarded:
            logger.debug(
                "Discarded %d stale microphone blocks", discarded
            )

        print("[READY] Waiting for wake word...")

        # --------------------------------------------------
        # CONTINUOUS WAKE WORD MONITORING
        # --------------------------------------------------

        while not self._closed:

            chunk = subscription.get(
                timeout=self.config.wake_queue_timeout
            )

            if chunk is None:
                continue

            if chunk.overflow_before_capture:
                logger.warning(
                    "Microphone reported an input overflow"
                )

            if wake_adapter.process(chunk.samples):

                self._wake_detected = True

                return True

        return False

    # --------------------------------------------------
    # SPEECH RECOGNITION
    # --------------------------------------------------

    def listen(self) -> dict | None:

        self.start()

        subscription = self._subscription
        endpoint = self._endpoint
        stt = self._stt

        if (
            subscription is None
            or endpoint is None
            or stt is None
        ):
            raise RuntimeError("VoiceEngine initialization incomplete")

        if not self._wake_detected:
            raise RuntimeError(
                "wait_for_wake_word() must detect wake word before listen()"
            )

        print("[LISTEN] Listening...")

        self._wake_detected = False

        endpoint.reset()

        listen_started = time.monotonic()

        while not self._closed:

            chunk = subscription.get(timeout=0.25)

            if chunk is None:

                if (
                    not endpoint.is_speaking
                    and time.monotonic() - listen_started
                    >= self.config.speech_start_timeout_seconds
                ):

                    print(
                        "[SLEEP] No speech detected. "
                        "Returning to wake-word mode."
                    )

                    return None

                continue

            if chunk.overflow_before_capture:
                logger.warning(
                    "Microphone input overflow during speech capture"
                )

            segment = endpoint.process(chunk.samples)

            if segment is None:
                continue

            if segment.audio.size == 0:
                continue

            print(
                f"[STT] Transcribing {segment.duration_seconds:.2f}s "
                f"utterance ({segment.ended_by})..."
            )

            result = stt.transcribe(segment.audio)

            if result is None:

                print("[STT] No speech recognized.")

                return {"text": ""}

            payload = result.to_dict()

            print(
                f"[STT] {payload.get('device', 'unknown')} | "
                f"{payload.get('processing_seconds', 0.0):.2f}s"
            )

            return payload

        return None

    # --------------------------------------------------
    # STATUS
    # --------------------------------------------------

    def get_stats(self) -> dict:

        if self._audio_service is None:
            return {"started": False}

        return self._audio_service.get_stats()

    # --------------------------------------------------
    # SHUTDOWN
    # --------------------------------------------------

    def close(self) -> None:

        if self._closed:
            return

        self._closed = True

        if self._subscription is not None:

            self._subscription.close()

            self._subscription = None

        if (
            self._audio_service is not None
            and self._owns_audio_service
        ):

            self._audio_service.stop()

        if self._stt is not None:
            self._stt.close()

        self._started = False

        logger.info("EDITH Voice Engine v2 stopped")
