from datetime import datetime, timezone
import sqlite3

from app.memory.database import get_connection


def _row_to_message(row: sqlite3.Row) -> dict:
    """Convert a guaranteed database row into a message dictionary."""

    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "role": row["role"],
        "content": row["content"],
        "created_at": row["created_at"],
    }


def save_message(
    session_id: str,
    role: str,
    content: str,
):
    if not isinstance(role, str) or not role.strip():
        raise ValueError("Message role is required.")

    if not isinstance(content, str) or not content.strip():
        raise ValueError("Message content cannot be empty.")

    created_at = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S")

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO messages (
                session_id,
                role,
                content,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                session_id,
                role.strip(),
                content.strip(),
                created_at,
            ),
        )

        message_id = cursor.lastrowid

        if message_id is None:
            raise RuntimeError(
                "Failed to retrieve inserted message ID."
            )

        connection.commit()
        return message_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def load_messages():
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT id, session_id, role, content, created_at
            FROM messages
            ORDER BY id ASC
            """
        ).fetchall()

        return [_row_to_message(row) for row in rows]

    finally:
        connection.close()


def load_session_messages(session_id: str):
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT id, session_id, role, content, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()

        return [_row_to_message(row) for row in rows]

    finally:
        connection.close()


def load_messages_between(
    start_time: str,
    end_time: str,
):
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT id, session_id, role, content, created_at
            FROM messages
            WHERE created_at >= ?
              AND created_at < ?
            ORDER BY id ASC
            """,
            (start_time, end_time),
        ).fetchall()

        return [_row_to_message(row) for row in rows]

    finally:
        connection.close()


def load_message(message_id: int):
    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT id, session_id, role, content, created_at
            FROM messages
            WHERE id = ?
            """,
            (message_id,),
        ).fetchone()

        if row is None:
            return None

        return _row_to_message(row)

    finally:
        connection.close()


def load_messages_around(
    message_id: int,
    session_id: str,
    window: int = 2,
):
    if not isinstance(window, int) or window < 0:
        raise ValueError(
            "Window must be a non-negative integer."
        )

    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT id, session_id, role, content, created_at
            FROM messages
            WHERE session_id = ?
              AND (
                    id = ?
                    OR id IN (
                        SELECT id
                        FROM messages
                        WHERE session_id = ?
                          AND id < ?
                        ORDER BY id DESC
                        LIMIT ?
                    )
                    OR id IN (
                        SELECT id
                        FROM messages
                        WHERE session_id = ?
                          AND id > ?
                        ORDER BY id ASC
                        LIMIT ?
                    )
              )
            ORDER BY id ASC
            """,
            (
                session_id,
                message_id,
                session_id,
                message_id,
                window,
                session_id,
                message_id,
                window,
            ),
        ).fetchall()

        return [_row_to_message(row) for row in rows]

    finally:
        connection.close()