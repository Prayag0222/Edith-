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


# --------------------------------------------------
# COMMAND DETECTION
# --------------------------------------------------

def is_exit_command(text: str) -> bool:
    """
    Normalize the recognized text and detect the exact exit command.

    Examples:
        Exit.
        EXIT!
        exit
    """

    normalized = re.sub(
        r"[^\w\s]",
        "",
        text.casefold(),
    ).strip()

    return normalized == "exit"


# --------------------------------------------------
# TEXT-TO-SPEECH CHUNKING
# --------------------------------------------------

def extract_speech_chunks(buffer: str, final: bool = False):
    """
    Split streamed LLM output into manageable TTS chunks.

    This allows Piper to start speaking before the complete
    LLM response has been generated.
    """

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

        # If punctuation hasn't arrived, split long text at a
        # nearby word boundary to prevent excessive TTS delay.
        if len(buffer) >= 180:

            split_at = buffer.rfind(" ", 0, 180)

            if split_at > 0:

                chunks.append(
                    buffer[:split_at].strip()
                )

                buffer = buffer[split_at + 1:]

                continue

        break

    return chunks, buffer


# --------------------------------------------------
# TTS WORKER
# --------------------------------------------------

def speech_worker(tts, speech_queue):
    """
    Run Piper in a separate thread.

    This allows LLM generation and speech playback to work
    concurrently instead of waiting for the full response.
    """

    try:
        tts.speak_stream(speech_queue)

    except Exception as error:
        print(f"\n[TTS ERROR] {error}")


# --------------------------------------------------
# MAIN ASSISTANT LOOP
# --------------------------------------------------

def run_assistant(
    edith,
    llm,
    conversation,
    voice,
    tts,
    memory_manager,
):

    while True:

        # --------------------------------------------------
        # SLEEP / WAKE MODE
        # --------------------------------------------------

        print("\n[READY] Waiting for wake word...")

        if not voice.wait_for_wake_word():
            continue

        print("[WAKE] Wake word detected.")

        # --------------------------------------------------
        # CONTINUOUS CONVERSATION MODE
        # --------------------------------------------------

        while True:

            # This call accepts the first turn after wake detection
            # and every subsequent turn during the active conversation.
            result = voice.listen()

            # None means the user remained silent for 7 seconds.
            # The voice engine has already ended the conversation.
            if result is None:

                print(
                    "[SLEEP] Conversation ended. "
                    "Waiting for wake word.\n"
                )

                break

            user_input = result.get("text", "").strip()

            if not user_input:

                print("[LISTEN] No usable transcription. Listening again.")

                voice.prepare_for_next_turn()

                continue

            print(f"You: {user_input}")

            # Exit is handled before calling the LLM.
            if is_exit_command(user_input):

                print("EDITH: Goodbye.")

                tts.speak("Goodbye.")

                return

            # --------------------------------------------------
            # THINKING / RESPONSE GENERATION
            # --------------------------------------------------

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

                # Generate the response incrementally.
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

                # Send any remaining text to Piper.
                remaining_chunks, _ = extract_speech_chunks(
                    speech_buffer,
                    final=True,
                )

                for speech_chunk in remaining_chunks:
                    speech_queue.put(speech_chunk)

                print("\n")

            finally:

                # None tells the TTS worker that no more text
                # will be added to this response.
                speech_queue.put(None)

                # Wait until all queued speech has been processed.
                speech_queue.join()

                worker.join()

            # --------------------------------------------------
            # PREPARE FOR NEXT USER TURN
            # --------------------------------------------------

            # Discard microphone audio captured during Piper playback.
            # The conversation stays active, so another wake word
            # is NOT required for the next question.
            voice.prepare_for_next_turn()


# --------------------------------------------------
# APPLICATION ENTRY POINT
# --------------------------------------------------

def main():

    edith = EdithAssistant()

    llm = OllamaClient(edith)

    # One shared microphone stream handles wake detection and speech.
    voice = VoiceEngine()

    # Existing Piper TTS implementation remains unchanged.
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

    print("Continuous Conversation Mode enabled.")
    print("Say 'Hey EDITH' to start.")
    print("Say 'exit' to stop.\n")

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