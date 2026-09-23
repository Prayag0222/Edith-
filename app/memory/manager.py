from app.memory.extractor import MemoryExtractor
from app.memory.structured_service import StructuredMemoryService


class MemoryManager:

    def __init__(self, ollama_client):
        self.extractor = MemoryExtractor(
            ollama_client
        )

        self.structured_memory = StructuredMemoryService()

    def process_message(
        self,
        user_message: str,
    ):
        result = self.extractor.extract(
            user_message
        )

        memories = result.get(
            "memories",
            [],
        )

        saved_memories = []

        for memory in memories:
            memory_id = self.structured_memory.remember(
                memory["type"],
                memory["key"],
                memory["value"],
            )

            saved_memories.append({
                "id": memory_id,
                "type": memory["type"],
                "key": memory["key"],
                "value": memory["value"],
            })

        return saved_memories