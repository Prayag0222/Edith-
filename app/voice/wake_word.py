import time
from collections import deque
from pathlib import Path

import numpy as np
import onnxruntime as ort
import sounddevice as sd

from openwakeword.utils import AudioFeatures


class WakeWordDetector:
    def __init__(
        self,
        wake_word: str = "hey_edith",
        sample_rate: int = 16000,
        chunk_size: int = 16000,
        threshold: float = 0.90,
        min_rms: float = 30.0,
    ):
        self.wake_word = wake_word
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.threshold = threshold
        self.min_rms = min_rms

        self.window_seconds = 2
        self.window_size = self.sample_rate * self.window_seconds

        self.cooldown_seconds = 2.0
        self.last_detection_time = 0.0

        # Resolve model paths relative to the EDITH project root.
        project_root = Path(__file__).resolve().parents[2]
        model_dir = project_root / "models" / "wakeword"

        wake_model_path = model_dir / "hey_edith.onnx"
        melspec_path = model_dir / "melspectrogram.onnx"
        embedding_path = model_dir / "embedding_model.onnx"

        required_files = [
            wake_model_path,
            melspec_path,
            embedding_path,
        ]

        for file_path in required_files:
            if not file_path.is_file():
                raise FileNotFoundError(
                    f"Required wake-word model not found: {file_path}"
                )

        print("[WAKE] Loading custom EDITH wake-word model...")

        self.session = ort.InferenceSession(
            str(wake_model_path),
            providers=["CPUExecutionProvider"],
        )

        self.input_name = self.session.get_inputs()[0].name

        self.features = AudioFeatures(
            melspec_model_path=str(melspec_path),
            embedding_model_path=str(embedding_path),
        )

        self.audio_buffer = deque(maxlen=self.window_size)

        print("[WAKE] Custom EDITH wake-word model loaded.")
        print(
            f"[WAKE] Threshold={self.threshold:.2f} | "
            f"Minimum RMS={self.min_rms:.1f}"
        )

    def wait_for_wake_word(self) -> bool:
        self.audio_buffer.clear()

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self.chunk_size,
        ) as stream:

            while True:
                audio_data, overflowed = stream.read(self.chunk_size)

                if overflowed:
                    print(
                        "\n[WAKE] Warning: microphone buffer overflow."
                    )

                chunk = np.asarray(
                    audio_data,
                    dtype=np.int16,
                ).flatten()

                self.audio_buffer.extend(chunk.tolist())

                if len(self.audio_buffer) < self.window_size:
                    continue

                audio = np.asarray(
                    self.audio_buffer,
                    dtype=np.int16,
                )

                # Calculate RMS before running expensive model inference.
                audio_float = audio.astype(np.float32)
                rms = float(
                    np.sqrt(np.mean(np.square(audio_float)))
                )

                # Reject near-silence and very low-level background noise.
                if rms < self.min_rms:
                    continue

                clip = audio[np.newaxis, :]

                embedded = self.features.embed_clips(
                    clip,
                    batch_size=1,
                )

                embedded = np.asarray(
                    embedded,
                    dtype=np.float32,
                )

                if embedded.ndim != 3 or embedded.shape[1] < 16:
                    continue

                n = embedded.shape[1]
                start = max(0, (n - 16) // 2)

                model_input = embedded[
                    :,
                    start:start + 16,
                    :,
                ]

                if model_input.shape[1] != 16:
                    continue

                raw_output = self.session.run(
                    None,
                    {self.input_name: model_input},
                )[0]

                output_array = np.asarray(
                    raw_output,
                    dtype=np.float32,
                ).flatten()

                if output_array.size == 0:
                    continue

                score = float(output_array[0])

                if not np.isfinite(score):
                    continue

                print(
                    f"\r[WAKE DEBUG] Score={score:.4f} | "
                    f"RMS={rms:.2f}",
                    end="",
                    flush=True,
                )

                now = time.monotonic()

                # Single-prediction activation: no extra confirmation delay.
                if score >= self.threshold:
                    if (
                        now - self.last_detection_time
                        >= self.cooldown_seconds
                    ):
                        print(
                            f"\n[WAKE] Hey EDITH detected! "
                            f"Score={score:.4f} | RMS={rms:.2f}"
                        )

                        self.last_detection_time = now
                        return True
