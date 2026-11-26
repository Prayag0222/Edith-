import re
import queue
import threading
import logging
from contextlib import ExitStack

import webview

from app.core.commands import (
    is_hibernate_command,
    is_shutdown_command,
    is_sleep_command,
)
from app.core.config import Settings
from app.core.lifecycle import ApplicationLifecycle, SingleInstanceGuard
from app.ui.system_tray import EdithSystemTray
from app.llm.client import OllamaClient
from app.conversation.service import ConversationService
from app.core.assistant import EdithAssistant
from app.memory.service import MemoryService
from app.memory.manager import MemoryManager
from app.memory.workers.worker_manager import BackgroundMemoryWorker

from app.voice.tts import TextToSpeech
from app.voice_v2.engine import VoiceEngine

from app.ui.desktop_window import EdithDesktopWindow
from app.ui.state_manager import EdithUIController


# --------------------------------------------------
# LOGGING
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# TEXT-TO-SPEECH CHUNKING
# --------------------------------------------------

def extract_speech_chunks(buffer: str, final: bool = False):
    """
    Split streamed LLM output into manageable TTS chunks.
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

        # Split long text at a word boundary to avoid
        # excessive delay before Piper receives text.
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

    This keeps speech synthesis and playback independent
    of the main LLM generation loop.
    """

    try:

        tts.speak_stream(speech_queue)

    except Exception:

        logger.exception("TTS worker failed")


def play_startup_greeting_once(
    tts,
    voice,
    desktop,
    tray,
    greeting,
    greeting_played,
):
    if greeting_played.is_set():
        return False

    if not voice.get_stats().get("running"):
        raise RuntimeError("Microphone is not ready for the startup greeting.")

    if not tray.is_ready:
        raise RuntimeError("EDITH tray icon is not ready for the startup greeting.")

    if not desktop._ready.wait(timeout=desktop.BRIDGE_TIMEOUT):
        greeting_played.set()
        logger.warning(
            "Startup greeting skipped because the EDITH UI bridge is not ready"
        )
        return False

    if not str(greeting).strip():
        greeting_played.set()
        logger.info("EDITH startup greeting is disabled")
        return False

    greeting_played.set()
    try:
        tts.speak(greeting)
    except Exception:
        logger.exception("EDITH startup greeting failed")
        return False

    return True


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
    ui,
    lifecycle,
    request_shutdown,
):

    while not lifecycle.is_shutting_down:

        # ----------------------------------------------
        # SLEEP / WAKE MODE
        # ----------------------------------------------

        print("\n[READY] Waiting for wake word...")

        if not voice.wait_for_wake_word():
            continue

        if not lifecycle.activate():
            return

        print("[WAKE] Wake word detected.")

        # Show the popup and enter listening state.
        ui.activate("LISTENING")

        # ----------------------------------------------
        # CONTINUOUS CONVERSATION MODE
        # ----------------------------------------------

        while True:

            result = voice.listen()

            # ------------------------------------------
            # IDLE TIMEOUT
            # ------------------------------------------

            if result is None:

                print(
                    "[SLEEP] Conversation ended. "
                    "Waiting for wake word.\n"
                )

                # Hide the popup without stopping EDITH.
                ui.sleep()
                lifecycle.sleep()

                break

            user_input = result.get("text", "").strip()

            if not user_input:

                print(
                    "[LISTEN] No usable transcription. "
                    "Listening again."
                )

                voice.prepare_for_next_turn()

                ui.set_state("LISTENING")

                continue

            print(f"You: {user_input}")
            lifecycle.note_interaction()

            # ------------------------------------------
            # SLEEP COMMAND
            # ------------------------------------------

            if is_sleep_command(user_input):

                print(
                    "[SLEEP] EDITH is waiting for the wake word."
                )

                voice.return_to_wake_word_mode()
                lifecycle.sleep()
                ui.sleep()

                break

            # ------------------------------------------
            # HIBERNATE COMMAND
            # ------------------------------------------

            if is_hibernate_command(user_input):

                print("[HIBERNATE] Releasing the Whisper model cache.")

                voice.return_to_wake_word_mode()
                lifecycle.sleep()
                ui.sleep()
                try:
                    lifecycle.hibernate_now()
                except Exception:
                    logger.warning(
                        "Manual hibernation failed; EDITH remains in wake-word mode."
                    )

                break

            # ------------------------------------------
            # SHUTDOWN COMMAND
            # ------------------------------------------

            if is_shutdown_command(user_input):

                print("EDITH: Goodbye.")

                ui.activate("SPEAKING")

                try:
                    tts.speak("Goodbye.")

                finally:
                    request_shutdown()

                return

            # ------------------------------------------
            # THINKING
            # ------------------------------------------

            print("[THINK] Thinking...")

            ui.set_state("THINKING")

            speech_queue = queue.Queue()

            worker = threading.Thread(
                target=speech_worker,
                args=(tts, speech_queue),
                name="EDITH-TTS-Worker",
                daemon=True,
            )

            worker.start()

            print("EDITH: ", end="", flush=True)

            ui.desktop.clear_response()

            speech_buffer = ""

            speaking_started = False

            try:

                # Generate LLM response incrementally.
                for chunk in edith.respond_stream(
                    conversation,
                    llm,
                    memory_manager,
                    user_input,
                ):

                    print(chunk, end="", flush=True)

                    ui.desktop.append_response(chunk)

                    speech_buffer += chunk

                    ready_chunks, speech_buffer = extract_speech_chunks(
                        speech_buffer
                    )

                    for speech_chunk in ready_chunks:

                        # Change to SPEAKING when the first
                        # speech chunk is ready for Piper.
                        if not speaking_started:

                            ui.set_state("SPEAKING")
                            speaking_started = True

                        speech_queue.put(speech_chunk)

                # Send remaining response text to Piper.
                remaining_chunks, _ = extract_speech_chunks(
                    speech_buffer,
                    final=True,
                )

                for speech_chunk in remaining_chunks:

                    if not speaking_started:

                        ui.set_state("SPEAKING")
                        speaking_started = True

                    speech_queue.put(speech_chunk)

                print("\n")

            finally:

                # Tell Piper that response generation is complete.
                speech_queue.put(None)

                # Wait until queued speech is processed.
                speech_queue.join()

                worker.join()

            # ------------------------------------------
            # PREPARE NEXT TURN
            # ------------------------------------------

            voice.prepare_for_next_turn()

            # EDITH is ready for another user utterance.
            ui.set_state("LISTENING")


