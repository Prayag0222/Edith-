from __future__ import annotations

import argparse
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np

from app.voice_v2.core.audio_input import AudioInputConfig, AudioInputService
from app.voice_v2.detection.endpoint_detector import (
    AdaptiveEndpointDetector,
    EndpointConfig,
)
from app.voice_v2.detection.silero_vad import SileroVAD, SileroVADConfig


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = PROJECT_ROOT / "voice_v2_test_recordings"


def save_wav(audio: np.ndarray, sample_rate: int, path: Path) -> None:
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


def run_stage(
    name: str,
    duration_seconds: float,
    service: AudioInputService,
    subscription,
    detector: AdaptiveEndpointDetector,
    sample_rate: int,
) -> dict:
    # Discard audio accumulated while the user was reading the prompt.
    while subscription.get(timeout=0) is not None:
        pass

    print(f"\n--- {name} | {duration_seconds:.0f} seconds ---")
    print("Starting in 2 seconds...")
    time.sleep(2)

    stage_started = time.monotonic()
    last_active = detector.is_speaking
    starts = 0
    segments = []
    blocks = 0
    stage_deadline = stage_started + duration_seconds

    while time.monotonic() < stage_deadline:
        remaining = max(0.01, min(0.1, stage_deadline - time.monotonic()))
        chunk = subscription.get(timeout=remaining)
        if chunk is None:
            continue

        blocks += 1
        was_active = detector.is_speaking
        segment = detector.process(chunk.samples)
        is_active = detector.is_speaking

        if not was_active and is_active:
            starts += 1
            print(
                f"[SPEECH START] stage_elapsed={time.monotonic() - stage_started:.3f}s "
                f"| audio_seq={chunk.sequence}"
            )

        if was_active and not is_active and segment is not None:
            segments.append(segment)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{timestamp}_{name.lower().replace(' ', '_')}.wav"
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            path = OUTPUT_DIR / filename
            save_wav(segment.audio, sample_rate, path)
            rms = float(np.sqrt(np.mean(np.square(segment.audio)))) if segment.audio.size else 0.0
            peak = float(np.max(np.abs(segment.audio))) if segment.audio.size else 0.0
            print(
                f"[SEGMENT #{len(segments)}] ended_by={segment.ended_by} "
                f"| duration={segment.duration_seconds:.2f}s "
                f"| speech_duration={segment.speech_duration_seconds:.2f}s "
                f"| rms={rms:.5f} | peak={peak:.5f}"
            )
            print(f"              saved={path}")

        last_active = is_active

    # Do not force-finalize an active utterance at a stage boundary. That would
    # distort the detector's real endpoint behavior.
    print(
        f"[STAGE RESULT] blocks={blocks}, speech_starts={starts}, "
        f"finalized_segments={len(segments)}, still_active={detector.is_speaking}"
    )
    return {
        "name": name,
        "blocks": blocks,
        "starts": starts,
        "segments": len(segments),
        "active_at_end": detector.is_speaking,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manual live-microphone validation for EDITH Voice Engine v2 Phase 3."
    )
    parser.add_argument("--device", default=None, help="Input device index or name.")
    parser.add_argument(
        "--long-seconds",
        type=int,
        default=300,
        help="Duration of the long-speech test (default: 300 seconds / 5 minutes).",
    )
    parser.add_argument(
        "--silence-seconds",
        type=int,
        default=10,
        help="Duration of the silence test (default: 10 seconds).",
    )
    args = parser.parse_args()

    device = args.device
    if isinstance(device, str) and device.isdigit():
        device = int(device)

    sample_rate = 16000
    print("EDITH Voice v2 — Phase 3 microphone validation")
    print("This test uses the existing AudioInputService and endpoint detector.")
    print("No old voice-engine files are imported or modified.")
    print(f"Input device: {device if device is not None else 'system default'}")
    print("Loading Silero ONNX VAD...")

    vad = SileroVAD(SileroVADConfig(sample_rate=sample_rate, use_onnx=True))
    endpoint = AdaptiveEndpointDetector(
        vad,
        EndpointConfig(sample_rate=sample_rate),
    )

    service = AudioInputService(
        AudioInputConfig(
            sample_rate=sample_rate,
            channels=1,
            block_duration_ms=20,
            device=device,
            start=True,
        )
    )
    subscription = service.subscribe(max_blocks=100)

    results = []
    try:
        print("\nMicrophone is live.")
        print("Keep the microphone environment quiet during the first test.")
        input("Press ENTER, then remain completely silent...")
        results.append(
            run_stage(
                "Silence",
                args.silence_seconds,
                service,
                subscription,
                endpoint,
                sample_rate,
            )
        )

        input(
            "\nPress ENTER. Say only: 'exit' once, then remain silent "
            "until the stage ends..."
        )
        endpoint.reset()
        results.append(
            run_stage("Short command", 8, service, subscription, endpoint, sample_rate)
        )

        input(
            "\nPress ENTER. Speak one normal sentence (about 5–10 seconds), "
            "then remain silent..."
        )
        endpoint.reset()
        results.append(
            run_stage("Normal speech", 15, service, subscription, endpoint, sample_rate)
        )

        input(
            "\nPress ENTER. Speak two short sentences with a deliberate "
            "2-second pause between them..."
        )
        endpoint.reset()
        results.append(
            run_stage("Natural pause", 20, service, subscription, endpoint, sample_rate)
        )

        input(
            f"\nPress ENTER. Speak continuously for up to {args.long_seconds} seconds. "
            "Use your normal speaking pace; avoid long pauses for this first test..."
        )
        endpoint.reset()
        results.append(
            run_stage(
                "Long speech",
                args.long_seconds,
                service,
                subscription,
                endpoint,
                sample_rate,
            )
        )

    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    finally:
        subscription.close()
        service.stop()

    stats = service.get_stats()
    print("\n========== FINAL REPORT ==========")
    for result in results:
        print(
            f"{result['name']}: starts={result['starts']}, "
            f"segments={result['segments']}, active_at_end={result['active_at_end']}"
        )
    print(f"Audio input stats: {stats}")
    print(f"Recorded WAV files: {OUTPUT_DIR}")
    print("==================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
