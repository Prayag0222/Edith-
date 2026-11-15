import sqlite3

from app.memory.database import (
    initialize_database,
    get_connection,
)


print("Initializing database...")

initialize_database()

connection = get_connection()

print("\nRECORD COUNTS")

for table in (
    "messages",
    "memory_vectors",
    "structured_memories",
):
    count = connection.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]

    print(f"{table}: {count}")


print("\nINDEXES")

for table in (
    "messages",
    "memory_vectors",
    "structured_memories",
):
    indexes = connection.execute(
        f"PRAGMA index_list({table})"
    ).fetchall()

    print(table)

    for index in indexes:
        print(dict(index))


print("\nFOREIGN KEY ENFORCEMENT:")

print(
    connection.execute(
        "PRAGMA foreign_keys"
    ).fetchone()[0]
)

print("\nINTEGRITY CHECK:")

print(
    connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]
)

connection.close()

print("\nDATABASE TEST COMPLETED")