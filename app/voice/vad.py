import webrtcvad


class VoiceActivityDetector:
    """
    Detects human speech in microphone audio.

    VAD does NOT:
        - transcribe speech
        - understand commands
        - generate responses

    It only determines whether an audio frame
    contains speech.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        aggressiveness: int = 2,
    ):
        self.sample_rate = sample_rate

        if aggressiveness not in (0, 1, 2, 3):
            raise ValueError(
                "Aggressiveness must be 0, 1, 2, or 3."
            )

        self.aggressiveness = aggressiveness

        self.vad = webrtcvad.Vad(
            aggressiveness
        )

    def is_speech(
        self,
        audio_frame: bytes,
    ) -> bool:
        """
        Determine whether an audio frame contains speech.

        WebRTC VAD expects:
            - 16-bit PCM audio
            - mono audio
            - 10, 20, or 30 ms frames
            - supported sample rates
        """

        return self.vad.is_speech(
            audio_frame,
            self.sample_rate,
        )