import time

import numpy as np
import sounddevice as sd
from typing import Dict
from openwakeword.model import Model
from typing import Dict, cast


SAMPLE_RATE = 16000
CHUNK_SIZE = 1280  # 80 ms at 16 kHz


print("Loading wake-word model...")

model = Model(
    wakeword_models=["hey_jarvis"],
    inference_framework="onnx",
)

print("Wake-word model loaded.")
print()
print("Listening for: 'Hey Jarvis'")
print("Press Ctrl+C to stop.")
print()


try:
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=CHUNK_SIZE,
    ) as stream:

        while True:
            audio, overflowed = stream.read(CHUNK_SIZE)

            if overflowed:
                continue

            audio = np.squeeze(audio)

            prediction = cast(Dict[str, float], model.predict(audio))

            score = prediction["hey_jarvis"]

            if score > 0.5:
                print(f"WAKE DETECTED! Score: {score:.2f}")
                time.sleep(1)

except KeyboardInterrupt:
    print("\nWake-word test stopped.")