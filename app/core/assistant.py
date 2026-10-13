from app.core.identity import EDITH_IDENTITY
from time import perf_counter


class EdithAssistant:
    def __init__(self):
        self.name = "EDITH"
        self.creator = "Prayag"
        self.administrator = "Prayag"
        self.identity = EDITH_IDENTITY

    def get_identity(self):
        return {
            "name": self.name,
            "creator": self.creator,
            "administrator": self.administrator,
        }

    def get_self_description(self):
        return (
            f"I am {self.name}, a personal AI assistant ."
            f" I was created and administered by {self.creator}. "
        )

    def respond(self, conversation, llm, memory_manager, user_input):
        total_start = perf_counter()

        # 1. Extract and save structured memories.
        start = perf_counter()
        saved_memories = memory_manager.process_message(user_input)
        print(f"[TIME] Memory extraction: {perf_counter() - start:.2f}s")

        # 2. Retrieve relevant memories.
        start = perf_counter()
        memory_context = conversation.memory_service.get_context(user_input)
        print(f"[TIME] Memory retrieval: {perf_counter() - start:.2f}s")

        # 3. Add the user message and prepare conversation history.
        conversation.add_user_message(user_input)
        messages = conversation.build_messages()

        # 4. Generate the response.
        start = perf_counter()
        response = llm.generate(messages, memory_context=memory_context)
        print(f"[TIME] LLM generation: {perf_counter() - start:.2f}s")

        # 5. Save the assistant response.
        conversation.add_assistant_message(response)

        print(f"[TIME] Total response processing: {perf_counter() - total_start:.2f}s")

        return response