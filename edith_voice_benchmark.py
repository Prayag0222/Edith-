#!/usr/bin/env python3
"""
EDITH Voice Hardware Benchmark
==============================

Standalone, read-only benchmark for deciding which voice workloads should use
the CPU and which (if any) should use the RTX GPU.

It does NOT import EDITH modules, edit project files, change Ollama settings,
download models, or open the microphone automatically.

Recommended:
    1. Close EDITH so its microphone/model instances do not interfere.
    2. Keep Ollama running with llama3.2:3b loaded if you want to measure the
       real GPU contention state.
    3. Put representative WAV recordings in a folder, or pass --audio FILE.
       Include English, Hindi (Devanagari), and Hinglish recordings.
    4. Run this script from the EDITH project root using its existing venv.

Examples (PowerShell):
    python edith_voice_benchmark.py --audio-dir .\\benchmark_audio
    python edith_voice_benchmark.py --audio .\\benchmark_audio\\hindi.wav
    python edith_voice_benchmark.py --audio-dir .\\benchmark_audio --models small,base

Optional model paths:
    --wakeword-model .\\models\\wakeword\\hey_edith.onnx
    --piper-en D:\\Edith\\en_US-lessac-medium.onnx
    --piper-hi D:\\Edith\\hi_IN-rohan-medium.onnx

Results are written to edith_benchmark_YYYYMMDD_HHMMSS.json and printed.
The script only loads locally available Faster-Whisper models
(local_files_only=True); it will not download missing models.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as _dt
import importlib.util
import json
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
import traceback
import wave
from pathlib import Path
from typing import Any

import numpy as np


def now() -> float:
    return time.perf_counter()


def timed_call(fn):
    started = now()
    value = fn()
    return value, now() - started


def run_command(args: list[str], timeout: float = 8.0) -> dict[str, Any]:
    try:
        p = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False
        )
        return {
            "available": True,
            "returncode": p.returncode,
            "stdout": p.stdout.strip(),
            "stderr": p.stderr.strip(),
        }
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


def module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * p)))
    return round(ordered[index], 4)


def summarize_times(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"runs": 0}
    return {
        "runs": len(values),
        "mean_s": round(statistics.mean(values), 4),
        "median_s": round(statistics.median(values), 4),
        "min_s": round(min(values), 4),
        "p90_s": percentile(values, 0.90),
        "max_s": round(max(values), 4),
    }


def collect_system_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "timestamp": _dt.datetime.now().astimezone().isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "modules": {
            name: module_available(name)
            for name in (
                "torch", "faster_whisper", "ctranslate2", "onnxruntime",
                "silero_vad", "piper", "sounddevice", "psutil"
            )
        },
    }

    try:
        import psutil
        info["cpu"] = {
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "ram_total_gb": round(psutil.virtual_memory().total / 1024**3, 2),
            "ram_available_gb": round(psutil.virtual_memory().available / 1024**3, 2),
            "cpu_percent_initial": psutil.cpu_percent(interval=0.5),
        }
    except Exception as exc:
        info["cpu_probe_error"] = str(exc)

    info["nvidia_smi"] = run_command([
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
        "--format=csv,noheader,nounits",
    ])
    info["nvidia_processes"] = run_command([
        "nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
        "--format=csv,noheader,nounits",
    ])

    # Ollama's process list is read-only. No model is started or unloaded.
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=2) as r:
            info["ollama_running_models"] = json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        info["ollama_running_models"] = {
            "available": False, "error": f"{type(exc).__name__}: {exc}"
        }

    try:
        import torch
        info["torch"] = {
            "version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda,
            "device_count": torch.cuda.device_count(),
        }
        if torch.cuda.is_available():
            info["torch"]["devices"] = [
                {
                    "index": i,
                    "name": torch.cuda.get_device_name(i),
                    "total_memory_gb": round(
                        torch.cuda.get_device_properties(i).total_memory / 1024**3, 2
                    ),
                    "allocated_gb": round(torch.cuda.memory_allocated(i) / 1024**3, 3),
                    "reserved_gb": round(torch.cuda.memory_reserved(i) / 1024**3, 3),
                }
                for i in range(torch.cuda.device_count())
            ]
    except Exception as exc:
        info["torch_probe_error"] = f"{type(exc).__name__}: {exc}"

    try:
        import ctranslate2
        info["ctranslate2"] = {
            "version": getattr(ctranslate2, "__version__", "unknown"),
            "cuda_device_count": ctranslate2.get_cuda_device_count(),
            "supported_compute_types_cpu": ctranslate2.get_supported_compute_types("cpu"),
        }
        if info["ctranslate2"]["cuda_device_count"]:
            info["ctranslate2"]["supported_compute_types_cuda"] = (
                ctranslate2.get_supported_compute_types("cuda")
            )
    except Exception as exc:
        info["ctranslate2_probe_error"] = f"{type(exc).__name__}: {exc}"

    return info


def load_audio_files(paths: list[Path]) -> list[dict[str, Any]]:
    """Read WAV files without requiring librosa or opening an audio device."""
    loaded = []
    for path in paths:
        try:
            with wave.open(str(path), "rb") as wf:
                channels = wf.getnchannels()
                width = wf.getsampwidth()
                rate = wf.getframerate()
                frames = wf.getnframes()
                raw = wf.readframes(frames)

            if width == 1:
                data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128
            elif width == 2:
                data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768
            elif width == 3:
                b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
                ints = (b[:, 0].astype(np.int32)
                        | (b[:, 1].astype(np.int32) << 8)
                        | (b[:, 2].astype(np.int32) << 16))
                ints = np.where(ints & 0x800000, ints - 0x1000000, ints)
                data = ints.astype(np.float32) / 8388608
            elif width == 4:
                data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648
            else:
                raise ValueError(f"Unsupported WAV sample width: {width}")

            if channels > 1:
                data = data.reshape(-1, channels).mean(axis=1)
            if rate != 16000:
                # scipy is used only if available; otherwise the audio is skipped.
                from scipy.signal import resample_poly
                from math import gcd
                g = gcd(rate, 16000)
                data = resample_poly(data, 16000 // g, rate // g).astype(np.float32)

            loaded.append({
                "path": str(path),
                "name": path.name,
                "audio": np.ascontiguousarray(data, dtype=np.float32),
                "sample_rate": 16000,
                "duration_s": round(len(data) / 16000, 3),
            })
        except Exception as exc:
            print(f"[AUDIO SKIP] {path}: {type(exc).__name__}: {exc}")
    return loaded


def benchmark_stt(audio_items: list[dict[str, Any]], model_sizes: list[str],
                  cpu_threads: list[int], repeats: int, test_cuda: bool) -> dict[str, Any]:
    result: dict[str, Any] = {"runs": [], "note": ""}
    if not module_available("faster_whisper"):
        result["note"] = "faster-whisper is not installed in this Python environment."
        return result
    if not audio_items:
        result["note"] = "No WAV samples supplied; STT inference and accuracy cannot be benchmarked."
        return result

    from faster_whisper import WhisperModel

    # One representative sample per language can be named en_*, hi_*, hinglish_*.
    # The script does not infer language labels from speech recognition output.
    for size in model_sizes:
        for device in (["cpu", "cuda"] if test_cuda else ["cpu"]):
            if device == "cuda":
                try:
                    import ctranslate2
                    if ctranslate2.get_cuda_device_count() < 1:
                        result["runs"].append({
                            "model": size, "device": "cuda", "skipped": "CUDA unavailable"
                        })
                        continue
                except Exception as exc:
                    result["runs"].append({
                        "model": size, "device": "cuda", "skipped": str(exc)
                    })
                    continue

            thread_options = cpu_threads if device == "cpu" else [0]
            for threads in thread_options:
                run = {
                    "model": size, "device": device,
                    "compute_type": "int8" if device == "cpu" else "float16",
                    "cpu_threads": threads if device == "cpu" else None,
                    "samples": [],
                }
                try:
                    kwargs = {
                        "device": device,
                        "compute_type": run["compute_type"],
                        "local_files_only": True,
                    }
                    if device == "cpu":
                        kwargs["cpu_threads"] = threads
                    load_started = now()
                    model = WhisperModel(size, **kwargs)
                    run["model_load_s"] = round(now() - load_started, 4)

                    for item in audio_items:
                        audio = item["audio"]
                        sample = {
                            "file": item["name"],
                            "duration_s": item["duration_s"],
                            "warm_runs_s": [],
                            "recognized_text": None,
                            "detected_language": None,
                            "language_probability": None,
                            "errors": [],
                        }
                        # First inference is reported separately as warm-up/cold-run.
                        for iteration in range(repeats + 1):
                            started = now()
                            try:
                                segments, info = model.transcribe(
                                    audio,
                                    beam_size=1,
                                    best_of=1,
                                    language=None,
                                    task="transcribe",
                                    vad_filter=False,
                                    condition_on_previous_text=False,
                                )
                                # Generator consumption is part of actual STT latency.
                                text_parts = [s.text.strip() for s in segments if s.text.strip()]
                                elapsed = now() - started
                                text = " ".join(text_parts)
                                if iteration == 0:
                                    sample["first_run_s"] = round(elapsed, 4)
                                    sample["recognized_text"] = text
                                    sample["detected_language"] = getattr(info, "language", None)
                                    sample["language_probability"] = getattr(
                                        info, "language_probability", None
                                    )
                                else:
                                    sample["warm_runs_s"].append(round(elapsed, 4))
                            except Exception as exc:
                                sample["errors"].append(
                                    f"{type(exc).__name__}: {exc}"
                                )
                                break
                        sample["warm_summary"] = summarize_times(sample["warm_runs_s"])
                        sample["rtf_warm_median"] = (
                            round(sample["warm_summary"]["median_s"] / item["duration_s"], 3)
                            if sample["warm_summary"].get("median_s") and item["duration_s"]
                            else None
                        )
                        run["samples"].append(sample)
                    del model
                except Exception as exc:
                    run["error"] = f"{type(exc).__name__}: {exc}"
                    run["traceback"] = traceback.format_exc(limit=3)
                result["runs"].append(run)
    result["note"] = (
        "STT accuracy requires manually checking recognized_text against the known transcript. "
        "Use the same audio files for every configuration."
    )
    return result


def benchmark_silero(audio_items: list[dict[str, Any]], repeats: int = 3) -> dict[str, Any]:
    out: dict[str, Any] = {"available": False}
    if repeats < 1:
        out["error"] = "Repeats must be at least 1."
        return out
    if not module_available("silero_vad"):
        out["note"] = "silero-vad package not installed."
        return out
    try:
        from silero_vad import load_silero_vad
        import torch

        load_started = now()
        model = load_silero_vad(onnx=True)
        out["model_load_s"] = round(now() - load_started, 4)
        out["runs"] = []

        from silero_vad import get_speech_timestamps

        for item in audio_items:
            frame_count = len(item["audio"])
            frame_count -= frame_count % 512
            audio = torch.from_numpy(item["audio"][:frame_count].copy())
            times: list[float] = []
            speech_scores: list[float] = []

            for rep in range(repeats + 1):
                started = now()
                segments = get_speech_timestamps(
                    audio,
                    model,
                    sampling_rate=16000,
                    return_seconds=False,
                )
                elapsed = now() - started
                speech_scores.extend(
                    float(score)
                    for segment in segments
                    if isinstance(segment, dict)
                    for score in (segment.get("speech_prob", segment.get("score")),)
                    if isinstance(score, (int, float))
                )

                if rep == 0:
                    out.setdefault("first_run_s", {})[item["name"]] = round(elapsed, 4)
                else:
                    times.append(elapsed)

            out["runs"].append({
                "file": item["name"],
                "duration_s": item["duration_s"],
                "frames": frame_count,
                "warm_summary": summarize_times(times),
                "real_time_factor": (
                    round(statistics.median(times) / item["duration_s"], 4)
                    if times and item["duration_s"] else None
                ),
                "mean_speech_probability": (
                    round(statistics.mean(speech_scores), 4) if speech_scores else None
                ),
            })
        out["available"] = True
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def benchmark_piper(model_paths: dict[str, Path], repeats: int = 3) -> dict[str, Any]:
    out: dict[str, Any] = {"runs": []}
    if not module_available("piper"):
        out["note"] = "piper-tts is not installed."
        return out
    from piper import PiperVoice

    test_text = {
        "english": "Hello. EDITH is ready. How can I help you today?",
        "hindi": "नमस्ते। एडिथ तैयार है। आज मैं आपकी क्या मदद कर सकती हूँ?",
    }
    for language, path in model_paths.items():
        if path is None:
            continue
        entry: dict[str, Any] = {"language": language, "model_path": str(path)}
        if not path.is_file():
            entry["error"] = "Model file not found."
            out["runs"].append(entry)
            continue
        try:
            load_started = now()
            voice = PiperVoice.load(model_path=str(path), use_cuda=False)
            entry["model_load_s"] = round(now() - load_started, 4)
            entry["sample_rate"] = voice.config.sample_rate
            entry["runs"] = []
            text = test_text["english" if language == "english" else "hindi"]
            first_audio_times = []
            total_times = []
            audio_durations = []
            for _ in range(repeats + 1):
                started = now()
                first_chunk_time = None
                total_audio = 0
                for chunk in voice.synthesize(text):
                    if first_chunk_time is None:
                        first_chunk_time = now() - started
                    audio = chunk.audio_int16_array
                    total_audio += len(audio)
                elapsed = now() - started
                if first_chunk_time is not None:
                    audio_durations.append(total_audio / voice.config.sample_rate)
                    if len(total_times) == 0:
                        entry["first_run_first_audio_s"] = round(first_chunk_time, 4)
                    else:
                        first_audio_times.append(first_chunk_time)
                total_times.append(elapsed)
            entry["warm_total_summary"] = summarize_times(total_times[1:])
            entry["warm_first_audio_summary"] = summarize_times(first_audio_times)
            entry["generated_audio_duration_s"] = (
                round(statistics.mean(audio_durations), 3) if audio_durations else None
            )
            entry["note"] = "CPU synthesis only; benchmark does not play audio."
            del voice
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
        out["runs"].append(entry)
    return out


def benchmark_wakeword_model(path: Path | None) -> dict[str, Any]:
    """Check the finalized ONNX model's load/runtime availability, not detection quality."""
    out: dict[str, Any] = {"available": False}
    if path is None:
        out["note"] = "Wake-word model path not supplied; no model file was changed."
        return out
    out["model_path"] = str(path)
    if not path.is_file():
        out["note"] = "Wake-word model not found at supplied path."
        return out
    if not module_available("onnxruntime"):
        out["note"] = "onnxruntime not installed."
        return out
    try:
        import onnxruntime as ort
        started = now()
        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        out["cpu_session_load_s"] = round(now() - started, 4)
        out["inputs"] = [
            {"name": x.name, "shape": x.shape, "type": x.type}
            for x in session.get_inputs()
        ]
        out["outputs"] = [
            {"name": x.name, "shape": x.shape, "type": x.type}
            for x in session.get_outputs()
        ]
        out["cpu_provider"] = session.get_providers()
        out["available"] = True
        out["note"] = (
            "Model load/provider check only. Actual wake-word inference needs the "
            "existing adapter's correctly shaped audio/features; this script deliberately "
            "does not invoke private legacy detector methods or retrain/change the model."
        )
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def benchmark_cpu_contention(audio_items, model_sizes, cpu_threads, repeats,
                             piper_paths, run_contention):
    """Measure whether CPU workloads interfere when executed concurrently."""
    out: dict[str, object] = {"performed": False}
    if not run_contention:
        out["note"] = "Pass --contention to run concurrent CPU stress probes."
        return out
    if not audio_items:
        out["note"] = "Contention test requires at least one WAV file."
        return out
    if not module_available("faster_whisper"):
        out["note"] = "faster-whisper unavailable."
        return out

    # This intentionally tests CPU STT alongside a CPU VAD pass. Piper is included
    # only when a local voice path is supplied. It does not run EDITH or open audio I/O.
    try:
        from faster_whisper import WhisperModel
        stt = WhisperModel(
            model_sizes[0], device="cpu", compute_type="int8",
            cpu_threads=cpu_threads[0], local_files_only=True
        )
        item = max(audio_items, key=lambda x: x["duration_s"])
        vad_enabled = module_available("silero_vad")
        piper_path = piper_paths.get("english") or piper_paths.get("hindi")
        piper_voice = None
        if piper_path and piper_path.is_file() and module_available("piper"):
            from piper import PiperVoice
            piper_voice = PiperVoice.load(model_path=str(piper_path), use_cuda=False)

        def stt_job():
            started = now()
            segs, _ = stt.transcribe(
                item["audio"], beam_size=1, best_of=1, vad_filter=False,
                condition_on_previous_text=False
            )
            list(segs)
            return now() - started

        def vad_job():
            if not vad_enabled:
                return None
            from silero_vad import get_speech_timestamps, load_silero_vad
            import torch
            model = load_silero_vad(onnx=True)
            started = now()
            get_speech_timestamps(
                torch.from_numpy(item["audio"].copy()),
                model,
                sampling_rate=16000,
            )
            return now() - started

        def piper_job():
            if piper_voice is None:
                return None
            started = now()
            list(piper_voice.synthesize(
                "EDITH is ready. नमस्ते, मैं आपकी सहायता कर सकती हूँ।"
            ))
            return now() - started

        # Baselines
        baseline = {
            "stt_s": stt_job(),
            "vad_s": vad_job(),
            "piper_s": piper_job(),
        }

        # Concurrent workload, fresh task instances share no microphone/audio device.
        started = now()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(stt_job), pool.submit(vad_job), pool.submit(piper_job)]
            concurrent_results = [f.result() for f in futures]
        out = {
            "performed": True,
            "audio_file": item["name"],
            "cpu_threads_for_stt": cpu_threads[0],
            "baseline": baseline,
            "concurrent_elapsed_s": round(now() - started, 4),
            "concurrent_task_elapsed_s": [
                round(x, 4) if x is not None else None for x in concurrent_results
            ],
            "note": (
                "This is a synthetic concurrency probe, not an exact EDITH turn. "
                "Compare STT time here with isolated STT time to see CPU contention."
            ),
        }
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def main():
    parser = argparse.ArgumentParser(description="EDITH CPU/GPU voice benchmark")
    parser.add_argument("--audio", action="append", default=[],
                        help="WAV file (16 kHz mono recommended); can be repeated.")
    parser.add_argument("--audio-dir", type=Path,
                        help="Folder containing representative WAV recordings.")
    parser.add_argument("--models", default="small,base",
                        help="Comma-separated locally cached Faster-Whisper models.")
    parser.add_argument("--cpu-threads", default="4,6,8,10",
                        help="Comma-separated CPU thread counts.")
    parser.add_argument("--repeats", type=int, default=3,
                        help="Warm inference/synthesis repetitions.")
    parser.add_argument("--no-cuda", action="store_true",
                        help="Skip CUDA STT tests.")
    parser.add_argument("--wakeword-model", type=Path, default=None)
    parser.add_argument("--piper-en", type=Path, default=None)
    parser.add_argument("--piper-hi", type=Path, default=None)
    parser.add_argument("--contention", action="store_true",
                        help="Run concurrent CPU STT + VAD + Piper probe.")
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    args = parser.parse_args()

    if args.repeats < 1:
        parser.error("--repeats must be >= 1")

    print("\n========== EDITH VOICE HARDWARE BENCHMARK ==========")
    print("Read-only mode: no EDITH source files, model files, or settings are modified.")
    print("Close EDITH before benchmarking to avoid competing microphone/model workloads.\n")

    report: dict[str, Any] = {
        "benchmark": "EDITH Voice Hardware Benchmark",
        "started_local": _dt.datetime.now().astimezone().isoformat(),
        "system": {},
        "audio_samples": [],
        "stt": {},
        "silero_vad_cpu": {},
        "piper_cpu": {},
        "wakeword_cpu": {},
        "cpu_contention": {},
    }

    print("[1/6] Collecting CPU, RAM, CUDA, VRAM and Ollama status...")
    report["system"] = collect_system_info()
    print(json.dumps({
        "cpu_count": report["system"].get("logical_cpu_count"),
        "torch": report["system"].get("torch"),
        "ctranslate2": report["system"].get("ctranslate2"),
        "ollama": report["system"].get("ollama_running_models"),
        "nvidia_smi": report["system"].get("nvidia_smi"),
    }, indent=2, ensure_ascii=False, default=lambda value: sorted(value) if isinstance(value, set) else str(value)))

    audio_paths = [Path(p) for p in args.audio]
    if args.audio_dir:
        audio_paths.extend(sorted(args.audio_dir.glob("*.wav")))
    # Deduplicate while preserving order.
    unique_paths = list(dict.fromkeys(p.resolve() for p in audio_paths))
    print(f"\n[2/6] Loading {len(unique_paths)} supplied WAV sample(s)...")
    audio_items = load_audio_files(unique_paths)
    report["audio_samples"] = [
        {k: v for k, v in item.items() if k != "audio"}
        for item in audio_items
    ]
    for item in audio_items:
        print(f"  {item['name']}: {item['duration_s']}s @ 16 kHz mono")
    if not audio_items:
        print("  No samples: STT accuracy and latency cannot be measured yet.")

    models = [x.strip() for x in args.models.split(",") if x.strip()]
    threads = [int(x.strip()) for x in args.cpu_threads.split(",") if x.strip()]
    print("\n[3/6] Benchmarking Faster-Whisper CPU int8 and optional CUDA float16...")
    report["stt"] = benchmark_stt(
        audio_items, models, threads, args.repeats, not args.no_cuda
    )

    print("\n[4/6] Benchmarking Silero VAD on CPU...")
    report["silero_vad_cpu"] = benchmark_silero(audio_items, args.repeats)

    print("\n[5/6] Benchmarking local Piper voices on CPU...")
    report["piper_cpu"] = benchmark_piper(
        {"english": args.piper_en, "hindi": args.piper_hi}, args.repeats
    )

    print("\n[6/6] Checking wake-word CPU runtime and optional concurrent CPU load...")
    report["wakeword_cpu"] = benchmark_wakeword_model(args.wakeword_model)
    report["cpu_contention"] = benchmark_cpu_contention(
        audio_items, models, threads, args.repeats,
        {"english": args.piper_en, "hindi": args.piper_hi},
        args.contention,
    )

    report["finished_local"] = _dt.datetime.now().astimezone().isoformat()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = args.output_dir / f"edith_benchmark_{stamp}.json"
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=lambda value: sorted(value) if isinstance(value, set) else str(value)), encoding="utf-8")

    print("\n================ BENCHMARK SUMMARY ================")
    print("STT results:")
    for run in report["stt"].get("runs", []):
        print(
            f"  {run.get('model')} | {run.get('device')} | "
            f"threads={run.get('cpu_threads')} | load={run.get('model_load_s')}s"
        )
        for sample in run.get("samples", []):
            print(
                f"    {sample['file']}: first={sample.get('first_run_s')}s, "
                f"warm={sample.get('warm_summary')}, "
                f"language={sample.get('detected_language')}, "
                f"RTF={sample.get('rtf_warm_median')}"
            )
    print("\nSilero VAD CPU:")
    print(json.dumps(report["silero_vad_cpu"], indent=2, ensure_ascii=False, default=lambda value: sorted(value) if isinstance(value, set) else str(value)))
    print("\nPiper CPU:")
    print(json.dumps(report["piper_cpu"], indent=2, ensure_ascii=False, default=lambda value: sorted(value) if isinstance(value, set) else str(value)))
    print("\nWake-word runtime check:")
    print(json.dumps(report["wakeword_cpu"], indent=2, ensure_ascii=False, default=lambda value: sorted(value) if isinstance(value, set) else str(value)))
    print("\nCPU contention:")
    print(json.dumps(report["cpu_contention"], indent=2, ensure_ascii=False, default=lambda value: sorted(value) if isinstance(value, set) else str(value)))
    print(f"\nFull JSON report: {output_path.resolve()}")
    print("\nIMPORTANT: This script does not measure Ollama token generation speed or")
    print("wake-word detection accuracy. It records Ollama/VRAM state and checks the")
    print("wake-word ONNX CPU provider. Keep your existing 20/20 + 0/30 wake-word")
    print("validation as the accuracy baseline.")


if __name__ == "__main__":
    main()
