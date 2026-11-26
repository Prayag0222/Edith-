import unittest
from unittest.mock import Mock, patch

from app.core.config import Settings
from app.core.lifecycle import ApplicationMode
from app.ui.system_tray import EdithSystemTray


class FakeTrayIcon:
    HAS_NOTIFICATION = True

    def __init__(self, *args, **kwargs):
        self.title = kwargs.get("title", "")
        self.menu = kwargs.get("menu")
        self.visible = False
        self.run_detached_calls = 0
        self.stop_calls = 0
        self.update_menu_calls = 0
        self.notifications = []

    def run_detached(self, setup):
        self.run_detached_calls += 1
        setup(self)

    def stop(self):
        self.stop_calls += 1

    def update_menu(self):
        self.update_menu_calls += 1

    def notify(self, message, title=None):
        self.notifications.append((message, title))


class SystemTrayTests(unittest.TestCase):
    def setUp(self):
        self.open_ui = Mock()
        self.hide_ui = Mock()
        self.exit_application = Mock()
        self.icons = []

        def create_icon(*args, **kwargs):
            icon = FakeTrayIcon(*args, **kwargs)
            self.icons.append(icon)
            return icon

        self.icon_factory = patch(
            "app.ui.system_tray.pystray.Icon",
            side_effect=create_icon,
        )
        self.icon_factory.start()
        self.addCleanup(self.icon_factory.stop)

        self.tray = EdithSystemTray(
            Settings.TRAY_ICON_PATH,
            self.open_ui,
            self.hide_ui,
            self.exit_application,
        )
        self.icon = self.icons[0]

    def test_icon_starts_once_and_stays_visible_through_state_updates(self):
        self.tray.start()
        self.tray.start()
        for mode in (
            ApplicationMode.ACTIVE,
            ApplicationMode.SLEEPING,
            ApplicationMode.HIBERNATING,
        ):
            self.tray.set_status(mode)
            self.assertTrue(self.icon.visible)

        self.assertTrue(self.tray.is_ready)
        self.assertTrue(self.icon.visible)
        self.assertEqual(self.icon.run_detached_calls, 1)
        self.assertEqual(self.icon.title, "EDITH - HIBERNATING")
        self.assertGreaterEqual(self.icon.update_menu_calls, 1)
        self.assertEqual(
            self.icon.menu.items[2].text,
            "Current status: HIBERNATING",
        )

    def test_menu_actions_use_the_supplied_application_callbacks(self):
        self.tray.start()

        self.tray._on_open(self.icon, None)
        self.tray._on_hide(self.icon, None)
        self.tray._on_show_status(self.icon, None)
        self.tray._on_exit(self.icon, None)

        self.open_ui.assert_called_once_with()
        self.hide_ui.assert_called_once_with()
        self.exit_application.assert_called_once_with()
        self.assertEqual(
            self.icon.notifications,
            [("Current status: SLEEPING", "EDITH")],
        )

    def test_stop_is_idempotent(self):
        self.tray.start()
        self.tray.stop()
        self.tray.stop()

        self.assertEqual(self.icon.stop_calls, 1)


if __name__ == "__main__":
    unittest.main()
