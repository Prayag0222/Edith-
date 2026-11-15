import sqlite3
from pathlib import Path


DATABASE_PATH = Path("data/database/edith.db")


def get_connection():
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=10,
    )

    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")

    return connection


def initialize_database():
    connection = get_connection()

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS memory_vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                embedding TEXT NOT NULL,
                FOREIGN KEY (message_id)
                    REFERENCES messages(id)
                    ON DELETE CASCADE
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS structured_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Compatibility migration.
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(messages)"
            )
        }

        if "session_id" not in columns:
            connection.execute(
                "ALTER TABLE messages ADD COLUMN session_id TEXT"
            )

        # Vector integrity and retrieval.
        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_memory_vectors_message_id
            ON memory_vectors(message_id)
        """)

        # Message retrieval.
        connection.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_messages_session_id
            ON messages(session_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_messages_created_at
            ON messages(created_at)
        """)

        # Efficient conversation-window queries.
        connection.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_messages_session_id_id
            ON messages(session_id, id)
        """)

        # Structured memory retrieval.
        connection.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_structured_memories_type_key
            ON structured_memories(type, key)
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()