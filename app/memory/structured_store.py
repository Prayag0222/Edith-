import sqlite3

from app.memory.database import get_connection


def _validate_memory_fields(
    memory_type: str,
    key: str,
    value: str,
):
    if not all(
        isinstance(item, str)
        for item in (memory_type, key, value)
    ):
        raise ValueError("Memory fields must be strings.")

    memory_type = memory_type.strip().lower()
    key = key.strip()
    value = value.strip()

    if not all((memory_type, key, value)):
        raise ValueError(
            "Memory type, key and value are required."
        )

    return memory_type, key, value


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a guaranteed database row into a dictionary."""

    return {
        "id": row["id"],
        "type": row["type"],
        "key": row["key"],
        "value": row["value"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def save_structured_memory(
    memory_type: str,
    key: str,
    value: str,
):
    memory_type, key, value = _validate_memory_fields(
        memory_type,
        key,
        value,
    )

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO structured_memories (type, key, value)
            VALUES (?, ?, ?)
            """,
            (memory_type, key, value),
        )

        memory_id = cursor.lastrowid

        if memory_id is None:
            raise RuntimeError(
                "Failed to save structured memory."
            )

        connection.commit()
        return memory_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def upsert_structured_memory(
    memory_type: str,
    key: str,
    value: str,
):
    memory_type, key, value = _validate_memory_fields(
        memory_type,
        key,
        value,
    )

    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        existing = connection.execute(
            """
            SELECT id
            FROM structured_memories
            WHERE LOWER(TRIM(type)) = ?
              AND LOWER(TRIM(key)) = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                memory_type,
                key.casefold(),
            ),
        ).fetchone()

        if existing is not None:

            memory_id = existing["id"]

            connection.execute(
                """
                UPDATE structured_memories
                SET value = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (value, memory_id),
            )

        else:

            cursor = connection.execute(
                """
                INSERT INTO structured_memories (
                    type,
                    key,
                    value
                )
                VALUES (?, ?, ?)
                """,
                (memory_type, key, value),
            )

            memory_id = cursor.lastrowid

            if memory_id is None:
                raise RuntimeError(
                    "Failed to save structured memory."
                )

        connection.commit()
        return memory_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def load_structured_memories():
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT id, type, key, value, created_at, updated_at
            FROM structured_memories
            ORDER BY id ASC
            """
        ).fetchall()

        return [_row_to_dict(row) for row in rows]

    finally:
        connection.close()


def update_structured_memory(
    memory_id: int,
    value: str,
):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Memory value cannot be empty.")

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            UPDATE structured_memories
            SET value = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (value.strip(), memory_id),
        )

        connection.commit()
        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def delete_structured_memory(memory_id: int):
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            DELETE FROM structured_memories
            WHERE id = ?
            """,
            (memory_id,),
        )

        connection.commit()
        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def find_structured_memory(
    memory_type: str,
    key: str,
):
    if not isinstance(memory_type, str) or not isinstance(key, str):
        raise ValueError(
            "Memory type and key must be strings."
        )

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT id, type, key, value, created_at, updated_at
            FROM structured_memories
            WHERE LOWER(TRIM(type)) = ?
              AND LOWER(TRIM(key)) = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                memory_type.strip().lower(),
                key.strip().casefold(),
            ),
        ).fetchone()

        if row is None:
            return None

        return _row_to_dict(row)

    finally:
        connection.close()