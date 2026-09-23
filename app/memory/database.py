import sqlite3
from pathlib import Path
from datetime import datetime,timezone
import json 
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

    connection.execute("""
    CREATE TABLE IF NOT EXISTS memory_vectors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL,
        embedding TEXT NOT NULL,
        FOREIGN KEY (message_id) REFERENCES messages(id)
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



