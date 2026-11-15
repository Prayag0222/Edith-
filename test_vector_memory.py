from app.memory.embeddings import EmbeddingService
from app.memory.database import get_connection
from app.memory.vector_store import (
    save_embedding,
    load_embeddings,
    delete_embedding,
)


def create_test_message():
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO messages (session_id, role, content)
            VALUES (?, ?, ?)
            """,
            ("vector-memory-test", "user", "Temporary vector test")
        )

        connection.commit()

        return cursor.lastrowid

    finally:
        connection.close()


def cleanup_test_message(message_id):
    connection = get_connection()

    try:
        connection.execute(
            "DELETE FROM memory_vectors WHERE message_id = ?",
            (message_id,),
        )

        connection.execute(
            "DELETE FROM messages WHERE id = ?",
            (message_id,),
        )

        connection.commit()

    finally:
        connection.close()


def run_test():
    print("\n1. Loading embedding model")

    embedding_service = EmbeddingService()

    print("Model loaded successfully.")

    print("\n2. Generating embedding")

    embedding = embedding_service.encode(
        "EDITH is my personal AI assistant."
    )

    print("Embedding dimensions:", len(embedding))

    assert len(embedding) == 384

    print("\n3. Creating temporary database message")

    message_id = create_test_message()

    print("Test message ID:", message_id)

    try:
        print("\n4. Saving embedding")

        save_embedding(message_id, embedding)

        print("Embedding saved.")

        print("\n5. Testing duplicate prevention")

        save_embedding(message_id, embedding)

        all_embeddings = load_embeddings()

        matching = [
            item for item in all_embeddings
            if item["message_id"] == message_id
        ]

        assert len(matching) == 1

        print("Duplicate prevention successful.")

        print("\n6. Testing retrieval")

        retrieved = matching[0]["embedding"]

        assert len(retrieved) == 384

        print("Embedding retrieved successfully.")

        print("\n7. Testing deletion")

        delete_embedding(message_id)

        all_embeddings = load_embeddings()

        matching = [
            item for item in all_embeddings
            if item["message_id"] == message_id
        ]

        assert len(matching) == 0

        print("Embedding deletion successful.")

        print("\nVECTOR MEMORY TEST PASSED")

    finally:
        cleanup_test_message(message_id)


if __name__ == "__main__":
    run_test()