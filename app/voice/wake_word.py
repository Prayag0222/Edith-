import numpy as np
import sounddevice as sd
from openwakeword.model import Model
from typing import Dict, cast
import time


class WakeWordDetector:
    def __init__(
        self,
        wake_word: str = "hey_jarvis",
        sample_rate: int = 16000,
        chunk_size: int = 1280,
        threshold: float = 0.4,
    ):
        self.wake_word = wake_word
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.threshold = threshold
        self.cooldown_seconds = 2.0
        self.last_detection_time = 0.0

        self.model = Model(
            wakeword_models=[wake_word],
            inference_framework="onnx",
        )

    def wait_for_wake_word(self):
        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self.chunk_size,
        ) as stream:

            while True:
                audio, overflowed = stream.read(self.chunk_size)

                if overflowed:
                    continue

                audio = np.squeeze(audio)

                prediction = cast(Dict[str, float], self.model.predict(audio))

                score = prediction[self.wake_word]

                if score >= self.threshold:
                    current_time = time.monotonic()

                    if current_time - self.last_detection_time < self.cooldown_seconds:
                        continue

                    print(f"[WAKE DEBUG] Score: {score:.3f}")
                    self.last_detection_time = current_time
                    return True