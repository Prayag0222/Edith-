from app.voice.vad import VoiceActivityDetector


def main():

    print()
    print("=" * 50)
    print("EDITH VOICE ACTIVITY DETECTOR TEST")
    print("=" * 50)
    print()

    vad = VoiceActivityDetector(
        sample_rate=16000,
        aggressiveness=2,
    )

    print("VAD initialized successfully.")
    print(f"Sample rate: {vad.sample_rate}")
    print(f"Aggressiveness: {vad.aggressiveness}")
    print()
    print("WebRTC VAD is ready.")
    print()


if __name__ == "__main__":
    main()
    