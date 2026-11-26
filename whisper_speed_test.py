import time
import os
from faster_whisper import WhisperModel

AUDIO = r"D:\Edith\benchmark_audio\english.wav"
MODEL = "small"

if not os.path.exists(AUDIO):
    raise FileNotFoundError(AUDIO)

configs = [
    ("CPU INT8", "cpu", "int8"),
    ("GPU FLOAT16", "cuda", "float16"),
]

for name, device, compute in configs:
    print(f"\n{'='*45}")
    print(f"Testing: {name}", flush=True)

    try:
        start = time.perf_counter()

        model = WhisperModel(
            MODEL,
            device=device,
            compute_type=compute,
            cpu_threads=6,
            num_workers=1,
            local_files_only=True,
        )

        load_time = time.perf_counter() - start
        print(f"Model load: {load_time:.2f}s", flush=True)

        # Warm-up
        segments, _ = model.transcribe(
            AUDIO,
            beam_size=1,
            best_of=1,
            condition_on_previous_text=False,
            vad_filter=False,
        )
        list(segments)

        # Actual measurement
        start = time.perf_counter()

        segments, info = model.transcribe(
            AUDIO,
            beam_size=1,
            best_of=1,
            condition_on_previous_text=False,
            vad_filter=False,
        )

        segments = list(segments)
        elapsed = time.perf_counter() - start

        print(f"Device: {name}")
        print(f"Inference: {elapsed:.3f}s")
        print(f"Audio duration: {info.duration:.2f}s")
        print(f"RTF: {elapsed / info.duration:.3f}")
        print("Transcript:", " ".join(s.text for s in segments))

        del model

    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}", flush=True)

print("\nBenchmark completed.")