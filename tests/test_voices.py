from pathlib import Path
from piper import PiperVoice
import sounddevice as sd

VOICES = {
    "English Female": Path(
        r"D:\Edith\models\tts\english\en_US-lessac-medium.onnx"
    ),
    "Hindi Female": Path(
        r"D:\Edith\models\tts\hindi\hi_IN-priyamvada-medium.onnx"
    ),
}

TEST_TEXT = {
    "English Female": (
        "Hello! I am Edith, your personal AI assistant. "
        "How can I help you today?"
    ),
    "Hindi Female": (
        "नमस्ते! मैं एडिथ हूँ, आपकी व्यक्तिगत AI सहायक। "
        "आज मैं आपकी क्या मदद कर सकती हूँ?"
    ),
}


def test_voice(name, model_path):
    print(f"\nLoading {name}...")

    if not model_path.exists():
        print(f"Model not found: {model_path}")
        return

    voice = PiperVoice.load(model_path, use_cuda=False)

    print(f"Speaking: {name}")

    with sd.OutputStream(
        samplerate=voice.config.sample_rate,
        channels=1,
        dtype="float32",
    ) as stream:

        for chunk in voice.synthesize(TEST_TEXT[name]):
            stream.write(chunk.audio_float_array.reshape(-1, 1))

    print(f"{name} test completed.")


for name, path in VOICES.items():
    test_voice(name, path)

print("\nAll voice tests completed.")