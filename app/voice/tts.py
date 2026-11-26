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

    English:
        Piper Lessac Medium

    Hindi:
        Piper Priyamvada Medium

    Features:
        - Automatic Hindi/English detection
        - Separate Piper models for each language
        - Streaming speech synthesis
        - Background audio generation
        - Bounded producer-consumer pipeline
        - Thread-safe playback
        - Audio sample-rate conversion
        - Safe resource cleanup
    """

    # --------------------------------------------------
    # VOICE CONFIGURATION
    # --------------------------------------------------

    ENGLISH_VOICE_PATH = Path(
        r"D:\Edith\en_US-lessac-medium.onnx"
    )

    HINDI_VOICE_PATH = Path(
        r"D:\Edith\models\tts\hindi\hi_IN-priyamvada-medium.onnx"
    )

    AUDIO_QUEUE_SIZE = 4
    QUEUE_TIMEOUT = 0.1

    # --------------------------------------------------
    # INITIALIZATION
    # --------------------------------------------------

    def __init__(
        self,
        voice_path: Optional[str] = None,
        hindi_voice_path: Optional[str] = None,
    ):

        # Optional arguments preserve compatibility with
        # existing code that passes voice_path explicitly.
        self.english_voice_path = Path(
            voice_path or self.ENGLISH_VOICE_PATH
        )

        self.hindi_voice_path = Path(
            hindi_voice_path or self.HINDI_VOICE_PATH
        )

        self._speech_lock = threading.Lock()
        self._closed = False

        self.output_stream = None

        # Validate both models before initializing Piper.
        for path in (
            self.english_voice_path,
            self.hindi_voice_path,
        ):

            if not path.is_file():
                raise FileNotFoundError(
                    f"Piper voice model not found: {path}"
                )

        print("[TTS] Loading English Lessac voice...")

        self.english_voice = PiperVoice.load(
            model_path=str(self.english_voice_path),
            use_cuda=False,
        )

        print("[TTS] Loading Hindi Priyamvada voice...")

        self.hindi_voice = PiperVoice.load(
            model_path=str(self.hindi_voice_path),
            use_cuda=False,
        )

        # Keep the existing self.voice attribute pointing
        # to the English model for compatibility.
        self.voice = self.english_voice

        self.english_sample_rate = (
            self.english_voice.config.sample_rate
        )

        self.hindi_sample_rate = (
            self.hindi_voice.config.sample_rate
        )

        # Both models currently use 22050 Hz.
        # English sample rate is the playback stream rate.
        self.sample_rate = self.english_sample_rate

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

        print("[TTS] Both Piper voices ready.")

        print(
            f"[TTS] English: {self.english_sample_rate} Hz | "
            f"Hindi: {self.hindi_sample_rate} Hz"
        )

    # --------------------------------------------------
    # LANGUAGE DETECTION
    # --------------------------------------------------

    @staticmethod
    def _contains_hindi(text: str) -> bool:
        """
        Detect Devanagari characters.

        Detection happens before text normalization because
        normalization must not destroy language information.
        """

        return any(
            "\u0900" <= character <= "\u097F"
            for character in text
        )

    def _select_voice(self, text: str):
        """
        Select the appropriate Piper model.

        If an utterance contains Devanagari characters,
        the entire utterance is routed to Hindi.
        """

        if self._contains_hindi(text):

            return (
                self.hindi_voice,
                self.hindi_sample_rate,
                "Hindi",
            )

        return (
            self.english_voice,
            self.english_sample_rate,
            "English",
        )

    # --------------------------------------------------
    # AUDIO RESAMPLING
    # --------------------------------------------------

    @staticmethod
    def _resample_audio(
        audio: np.ndarray,
        source_rate: int,
        target_rate: int,
    ) -> np.ndarray:
        """
        Convert audio to the playback stream's sample rate.

        Linear interpolation is used only when the rates differ.
        """

        if source_rate == target_rate:
            return audio

        if audio.size == 0:
            return audio

        target_length = int(
            len(audio) * target_rate / source_rate
        )

        if target_length <= 0:
            return np.array([], dtype=np.float32)

        old_positions = np.arange(
            len(audio),
            dtype=np.float32,
        )

        new_positions = np.linspace(
            0,
            len(audio) - 1,
            target_length,
            dtype=np.float32,
        )

        return np.interp(
            new_positions,
            old_positions,
            audio,
        ).astype(np.float32)

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
        Generate speech in a background thread.

        Text is processed incrementally. The selected voice
        remains unchanged for each individual text segment.
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

                    if not text.strip():
                        continue

                    # Select language before normalization.
                    selected_voice, source_rate, language = (
                        self._select_voice(text)
                    )

                    if selected_voice is None:
                        continue

                    clean_text = normalize_for_speech(text)

                    if not clean_text:
                        continue

                    print(f"[TTS] Speaking: {language}")

                    # Generate audio incrementally.
                    for chunk in selected_voice.synthesize(
                        clean_text
                    ):

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

                        if audio.dtype != np.float32:

                            audio = audio.astype(
                                np.float32,
                                copy=False,
                            )

                        if not audio.flags.c_contiguous:

                            audio = np.ascontiguousarray(audio)

                        # Resample only when model sample rates differ.
                        audio = self._resample_audio(
                            audio,
                            source_rate,
                            self.sample_rate,
                        )

                        if audio.size == 0:
                            continue

                        if not put_audio(audio):
                            break

                finally:

                    speech_queue.task_done()

        except Exception as error:

            errors.append(error)

        finally:

            # Signal the playback consumer that generation ended.
            if not stop_event.is_set():
                put_audio(None)

    # --------------------------------------------------
    # STREAMING PLAYBACK
    # --------------------------------------------------

    def speak_stream(self, speech_queue):
        """
        Synthesize and play speech concurrently.

        Existing public interface is preserved.
        """

        if self._closed:
            raise RuntimeError("TTS engine is closed.")

        with self._speech_lock:

            if self._closed:
                raise RuntimeError("TTS engine is closed.")

            output_stream = self.output_stream

            if output_stream is None:
                raise RuntimeError(
                    "Audio output stream is not initialized."
                )

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
    # SINGLE SPEECH REQUEST
    # --------------------------------------------------

    def speak(self, text: str):
        """
        Speak a single Hindi or English text string.
        """

        if not isinstance(text, str) or not text.strip():
            return

        if self._closed:
            raise RuntimeError("TTS engine is closed.")

        speech_queue = queue.Queue()

        speech_queue.put(text)
        speech_queue.put(None)

        self.speak_stream(speech_queue)

    # --------------------------------------------------
    # SHUTDOWN
    # --------------------------------------------------

    def close(self):
        """
        Stop playback and release both voice models.
        """

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

            self.english_voice = None
            self.hindi_voice = None
            self.voice = None

        print("[TTS] Both Piper voices closed.")