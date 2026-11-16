import soundfile as sf

from app.voice_v2.recognition import SpeechToTextEngine

audio, sample_rate = sf.read(
    r"D:\Edith\voice_v2_test_recordings\20261116_213026_543771_natural_pause.wav",
    dtype="float32"
)

stt = SpeechToTextEngine()

try:
    result = stt.transcribe(audio)

    if result:
        print("Transcript:", result.text)
        print("Language:", result.language)
        print("Model:", result.model_size)
        print("Device:", result.device)
        print("Processing time:", result.processing_seconds)

finally:
    stt.close()