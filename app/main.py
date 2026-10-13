import re

from app.llm.client import OllamaClient
from app.conversation.service import ConversationService
from app.core.assistant import EdithAssistant
from app.memory.service import MemoryService
from app.memory.manager import MemoryManager
from app.voice.stt import SpeechToText
from app.voice.tts import TextToSpeech
from app.voice.wake_word import WakeWordDetector
from time import perf_counter


def is_exit_command(text: str) -> bool:
    """Recognize exit commands despite capitalization or punctuation."""
    normalized = re.sub(r"[^\w\s]", "", text.casefold()).strip()
    return normalized == "exit"


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
        print("EDITH is ready — Local AI: Online\n")
    else:
        print("EDITH is ready — Local AI: Offline\n")

    print("Type 'exit' to stop.\n")

    while True:
        print("[READY] Waiting for wake word...")
        print("[DEBUG] Wake-word detector starting...")

        wake_detected = wake_word.wait_for_wake_word()

        print(f"[DEBUG] Wake-word detector returned: {wake_detected}")

        if not wake_detected:
            continue

        print("[WAKE] Wake word detected.")

        # Keep listening until the conversation times out or EDITH exits.
        while True:
            print("[LISTEN] Listening...")

            result = stt.listen()

            if result is None:
                print("[SLEEP] Conversation timed out. Waiting for wake word.\n")
                break

            user_input = result.get("text", "").strip()

            if not user_input:
                continue

            print(f"You: {user_input}")

            if is_exit_command(user_input):
                print("EDITH: Goodbye.")
                tts.speak("Goodbye.")
                return

            print("[THINK] Thinking...")

            response_start = perf_counter()

            response = edith.respond(
                conversation,
                llm,
                memory_manager,
                user_input,
            )

            print(
                f"[TIME] Total response processing: "
                f"{perf_counter() - response_start:.2f}s\n"
            )

            print(f"EDITH: {response}\n")
            tts.speak(response)

if __name__ == "__main__":
    main()