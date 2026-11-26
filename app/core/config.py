import os

from dotenv import load_dotenv


load_dotenv()


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

    OLLAMA_THINK = os.getenv(
        "OLLAMA_THINK","FALSE"
    )


settings = Settings()