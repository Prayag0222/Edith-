import unittest
from unittest.mock import Mock

from app.ui.desktop_window import EdithDesktopWindow


class DesktopWindowLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.desktop = EdithDesktopWindow.__new__(EdithDesktopWindow)
        self.desktop.window = Mock()
        self.desktop._closed = False
        self.desktop._allow_close = False

    def test_user_close_hides_window_and_cancels_close(self):
        self.assertFalse(self.desktop._on_closing())
        self.desktop.window.hide.assert_called_once_with()
        self.assertFalse(self.desktop._closed)

    def test_programmatic_close_is_allowed(self):
        self.desktop.close()

        self.assertTrue(self.desktop._allow_close)
        self.desktop.window.destroy.assert_called_once_with()
        self.assertTrue(self.desktop._on_closing())


if __name__ == "__main__":
    unittest.main()
