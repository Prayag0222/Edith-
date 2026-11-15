from app.memory.structured_store import (
    upsert_structured_memory,
    load_structured_memories,
    update_structured_memory,
    delete_structured_memory,
    find_structured_memory,
)


VALID_MEMORY_TYPES = {
    "fact",
    "preference",
    "project",
    "person",
}


class StructuredMemoryService:

    def remember(
        self,
        memory_type: str,
        key: str,
        value: str,
    ):

        if not all(
            isinstance(item, str)
            for item in (memory_type, key, value)
        ):
            raise ValueError(
                "Memory fields must be strings."
            )

        memory_type = memory_type.strip().lower()
        key = key.strip()
        value = value.strip()

        if memory_type not in VALID_MEMORY_TYPES:
            raise ValueError(
                f"Unsupported memory type: {memory_type}"
            )

        if not key or not value:
            raise ValueError(
                "Memory key and value are required."
            )

        return upsert_structured_memory(
            memory_type,
            key,
            value,
        )

    def get_all(self):
        return load_structured_memories()

    def update(
        self,
        memory_id: int,
        value: str,
    ):
        return update_structured_memory(
            memory_id,
            value,
        )

    def forget(
        self,
        memory_id: int,
    ):
        return delete_structured_memory(
            memory_id,
        )

    def find(
        self,
        memory_type: str,
        key: str,
    ):
        return find_structured_memory(
            memory_type,
            key,
        )

    def get(
        self,
        memory_type: str,
        key: str,
    ):
        return self.find(
            memory_type,
            key,
        )