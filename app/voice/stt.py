import os

from app.voice.cuda_runtime import setup_cuda_runtime
from app.voice.adaptive_engine import AdaptiveVoiceEngine
from app.voice.audio import AudioRecorder
from app.voice.model_manager import WhisperModelManager
from app.voice.task_classifier import VoiceTaskClassifier


# Configure CUDA before Faster-Whisper models are loaded.
setup_cuda_runtime()


class SpeechToText:
    """
    Adaptive Speech-to-Text service for EDITH.

    Responsibilities:

        - Coordinate audio recording
        - Use WebRTC VAD through AudioRecorder
        - Ask the adaptive engine for a resource decision
        - Obtain the appropriate Whisper model
        - Transcribe audio
        - Return clean transcription data
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        silence_duration: float = 1.2,
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

        self.adaptive_engine = (
            AdaptiveVoiceEngine()
        )

        self.model_manager = (
            WhisperModelManager()
        )
        self.task_classifier = (
            VoiceTaskClassifier()
        )

    def _get_model(self, task_type: str):
        """
        Ask the adaptive engine which model/device
        should be used, then retrieve that model.
        """

        decision = (
            self.adaptive_engine.get_decision(
                task_type
            )
        )

        print()
        print("--- STT RESOURCE DECISION ---")

        print(
            f"Task: {task_type}"
        )

        print(
            f"Model: {decision.model_size}"
        )

        print(
            f"Device: {decision.device}"
        )

        print(
            f"Compute: {decision.compute_type}"
        )

        print(
            f"Reason: {decision.reason}"
        )

        print(
            "-----------------------------"
        )

        if (
            decision.device == "cuda"
            and decision.model_size == "medium"
        ):
            model = (
                self.model_manager.get_gpu_model()
            )

        else:
            model = (
                self.model_manager.get_cpu_model()
            )

        return model, decision

    def _transcribe_first_pass(self, audio_path: str):
        model = self.model_manager.get_cpu_model()

        segments, info = model.transcribe(
            audio_path,
            beam_size=3,
            language=None,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=False,
        )

        text_parts = []

        for segment in segments:
            text = segment.text.strip()
            if text:
                text_parts.append(text)

        return {
            "text": " ".join(text_parts).strip(),
            "language": info.language,
            "language_probability": info.language_probability,
        }



    def transcribe_file(
        self,
        audio_path: str,
        task_type: str = "conversation",
    ):
        """
        Transcribe an existing audio file.
        """

        model, decision = self._get_model(
            task_type
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
                text_parts.append(
                    text
                )

        text = " ".join(
            text_parts
        ).strip()

        return {
            "text": text,
            "language": info.language,
            "language_probability": (
                info.language_probability
            ),
            "model": decision.model_size,
            "device": decision.device,
            "compute_type": decision.compute_type,
            "reason": decision.reason,
        }

    def listen(self):
        audio = self.audio_recorder.record_until_silence()

        if audio is None:
            print("No speech detected.")
            return None

        temporary_path = self.audio_recorder.save_wav(audio)

        try:
            # First pass: lightweight CPU Whisper
            print("First pass: small CPU model...")
            first_pass = self._transcribe_first_pass(temporary_path)

            text = first_pass["text"]

            if not text:
                print("No speech recognized.")
                return None

            # Classify the transcription
            classification = self.task_classifier.classify(text)

            print(
                f"Task: {classification.task_type} "
                f"| Confidence: {classification.confidence:.2f} "
                f"| {classification.reason}"
            )

            # Simple command → keep lightweight result
            if (
                classification.task_type == "command"
                and classification.confidence >= 0.80
            ):
                return {
                    **first_pass,
                    "task_type": "command",
                    "classification_confidence": classification.confidence,
                    "model": "small",
                    "device": "cpu",
                    "compute_type": "int8",
                    "reason": "Simple command; no escalation needed.",
                }

            # Conversation / ambiguous → medium model
            print("Escalating to medium CUDA model...")

            return self.transcribe_file(
                temporary_path,
                task_type="conversation",
            ) | {
                "task_type": classification.task_type,
                "classification_confidence": classification.confidence,
            }

        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)

    def test(
        self,
        task_type: str = "conversation",
    ):
        """
        Test microphone + adaptive STT.
        """

        print()

        print(
            "=" * 50
        )

        print(
            "EDITH ADAPTIVE SPEECH-TO-TEXT TEST"
        )

        print(
            "=" * 50
        )

        print()

        print(
            f"Task type: {task_type}"
        )

        print()

        print(
            "Speak naturally after "
            "'Listening...' appears."
        )

        print(
            "Pause after your sentence."
        )

        print()

        result = self.listen()

        if result is None:
            return

        print()

        print(
            "-" * 50
        )

        print(
            f"Detected language: "
            f"{result['language']}"
        )

        print(
            f"Confidence: "
            f"{result['language_probability']:.2f}"
        )

        print(
            f"Model: "
            f"{result['model']}"
        )

        print(
            f"Device: "
            f"{result['device']}"
        )

        print(
            f"Compute: "
            f"{result['compute_type']}"
        )

        print(
            f"Reason: "
            f"{result['reason']}"
        )

        print(
            f"TEXT: "
            f"{result['text']}"
        )

        print(
            "-" * 50
        )


if __name__ == "__main__":

    stt = SpeechToText()

    stt.test(
        task_type="conversation"
    )