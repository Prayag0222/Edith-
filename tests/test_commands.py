import unittest

from app.core.commands import (
    is_hibernate_command,
    is_shutdown_command,
    is_sleep_command,
)


class CommandTests(unittest.TestCase):
    def test_sleep_command_is_case_and_punctuation_insensitive(self):
        self.assertTrue(is_sleep_command("Sleep!"))
        self.assertTrue(is_sleep_command("  SLEEP  "))

    def test_sleep_command_requires_an_exact_command(self):
        self.assertFalse(is_sleep_command("don't sleep"))
        self.assertFalse(is_sleep_command("sleep mode"))
        self.assertFalse(is_sleep_command(""))

    def test_sleep_aliases_are_exact_and_normalized(self):
        self.assertTrue(is_sleep_command("Go   to sleep!"))
        self.assertTrue(is_sleep_command("stop."))
        self.assertTrue(is_sleep_command("Sleep"))
        self.assertFalse(is_sleep_command("exit"))
        self.assertFalse(is_sleep_command("please stop"))

    def test_hibernate_command_requires_an_exact_command(self):
        self.assertTrue(is_hibernate_command("Hibernate!"))
        self.assertFalse(is_hibernate_command("please hibernate"))

    def test_exit_is_the_only_exact_shutdown_command(self):
        self.assertTrue(is_shutdown_command("Exit!"))
        self.assertFalse(is_shutdown_command("please exit"))
        self.assertFalse(is_shutdown_command("shutdown edith"))


if __name__ == "__main__":
    unittest.main()
