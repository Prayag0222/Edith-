import queue
import threading
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd

from piper import PiperVoice
from app.voice.text_normalizer import normalize_for_speech


class TextToSpeech:
    """
    EDITH Text-to-Speech engine.

    Features:
        - Lazy-independent Piper voice initialization
        - Streaming speech synthesis
        - Bounded producer-consumer audio pipeline
        - Low-latency audio playback
        - Thread-safe speech requests
        - Safe producer cancellation
        - Reliable resource cleanup
    """

    AUDIO_QUEUE_SIZE = 4
    QUEUE_TIMEOUT = 0.1

    def __init__(
        self,
        voice_path: str = r"D:\Edith\en_US-lessac-medium.onnx",
    ):
        self.voice_path = Path(voice_path)

        if not self.voice_path.is_file():
            raise FileNotFoundError(
                f"Piper voice model not found: {self.voice_path}"
            )

        self._speech_lock = threading.Lock()
        self._closed = False

        self.output_stream = None

        self.voice = PiperVoice.load(
            model_path=str(self.voice_path),
            use_cuda=False,
        )

        self.sample_rate = self.voice.config.sample_rate

        try:
            self.output_stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                latency="low",
            )

            self.output_stream.start()

        except Exception:
            if self.output_stream is not None:
                try:
                    self.output_stream.close()
                except Exception:
                    pass

            raise

    # --------------------------------------------------
    # AUDIO PRODUCER
    # --------------------------------------------------

    def _produce_audio(
        self,
        speech_queue,
        audio_queue,
        stop_event,
        errors,
    ):
        """
        Generate speech chunks in a background thread.
        """

        def put_audio(audio):
            while not stop_event.is_set():

                try:
                    audio_queue.put(
                        audio,
                        timeout=self.QUEUE_TIMEOUT,
                    )
                    return True

                except queue.Full:
                    continue

            return False

        try:
            while not stop_event.is_set():

                try:
                    text = speech_queue.get()

                except Exception:
                    break

                try:
                    if text is None:
                        break

                    if not isinstance(text, str):
                        continue

                    clean_text = normalize_for_speech(text)

                    if not clean_text:
                        continue

                    for chunk in self.voice.synthesize(clean_text):

                        if stop_event.is_set():
                            break

                        audio = chunk.audio_float_array

                        if not isinstance(audio, np.ndarray):
                            audio = np.asarray(
                                audio,
                                dtype=np.float32,
                            )

                        if audio.size == 0:
                            continue

                        if not audio.flags.c_contiguous:
                            audio = np.ascontiguousarray(audio)

                        if not put_audio(audio):
                            break

                finally:
                    speech_queue.task_done()

        except Exception as error:
            errors.append(error)

        finally:
            # Signal the playback consumer that synthesis ended.
            if not stop_event.is_set():
                put_audio(None)

    # --------------------------------------------------
    # STREAMING PLAYBACK
    # --------------------------------------------------

    def speak_stream(self, speech_queue):
        """
        Synthesize and play speech concurrently.

        The producer generates audio while the consumer
        plays previously generated chunks.
        """

        if self._closed:
            raise RuntimeError("TTS engine is closed.")

        with self._speech_lock:

            if self._closed:
                raise RuntimeError("TTS engine is closed.")

            output_stream = self.output_stream

            if output_stream is None:
                raise RuntimeError("Audio output stream is not initialized.")

            audio_queue = queue.Queue(
                maxsize=self.AUDIO_QUEUE_SIZE
            )

            stop_event = threading.Event()
            errors = []

            producer = threading.Thread(
                target=self._produce_audio,
                args=(
                    speech_queue,
                    audio_queue,
                    stop_event,
                    errors,
                ),
                name="EDITH-TTS-Producer",
                daemon=True,
            )

            producer.start()

            playback_error = None

            try:
                while True:

                    audio = audio_queue.get()

                    if audio is None:
                        break

                    audio = np.asarray(
                        audio,
                        dtype=np.float32,
                    ).reshape(-1, 1)

                    if audio.size == 0:
                        continue

                    output_stream.write(audio)

            except Exception as error:
                playback_error = error

            finally:
                if playback_error is not None:
                    stop_event.set()

                producer.join()

            if playback_error is not None:
                raise RuntimeError(
                    f"TTS playback failed: {playback_error}"
                ) from playback_error

            if errors:
                raise RuntimeError(
                    f"Piper synthesis failed: {errors[0]}"
                ) from errors[0]

    # --------------------------------------------------
    # SIMPLE SPEECH
    # --------------------------------------------------

    def speak(self, text: str):
        """Speak a single text string."""

        if not isinstance(text, str) or not text.strip():
            return

        speech_queue = queue.Queue()

        speech_queue.put(text)
        speech_queue.put(None)

        self.speak_stream(speech_queue)

    # --------------------------------------------------
    # SHUTDOWN
    # --------------------------------------------------

    def close(self):
        """Stop playback and release audio resources."""

        with self._speech_lock:

            if self._closed:
                return

            self._closed = True

            if self.output_stream is not None:

                try:
                    self.output_stream.stop()
                finally:
                    self.output_stream.close()

                self.output_stream = None