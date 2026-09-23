from app.llm.client import OllamaClient
from app.conversation.service import ConversationService
from app.core.assistant import EdithAssistant
from app.memory.service import MemoryService
from app.memory.manager import MemoryManager


def main():
    edith = EdithAssistant()
    llm = OllamaClient(edith)

    memory = MemoryService()
    memory_manager = MemoryManager(llm)

    conversation = ConversationService(memory)

    if llm.is_available():
        print("EDITH is ready ")
        print(" Local engine AI is: Online\n")
    else:
        print("EDITH is ready ")
        print(" Local engine AI is: Offline\n")

    print("Type 'exit' to stop.\n")

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() == "exit":
            print("EDITH: Goodbye.")
            break

        if not user_input:
            continue

        response = edith.respond(
            conversation,
            llm,
            memory_manager,
            user_input,
        )

        print(f"EDITH: {response}\n")


if __name__ == "__main__":
    main()