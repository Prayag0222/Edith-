from app.memory.database import get_connection


def clear_database():
    connection = get_connection()

    connection.execute("DELETE FROM memory_vectors")
    connection.execute("DELETE FROM messages")
    connection.execute("DELETE FROM structured_memories")

    connection.commit()
    connection.close()

    print("EDITH memory database cleared.")


if __name__ == "__main__":
    clear_database()