# --------------------------------------------------
# APPLICATION RUNTIME
# --------------------------------------------------

def assistant_runtime(
    edith,
    llm,
    conversation,
    voice,
    tts,
    memory_manager,
    ui,
    lifecycle,
    desktop,
    tray,
    startup_greeting,
    greeting_played,
    request_shutdown,
):

    """
    Runs EDITH's backend independently of the GUI event loop.

    pywebview owns the main thread.
    The assistant runs in a background thread.
    """

    try:
        play_startup_greeting_once(
            tts,
            voice,
            desktop,
            tray,
            startup_greeting,
            greeting_played,
        )

        run_assistant(
            edith,
            llm,
            conversation,
            voice,
            tts,
            memory_manager,
            ui,
            lifecycle,
            request_shutdown,
        )

    except Exception:

        logger.exception("EDITH encountered an unexpected error")

    finally:
        request_shutdown()


# --------------------------------------------------
# APPLICATION ENTRY POINT
# --------------------------------------------------

def main():

    instance_guard = SingleInstanceGuard()
    if not instance_guard.acquire():
        logger.warning("EDITH is already running; ignoring duplicate launch.")
        print("EDITH is already running.")
        return

    with ExitStack() as cleanup:
        cleanup.callback(instance_guard.close)

        edith = EdithAssistant()

        llm = OllamaClient(edith)

        voice = VoiceEngine()
        cleanup.callback(voice.close)

        tts = TextToSpeech()
        cleanup.callback(tts.close)

        memory = MemoryService()

        memory_manager = MemoryManager(llm)

        memory_worker = BackgroundMemoryWorker(
            memory,
            memory_manager,
            llm,
        )
        cleanup.callback(memory_worker.close)

        conversation = ConversationService(
            memory,
            memory_worker,
        )

        desktop = EdithDesktopWindow()
        cleanup.callback(desktop.close)
        desktop.create()

        ui = EdithUIController(desktop)
        cleanup.callback(ui.close)

        tray = None

        def update_tray_status(mode):
            if tray is not None:
                tray.set_status(mode)

        lifecycle = ApplicationLifecycle(
            Settings.HIBERNATE_AFTER_SECONDS,
            voice.hibernate,
            on_mode_change=update_tray_status,
        )
        cleanup.callback(lifecycle.shutdown)

        def request_shutdown():
            lifecycle.shutdown()
            ui.close()

        cleanup.callback(request_shutdown)

        tray = EdithSystemTray(
            Settings.TRAY_ICON_PATH,
            open_ui=desktop.show,
            hide_ui=desktop.hide,
            exit_application=request_shutdown,
            initial_status=lifecycle.mode,
        )
        cleanup.callback(tray.stop)

        voice.start()
        if not voice.get_stats().get("running"):
            raise RuntimeError("EDITH microphone stream did not start.")
        lifecycle.start()
        tray.start()

        # ----------------------------------------------
        # STARTUP STATUS
        # ----------------------------------------------

        if llm.is_available():

            print("EDITH is ready — Local AI: Online\n")

        else:

            print("EDITH is ready — Local AI: Offline\n")

        print("Continuous Conversation Mode enabled.")
        print("Say 'Hey EDITH' to start.")
        print("Say 'sleep', 'stop', or 'go to sleep' to wait.")
        print("Say 'hibernate' to release the Whisper model.")
        print("Say 'exit' to stop EDITH.\n")

        greeting_played = threading.Event()

        # ----------------------------------------------
        # START ASSISTANT THREAD
        # ----------------------------------------------

        assistant_thread = threading.Thread(
            target=assistant_runtime,
            args=(
                edith,
                llm,
                conversation,
                voice,
                tts,
                memory_manager,
                ui,
                lifecycle,
                desktop,
                tray,
                Settings.STARTUP_GREETING,
                greeting_played,
                request_shutdown,
            ),
            name="EDITH-Assistant",
            daemon=True,
        )

        assistant_started = False
        try:
            assistant_thread.start()
            assistant_started = True

            # pywebview manages the main GUI thread.
            webview.start()

        finally:
            request_shutdown()
            if assistant_started:
                try:
                    if assistant_thread.is_alive():
                        voice.close()
                finally:
                    assistant_thread.join()


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    main()