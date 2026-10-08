from urllib import response

from app.llm.client import OllamaClient
from app.conversation.service import ConversationService
from app.core.assistant import EdithAssistant
from app.memory.service import MemoryService
from app.memory.manager import MemoryManager
from app.voice import tts
from app.voice.stt import SpeechToText
from app.voice.tts import TextToSpeech
from app.voice.wake_word import WakeWordDetector

def main():
    edith = EdithAssistant()
    llm = OllamaClient(edith)

    memory = MemoryService()
    memory_manager = MemoryManager(llm)

    conversation = ConversationService(memory)
    stt = SpeechToText()
    tts = TextToSpeech()
    wake_word = WakeWordDetector()

    if llm.is_available():
        print("EDITH is ready ")
        print(" Local engine AI is: Online\n")
    else:
        print("EDITH is ready ")
        print(" Local engine AI is: Offline\n")

    print("Type 'exit' to stop.\n")

    while True:
        print("Waiting for wake word...")

        wake_word.wait_for_wake_word()

        print("Wake word detected!")
        print("Listening...")

        result = stt.listen()

        if result is None:
            continue

        user_input = result["text"].strip()
        print(f"You: {user_input}")

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
        tts.speak(response)


if __name__ == "__main__":
    main()