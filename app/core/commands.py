import re


def _normalize_command(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.casefold()).strip()


def is_exit_command(text: str) -> bool:
    return _normalize_command(text) == "exit"


def is_sleep_command(text: str) -> bool:
    return _normalize_command(text) == "sleep"
