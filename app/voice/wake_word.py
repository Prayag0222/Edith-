import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import sounddevice as sd

from openwakeword.utils import AudioFeatures


class WakeWordDetector:
    """
    Low-latency EDITH wake-word detector.

    Features:
        - Frozen custom ONNX wake-word model
        - Efficient NumPy circular audio buffer
        - Reduced detection latency
        - RMS-based silence filtering
        - Optimized ONNX inference
        - No unnecessary terminal logging
    """

    WINDOW_SECONDS = 2
    COOLDOWN_SECONDS = 2.0

    def __init__(
        self,
        wake_word: str = "hey_edith",
        sample_rate: int = 16000,
        chunk_size: int = 8000,
        threshold: float = 0.90,
        min_rms: float = 30.0,
    ):
        if sample_rate <= 0:
            raise ValueError("Sample rate must be positive.")

        if chunk_size <= 0:
            raise ValueError("Chunk size must be positive.")

        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0 and 1.")

        if min_rms < 0:
            raise ValueError("Minimum RMS cannot be negative.")

        self.wake_word = wake_word
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.threshold = threshold
        self.min_rms = min_rms

        self.window_size = (
            self.sample_rate * self.WINDOW_SECONDS
        )

        self.cooldown_seconds = self.COOLDOWN_SECONDS
        self.last_detection_time = 0.0

        # --------------------------------------------------
        # MODEL PATHS
        # --------------------------------------------------

        project_root = Path(__file__).resolve().parents[2]
        model_dir = project_root / "models" / "wakeword"

        wake_model_path = model_dir / "hey_edith.onnx"
        melspec_path = model_dir / "melspectrogram.onnx"
        embedding_path = model_dir / "embedding_model.onnx"

        for file_path in (
            wake_model_path,
            melspec_path,
            embedding_path,
        ):
            if not file_path.is_file():
                raise FileNotFoundError(
                    f"Required wake-word model not found: {file_path}"
                )

        # --------------------------------------------------
        # ONNX SESSION
        # --------------------------------------------------

        session_options = ort.SessionOptions()

        session_options.execution_mode = (
            ort.ExecutionMode.ORT_SEQUENTIAL
        )

        session_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        session_options.intra_op_num_threads = 1
        session_options.inter_op_num_threads = 1

        self.session = ort.InferenceSession(
            str(wake_model_path),
            sess_options=session_options,
            providers=["CPUExecutionProvider"],
        )

        self.input_name = self.session.get_inputs()[0].name

        # --------------------------------------------------
        # AUDIO FEATURES
        # --------------------------------------------------

        self.features = AudioFeatures(
            melspec_model_path=str(melspec_path),
            embedding_model_path=str(embedding_path),
        )

        # --------------------------------------------------
        # NUMPY CIRCULAR BUFFER
        # --------------------------------------------------

        self.audio_buffer = np.zeros(
            self.window_size,
            dtype=np.int16,
        )

        self._write_position = 0
        self._samples_collected = 0

    # --------------------------------------------------
    # BUFFER MANAGEMENT
    # --------------------------------------------------

    def _add_audio(self, chunk: np.ndarray):
        """
        Add incoming audio to the circular buffer.
        """

        chunk = np.asarray(
            chunk,
            dtype=np.int16,
        ).reshape(-1)

        if chunk.size == 0:
            return

        chunk_size = chunk.size

        if chunk_size >= self.window_size:

            self.audio_buffer[:] = chunk[-self.window_size:]

            self._write_position = 0
            self._samples_collected = self.window_size

            return

        end_position = self._write_position + chunk_size

        if end_position <= self.window_size:

            self.audio_buffer[
                self._write_position:end_position
            ] = chunk

        else:

            first_part = self.window_size - self._write_position

            self.audio_buffer[
                self._write_position:
            ] = chunk[:first_part]

            self.audio_buffer[
                :chunk_size - first_part
            ] = chunk[first_part:]

        self._write_position = (
            end_position % self.window_size
        )

        self._samples_collected = min(
            self._samples_collected + chunk_size,
            self.window_size,
        )

    def _get_audio_window(self) -> np.ndarray:
        """
        Return chronological audio from the circular buffer.
        """

        if self._write_position == 0:
            return self.audio_buffer.copy()

        return np.concatenate(
            (
                self.audio_buffer[self._write_position:],
                self.audio_buffer[:self._write_position],
            )
        )

    # --------------------------------------------------
    # AUDIO VALIDATION
    # --------------------------------------------------

    def _calculate_rms(self, audio: np.ndarray) -> float:

        audio_float = audio.astype(
            np.float32,
            copy=False,
        )

        return float(
            np.sqrt(
                np.mean(
                    audio_float * audio_float
                )
            )
        )

    # --------------------------------------------------
    # WAKE WORD INFERENCE
    # --------------------------------------------------

    def _detect(self, audio: np.ndarray) -> float:
        """
        Run embedding extraction and ONNX inference.
        """

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
            return 0.0

        n = embedded.shape[1]

        start = max(
            0,
            (n - 16) // 2,
        )

        model_input = embedded[
            :,
            start:start + 16,
            :,
        ]

        if model_input.shape[1] != 16:
            return 0.0

        output = self.session.run(
            None,
            {
                self.input_name: model_input,
            },
        )[0]

        output = np.asarray(
            output,
            dtype=np.float32,
        )

        if output.size == 0:
            return 0.0

        score = float(output.reshape(-1)[0])

        if not np.isfinite(score):
            return 0.0

        return score

    # --------------------------------------------------
    # MAIN WAKE WORD LOOP
    # --------------------------------------------------

    def wait_for_wake_word(self) -> bool:

        self.audio_buffer.fill(0)

        self._write_position = 0
        self._samples_collected = 0

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self.chunk_size,
        ) as stream:

            while True:

                audio_data, overflowed = stream.read(
                    self.chunk_size
                )

                if overflowed:
                    continue

                chunk = np.asarray(
                    audio_data,
                    dtype=np.int16,
                ).reshape(-1)

                self._add_audio(chunk)

                if self._samples_collected < self.window_size:
                    continue

                audio = self._get_audio_window()

                rms = self._calculate_rms(audio)

                # Reject low-level background noise.
                if rms < self.min_rms:
                    continue

                score = self._detect(audio)

                if score < self.threshold:
                    continue

                now = time.monotonic()

                if (
                    now - self.last_detection_time
                    < self.cooldown_seconds
                ):
                    continue

                self.last_detection_time = now

                print(
                    f"\n[WAKE] Hey EDITH detected "
                    f"| Score: {score:.4f}"
                )

                return True

    # --------------------------------------------------
    # CLEANUP
    # --------------------------------------------------

    def reset(self):

        self.audio_buffer.fill(0)

        self._write_position = 0
        self._samples_collected = 0