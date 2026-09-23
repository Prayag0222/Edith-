from app.memory.structured_store import (
    save_structured_memory,
    load_structured_memories,
    update_structured_memory,
    delete_structured_memory,
    find_structured_memory
)


class StructuredMemoryService:

    def remember(
        self,
        memory_type: str,
        key: str,
        value: str,
    ):
        existing_memory = self.find(
            memory_type,
            key,
        )

        if existing_memory is not None:
            update_structured_memory(
                existing_memory["id"],
                value,
            )

            return existing_memory["id"]

        return save_structured_memory(
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
        update_structured_memory(
            memory_id,
            value,
        )

    def forget(
        self,
        memory_id: int,
    ):
        delete_structured_memory(
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

     