import sqlite3
from pathlib import Path
from datetime import datetime


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

DATABASE_PATH = Path("data/database/edith.db")

BACKUP_DIRECTORY = Path("data/database/backups")


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def get_connection():

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


# --------------------------------------------------
# DATABASE BACKUP
# --------------------------------------------------

def create_backup():

    BACKUP_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_path = (
        BACKUP_DIRECTORY
        / f"edith_backup_{timestamp}.db"
    )

    source = get_connection()

    destination = sqlite3.connect(backup_path)

    try:
        source.backup(destination)
        destination.commit()

    finally:
        destination.close()
        source.close()

    print("\n[BACKUP] Database backup created:")
    print(backup_path)

    return backup_path


# --------------------------------------------------
# LOAD MESSAGES
# --------------------------------------------------

def load_all_messages():

    connection = get_connection()

    try:
        messages = connection.execute(
            """
            SELECT
                m.id,
                m.session_id,
                m.role,
                m.content,
                m.created_at,
                (
                    SELECT COUNT(*)
                    FROM memory_vectors v
                    WHERE v.message_id = m.id
                ) AS embedding_count

            FROM messages m

            ORDER BY m.id ASC
            """
        ).fetchall()

        return messages

    finally:
        connection.close()


# --------------------------------------------------
# DISPLAY MESSAGES
# --------------------------------------------------

def display_messages():

    messages = load_all_messages()

    if not messages:
        print("\nNo messages found.")
        return

    print("\n" + "=" * 90)
    print("EDITH MEMORY DATABASE")
    print("=" * 90)

    for message in messages:

        print("\n" + "-" * 90)

        print(f"ID: {message['id']}")
        print(f"Role: {message['role']}")
        print(f"Date: {message['created_at']}")
        print(f"Session: {message['session_id']}")
        print(
            f"Embeddings: {message['embedding_count']}"
        )

        print("\nContent:")
        print(message["content"])

    print("\n" + "=" * 90)

    print(f"Total messages: {len(messages)}")


# --------------------------------------------------
# INSPECT DATABASE STATISTICS
# --------------------------------------------------

def display_statistics():

    connection = get_connection()

    try:

        message_count = connection.execute(
            "SELECT COUNT(*) FROM messages"
        ).fetchone()[0]

        user_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM messages
            WHERE role = 'user'
            """
        ).fetchone()[0]

        assistant_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM messages
            WHERE role = 'assistant'
            """
        ).fetchone()[0]

        embedding_count = connection.execute(
            "SELECT COUNT(*) FROM memory_vectors"
        ).fetchone()[0]

        structured_count = connection.execute(
            "SELECT COUNT(*) FROM structured_memories"
        ).fetchone()[0]

    finally:
        connection.close()

    print("\nDATABASE STATISTICS")
    print("-" * 40)

    print(f"Total messages: {message_count}")
    print(f"User messages: {user_count}")
    print(f"Assistant messages: {assistant_count}")
    print(f"Embeddings: {embedding_count}")
    print(f"Structured memories: {structured_count}")


# --------------------------------------------------
# DELETE SELECTED MESSAGES
# --------------------------------------------------

def delete_selected_messages(message_ids):

    if not message_ids:
        print("\nNo message IDs provided.")
        return

    connection = get_connection()

    try:

        placeholders = ",".join(
            "?" for _ in message_ids
        )

        selected_messages = connection.execute(
            f"""
            SELECT id, role, content, created_at
            FROM messages
            WHERE id IN ({placeholders})
            ORDER BY id ASC
            """,
            message_ids,
        ).fetchall()

        if not selected_messages:

            print("\nNo matching messages found.")
            return

        found_ids = {
            message["id"]
            for message in selected_messages
        }

        missing_ids = set(message_ids) - found_ids

        if missing_ids:
            print(
                f"\nInvalid message IDs: {sorted(missing_ids)}"
            )
            print("No messages were deleted.")
            return

        print("\nSELECTED MESSAGES")
        print("=" * 90)

        for message in selected_messages:

            print("\n" + "-" * 90)

            print(f"ID: {message['id']}")
            print(f"Role: {message['role']}")
            print(f"Date: {message['created_at']}")
            print(f"Content: {message['content']}")

        print("\n" + "=" * 90)

        confirmation = input(
            "\nType DELETE to permanently remove these messages: "
        ).strip()

        if confirmation != "DELETE":

            print("\nDeletion cancelled.")
            return

        # Backup before modifying the database.
        create_backup()

        # Delete messages and embeddings atomically.
        try:

            connection.execute("BEGIN IMMEDIATE")

            vector_cursor = connection.execute(
                f"""
                DELETE FROM memory_vectors
                WHERE message_id IN ({placeholders})
                """,
                message_ids,
            )

            message_cursor = connection.execute(
                f"""
                DELETE FROM messages
                WHERE id IN ({placeholders})
                """,
                message_ids,
            )

            connection.commit()

        except Exception:

            connection.rollback()
            raise

        print("\n[CLEANUP COMPLETE]")
        print(
            f"Messages deleted: {message_cursor.rowcount}"
        )
        print(
            f"Embeddings deleted: {vector_cursor.rowcount}"
        )

    finally:
        connection.close()


# --------------------------------------------------
# MAIN MENU
# --------------------------------------------------

def main():

    print("\nEDITH MEMORY CLEANUP UTILITY")
    print("=" * 50)

    while True:

        print("\n1. View database statistics")
        print("2. View all messages")
        print("3. Delete selected messages")
        print("4. Exit")

        choice = input("\nSelect option: ").strip()

        if choice == "1":

            display_statistics()

        elif choice == "2":

            display_messages()

        elif choice == "3":

            raw_ids = input(
                "\nEnter message IDs separated by commas: "
            ).strip()

            try:

                message_ids = list(
                    dict.fromkeys(
                        int(value.strip())
                        for value in raw_ids.split(",")
                        if value.strip()
                    )
                )

                if any(message_id <= 0 for message_id in message_ids):
                    raise ValueError

                delete_selected_messages(message_ids)

            except ValueError:

                print(
                    "\nInvalid input. Enter numeric message IDs."
                )

        elif choice == "4":

            print("\nExiting cleanup utility.")
            break

        else:

            print("\nInvalid option.")


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":

    main()