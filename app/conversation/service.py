import uuid

from app.memory.database import (
    initialize_database,
    save_message,
    save_embedding,
)

from app.memory.embeddings import EmbeddingService


class ConversationService:
    def __init__(self,embedding_service=None):
        self.session_id = str(uuid.uuid4())

        initialize_database()

        self.embedding_service = embedding_service or EmbeddingService()

        self.max_messages = 20
        self.messages = []

    def add_user_message(self, content: str):
        self.messages.append({
            "role": "user",
            "content": content,
        })

        message_id = save_message(
            self.session_id,
            "user",
            content,
        )
        embedding = self.embedding_service.encode(content)

        save_embedding(message_id, embedding)

        self._trim_messages()

    def add_assistant_message(self, content: str):
        self.messages.append({
            "role": "assistant",
            "content": content,
        })

        save_message(
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