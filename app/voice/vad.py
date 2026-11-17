import webrtcvad


class VoiceActivityDetector:
    """
    Lightweight WebRTC Voice Activity Detector.

    Detects whether a PCM audio frame contains human speech.
    """

    SUPPORTED_SAMPLE_RATES = (8000, 16000, 32000, 48000)
    SUPPORTED_FRAME_DURATIONS = (10, 20, 30)

    def __init__(
        self,
        sample_rate: int = 16000,
        aggressiveness: int = 2,
    ):
        if sample_rate not in self.SUPPORTED_SAMPLE_RATES:
            raise ValueError(
                f"Unsupported sample rate: {sample_rate}. "
                f"Supported rates: {self.SUPPORTED_SAMPLE_RATES}"
            )

        if aggressiveness not in (0, 1, 2, 3):
            raise ValueError(
                "Aggressiveness must be 0, 1, 2, or 3."
            )

        self.sample_rate = sample_rate
        self.aggressiveness = aggressiveness

        self.vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, audio_frame: bytes) -> bool:
        """
        Analyze one mono PCM16 audio frame.

        Accepted frame durations: 10, 20 or 30 ms.
        """

        if not isinstance(audio_frame, bytes):
            raise TypeError("Audio frame must be bytes.")

        frame_length = len(audio_frame)

        if frame_length == 0:
            raise ValueError("Audio frame cannot be empty.")

        bytes_per_sample = 2

        valid_frame_sizes = {
            int(
                self.sample_rate
                * duration
                / 1000
                * bytes_per_sample
            )
            for duration in self.SUPPORTED_FRAME_DURATIONS
        }

        if frame_length not in valid_frame_sizes:
            raise ValueError(
                "Invalid PCM16 frame length for "
                f"{self.sample_rate} Hz audio: {frame_length} bytes."
            )

        return self.vad.is_speech(
            audio_frame,
            self.sample_rate,
        )