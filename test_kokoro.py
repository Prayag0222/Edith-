import sounddevice as sd
from kokoro_onnx import Kokoro

MODEL = r"D:\Edith\models\tts\kokoro\kokoro-v1.0.onnx"
VOICES = r"D:\Edith\models\tts\kokoro\voices-v1.0.bin"

print("Loading Kokoro...")

kokoro = Kokoro(MODEL, VOICES)

text = (
    "Hello! I am EDITH, your personal artificial intelligence assistant. "
    "I am designed to understand your instructions clearly and help you "
    "with your daily activities. I can analyze complex information, "
    "manage projects, and provide accurate answers. "
    "How may I assist you today?"
)

for voice in ["af_heart", "af_bella", "af_nicole", "bf_emma"]:

    print(f"\nTesting: {voice}")

    audio, sample_rate = kokoro.create(
        text,
        voice=voice,
        speed=0.95,
        lang="en-us" if voice.startswith("af_") else "en-gb"
    )

    sd.play(audio, sample_rate)
    sd.wait()

print("\nAll voice tests completed.")