import os

from app.voice.cuda_runtime import setup_cuda_runtime
from app.voice.adaptive_engine import AdaptiveVoiceEngine
from app.voice.audio import AudioRecorder
from app.voice.model_manager import WhisperModelManager
from app.voice.task_classifier import VoiceTaskClassifier


setup_cuda_runtime()


class SpeechToText:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        silence_duration: float = 1.5,
        max_recording_seconds: float = 20.0,
        vad_aggressiveness: int = 2,
    ):
        self.audio_recorder = AudioRecorder(
            sample_rate=sample_rate,
            channels=channels,
            silence_duration=silence_duration,
            max_recording_seconds=max_recording_seconds,
            vad_aggressiveness=vad_aggressiveness,
        )

        self.adaptive_engine = AdaptiveVoiceEngine()
        self.model_manager = WhisperModelManager()
        self.task_classifier = VoiceTaskClassifier()

    def _get_model(self):
        decision = self.adaptive_engine.get_decision(
        "conversation",
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

    def transcribe_file(self, audio_path: str):
        model, decision = self._get_model()

        print(
            f"[STT] {decision.model_size} "
            f"{decision.device}"
        )

        segments, info = model.transcribe(
            audio_path,
            beam_size=5,
            language=None,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 500,
            },
            condition_on_previous_text=False,
        )

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

    def listen(self):
        audio = self.audio_recorder.record_until_silence()

        if audio is None:
            print("No speech detected.")
            return None

        temporary_path = self.audio_recorder.save_wav(audio)

        try:
            result = self.transcribe_file(temporary_path)

            if result is None:
                print("No speech recognized.")
                return None

            return result

        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)