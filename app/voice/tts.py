import os
import subprocess
import sys
import tempfile
import winsound


class TextToSpeech:
    def __init__(self, voice: str = "en_US-lessac-medium"):
        self.voice = voice

    def speak(self, text: str):
        if not text or not text.strip():
            return

        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        ) as temp_file:
            output_path = temp_file.name

        try:
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

            winsound.PlaySound(
                output_path,
                winsound.SND_FILENAME,
            )

        finally:
            if os.path.exists(output_path):
                os.remove(output_path)


if __name__ == "__main__":
    tts = TextToSpeech()
    tts.speak("Hello Prayag. I am EDITH, your personal AI assistant.")