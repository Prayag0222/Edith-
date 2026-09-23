from app.memory.database import get_connection
from datetime import datetime, timezone



def save_message(session_id: str, role: str, content: str):
    connection = get_connection()

    created_at = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    cursor = connection.execute(
        """
        INSERT INTO messages (session_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, role, content, created_at),
    )

    message_id = cursor.lastrowid

    if message_id is None:
        connection.close()
        raise RuntimeError("Failed to retrieve inserted message ID")

    connection.commit()
    connection.close()

    return message_id

def load_messages():
    connection = get_connection()

    cursor = connection.execute(
        """
        SELECT id,session_id, role, content, created_at
        FROM messages
        ORDER BY id ASC
        """
    )

    messages = []

    for message_id, session_id, role, content, created_at in cursor.fetchall():
        messages.append({
            "id": message_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "created_at": created_at,
        })

    connection.close()

    return messages


def load_session_messages(session_id:str):
    connection = get_connection()

    cursor = connection.execute("""
    SELECT session_id, role,content, created_at
    FROM messages
    WHERE session_id = ?
    ORDER BY id ASC
    """, (session_id,),)

    messages = []

    for session_id, role, content, created_at in cursor.fetchall():
        messages.append({
            "session_id": session_id,
            "role": role,
            "content": content,
            "created_at": created_at,
        })

    connection.close()

    return messages    

def load_messages_between(start_time: str, end_time: str):

    connection = get_connection()

    cursor = connection.execute(
        """
        SELECT id,session_id, role, content, created_at
        FROM messages
        WHERE created_at >= ?
        AND created_at <= ?
        ORDER BY id ASC
        """,
        (start_time, end_time),
    )

    messages = []

    for message_id, session_id, role, content, created_at in cursor.fetchall():
        messages.append({
            "id": message_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "created_at": created_at,
        })

    connection.close()

    return messages

def load_message(message_id: int):
    connection = get_connection()

    cursor = connection.execute(
        """
        SELECT id, session_id, role, content, created_at
        FROM messages
        WHERE id = ?
        """,
        (message_id,),
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return {
        "id": row[0],
        "session_id": row[1],
        "role": row[2],
        "content": row[3],
        "created_at": row[4],
    }


