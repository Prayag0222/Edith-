from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True, slots=True)
class SileroVADConfig:
    sample_rate: int = 16000
    threshold: float = 0.55
    min_speech_duration_ms: int = 80
    min_silence_duration_ms: int = 120
    use_onnx: bool = True

    def __post_init__(self):
        if self.sample_rate not in (8000, 16000):
            raise ValueError("Silero VAD supports 8000 or 16000 Hz input")
        if not 0.0 < self.threshold < 1.0:
            raise ValueError("threshold must be between 0 and 1")
        if self.min_speech_duration_ms < 0 or self.min_silence_duration_ms < 0:
            raise ValueError("Duration settings cannot be negative")


class SileroVAD:
    """
    Stateful Silero VAD wrapper.

    At 16 kHz, Silero expects 512-sample (32 ms) frames. At 8 kHz it expects
    256-sample frames. The wrapper buffers arbitrary input chunks and emits
    one speech probability for each complete model frame.
    """

    def __init__(self, config: SileroVADConfig | None = None):
        self.config = config or SileroVADConfig()
        try:
            from silero_vad import load_silero_vad
        except ImportError as exc:
            raise ImportError(
                "Install Silero VAD dependencies: "
                "pip install silero-vad onnxruntime"
            ) from exc

        self.model = load_silero_vad(onnx=self.config.use_onnx)
        self.frame_size = 512 if self.config.sample_rate == 16000 else 256
        self._pending = np.empty(0, dtype=np.float32)

    def reset(self):
        self._pending = np.empty(0, dtype=np.float32)
        reset = getattr(self.model, "reset_states", None)
        if callable(reset):
            reset()

    def process(self, audio: np.ndarray) -> list[float]:
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return []
        if not np.all(np.isfinite(samples)):
            raise ValueError("Audio contains NaN or infinite values")

        if self._pending.size:
            samples = np.concatenate((self._pending, samples))

        complete_count = samples.size // self.frame_size
        if complete_count == 0:
            self._pending = samples.copy()
            return []

        usable = complete_count * self.frame_size
        frames = samples[:usable].reshape(complete_count, self.frame_size)
        self._pending = samples[usable:].copy()

        probabilities: list[float] = []
        for frame in frames:
            # Silero's ONNX wrapper accepts a torch tensor in the public API.
            # Import torch lazily so audio capture does not require it.
            try:
                import torch
                tensor = torch.from_numpy(frame.copy())
                probability = self.model(tensor, self.config.sample_rate)
                if hasattr(probability, "item"):
                    probability = probability.item()
                probabilities.append(float(probability))
            except Exception as exc:
                raise RuntimeError(f"Silero VAD inference failed: {exc}") from exc

        return probabilities
