import unittest
from unittest.mock import Mock, patch

import numpy as np

from app.voice.adaptive_engine import AdaptiveVoiceEngine
from app.voice.stt import SpeechToText


class _AudioRecorder:
    def __init__(self):
        self.saved_audio = None

    def record_until_silence(self):
        return np.array([0.1, 0.2], dtype=np.float32)

    def save_wav(self, audio):
        self.saved_audio = audio
        return "temporary.wav"


class VoiceProcessingTests(unittest.TestCase):
    def test_recorded_audio_is_suppressed_before_transcription(self):
        speech_to_text = SpeechToText.__new__(SpeechToText)
        recorder = _AudioRecorder()
        speech_to_text.audio_recorder = recorder
        speech_to_text.noise_suppressor = Mock()
        speech_to_text.noise_suppressor.process.return_value = np.array(
            [0.01, 0.02],
            dtype=np.float32,
        )
        speech_to_text.transcribe_file = lambda path: {"text": "hello"}

        with patch("app.voice.stt.os.path.exists", return_value=True), patch(
            "app.voice.stt.os.remove"
        ):
            result = speech_to_text.listen()

        np.testing.assert_allclose(
            recorder.saved_audio,
            [0.01, 0.02],
        )
        speech_to_text.noise_suppressor.process.assert_called_once()
        self.assertEqual(result, {"text": "hello"})

    def test_gpu_is_preferred_for_commands_and_reused_when_loaded(self):
        engine = AdaptiveVoiceEngine.__new__(AdaptiveVoiceEngine)
        engine.gpu_available = True
        engine.get_gpu_stats = lambda: {
            "gpu_usage": 75.0,
            "vram_used": 1000.0,
            "vram_total": 4096.0,
            "vram_free": 3096.0,
            "vram_usage": 24.4,
            "available": True,
        }

        command_decision = engine.get_decision("command")
        loaded_decision = engine.get_decision(
            "conversation",
            gpu_model_loaded=True,
        )

        self.assertEqual(command_decision.device, "cuda")
        self.assertEqual(loaded_decision.device, "cuda")


if __name__ == "__main__":
    unittest.main()
