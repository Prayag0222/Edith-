import unittest

from app.core.commands import is_exit_command, is_sleep_command


class CommandTests(unittest.TestCase):
    def test_sleep_command_is_case_and_punctuation_insensitive(self):
        self.assertTrue(is_sleep_command("Sleep!"))
        self.assertTrue(is_sleep_command("  SLEEP  "))

    def test_sleep_command_requires_an_exact_command(self):
        self.assertFalse(is_sleep_command("don't sleep"))
        self.assertFalse(is_sleep_command("sleep mode"))
        self.assertFalse(is_sleep_command(""))

    def test_exit_command_keeps_existing_normalization(self):
        self.assertTrue(is_exit_command("Exit!"))
        self.assertFalse(is_exit_command("please exit"))


if __name__ == "__main__":
    unittest.main()
