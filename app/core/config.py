import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings:
    APP_NAME = os.getenv("EDITH_APP_NAME", "EDITH")
    OLLAMA_BASE_URL = os.getenv(
        "OLLAMA_BASE_URL",
        "http://localhost:11434",
    )
    OLLAMA_MODEL = os.getenv(
        "OLLAMA_MODEL",
        "edith:latest",
    )
    OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "45s")
    HIBERNATE_AFTER_SECONDS = float(
        os.getenv("EDITH_HIBERNATE_AFTER_SECONDS", "300")
    )
    TRAY_ICON_PATH = Path(
        os.getenv(
            "EDITH_TRAY_ICON_PATH",
            str(PROJECT_ROOT / "app" / "ui" / "assets" / "edith_placeholder.ico"),
        )
    )
    STARTUP_GREETING = os.getenv(
        "EDITH_STARTUP_GREETING",
        "EDITH is online. All systems are ready.",
    )

    OLLAMA_THINK = os.getenv(
        "OLLAMA_THINK","FALSE"
    )


settings = Settings()