import os
import subprocess
import sys
import tempfile
import winsound
from time import perf_counter

from matplotlib.pylab import rint


class TextToSpeech:
    def __init__(self, voice: str = "en_US-lessac-medium"):
        self.voice = voice

    def speak(self, text: str):
        if not text or not text.strip():
            return
        total_start = perf_counter()

        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        ) as temp_file:
            output_path = temp_file.name

        try:
            generation_start = perf_counter()

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "piper",
                    "-m",
                    self.voice,
                    "--output_file",
                    output_path,
                    "--",
                    text,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            
            print(f"[TIME] TTS generation: {perf_counter() - generation_start:.2f}s")

            playback_start = perf_counter()
            winsound.PlaySound(
                output_path,
                winsound.SND_FILENAME,
            )

            print(f"[TIME] TTS playback: {perf_counter() - playback_start:.2f}s")
            print(f"[TIME] Total TTS: {perf_counter() - total_start:.2f}s")

        finally:
            if os.path.exists(output_path):
                os.remove(output_path)


if __name__ == "__main__":
    tts = TextToSpeech()
    tts.speak("Hello Prayag. I am EDITH, your personal AI assistant.")