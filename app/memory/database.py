import sqlite3
from pathlib import Path
from datetime import datetime,timezone

DATABASE_PATH = Path("data/database/edith.db")


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)

    return connection

def initialize_database():
    connection = get_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    columns = connection.execute(
        "PRAGMA table_info(messages)"
    ).fetchall()

    column_names = [column[1] for column in columns]

    if "session_id" not in column_names:
        connection.execute(
            "ALTER TABLE messages ADD COLUMN session_id TEXT"
        )

    connection.commit()
    connection.close()

def save_message(session_id: str, role: str, content: str):
    connection = get_connection()

    created_at = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    connection.execute(
        """
        INSERT INTO messages (session_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, role, content, created_at),
    )

    connection.commit()
    connection.close()

def load_messages():
    connection = get_connection()

    cursor = connection.execute(
        """
        SELECT session_id, role, content, created_at
        FROM messages
        ORDER BY id ASC
        """
    )

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
        SELECT session_id, role, content, created_at
        FROM messages
        WHERE created_at >= ?
        AND created_at <= ?
        ORDER BY id ASC
        """,
        (start_time, end_time),
    )

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