import re


def _normalize_command(text: str) -> str:
    normalized = re.sub(r"[^\w\s]", "", text.casefold())
    return " ".join(normalized.split())


def is_shutdown_command(text: str) -> bool:
    return _normalize_command(text) == "exit"


def is_sleep_command(text: str) -> bool:
    return _normalize_command(text) in {
        "sleep",
        "stop",
        "go to sleep",
    }


def is_hibernate_command(text: str) -> bool:
    return _normalize_command(text) == "hibernate"
