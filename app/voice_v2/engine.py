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

    # Time allowed for the user to begin speaking after EDITH
    # finishes responding. After 7 seconds, EDITH enters sleep mode.
    speech_start_timeout_seconds: float = 7.0

    max_utterance_seconds: float = 600.0


class VoiceEngine:
    """
    EDITH Voice Engine v2.

    Responsibilities:
        1. Continuously monitor for the wake word.
        2. Capture user speech.
        3. Support multiple conversation turns after one wake word.
        4. Automatically return to wake-word mode after inactivity.

    Public interface:
        wait_for_wake_word()
        listen()
        prepare_for_next_turn()
        close()

    Only one microphone stream is used.
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

        # True means EDITH has an active conversation session.
        # Multiple listen() calls are allowed while this is True.
        self._conversation_active = False

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
    # WAKE WORD MODE
    # --------------------------------------------------

    def wait_for_wake_word(self) -> bool:

        self.start()

        subscription = self._subscription
        wake_adapter = self._wake_adapter

        if subscription is None or wake_adapter is None:
            raise RuntimeError("VoiceEngine initialization incomplete")

        if self._wake_detected:
            return True

        # A new wake session should only begin after the previous
        # conversation has ended.
        if self._conversation_active:
            raise RuntimeError(
                "Cannot wait for wake word during an active conversation"
            )

        # Discard audio left over from the previous conversation/TTS.
        # This prevents EDITH from detecting its own spoken response.
        discarded = subscription.discard_pending()

        # Start wake detection with a clean rolling audio buffer.
        wake_adapter.reset()

        if discarded:
            logger.debug(
                "Discarded %d stale audio blocks before wake detection",
                discarded,
            )

        print("[READY] Waiting for wake word...")

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
    # CONVERSATION MODE
    # --------------------------------------------------


    def listen(self) -> dict | None:
        """
        Listen for one user utterance.

        The first call requires a wake-word detection.
        Subsequent calls are allowed during the same conversation.

        Returns:
            dict: Transcription result.
            None: No speech detected within the idle timeout.
        """

        self.start()

        subscription = self._subscription
        endpoint = self._endpoint
        stt = self._stt

        if subscription is None or endpoint is None or stt is None:
            raise RuntimeError("VoiceEngine initialization incomplete")

        # First conversation turn must be activated by the wake word.
        if not self._wake_detected and not self._conversation_active:
            raise RuntimeError(
                "Wake word must be detected before starting a conversation"
            )

        # Consume the wake activation exactly once.
        if self._wake_detected:
            self._wake_detected = False
            self._conversation_active = True

        print("[LISTEN] Listening...")

        # Every conversation turn starts with a clean endpoint detector.
        endpoint.reset()

        # Start the inactivity timer after EDITH is ready to listen.
        listen_started = time.monotonic()

        while not self._closed:

            # IMPORTANT:
            # Check timeout on EVERY iteration, not only when chunk is None.
            # The microphone continuously produces audio chunks, including silence.
            #
            # We only apply this timeout before speech detection activates.
            # Once speech starts, endpoint detection manages the utterance.
            if (
                not endpoint.is_speaking
                and time.monotonic() - listen_started
                >= self.config.speech_start_timeout_seconds
            ):

                print(
                    "[SLEEP] No speech detected for "
                    f"{self.config.speech_start_timeout_seconds:.0f} seconds. "
                    "Returning to wake-word mode."
                )

                self._conversation_active = False
                return None

            chunk = subscription.get(timeout=0.25)

            # A timeout from the queue simply means no block was available.
            # The main inactivity timer is checked again on the next iteration.
            if chunk is None:
                continue

            if chunk.overflow_before_capture:
                logger.warning(
                    "Microphone input overflow during speech capture"
                )

            # Process the incoming audio through the existing endpoint detector.
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

                # Keep conversation active so the user can try again.
                return {"text": ""}

            payload = result.to_dict()

            print(
                f"[STT] {payload.get('device', 'unknown')} | "
                f"{payload.get('processing_seconds', 0.0):.2f}s"
            )

            return payload

        self._conversation_active = False
        return None

    # --------------------------------------------------
    # PREPARE NEXT CONVERSATION TURN
    # --------------------------------------------------

    def prepare_for_next_turn(self) -> None:
        """
        Clean microphone audio after EDITH finishes speaking.

        Piper playback is captured by the continuously running microphone.
        We therefore perform two cleanup passes:

        1. Discard audio already captured during TTS playback.
        2. Wait for the remaining acoustic echo/reverberation to settle.
        3. Discard audio captured during that settling period.

        This prevents EDITH's previous response from becoming the next
        user's input.
        """

        if not self._conversation_active:
            return

        subscription = self._subscription

        if subscription is None:
            return

        # First pass: remove audio accumulated during Piper playback.
        first_discard = subscription.discard_pending()

        # Allow the final sound from the speakers to decay before listening.
        # This is a settling period, not a delay during speech recognition.
        tts_tail_seconds = 0.5
        time.sleep(tts_tail_seconds)

        # Second pass: remove audio captured during acoustic settling.
        second_discard = subscription.discard_pending()

        # Reset VAD state so old audio cannot influence the next utterance.
        if self._endpoint is not None:
            self._endpoint.reset()

        logger.debug(
            "TTS cleanup complete | First discard: %d | "
            "Second discard: %d | Settling: %.2fs",
            first_discard,
            second_discard,
            tts_tail_seconds,
        )

        print("[LISTEN] Microphone ready for next user turn.")
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

        self._conversation_active = False
        self._wake_detected = False

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