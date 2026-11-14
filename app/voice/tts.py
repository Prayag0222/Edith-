
import queue
import threading
from pathlib import Path

import sounddevice as sd

from piper import PiperVoice
from app.voice.text_normalizer import normalize_for_speech

class TextToSpeech:
    def __init__(
        self,
        voice_path: str = r"D:\Edith\en_US-lessac-medium.onnx",
    ):
        self.voice_path = Path(voice_path)

        if not self.voice_path.exists():
            raise FileNotFoundError(
                f"Piper voice model not found: {self.voice_path}"
            )

        print("[TTS] Loading Piper voice...")

        # Load model only once.
        self.voice = PiperVoice.load(
            model_path=self.voice_path,
            use_cuda=False,
        )

        self.sample_rate = self.voice.config.sample_rate

        # Keep audio output open.
        self.output_stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            latency="low",
        )

        self.output_stream.start()

        print("[TTS] Piper voice ready.")

    def speak_stream(self, speech_queue):
        audio_queue = queue.Queue(maxsize=8)
        errors = []

        def audio_generator():
            try:
                while True:
                    text = speech_queue.get()

                    try:
                        if text is None:
                            break

                        clean_text = normalize_for_speech(text)

                        if not clean_text:
                            continue

                        for chunk in self.voice.synthesize(clean_text):
                            audio_queue.put(chunk)
                    finally:
                        speech_queue.task_done()

            except Exception as error:
                errors.append(error)

            finally:
                audio_queue.put(None)

        producer = threading.Thread(
            target=audio_generator,
            daemon=True,
        )

        producer.start()

        while True:
            audio = audio_queue.get()

            if audio is None:
                break

            self.output_stream.write(
                audio.reshape(-1, 1)
            )

        producer.join()

        if errors:
            raise RuntimeError(
                f"Piper synthesis failed: {errors[0]}"
            ) from errors[0]

    def speak(self, text: str):
        if not text or not text.strip():
            return

        speech_queue = queue.Queue()

        speech_queue.put(text)
        speech_queue.put(None)

        self.speak_stream(speech_queue)

    def close(self):
        if self.output_stream:
            self.output_stream.stop()
            self.output_stream.close()
