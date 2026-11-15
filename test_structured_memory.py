from app.memory.structured_service import StructuredMemoryService

service = StructuredMemoryService()

print("1. Checking existing memories")

existing = service.get_all()
print("Existing memories:", len(existing))

assert len(existing) == 15, "Existing memory count changed"

print("\n2. Testing new memory")

memory_id = service.remember(
    "project",
    "__edith_test_memory__",
    "Testing structured memory",
)

assert memory_id is not None

print("Created:", memory_id)

print("\n3. Testing update without duplication")

updated_id = service.remember(
    "project",
    "__edith_test_memory__",
    "Updated structured memory",
)

assert updated_id == memory_id

matches = [
    item for item in service.get_all()
    if item["key"] == "__edith_test_memory__"
]

assert len(matches) == 1
assert matches[0]["value"] == "Updated structured memory"

print("Update successful. No duplicate created.")

print("\n4. Testing retrieval")

found = service.find(
    "project",
    "__edith_test_memory__",
)

assert found is not None
assert found["id"] == memory_id

print("Retrieval successful.")

print("\n5. Testing deletion")

deleted = service.forget(memory_id)

assert deleted is True

assert service.find(
    "project",
    "__edith_test_memory__",
) is None

print("Deletion successful.")

print("\n6. Verifying original memories")

final_memories = service.get_all()

assert len(final_memories) == 15

print("Original memories preserved:", len(final_memories))
print("\nSTRUCTURED MEMORY TEST PASSED")