import uuid

from app.memory.service import MemoryService


class ConversationService:
    def __init__(self, memory_service=None):
        self.session_id = str(uuid.uuid4())

        self.memory_service = (
            memory_service
            or MemoryService()
        )

        self.max_messages = 20
        self.messages = []

    def add_user_message(self, content: str):
        self.messages.append({
            "role": "user",
            "content": content,
        })

        self.memory_service.store_message(
            self.session_id,
            "user",
            content,
        )

        self._trim_messages()

    def add_assistant_message(self, content: str):
        self.messages.append({
            "role": "assistant",
            "content": content,
        })

        self.memory_service.store_message(
            self.session_id,
            "assistant",
            content,
        )

        self._trim_messages()

    def _trim_messages(self):
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

    def get_messages(self):
        return self.messages

    def build_messages(self) -> list[dict]:
        return self.messages