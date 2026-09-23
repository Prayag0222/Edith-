from app.memory.database import get_connection




def save_structured_memory(
    memory_type: str,
    key: str,
    value: str,
):
    connection = get_connection()

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
     connection.close()
     raise RuntimeError("Failed to retrieve structured memory ID")


    connection.commit()
    connection.close()

    return memory_id

def load_structured_memories():
    connection = get_connection()

    cursor = connection.execute(
        """
        SELECT id, type, key, value, created_at, updated_at
        FROM structured_memories
        ORDER BY id ASC
        """
    )

    memories = []

    for memory_id, memory_type, key, value, created_at, updated_at in cursor.fetchall():
        memories.append({
            "id": memory_id,
            "type": memory_type,
            "key": key,
            "value": value,
            "created_at": created_at,
            "updated_at": updated_at,
        })

    connection.close()

    return memories


def update_structured_memory(
    memory_id: int,
    value: str,
):
    connection = get_connection()

    connection.execute(
        """
        UPDATE structured_memories
        SET value = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (value, memory_id),
    )

    connection.commit()
    connection.close()

def delete_structured_memory(memory_id: int):
    connection = get_connection()

    connection.execute(
        """
        DELETE FROM structured_memories
        WHERE id = ?
        """,
        (memory_id,),
    )

    connection.commit()
    connection.close()

def find_structured_memory(
    memory_type: str,
    key: str,
):
    connection = get_connection()

    cursor = connection.execute(
        """
        SELECT id, type, key, value, created_at, updated_at
        FROM structured_memories
        WHERE type = ?
        AND key = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (memory_type, key),
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return {
        "id": row[0],
        "type": row[1],
        "key": row[2],
        "value": row[3],
        "created_at": row[4],
        "updated_at": row[5],
    }