from app.memory.message_store import (
    save_message,
    load_messages,
    load_session_messages,
    load_message,
    load_messages_around,
    load_messages_between,
)

from app.memory.database import get_connection


def cleanup(session_id):
    connection = get_connection()

    try:
        connection.execute(
            "DELETE FROM messages WHERE session_id = ?",
            (session_id,),
        )

        connection.commit()

    finally:
        connection.close()


def run_test():

    session_id = "message-store-test"

    cleanup(session_id)

    try:
        print("1. Testing message insertion")

        first_id = save_message(
            session_id,
            "user",
            "Hello EDITH",
        )

        second_id = save_message(
            session_id,
            "assistant",
            "Hello. How can I help?",
        )

        third_id = save_message(
            session_id,
            "user",
            "Remember my project.",
        )

        assert first_id < second_id < third_id

        print("Message insertion passed.")

        print("\n2. Testing session retrieval")

        session_messages = load_session_messages(session_id)

        assert len(session_messages) == 3
        assert session_messages[0]["id"] == first_id

        print("Session retrieval passed.")

        print("\n3. Testing individual retrieval")

        message = load_message(second_id)

        assert message is not None
        assert message["content"] == "Hello. How can I help?"

        print("Individual retrieval passed.")

        print("\n4. Testing conversation context")

        context = load_messages_around(
            message_id=second_id,
            session_id=session_id,
            window=1,
        )

        assert len(context) == 3

        print("Conversation context passed.")

        print("\n5. Testing global message retrieval")

        all_messages = load_messages()

        assert any(
            item["id"] == first_id
            for item in all_messages
        )

        print("Global retrieval passed.")

        print("\n6. Testing date range retrieval")

        target = load_message(first_id)

        start_time = target["created_at"]
        end_time = "9999-12-31 23:59:59"

        range_messages = load_messages_between(
            start_time,
            end_time,
        )

        assert any(
            item["id"] == first_id
            for item in range_messages
        )

        print("Date range retrieval passed.")

        print("\nMESSAGE STORE TEST PASSED")

    finally:
        cleanup(session_id)


if __name__ == "__main__":
    run_test()