import os
import threading
import time
import unittest
import uuid
from unittest.mock import Mock

from app.core.lifecycle import (
    ApplicationLifecycle,
    ApplicationMode,
    SingleInstanceGuard,
)


class ApplicationLifecycleTests(unittest.TestCase):
    def test_hibernates_after_sleep_timeout(self):
        hibernated = threading.Event()
        lifecycle = ApplicationLifecycle(0.05, hibernated.set)
        lifecycle.start()

        try:
            self.assertTrue(hibernated.wait(1))
            self.assertEqual(lifecycle.mode, ApplicationMode.HIBERNATING)
        finally:
            lifecycle.shutdown()

    def test_active_mode_pauses_timeout_until_sleep(self):
        hibernated = threading.Event()
        lifecycle = ApplicationLifecycle(0.05, hibernated.set)
        lifecycle.activate()
        lifecycle.start()

        try:
            time.sleep(0.1)
            self.assertFalse(hibernated.is_set())
            lifecycle.sleep()
            self.assertTrue(hibernated.wait(1))
        finally:
            lifecycle.shutdown()

    def test_manual_hibernation_requires_sleeping_mode(self):
        hibernate_action = Mock()
        lifecycle = ApplicationLifecycle(1, hibernate_action)
        lifecycle.activate()

        with self.assertRaises(RuntimeError):
            lifecycle.hibernate_now()

        lifecycle.sleep()
        self.assertTrue(lifecycle.hibernate_now())
        self.assertEqual(lifecycle.mode, ApplicationMode.HIBERNATING)
        hibernate_action.assert_called_once_with()
        lifecycle.shutdown()

    def test_failed_hibernation_returns_to_sleeping_and_is_reported(self):
        def fail_hibernation():
            raise RuntimeError("model release failed")

        lifecycle = ApplicationLifecycle(1, fail_hibernation)
        with self.assertLogs("app.core.lifecycle", level="ERROR"):
            with self.assertRaisesRegex(RuntimeError, "model release failed"):
                lifecycle.hibernate_now()

        self.assertEqual(lifecycle.mode, ApplicationMode.SLEEPING)
        lifecycle.shutdown()

    def test_shutdown_stops_future_hibernation(self):
        hibernated = threading.Event()
        lifecycle = ApplicationLifecycle(0.05, hibernated.set)
        lifecycle.start()
        lifecycle.shutdown()

        time.sleep(0.1)
        self.assertFalse(hibernated.is_set())
        self.assertEqual(lifecycle.mode, ApplicationMode.SHUTTING_DOWN)

    def test_mode_changes_are_reported_to_observer(self):
        changed_modes = []
        lifecycle = ApplicationLifecycle(1, Mock(), changed_modes.append)

        lifecycle.activate()
        lifecycle.sleep()
        lifecycle.hibernate_now()
        lifecycle.shutdown()

        self.assertEqual(
            changed_modes,
            [
                ApplicationMode.ACTIVE,
                ApplicationMode.SLEEPING,
                ApplicationMode.HIBERNATING,
                ApplicationMode.SHUTTING_DOWN,
            ],
        )


@unittest.skipUnless(os.name == "nt", "Windows named mutex required")
class SingleInstanceGuardTests(unittest.TestCase):
    def test_second_guard_cannot_acquire_existing_mutex(self):
        name = "Local\\EDITH.Tests." + str(uuid.uuid4())
        first = SingleInstanceGuard(name)
        second = SingleInstanceGuard(name)

        try:
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
        finally:
            first.close()
            second.close()


if __name__ == "__main__":
    unittest.main()
