import json
import math

from app.memory.database import get_connection


def _normalize_embedding(embedding):
    """
    Convert an embedding into a validated flat Python list.
    Supports NumPy arrays and regular Python lists.
    """

    if hasattr(embedding, "tolist"):
        embedding = embedding.tolist()

    if not isinstance(embedding, (list, tuple)):
        raise TypeError("Embedding must be a list or NumPy array.")

    if not embedding:
        raise ValueError("Embedding cannot be empty.")

    if any(isinstance(value, (list, tuple)) for value in embedding):
        raise ValueError("Embedding must be a one-dimensional vector.")

    normalized = []

    for value in embedding:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Embedding contains a non-numeric value.")

        value = float(value)

        if not math.isfinite(value):
            raise ValueError("Embedding contains a non-finite value.")

        normalized.append(value)

    return normalized


def save_embedding(message_id: int, embedding):
    """
    Save one embedding per message.

    Existing embeddings for the same message are replaced,
    preventing duplicate vector records.
    """

    if not isinstance(message_id, int):
        raise TypeError("message_id must be an integer.")

    embedding_list = _normalize_embedding(embedding)

    embedding_json = json.dumps(
        embedding_list,
        allow_nan=False,
    )

    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        connection.execute(
            """
            DELETE FROM memory_vectors
            WHERE message_id = ?
            """,
            (message_id,),
        )

        connection.execute(
            """
            INSERT INTO memory_vectors (message_id, embedding)
            VALUES (?, ?)
            """,
            (message_id, embedding_json),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def load_embeddings():
    """
    Load all stored embeddings in insertion order.
    """

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT message_id, embedding
            FROM memory_vectors
            ORDER BY id ASC
            """
        )

        rows = cursor.fetchall()

        embeddings = []

        for message_id, embedding_json in rows:
            try:
                embedding = json.loads(embedding_json)
                embedding = _normalize_embedding(embedding)

            except (json.JSONDecodeError, TypeError, ValueError) as error:
                raise ValueError(
                    f"Invalid embedding stored for message ID {message_id}: "
                    f"{error}"
                ) from error

            embeddings.append({
                "message_id": message_id,
                "embedding": embedding,
            })

        return embeddings

    finally:
        connection.close()


def delete_embedding(message_id: int):
    """
    Delete all embeddings associated with a message.
    """

    if not isinstance(message_id, int):
        raise TypeError("message_id must be an integer.")

    connection = get_connection()

    try:
        connection.execute(
            """
            DELETE FROM memory_vectors
            WHERE message_id = ?
            """,
            (message_id,),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()