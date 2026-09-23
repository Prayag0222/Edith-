from app.memory.embeddings import EmbeddingService
from app.memory.search import (
    index_messages,
    search_memory,
    search_messages_in_range,
)
from app.memory.time_parser import get_time_range
from app.memory.vector_store import  save_embedding
from app.memory.message_store import (
   save_message,
)

from app.memory.structured_service import StructuredMemoryService

class MemoryService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.structured_memory = StructuredMemoryService()

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
    def search_structured_memories(
        self,
        text: str,
    ):
        memories = self.structured_memory.get_all()

        query = text.lower()

        relevant = []

        for memory in memories:
            key = memory["key"].lower()
            value = memory["value"].lower()

            if (
                key in query
                or value in query
                or any(
                    word in key or word in value
                    for word in query.split()
                    if len(word) > 2
                )
            ):
                relevant.append(memory)

        return relevant

    def get_structured_memories(self):
        return self.structured_memory.get_all()

    def build_memory_context(
        self,
        text: str,
        top_k: int = 5,
        min_score: float = 0.30,
    ):
        semantic_memories = self.get_relevant_memories(
            text,
            top_k=top_k,
            min_score=min_score,
        )

        structured_memories = self.search_structured_memories(text)

        sections = []

        if structured_memories:
            structured_lines = [
                "Known facts and preferences about the user:"
            ]

            for memory in structured_memories:
                structured_lines.append(
                    f"- {memory['type']}: "
                    f"{memory['key']} = {memory['value']}"
                )

            sections.append(
                "\n".join(structured_lines)
            )

        if semantic_memories:
            semantic_lines = [
                "Relevant memories from previous conversations:"
            ]

            for memory in semantic_memories:
                semantic_lines.append(
                    f"- {memory['content']}"
                )

            sections.append(
                "\n".join(semantic_lines)
            )

        if not sections:
            return "No relevant memory was found."

        return "\n\n".join(sections)

    def get_context(self, text: str, top_k: int = 5, min_score: float = 0.30):
        return self.build_memory_context(
            text,
            top_k=top_k,
            min_score=min_score,
        )

    def index_messages(self):
        return index_messages()