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
            f"I am {self.name}, a personal AI assistant ."
            f" I was created and administered by {self.creator}. "
        )

    def respond(self, conversation, llm, memory_manager,user_input):
        saved_memories = memory_manager.process_message(user_input)
        memory_context = conversation.memory_service.get_context(user_input)
        
            
        conversation.add_user_message(user_input)

        messages = conversation.build_messages()

        response = llm.generate(messages,memory_context=memory_context)

        conversation.add_assistant_message(response)

        return response