from app.memory.database import get_connection
import json


def save_embedding(message_id: int, embedding):
    connection = get_connection()

    embedding_json = json.dumps(embedding.tolist())

    connection.execute(
        """
        INSERT INTO memory_vectors (message_id, embedding)
        VALUES (?, ?)
        """,
        (message_id, embedding_json),
    )

    connection.commit()
    connection.close()


def load_embeddings():
    connection = get_connection()

    cursor = connection.execute(
        """
        SELECT message_id, embedding
        FROM memory_vectors
        ORDER BY id ASC
        """
    )

    embeddings = []

    for message_id, embedding_json in cursor.fetchall():
        embeddings.append({
            "message_id": message_id,
            "embedding": json.loads(embedding_json),
        })

    connection.close()

    return embeddings


def delete_embedding(message_id: int):
    connection = get_connection()

    connection.execute(
        """
        DELETE FROM memory_vectors
        WHERE message_id = ?
        """,
        (message_id,),
    )

    connection.commit()
    connection.close()



