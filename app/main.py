import re
import queue
import threading

from app.llm.client import OllamaClient
from app.conversation.service import ConversationService
from app.core.assistant import EdithAssistant
from app.memory.service import MemoryService
from app.memory.manager import MemoryManager
from app.memory.workers.worker_manager import BackgroundMemoryWorker

from app.voice.tts import TextToSpeech
from app.voice_v2.engine import VoiceEngine


def is_exit_command(text: str) -> bool:
    normalized = re.sub(
        r"[^\w\s]",
        "",
        text.casefold(),
    ).strip()

    return normalized == "exit"


def extract_speech_chunks(buffer: str, final: bool = False):
    chunks = []

    if final:
        if buffer.strip():
            chunks.append(buffer.strip())

        return chunks, ""

    while buffer:
        match = re.search(
            r"""[.!?]["')\]]*\s+""",
            buffer,
        )

        if match:
            chunk = buffer[:match.end()].strip()
            buffer = buffer[match.end():]

            if chunk:
                chunks.append(chunk)

            continue

        # Avoid waiting too long for punctuation.
        if len(buffer) >= 180:
            split_at = buffer.rfind(" ", 0, 180)

            if split_at > 0:
                chunks.append(buffer[:split_at].strip())
                buffer = buffer[split_at + 1:]
                continue

        break

    return chunks, buffer


def speech_worker(tts, speech_queue):
    try:
        tts.speak_stream(speech_queue)

    except Exception as error:
        print(f"\n[TTS ERROR] {error}")


def run_assistant(
    edith,
    llm,
    conversation,
    voice,
    tts,
    memory_manager,
):
    while True:
        print("\n[READY] Waiting for wake word...")

        if not voice.wait_for_wake_word():
            continue

        print("[WAKE] Wake word detected.")

        print("[LISTEN] Listening...")

        result = voice.listen()

        if result is None:
            print("[SLEEP] No speech detected. Returning to wake-word mode.")
            continue

        user_input = result.get("text", "").strip()

        if not user_input:
            print("[SLEEP] No transcription received.")
            continue

        print(f"You: {user_input}")

        if is_exit_command(user_input):
            print("EDITH: Goodbye.")
            tts.speak("Goodbye.")
            return

        print("[THINK] Thinking...")

        speech_queue = queue.Queue()

        worker = threading.Thread(
            target=speech_worker,
            args=(tts, speech_queue),
            daemon=True,
        )

        worker.start()

        print("EDITH: ", end="", flush=True)

        speech_buffer = ""

        try:
            for chunk in edith.respond_stream(
                conversation,
                llm,
                memory_manager,
                user_input,
            ):
                print(chunk, end="", flush=True)

                speech_buffer += chunk

                ready_chunks, speech_buffer = extract_speech_chunks(
                    speech_buffer
                )

                for speech_chunk in ready_chunks:
                    speech_queue.put(speech_chunk)

            remaining_chunks, _ = extract_speech_chunks(
                speech_buffer,
                final=True,
            )

            for speech_chunk in remaining_chunks:
                speech_queue.put(speech_chunk)

            print("\n")

        finally:
            speech_queue.put(None)
            speech_queue.join()
            worker.join()


def main():
    edith = EdithAssistant()
    llm = OllamaClient(edith)

    # New unified voice engine.
    # One shared microphone stream handles wake detection and listening.
    voice = VoiceEngine()

    # Existing Piper TTS remains unchanged.
    tts = TextToSpeech()

    memory = MemoryService()
    memory_manager = MemoryManager(llm)

    memory_worker = BackgroundMemoryWorker(
        memory,
        memory_manager,
        llm,
    )

    conversation = ConversationService(
        memory,
        memory_worker,
    )

    if llm.is_available():
        print("EDITH is ready — Local AI: Online\n")
    else:
        print("EDITH is ready — Local AI: Offline\n")

    print("Type 'exit' to stop.\n")

    try:
        run_assistant(
            edith,
            llm,
            conversation,
            voice,
            tts,
            memory_manager,
        )

    finally:
        print("\n[SHUTDOWN] Closing EDITH...")

        try:
            voice.close()
        finally:
            try:
                tts.close()
            finally:
                memory_worker.close()

        print("[SHUTDOWN] EDITH closed.")


if __name__ == "__main__":
    main()