import tempfile
import wave
from collections import deque

import numpy as np
import sounddevice as sd

from app.voice.vad import VoiceActivityDetector


class AudioRecorder:
    """
    Handles microphone input and audio preparation.

    Responsibilities:
        - Capture microphone audio
        - Detect human speech using WebRTC VAD
        - Reject silence/background noise
        - Keep a short pre-buffer
        - Continue recording through brief VAD mistakes
        - Detect genuine end-of-speech
        - Convert recorded audio into a WAV file
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        silence_duration: float = 1.5,
        max_recording_seconds: float = 20.0,
        vad_aggressiveness: int = 2,
    ):
        self.sample_rate = sample_rate
        self.channels = channels

        self.silence_duration = silence_duration
        self.max_recording_seconds = (
            max_recording_seconds
        )

        self.vad = VoiceActivityDetector(
            sample_rate=self.sample_rate,
            aggressiveness=vad_aggressiveness,
        )

    # --------------------------------------------------
    # AUDIO CONVERSION
    # --------------------------------------------------

    def _float_to_pcm16(
        self,
        audio: np.ndarray,
    ) -> bytes:
        """
        Convert float32 microphone audio into
        signed 16-bit PCM bytes.

        WebRTC VAD requires:
            - mono
            - PCM16
            - 10/20/30 ms frames
        """

        audio = np.asarray(
            audio,
            dtype=np.float32,
        )

        audio = np.clip(
            audio,
            -1.0,
            1.0,
        )

        pcm_audio = (
            audio * 32767
        ).astype(
            np.int16
        )

        return pcm_audio.tobytes()

    # --------------------------------------------------
    # AUDIO ENERGY
    # --------------------------------------------------

    def _calculate_rms(
        self,
        audio: np.ndarray,
    ) -> float:
        """
        Calculate RMS audio energy.

        RMS gives us a simple measurement of
        how loud the microphone signal is.
        """

        if len(audio) == 0:
            return 0.0

        audio = audio.astype(
            np.float32
        )

        return float(
            np.sqrt(
                np.mean(
                    np.square(audio)
                )
            )
        )

    # --------------------------------------------------
    # FRAME SPLITTING
    # --------------------------------------------------

    def _frame_audio(
        self,
        audio: np.ndarray,
        frame_duration_ms: int = 30,
    ):
        """
        Split audio into WebRTC-compatible frames.

        WebRTC VAD supports:
            10 ms
            20 ms
            30 ms

        EDITH uses 30 ms frames.
        """

        frame_size = int(
            self.sample_rate
            * frame_duration_ms
            / 1000
        )

        total_samples = len(audio)

        for start in range(
            0,
            total_samples - frame_size + 1,
            frame_size,
        ):
            end = start + frame_size

            yield audio[start:end]

    # --------------------------------------------------
    # VAD ANALYSIS
    # --------------------------------------------------

    def _analyze_speech(
        self,
        audio_chunk: np.ndarray,
    ):
        """
        Analyze one microphone block.

        Returns:

            {
                "rms": float,
                "speech_frames": int,
                "total_frames": int,
            }

        This method does NOT decide whether EDITH
        should start or stop recording.

        It only gathers evidence.
        """

        rms = self._calculate_rms(
            audio_chunk
        )

        speech_frames = 0
        total_frames = 0

        for frame in self._frame_audio(
            audio_chunk,
            frame_duration_ms=30,
        ):
            pcm_frame = (
                self._float_to_pcm16(
                    frame
                )
            )

            try:

                is_speech = (
                    self.vad.is_speech(
                        pcm_frame
                    )
                )

            except Exception:

                is_speech = False

            total_frames += 1

            if is_speech:
                speech_frames += 1

        return {
            "rms": rms,
            "speech_frames": speech_frames,
            "total_frames": total_frames,
        }

    # --------------------------------------------------
    # SPEECH START DETECTION
    # --------------------------------------------------

    def _is_speech_start(
        self,
        analysis,
    ) -> bool:
        """
        Decide whether the user has actually started
        speaking.

        Starting recording is intentionally stricter
        than continuing an existing recording.

        This prevents random background noise from
        waking EDITH.
        """

        rms = analysis["rms"]
        speech_frames = analysis[
            "speech_frames"
        ]

        # Very quiet microphone signal.
        if rms < 0.008:
            return False

        # Require multiple VAD-positive frames
        # before declaring that speech has started.
        if speech_frames >= 2:
            return True

        return False

    # --------------------------------------------------
    # SPEECH CONTINUATION
    # --------------------------------------------------

    def _is_speech_continuation(
        self,
        analysis,
    ) -> bool:
        """
        Decide whether an already-active speech session
        should continue.

        This is intentionally more forgiving.

        Natural speech contains:
            - quiet syllables
            - pauses
            - consonants
            - short VAD mistakes

        We don't want those to terminate recording.
        """

        rms = analysis["rms"]
        speech_frames = analysis[
            "speech_frames"
        ]

        # Strong VAD evidence.
        if speech_frames >= 1:
            return True

        # Moderate audio energy.

        # This allows EDITH to survive short VAD
        # mistakes while the user is still talking.
        if rms >= 0.012:
            return True

        return False

    # --------------------------------------------------
    # RECORDING
    # --------------------------------------------------

    def record_until_silence(self):
        """
        Record microphone input until genuine silence.

        Recording has two states:

            WAITING
                ↓
            SPEECH START
                ↓
            RECORDING
                ↓
            TEMPORARY VAD MISS
                ↓
            CONTINUE
                ↓
            REAL SILENCE
                ↓
            STOP

        This prevents both:

            1. Background noise from triggering EDITH.
            2. Natural speech from being cut prematurely.
        """

        block_duration = 0.1

        block_size = int(
            self.sample_rate
            * block_duration
        )

        silence_blocks_required = max(
            1,
            int(
                self.silence_duration
                / block_duration
            ),
        )

        max_blocks = int(
            self.max_recording_seconds
            / block_duration
        )

        # 500 ms pre-buffer.
        #
        # This protects the beginning of words.
        pre_buffer_blocks = 5

        pre_buffer = deque(
            maxlen=pre_buffer_blocks
        )

        recorded_chunks = []

        speaking = False
        silent_blocks = 0

        print("Listening...")

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            blocksize=block_size,
        ) as stream:

            for _ in range(max_blocks):

                audio_chunk, overflowed = (
                    stream.read(
                        block_size
                    )
                )

                if overflowed:
                    print(
                        "Warning: microphone "
                        "buffer overflow."
                    )

                audio_chunk = (
                    audio_chunk.copy()
                )

                mono_chunk = (
                    audio_chunk[:, 0]
                )

                analysis = (
                    self._analyze_speech(
                        mono_chunk
                    )
                )

                pre_buffer.append(
                    mono_chunk
                )

                # ----------------------------------
                # WAITING FOR SPEECH
                # ----------------------------------

                if not speaking:

                    speech_started = (
                        self._is_speech_start(
                            analysis
                        )
                    )

                    if speech_started:

                        speaking = True

                        recorded_chunks.extend(
                            list(pre_buffer)
                        )

                        silent_blocks = 0

                    continue

                # ----------------------------------
                # ALREADY RECORDING
                # ----------------------------------

                speech_continues = (
                    self._is_speech_continuation(
                        analysis
                    )
                )

                recorded_chunks.append(
                    mono_chunk
                )

                if speech_continues:

                    # User is still talking.
                    #
                    # Reset the silence timer.
                    silent_blocks = 0

                else:

                    # Possible silence.
                    silent_blocks += 1

                    if (
                        silent_blocks
                        >= silence_blocks_required
                    ):
                        break

        # ------------------------------------------
        # NO SPEECH EVER STARTED
        # ------------------------------------------

        if not speaking:
            return None

        if not recorded_chunks:
            return None

        return np.concatenate(
            recorded_chunks
        )

    # --------------------------------------------------
    # WAV CREATION
    # --------------------------------------------------

    def save_wav(
        self,
        audio,
    ):
        """
        Save recorded audio as a temporary WAV file.
        """

        temporary_file = (
            tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
            )
        )

        temporary_path = (
            temporary_file.name
        )

        temporary_file.close()

        audio = np.asarray(
            audio,
            dtype=np.float32,
        )

        audio = np.clip(
            audio,
            -1.0,
            1.0,
        )

        pcm_audio = (
            audio * 32767
        ).astype(
            np.int16
        )

        with wave.open(
            temporary_path,
            "wb",
        ) as wav_file:

            wav_file.setnchannels(
                self.channels
            )

            wav_file.setsampwidth(
                2
            )

            wav_file.setframerate(
                self.sample_rate
            )

            wav_file.writeframes(
                pcm_audio.tobytes()
            )

        return temporary_path