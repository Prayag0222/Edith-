import unittest
from unittest.mock import Mock

from app.voice_v2.engine import VoiceEngine


class VoiceEngineSleepTests(unittest.TestCase):
    def setUp(self):
        self.engine = VoiceEngine.__new__(VoiceEngine)
        self.engine._conversation_active = True
        self.engine._wake_detected = False
        self.engine._subscription = Mock()
        self.engine._wake_adapter = Mock()
        self.engine._endpoint = Mock()
        self.engine._stt = Mock()
        self.engine._closed = False
        self.engine._audio_service = Mock()
        self.engine._owns_audio_service = True

    def test_return_to_wake_word_mode_clears_audio_and_resets_detectors(self):
        self.engine.return_to_wake_word_mode()

        self.engine._subscription.discard_pending.assert_called_once_with()
        self.engine._endpoint.reset.assert_called_once_with()
        self.engine._wake_adapter.reset.assert_called_once_with()
        self.assertFalse(self.engine._conversation_active)
        self.assertFalse(self.engine._wake_detected)

    def test_return_to_wake_word_mode_is_idempotent_when_inactive(self):
        self.engine._conversation_active = False

        self.engine.return_to_wake_word_mode()

        self.engine._subscription.discard_pending.assert_not_called()
        self.engine._endpoint.reset.assert_not_called()
        self.engine._wake_adapter.reset.assert_not_called()

    def test_hibernate_releases_only_the_stt_model_cache(self):
        self.engine._conversation_active = False
        self.engine.hibernate()

        self.engine._stt.close.assert_called_once_with()
        self.engine._subscription.close.assert_not_called()
        self.engine._wake_adapter.reset.assert_not_called()
        self.engine._audio_service.stop.assert_not_called()

    def test_hibernate_requires_an_idle_voice_engine(self):
        with self.assertRaisesRegex(RuntimeError, "idle"):
            self.engine.hibernate()

        self.engine._stt.close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
