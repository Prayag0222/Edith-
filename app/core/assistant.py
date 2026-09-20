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

    def respond(self, conversation, llm, user_input):
        conversation.add_user_message(user_input)

        messages = conversation.build_messages()

        response = llm.generate(messages)

        conversation.add_assistant_message(response)

        return response