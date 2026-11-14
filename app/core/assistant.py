from app.core.identity import EDITH_IDENTITY


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
            f"I am {self.name}, a personal AI assistant."
            f" I was created and administered by {self.creator}."
        )

    def respond_stream(
        self,
        conversation,
        llm,
        memory_manager,
        user_input,
    ):
        conversation.wait_for_persistence()
        memory_context = conversation.memory_service.get_context(
            user_input
        )

        conversation.add_user_message(user_input)
        messages = conversation.build_messages()

        response_parts = []

        try:
            for chunk in llm.generate_stream(
                messages,
                memory_context=memory_context,
            ):
                if chunk:
                    response_parts.append(chunk)
                    yield chunk
        finally:
            conversation.process_user_memory(
                user_input,
                memory_manager,
            )

        response = "".join(response_parts).strip()

        if response:
            conversation.add_assistant_message(response)

    def respond(
        self,
        conversation,
        llm,
        memory_manager,
        user_input,
    ):
        return "".join(
            self.respond_stream(
                conversation,
                llm,
                memory_manager,
                user_input,
            )
        ).strip()