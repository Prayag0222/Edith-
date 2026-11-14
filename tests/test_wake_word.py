
import time

from matplotlib.pylab import cast
import numpy as np
import sounddevice as sd
from openwakeword.model import Dict, Model


SAMPLE_RATE = 16000
CHUNK_SIZE = 1280

WAKE_WORD = "hey_jarvis"
THRESHOLD = 0.3

REPORT_INTERVAL = 0.25


def main():
    print("=" * 50)
    print("EDITH — WAKE-WORD DIAGNOSTICS")
    print("=" * 50)

    print(f"Wake word: {WAKE_WORD}")
    print(f"Activation threshold: {THRESHOLD}")
    print(f"Sample rate: {SAMPLE_RATE} Hz")
    print("\nLoading wake-word model...")

    model = Model(
        wakeword_models=[WAKE_WORD],
        inference_framework="onnx",
    )

    print("Model loaded.")
    print("Listening for diagnostic purposes.")
    print("Say 'Hey Jarvis' naturally.")
    print("Press Ctrl+C to stop.\n")

    last_report = 0.0
    last_score = 0.0
    previous_state = False

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
                    print("[AUDIO WARNING] Input buffer overflow")
                    continue

                audio = np.squeeze(audio)

                prediction = cast(Dict[str, float], model.predict(audio))
                score = float(prediction[WAKE_WORD])

                now = time.monotonic()
                detected = score >= THRESHOLD

                if now - last_report >= REPORT_INTERVAL:
                    print(
                        f"\rScore: {score:.3f} | "
                        f"Threshold: {THRESHOLD:.2f} | "
                        f"Above threshold: {detected}",
                        end="",
                        flush=True,
                    )
                    last_report = now
                    last_score = score

                if detected and not previous_state:
                    print(
                        f"\n[ACTIVATION] Score: {score:.3f}"
                    )

                previous_state = detected

    except KeyboardInterrupt:
        print("\n\nDiagnostic stopped.")

    finally:
        print("Wake-word diagnostic finished.")


if __name__ == "__main__":
    main()

