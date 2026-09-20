import json
import urllib.error
import urllib.request

from app.core.config import settings
from app.core.identity import EDITH_IDENTITY


class OllamaClient:
    def __init__(self, edith, model: str | None = None):
        self.edith = edith
        self.model = model or settings.OLLAMA_MODEL
        self.base_url = settings.OLLAMA_BASE_URL

    def is_available(self) -> bool:
        url = f"{self.base_url}/api/tags"

        try:
            with urllib.request.urlopen(url, timeout=2):
                return True

        except urllib.error.URLError:
            return False

    def generate(self, messages: list[dict]) -> str:
        url = f"{self.base_url}/api/chat"

        identity = self.edith.get_identity()
        self_description = self.edith.get_self_description()

        system_message = f"""
{EDITH_IDENTITY}

Current EDITH identity:
Name: {identity["name"]}
Creator: {identity["creator"]}
Administrator: {identity["administrator"]}

DITH's own self-description:
{self_description}

COMMUNICATION RULES:
- You are EDITH, speaking directly to Prayag.
- When referring to yourself, use first-person language: "I", "me", "my".
- When referring to Prayag, use second-person language: "you", "your".
- Never confuse EDITH's identity with Prayag's identity.
- If asked about yourself, describe yourself as EDITH.
- Respond naturally and conversationally rather than like a command system.
"""

        chat_messages = [
            {
                "role": "system",
                "content": system_message,
            }
        ]

        chat_messages.extend(messages)

        data = {
            "model": self.model,
            "messages": chat_messages,
            "stream": False,
        }

        request = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))

            return result["message"]["content"]

        except urllib.error.URLError:
            return "My local AI engine is currently unavailable."