from app.voice_v2.recognition.stt_engine import SpeechToTextEngine
import numpy as np

stt = SpeechToTextEngine()

try:
    print("Testing CUDA Whisper inference...")

    # 5 seconds of silence, used only to test model execution.
    audio = np.zeros(16000 * 5, dtype=np.float32)

    result = stt.transcribe(audio)

    print("Result:", result)
    print("Model status:", stt.model_manager.status())

finally:
    stt.close()