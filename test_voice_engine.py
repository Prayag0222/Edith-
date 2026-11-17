import time
from app.voice_v2.engine import VoiceEngine


TESTS = [
    {
        "name": "SHORT COMMAND",
        "instruction": 'Say clearly: "Exit."',
        "expected": "exit",
    },
    {
        "name": "NATURAL PAUSE",
        "instruction": (
            "Say: 'Explain what EDITH is.' "
            "Pause for 2 seconds. "
            "Then say: 'Also explain what we are testing today.'"
        ),
        "expected": "both sentences should appear in one transcript",
    },
    {
        "name": "REPEATED WAKE ACTIVATION",
        "instruction": 'Say: "What is 25 multiplied by 4?"',
        "expected": "What is 25 multiplied by 4?",
    },
]


def main():
    engine = VoiceEngine()

    try:
        print("\n========== EDITH VOICE STRESS TEST ==========")

        engine.start()

        for index, test in enumerate(TESTS, start=1):
            print(f"\n\n========== TEST {index}: {test['name']} ==========")
            print("Instruction:", test["instruction"])

            print("\n[READY] Say: Hey EDITH")

            wake_started = time.perf_counter()
            detected = engine.wait_for_wake_word()
            wake_time = time.perf_counter() - wake_started

            if not detected:
                print("[FAIL] Wake word not detected.")
                continue

            print(f"[PASS] Wake detected in {wake_time:.2f}s")
            print("[LISTEN] Speak now...")

            listen_started = time.perf_counter()
            result = engine.listen()
            listen_time = time.perf_counter() - listen_started

            print("\n---------- RESULT ----------")

            if result:
                print("Transcript:", result.get("text"))
                print("Audio duration:", result.get("audio_duration_seconds"))
                print("STT device:", result.get("device"))
                print("STT latency:", result.get("processing_seconds"))
                print(f"Total listen time: {listen_time:.2f}s")
                print("[PASS] Transcription received.")
            else:
                print("[FAIL] No transcription received.")

            print("----------------------------")

        print("\n========== FINAL ENGINE STATS ==========")
        print(engine.get_stats())

    except KeyboardInterrupt:
        print("\n[STOP] Test interrupted.")

    except Exception as error:
        print(f"\n[ERROR] {type(error).__name__}: {error}")
        raise

    finally:
        engine.close()
        print("\n[ENGINE] Closed cleanly.")


if __name__ == "__main__":
    main()