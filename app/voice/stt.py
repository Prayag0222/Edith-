import os
from typing import Optional, Union

import numpy as np

from app.voice.cuda_runtime import setup_cuda_runtime
from app.voice.adaptive_engine import AdaptiveVoiceEngine
from app.voice.audio import AudioRecorder
from app.voice.model_manager import WhisperModelManager
from app.voice.noise_suppression import NoiseSuppressor
from app.voice.task_classifier import VoiceTaskClassifier


# Initialize CUDA runtime once when this module loads.
setup_cuda_runtime()


class SpeechToText:
    """
    EDITH Speech-to-Text engine.

    Features:
        - Adaptive CPU/GPU model selection
        - Lazy Whisper model loading
        - Cached model reuse
        - Direct NumPy audio transcription
        - Noise suppression
        - Voice activity detection
        - Task classification
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        silence_duration: float = 1.5,
        max_recording_seconds: float = 20.0,
        vad_aggressiveness: int = 2,
    ):
        self.sample_rate = sample_rate

        self.audio_recorder = AudioRecorder(
            sample_rate=sample_rate,
            channels=channels,
            silence_duration=silence_duration,
            max_recording_seconds=max_recording_seconds,
            vad_aggressiveness=vad_aggressiveness,
        )

        self.noise_suppressor = NoiseSuppressor(
            sample_rate=sample_rate,
        )

        self.adaptive_engine = AdaptiveVoiceEngine()
        self.model_manager = WhisperModelManager()
        self.task_classifier = VoiceTaskClassifier()

    # --------------------------------------------------
    # MODEL SELECTION
    # --------------------------------------------------

    def _get_model(self):
        decision = self.adaptive_engine.get_decision(
            task_type="conversation",
            gpu_model_loaded=self.model_manager.is_gpu_model_loaded(),
        )

        if (
            decision.device == "cuda"
            and decision.model_size == "medium"
        ):
            model = self.model_manager.get_gpu_model()
        else:
            model = self.model_manager.get_cpu_model()

        return model, decision

    # --------------------------------------------------
    # TRANSCRIPTION
    # --------------------------------------------------

    def _transcribe(
        self,
        audio: Union[str, np.ndarray],
    ) -> Optional[dict]:

        model, decision = self._get_model()

        segments, info = model.transcribe(
            audio,
            beam_size=5,
            language=None,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 500,
            },
            condition_on_previous_text=False,
        )

        # faster-whisper generates segments lazily.
        # Consume them once.
        text_parts = []

        for segment in segments:
            text = segment.text.strip()

            if text:
                text_parts.append(text)

        text = " ".join(text_parts).strip()

        if not text:
            return None

        classification = self.task_classifier.classify(text)

        return {
            "text": text,
            "language": info.language,
            "language_probability": info.language_probability,
            "model": decision.model_size,
            "device": decision.device,
            "compute_type": decision.compute_type,
            "reason": decision.reason,
            "task_type": classification.task_type,
            "classification_confidence": classification.confidence,
        }

    # --------------------------------------------------
    # FILE TRANSCRIPTION
    # --------------------------------------------------

    def transcribe_file(self, audio_path: str) -> Optional[dict]:
        """
        Transcribe an existing audio file.

        Preserves the existing public interface.
        """

        if not os.path.isfile(audio_path):
            raise FileNotFoundError(
                f"Audio file not found: {audio_path}"
            )

        return self._transcribe(audio_path)

    # --------------------------------------------------
    # LIVE LISTENING
    # --------------------------------------------------

    def listen(self) -> Optional[dict]:
        """
        Record, suppress noise and transcribe speech.

        Uses NumPy audio directly instead of creating
        and reopening a temporary WAV file.
        """

        audio = self.audio_recorder.record_until_silence()

        if audio is None:
            return None

        audio = np.asarray(
            audio,
            dtype=np.float32,
        ).reshape(-1)

        if audio.size == 0:
            return None

        audio = self.noise_suppressor.process(audio)

        if audio.size == 0:
            return None

        return self._transcribe(audio)

    # --------------------------------------------------
    # SHUTDOWN
    # --------------------------------------------------

    def close(self):
        """Release background resources."""

        self.adaptive_engine.close()