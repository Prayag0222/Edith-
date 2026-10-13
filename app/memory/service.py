from app.memory.embeddings import EmbeddingService
from app.memory.search import (
index_messages as index_all_messages,
search_memory,
search_messages_in_range,
)
from app.memory.time_parser import get_time_range
from app.memory.message_store import save_message
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
        message_id = save_message(session_id, role, content)

        if role == "user":
            embedding = self.embedding_service.encode(content)

            from app.memory.vector_store import save_embedding
            save_embedding(message_id, embedding)

        return message_id

    def search(
        self,
        text: str,
        top_k: int = 20,
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
        top_k: int = 20,
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
        top_k: int = 20,
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

    def search_structured_memories(self, text: str):
        memories = self.structured_memory.get_all()
        query_words = {
            word.casefold().strip(".,!?;:")
            for word in text.split()
            if len(word.strip(".,!?;:")) > 2
        }

        relevant = []

        for memory in memories:
            key = memory["key"].casefold()
            value = memory["value"].casefold()

            if (
                key in text.casefold()
                or value in text.casefold()
                or any(
                    word in key or word in value
                    for word in query_words
                )
            ):
                relevant.append(memory)

        return relevant

    def get_structured_memories(self):
        return self.structured_memory.get_all()

    def build_memory_context(
        self,
        text: str,
        top_k: int = 20,
        min_score: float = 0.30,
    ):
        time_range = get_time_range(text)

        memories = self.get_relevant_memories(
            text,
            top_k=top_k,
            min_score=min_score,
        )

        sections = []

        if time_range is not None:
            from datetime import datetime, timedelta
            from zoneinfo import ZoneInfo

            local_tz = ZoneInfo("Asia/Kolkata")
            start_utc = datetime.strptime(
                time_range[0], "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=ZoneInfo("UTC"))
            local_date = start_utc.astimezone(local_tz).date()

            sections.append(
                f"HISTORICAL CONVERSATION RECORDS\n"
                f"Requested date: {local_date.isoformat()} "
                f"(India Standard Time)\n"
                "These records were retrieved from the requested period. "
                "Use them as evidence when answering questions about that day."
            )

            if memories:
                history_lines = []

                for memory in memories:
                    timestamp = memory.get("created_at", "Unknown time")
                    role = memory.get("role", "unknown")
                    speaker = "Prayag" if role == "user" else "EDITH"
                    content = memory.get("content", "").strip()

                    if content:
                        history_lines.append(
                            f"[{timestamp} UTC] {speaker}: {content}"
                        )

                if history_lines:
                    sections.append("\n".join(history_lines))
            else:
                sections.append(
                    "No messages were found in the requested period."
                )

        else:
            structured_memories = self.search_structured_memories(text)

            if structured_memories:
                structured_lines = [
                    "KNOWN FACTS AND PREFERENCES"
                ]

                for memory in structured_memories:
                    structured_lines.append(
                        f"- {memory['type']}: "
                        f"{memory['key']} = {memory['value']}"
                    )

                sections.append("\n".join(structured_lines))

            if memories:
                semantic_lines = [
                    "RELEVANT MEMORIES FROM PREVIOUS CONVERSATIONS"
                ]

                for memory in memories:
                    role = memory.get("role", "unknown")
                    speaker = "Prayag" if role == "user" else "EDITH"
                    timestamp = memory.get("created_at", "Unknown time")

                    semantic_lines.append(
                        f"[{timestamp}] {speaker}: {memory['content']}"
                    )

                sections.append("\n".join(semantic_lines))

        if not sections:
            return "No relevant memory was found."

        return "\n\n".join(sections)

    def get_context(
        self,
        text: str,
        top_k: int = 20,
        min_score: float = 0.30,
    ):
        return self.build_memory_context(
            text,
            top_k=top_k,
            min_score=min_score,
        )

    def index_messages(self):
        return index_all_messages()

