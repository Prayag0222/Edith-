from datetime import datetime
from zoneinfo import ZoneInfo

from app.memory.embeddings import EmbeddingService
from app.memory.search import (
    index_messages as index_all_messages,
    search_memory,
    search_messages_in_range,
    expand_conversation_context,
)
from app.memory.time_parser import get_time_range
from app.memory.message_store import save_message
from app.memory.vector_store import save_embedding
from app.memory.structured_service import StructuredMemoryService


# --------------------------------------------------
# STRUCTURED MEMORY QUERY PROCESSING
# --------------------------------------------------

_MEMORY_QUERY_STOP_WORDS = {
    "about", "and", "are", "did", "does", "for",
    "from", "have", "how", "into", "is", "me",
    "my", "of", "on", "or", "our", "please",
    "say", "tell", "the", "to", "was", "we",
    "were", "what", "when", "where", "which",
    "who", "why", "you", "your",
}


def _memory_terms(text: str) -> set[str]:

    normalized = "".join(
        character.casefold() if character.isalnum() else " "
        for character in text
    )

    return {
        word
        for word in normalized.split()
        if len(word) > 2
        and word not in _MEMORY_QUERY_STOP_WORDS
    }


# --------------------------------------------------
# MEMORY SERVICE
# --------------------------------------------------

class MemoryService:

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.structured_memory = StructuredMemoryService()

    # --------------------------------------------------
    # MESSAGE STORAGE
    # --------------------------------------------------

    def store_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ):

        if role not in {"user", "assistant"}:
            raise ValueError(
                f"Unsupported message role: {role}"
            )

        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                "Message content cannot be empty"
            )

        content = content.strip()

        message_id = save_message(
            session_id,
            role,
            content,
        )

        embedding = self.embedding_service.encode(content)

        save_embedding(
            message_id,
            embedding,
        )

        return message_id

    # --------------------------------------------------
    # SEMANTIC SEARCH
    # --------------------------------------------------

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

    # --------------------------------------------------
    # HISTORICAL SEARCH
    # --------------------------------------------------

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

    # --------------------------------------------------
    # RELEVANT MEMORY RETRIEVAL
    # --------------------------------------------------

    def _retrieve_memories(
        self,
        text: str,
        time_range,
        top_k: int,
        min_score: float,
    ):

        if time_range is not None:

            start_time, end_time = time_range

            results = self.search_in_time_range(
                text,
                start_time,
                end_time,
                top_k=top_k,
                min_score=min_score,
            )

        else:

            results = self.search(
                text,
                top_k=top_k,
                min_score=min_score,
            )

        return expand_conversation_context(
            results,
            window=1,
            max_messages=30,
            max_anchors=5,
        )

    def get_relevant_memories(
        self,
        text: str,
        top_k: int = 10,
        min_score: float = 0.30,
    ):

        time_range = get_time_range(text)

        return self._retrieve_memories(
            text,
            time_range,
            top_k,
            min_score,
        )

    # --------------------------------------------------
    # STRUCTURED MEMORY
    # --------------------------------------------------

    def search_structured_memories(self, text: str):

        query_words = _memory_terms(text)

        if not query_words:
            return []

        memories = self.structured_memory.get_all()

        relevant = []

        minimum_matches = min(2, len(query_words))

        for memory in memories:

            memory_words = _memory_terms(
                f"{memory['key']} {memory['value']}"
            )

            matching_count = len(query_words & memory_words)

            if matching_count >= minimum_matches:
                relevant.append(memory)

        return relevant

    def get_structured_memories(self):
        return self.structured_memory.get_all()

    # --------------------------------------------------
    # CONTEXT FORMATTING
    # --------------------------------------------------

    @staticmethod
    def _format_conversation_memories(memories, utc_label=False):

        lines = []

        for memory in memories:

            content = memory.get("content", "").strip()

            if not content:
                continue

            role = memory.get("role")

            speaker = "Prayag" if role == "user" else "EDITH"

            marker = (
                "MATCH"
                if memory.get("is_match")
                else "CONTEXT"
            )

            timestamp = memory.get(
                "created_at",
                "Unknown time",
            )

            timestamp_label = (
                f"[{timestamp} UTC]"
                if utc_label
                else f"[{timestamp}]"
            )

            lines.append(
                f"[{marker}] {timestamp_label} "
                f"{speaker}: {content}"
            )

        return lines

    # --------------------------------------------------
    # MEMORY CONTEXT BUILDER
    # --------------------------------------------------

    def build_memory_context(
        self,
        text: str,
        top_k: int = 20,
        min_score: float = 0.30,
    ):

        time_range = get_time_range(text)

        memories = self._retrieve_memories(
            text,
            time_range,
            top_k,
            min_score,
        )

        sections = []

        # Historical conversation context
        if time_range is not None:

            start_utc = datetime.strptime(
                time_range[0],
                "%Y-%m-%d %H:%M:%S",
            ).replace(
                tzinfo=ZoneInfo("UTC")
            )

            local_date = start_utc.astimezone(
                ZoneInfo("Asia/Kolkata")
            ).date()

            sections.append(
                "HISTORICAL CONVERSATION RECORDS\n"
                f"Requested date: {local_date.isoformat()} "
                "(India Standard Time)\n"
                "The following messages were retrieved from "
                "the requested period.\n"
                "MATCH means the message directly matched the query.\n"
                "CONTEXT means it is surrounding conversation."
            )

            history_lines = self._format_conversation_memories(
                memories,
                utc_label=True,
            )

            if history_lines:
                sections.append("\n".join(history_lines))
            else:
                sections.append(
                    "No relevant messages were found "
                    "in the requested period."
                )

        # General long-term memory context
        else:

            structured_memories = self.search_structured_memories(
                text
            )

            if structured_memories:

                structured_lines = [
                    "KNOWN FACTS AND PREFERENCES"
                ]

                structured_lines.extend(
                    f"- {memory['type']}: "
                    f"{memory['key']} = {memory['value']}"
                    for memory in structured_memories
                )

                sections.append(
                    "\n".join(structured_lines)
                )

            semantic_lines = self._format_conversation_memories(
                memories
            )

            if semantic_lines:

                sections.append(
                    "RELEVANT MEMORIES FROM PREVIOUS CONVERSATIONS\n"
                    "MATCH means a direct retrieval result.\n"
                    "CONTEXT means surrounding conversation.\n"
                    + "\n".join(semantic_lines)
                )

        if not sections:
            return "No relevant memory was found."

        return "\n\n".join(sections)

    # --------------------------------------------------
    # PUBLIC CONTEXT API
    # --------------------------------------------------

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

    # --------------------------------------------------
    # MEMORY INDEXING
    # --------------------------------------------------

    def index_messages(self):
        return index_all_messages()