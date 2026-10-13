import json
import urllib.error
import urllib.request

from app.core.config import settings
from app.core.identity import EDITH_IDENTITY
from app.core.behavior import EDITH_BEHAVIOR


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
        except (urllib.error.URLError, TimeoutError):
            return False

    def generate(
        self,
        messages: list[dict],
        memory_context: str = "",
    ) -> str:
        url = f"{self.base_url}/api/chat"

        identity = self.edith.get_identity()
        self_description = self.edith.get_self_description()

        if memory_context.strip():
            memory_section = f"""
AVAILABLE MEMORY CONTEXT

The following information was retrieved from EDITH's memory.
Use it when relevant to the user's question.

{memory_context}

MEMORY RULES:

* If the user asks about previous conversations, examine the available
  historical records before answering.
* If historical records for the requested date are present, summarize
  those records directly.
* Use speaker labels to distinguish what Prayag said from what EDITH said.
* Do not claim that previous conversations are inaccessible when relevant
  records are included above.
* Do not invent events, decisions, or tasks that the records do not support.
* If the records are incomplete, clearly distinguish known details from
  missing information.
"""
        else:
            memory_section = """
AVAILABLE MEMORY CONTEXT

No memory context was provided for this request.
Do not claim to have retrieved memories or invent past conversations.
"""

        system_message = f"""
{EDITH_IDENTITY}

{EDITH_BEHAVIOR}

CURRENT IDENTITY
Name: {identity["name"]}
Creator: {identity["creator"]}
Administrator: {identity["administrator"]}

SELF-DESCRIPTION
{self_description}

{memory_section}

COMMUNICATION RULES

* Speak directly to Prayag.
* Refer to yourself as "I", "me", or "my".
* Refer to Prayag as "you" or "your".
* Never confuse your identity with Prayag's identity.
* Do not claim an action was completed unless it was actually executed.
* Respond naturally, clearly, and directly.
"""

        chat_messages = [
            {
                "role": "system",
                "content": system_message,
            },
            *messages,
        ]

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
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))

            content = result.get("message", {}).get("content", "")
            return content.strip() or "I couldn't generate a response."

        except (urllib.error.URLError, TimeoutError):
            return "My local AI engine is currently unavailable."
        except (json.JSONDecodeError, KeyError, TypeError):
            return "I encountered an error processing the local AI response."

