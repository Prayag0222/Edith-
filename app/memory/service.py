from app.memory.embeddings import EmbeddingService
from app.memory.search import (
    index_messages,
    search_memory,
    search_messages_in_range,
)
from app.memory.time_parser import get_time_range
from app.memory.database import save_message, save_embedding


class MemoryService:
    def __init__(self):
        self.embedding_service = EmbeddingService()

    def store_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ):
        message_id = save_message(
            session_id,
            role,
            content,
        )

        if role == "user":
            embedding = self.embedding_service.encode(
                content
            )

            save_embedding(
                message_id,
                embedding,
            )

        return message_id

   

    def search(
        self,
        text: str,
        top_k: int = 5,
        min_score: float = 0.30,
    ):
        return search_memory(
            text,
            self.embedding_service,
            top_k=top_k,
            min_score=min_score,
        )


    def search_in_time_range(
    self,
    text: str,
    start_time: str,
    end_time: str,
    top_k: int = 5,
    min_score: float = 0.30,
):
     return search_messages_in_range(
        text,
        start_time,
        end_time,
        self.embedding_service,
        top_k=top_k,
        min_score=min_score,
    )


    def get_relevant_memories(
    self,
    text: str,
    top_k: int = 5,
    min_score: float = 0.30,
):
     time_range = get_time_range(text)

     if time_range is not None:
        start_time, end_time = time_range

        return self.search_in_time_range(
            text,
            start_time,
            end_time,
            top_k=top_k,
            min_score=min_score,
        )

     return self.search(
        text,
        top_k=top_k,
        min_score=min_score,
    )
    def build_memory_context(
        self,
        text: str,
        top_k: int = 5,
        min_score: float = 0.30,
        ):
        memories = self.get_relevant_memories(
            text,
            top_k=top_k,
            min_score=min_score,
        )

        if not memories:
            return ""

        lines = [
            "Relevant memories from previous conversations:"
        ]

        for memory in memories:
            lines.append(
                f"- {memory['content']}"
            )

        return "\n".join(lines)

    def get_context(self, text: str, top_k: int = 5, min_score: float = 0.30):
        return self.build_memory_context(
            text,
            top_k=top_k,
            min_score=min_score,
        )

    def index_messages(self):
        return index_messages()