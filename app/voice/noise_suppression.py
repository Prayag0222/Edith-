import numpy as np


class NoiseSuppressor:
    """
    Non-stationary spectral noise suppression.

    Features:
        - Lazy loading of noisereduce
        - Configurable suppression strength
        - Short-audio bypass
        - Protection against excessive attenuation
        - Safe fallback to original audio
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        strength: float = 0.75,
        enabled: bool = True,
        minimum_duration: float = 0.25,
    ):
        if sample_rate <= 0:
            raise ValueError("Sample rate must be positive.")

        if not np.isfinite(strength):
            raise ValueError("Suppression strength must be finite.")

        if minimum_duration < 0:
            raise ValueError("Minimum duration cannot be negative.")

        self.sample_rate = sample_rate
        self.strength = float(np.clip(strength, 0.0, 1.0))
        self.enabled = enabled
        self.minimum_duration = minimum_duration

        self._noise_reduction = None

    # --------------------------------------------------
    # AUDIO METRICS
    # --------------------------------------------------

    @staticmethod
    def _calculate_rms(audio: np.ndarray) -> float:
        if audio.size == 0:
            return 0.0

        return float(
            np.sqrt(np.mean(np.square(audio)))
        )

    # --------------------------------------------------
    # LAZY DEPENDENCY LOADING
    # --------------------------------------------------

    def _load_noise_reduction(self):
        if self._noise_reduction is None:
            import noisereduce

            self._noise_reduction = noisereduce.reduce_noise

        return self._noise_reduction

    # --------------------------------------------------
    # NOISE SUPPRESSION
    # --------------------------------------------------

    def process(self, audio: np.ndarray) -> np.ndarray:
        audio = np.asarray(
            audio,
            dtype=np.float32,
        ).reshape(-1)

        if not self.enabled or self.strength <= 0:
            return audio

        if audio.size == 0:
            return audio

        duration = audio.size / self.sample_rate

        if duration < self.minimum_duration:
            return audio

        original_rms = self._calculate_rms(audio)

        if not np.isfinite(original_rms) or original_rms < 0.001:
            return audio

        try:
            reduce_noise = self._load_noise_reduction()

            cleaned_audio = reduce_noise(
                y=audio,
                sr=self.sample_rate,
                stationary=False,
                prop_decrease=self.strength,
                n_fft=512,
                hop_length=128,
            )

            cleaned_audio = np.asarray(
                cleaned_audio,
                dtype=np.float32,
            ).reshape(-1)

            if cleaned_audio.shape != audio.shape:
                raise ValueError(
                    "Noise suppression changed audio length."
                )

            if not np.all(np.isfinite(cleaned_audio)):
                raise ValueError(
                    "Noise suppression produced invalid audio."
                )

            np.clip(
                cleaned_audio,
                -1.0,
                1.0,
                out=cleaned_audio,
            )

            cleaned_rms = self._calculate_rms(cleaned_audio)

            # Reject excessive speech attenuation.
            if cleaned_rms < original_rms * 0.08:
                return audio

            return cleaned_audio

        except Exception as error:
            print(f"[NOISE] Suppression failed: {error}")
            return audio