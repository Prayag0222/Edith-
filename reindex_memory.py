from app.memory.search import index_messages

if __name__ == "__main__":
    count = index_messages()

    print(f"Successfully indexed {count} messages.")