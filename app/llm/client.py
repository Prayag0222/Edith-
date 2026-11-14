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

    def _build_messages(
        self,
        messages: list[dict],
        memory_context: str = "",
    ) -> list[dict]:

        identity = self.edith.get_identity()
        self_description = self.edith.get_self_description()

        if memory_context.strip():
            memory_section = f"""
AVAILABLE MEMORY CONTEXT

The following information was retrieved from EDITH's memory.
Use it when relevant to the user's question.

{memory_context}

MEMORY RULES:

* Memory is supporting context, not the answer itself.
* Identify what the user is actually asking before retrieving information.
* Use relevant memories to answer the question directly.
* Do not repeat identity information unless the user asks about identity.
* When asked about previous conversations, summarize relevant historical records.
* Distinguish known information from missing information.
* Never invent events, decisions, or personal details.
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

        return [
            {
                "role": "system",
                "content": system_message,
            },
            *messages,
        ]

    def generate_stream(
        self,
        messages: list[dict],
        memory_context: str = "",
    ):
        """
        Generate an AI response incrementally.

        Yields text chunks as soon as Ollama produces them.
        """

        url = f"{self.base_url}/api/chat"

        chat_messages = self._build_messages(
            messages,
            memory_context,
        )

        data = {
            "model": self.model,
            "messages": chat_messages,
            "stream": True,
        }

        request = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        received_content = False

        try:
            with urllib.request.urlopen(
                request,
                timeout=120,
            ) as response:

                for line in response:
                    if not line.strip():
                        continue

                    try:
                        result = json.loads(line.decode("utf-8"))
                    except json.JSONDecodeError:
                        continue

                    if "error" in result:
                        raise RuntimeError(result["error"])

                    content = result.get(
                        "message", {}
                    ).get("content", "")

                    if content:
                        received_content = True
                        yield content

                    if result.get("done", False):
                        break

            if not received_content:
                yield "I couldn't generate a response."

        except (urllib.error.URLError, TimeoutError):
            if not received_content:
                yield "My local AI engine is currently unavailable."

        except (RuntimeError, json.JSONDecodeError, KeyError, TypeError):
            if not received_content:
                yield "I encountered an error processing the local AI response."

    def generate(
        self,
        messages: list[dict],
        memory_context: str = "",
    ) -> str:
        """
        Backward-compatible method.
        Collects streamed chunks into a complete response.
        """

        return "".join(
            self.generate_stream(
                messages,
                memory_context,
            )
        ).strip()