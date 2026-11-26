import threading
import unittest
from unittest.mock import Mock

from app.core.lifecycle import ApplicationLifecycle, ApplicationMode
from app.main import play_startup_greeting_once, run_assistant


class MainLifecycleTests(unittest.TestCase):
    def test_hibernate_wake_sleep_and_exit_follow_distinct_paths(self):
        changed_modes = []
        hibernate_action = Mock()
        lifecycle = ApplicationLifecycle(3600, hibernate_action, changed_modes.append)
        voice = Mock()
        voice.wait_for_wake_word.return_value = True
        voice.listen.side_effect = [
            {"text": "Hibernate"},
            {"text": "Go to sleep"},
            {"text": "Exit"},
        ]
        ui = Mock()
        tts = Mock()
        shutdown_requests = []

        def request_shutdown():
            shutdown_requests.append(True)
            lifecycle.shutdown()
            ui.close()

        run_assistant(
            Mock(),
            Mock(),
            Mock(),
            voice,
            tts,
            Mock(),
            ui,
            lifecycle,
            request_shutdown,
        )

        self.assertEqual(hibernate_action.call_count, 1)
        self.assertEqual(voice.wait_for_wake_word.call_count, 3)
        self.assertEqual(voice.return_to_wake_word_mode.call_count, 2)
        self.assertEqual(ui.activate.call_count, 4)
        self.assertEqual(ui.sleep.call_count, 2)
        tts.speak.assert_called_once_with("Goodbye.")
        self.assertEqual(shutdown_requests, [True])
        self.assertEqual(
            changed_modes,
            [
                ApplicationMode.ACTIVE,
                ApplicationMode.SLEEPING,
                ApplicationMode.HIBERNATING,
                ApplicationMode.ACTIVE,
                ApplicationMode.SLEEPING,
                ApplicationMode.ACTIVE,
                ApplicationMode.SHUTTING_DOWN,
            ],
        )

    def test_startup_greeting_is_played_once_after_readiness(self):
        voice = Mock()
        voice.get_stats.return_value = {"running": True}
        desktop = Mock()
        desktop.BRIDGE_TIMEOUT = 0.1
        desktop._ready = threading.Event()
        desktop._ready.set()
        tray = Mock()
        tray.is_ready = True
        tts = Mock()
        greeting_played = threading.Event()

        self.assertTrue(
            play_startup_greeting_once(
                tts,
                voice,
                desktop,
                tray,
                "EDITH is online.",
                greeting_played,
            )
        )
        self.assertFalse(
            play_startup_greeting_once(
                tts,
                voice,
                desktop,
                tray,
                "EDITH is online.",
                greeting_played,
            )
        )

        tts.speak.assert_called_once_with("EDITH is online.")


if __name__ == "__main__":
    unittest.main()
