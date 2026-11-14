import numpy as np
import noisereduce as nr


class NoiseSuppressor:
    """
    Non-stationary spectral noise suppression.

    Responsibilities:
        - Reduce environmental background noise.
        - Preserve speech as much as possible.
        - Avoid unnecessary processing of short recordings.
        - Prevent excessive attenuation.
        - Keep the original audio if processing fails.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        strength: float = 0.75,
        enabled: bool = True,
        minimum_duration: float = 0.25,
    ):
        self.sample_rate = sample_rate
        self.strength = float(np.clip(strength, 0.0, 1.0))
        self.enabled = enabled
        self.minimum_duration = minimum_duration

    # -----------------------------------------------
    # AUDIO METRICS
    # -----------------------------------------------

    def _calculate_rms(self, audio: np.ndarray) -> float:
        if len(audio) == 0:
            return 0.0

        return float(
            np.sqrt(
                np.mean(
                    np.square(audio.astype(np.float32))
                )
            )
        )

    # -----------------------------------------------
    # NOISE SUPPRESSION
    # -----------------------------------------------

    def process(self, audio: np.ndarray) -> np.ndarray:

        audio = np.asarray(
            audio,
            dtype=np.float32,
        ).flatten()

        if not self.enabled:
            return audio

        if len(audio) == 0:
            return audio

        duration = len(audio) / self.sample_rate

        if duration < self.minimum_duration:
            return audio

        original_audio = audio.copy()

        original_rms = self._calculate_rms(
            original_audio
        )

        if original_rms < 0.001:
            return original_audio

        try:

            cleaned_audio = nr.reduce_noise(
                y=original_audio,
                sr=self.sample_rate,
                stationary=False,
                prop_decrease=self.strength,
                n_fft=512,
                hop_length=128,
            )

            cleaned_audio = np.asarray(
                cleaned_audio,
                dtype=np.float32,
            )

            cleaned_audio = np.nan_to_num(
                cleaned_audio,
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            )

            cleaned_audio = np.clip(
                cleaned_audio,
                -1.0,
                1.0,
            )

            cleaned_rms = self._calculate_rms(
                cleaned_audio
            )

            # Reject suspiciously aggressive processing.
            if cleaned_rms < original_rms * 0.08:
                print(
                    "[NOISE] Suppression rejected: "
                    "excessive audio attenuation."
                )

                return original_audio

            reduction = (
                1.0 - cleaned_rms / original_rms
            ) * 100

            print(
                f"[NOISE] Suppression completed | "
                f"RMS change: {reduction:.1f}%"
            )

            return cleaned_audio

        except Exception as error:

            print(
                f"[NOISE] Suppression failed: {error}"
            )

            print(
                "[NOISE] Using original audio."
            )

            return original_audio