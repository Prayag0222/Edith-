import time
import wave
import numpy as np
import sounddevice as sd

from pathlib import Path
from datetime import datetime

from app.voice_v2.recognition.stt_engine import SpeechToTextEngine


# ==========================================
# CONFIGURATION
# ==========================================

SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 320
RECORD_SECONDS = 20

OUTPUT_DIR = Path("voice_v2_test_recordings")
OUTPUT_DIR.mkdir(exist_ok=True)


# ==========================================
# MICROPHONE CAPTURE
# ==========================================

def record_microphone():

    audio_blocks = []
    callback_errors = []

    def callback(indata, frames, time_info, status):

        if status:
            callback_errors.append(str(status))

        audio_blocks.append(indata.copy())

    print("\n===================================")
    print("       EDITH REAL MIC TEST")
    print("===================================")

    print("\nDefault microphone:")
    print(sd.query_devices(kind="input"))

    print(f"\nSample rate: {SAMPLE_RATE}")
    print(f"Duration: {RECORD_SECONDS} seconds")

    input("\nPress ENTER when you are ready...")

    print("\nRecording starts in:")

    for i in range(3, 0, -1):
        print(i)
        time.sleep(1)

    print("\n[SPEAK NOW] Recording...")

    start_time = time.perf_counter()

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        blocksize=BLOCK_SIZE,
        callback=callback
    ):

        time.sleep(RECORD_SECONDS)

    elapsed = time.perf_counter() - start_time

    if not audio_blocks:
        raise RuntimeError("No microphone audio captured.")

    audio = np.concatenate(audio_blocks, axis=0).reshape(-1)

    print("\nRecording completed.")

    print("Captured samples:", len(audio))
    print("Actual duration:", round(len(audio) / SAMPLE_RATE, 2), "seconds")
    print("Capture time:", round(elapsed, 2), "seconds")
    print("Peak amplitude:", round(float(np.max(np.abs(audio))), 4))
    print("RMS amplitude:", round(float(np.sqrt(np.mean(audio ** 2))), 4))
    print("Callback warnings:", callback_errors)

    return audio


# ==========================================
# SAVE WAV
# ==========================================

def save_recording(audio):

    filename = datetime.now().strftime(
        "mic_test_%Y%m%d_%H%M%S.wav"
    )

    filepath = OUTPUT_DIR / filename

    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767).astype(np.int16)

    with wave.open(str(filepath), "wb") as wav:

        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())

    print("\nSaved recording:", filepath)

    return filepath


# ==========================================
# WHISPER TRANSCRIPTION
# ==========================================

def transcribe_audio(audio):

    print("\n===================================")
    print("       WHISPER TRANSCRIPTION")
    print("===================================")

    stt = SpeechToTextEngine()

    try:

        started = time.perf_counter()

        result = stt.transcribe(audio)

        total_time = time.perf_counter() - started

        if result is None:
            print("\nNo speech recognized.")
            return

        print("\nTranscript:", result.text)
        print("Language:", result.language)
        print("Model:", result.model_size)
        print("Device:", result.device)
        print("Compute type:", result.compute_type)

        print(
            "Whisper processing time:",
            round(result.processing_seconds, 3),
            "seconds"
        )

        print(
            "Total transcription time:",
            round(total_time, 3),
            "seconds"
        )

        print("Audio duration:", result.audio_duration_seconds)
        print("Classification:", result.task_type)

        print("\nModel manager status:")
        print(stt.model_manager.status())

    finally:
        stt.close()


# ==========================================
# MAIN
# ==========================================

def main():

    audio = record_microphone()

    save_recording(audio)

    transcribe_audio(audio)

    print("\n===================================")
    print("       MIC TEST COMPLETED")
    print("===================================")


if __name__ == "__main__":
    main()