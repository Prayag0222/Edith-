import time
from app.voice_v2 import AudioInputService, AudioInputConfig
from app.voice_v2.core.audio_device import list_input_devices


def main():
    print("Available microphone devices:")
    for device in list_input_devices():
        print(f"[{device['index']}] {device['name']} "
              f"(inputs={device['max_input_channels']})")

    service = AudioInputService(AudioInputConfig())
    subscription = service.subscribe()
    blocks = samples = 0
    started = time.monotonic()
    print("\\nSpeak into the microphone for 10 seconds...")
    try:
        while time.monotonic() - started < 10:
            chunk = subscription.get(timeout=0.5)
            if chunk is not None:
                blocks += 1
                samples += chunk.samples.size
        print("\\n--- RESULT ---")
        print("Blocks:", blocks)
        print("Samples:", samples)
        print(f"Captured audio: {samples / 16000:.2f}s")
        print("Stats:", service.get_stats())
        if blocks == 0:
            raise RuntimeError("No audio captured; check microphone permissions/device.")
    finally:
        subscription.close()
        service.stop()
        print("Microphone stopped cleanly.")


if __name__ == "__main__":
    main()
