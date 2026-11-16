import tempfile
import wave
from collections import deque
from math import ceil
from pathlib import Path

import numpy as np
import sounddevice as sd

from app.voice.vad import VoiceActivityDetector


class AudioRecorder:
    """
    Microphone capture and speech-aware audio recording.

    Features:
        - 16 kHz mono microphone capture
        - WebRTC voice activity detection
        - Short pre-buffer to preserve initial words
        - Tolerance for brief speech detection failures
        - Configurable silence termination
        - Maximum recording duration
        - Temporary WAV generation
    """

    BLOCK_DURATION = 0.12
    VAD_FRAME_DURATION_MS = 30

    PRE_BUFFER_SECONDS = 0.5
    SPEECH_START_RMS = 0.008
    SPEECH_CONTINUATION_RMS = 0.012

    SUPPORTED_SAMPLE_RATES = (8000, 16000, 32000, 48000)

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        silence_duration: float = 1.5,
        max_recording_seconds: float = 20.0,
        vad_aggressiveness: int = 2,
        initial_silence_timeout: float = 8.0,
    ):
        if sample_rate not in self.SUPPORTED_SAMPLE_RATES:
            raise ValueError(
                f"Unsupported VAD sample rate: {sample_rate}"
            )

        if channels != 1:
            raise ValueError(
                "AudioRecorder requires mono microphone input."
            )

        if silence_duration <= 0:
            raise ValueError("silence_duration must be positive.")

        if max_recording_seconds <= 0:
            raise ValueError(
                "max_recording_seconds must be positive."
            )

        if initial_silence_timeout <= 0:
            raise ValueError(
                "initial_silence_timeout must be positive."
            )

        self.sample_rate = sample_rate
        self.channels = channels

        self.silence_duration = silence_duration
        self.max_recording_seconds = max_recording_seconds
        self.initial_silence_timeout = initial_silence_timeout

        self.block_size = int(
            self.sample_rate * self.BLOCK_DURATION
        )

        self.block_duration = (
            self.block_size / self.sample_rate
        )

        self.frame_size = int(
            self.sample_rate
            * self.VAD_FRAME_DURATION_MS
            / 1000
        )

        if self.block_size % self.frame_size != 0:
            raise ValueError(
                "Audio block size must contain complete VAD frames."
            )

        self.vad = VoiceActivityDetector(
            sample_rate=self.sample_rate,
            aggressiveness=vad_aggressiveness,
        )

    # --------------------------------------------------
    # AUDIO CONVERSION
    # --------------------------------------------------

    @staticmethod
    def _float_to_pcm16(audio: np.ndarray) -> bytes:
        audio = np.asarray(audio, dtype=np.float32)

        pcm_audio = (
            np.clip(audio, -1.0, 1.0) * 32767
        ).astype(np.int16)

        return pcm_audio.tobytes()

    # --------------------------------------------------
    # AUDIO ENERGY
    # --------------------------------------------------

    @staticmethod
    def _calculate_rms(audio: np.ndarray) -> float:
        if audio.size == 0:
            return 0.0

        audio = np.asarray(audio, dtype=np.float32)

        return float(
            np.sqrt(np.mean(audio * audio))
        )

    # --------------------------------------------------
    # FRAME SPLITTING
    # --------------------------------------------------

    def _frame_audio(self, audio: np.ndarray):
        """
        Split audio into complete 30 ms WebRTC frames.

        Recording blocks are configured to contain an exact
        number of VAD frames, preventing discarded samples.
        """

        for start in range(
            0,
            len(audio),
            self.frame_size,
        ):
            end = start + self.frame_size

            if end > len(audio):
                break

            yield audio[start:end]

    # --------------------------------------------------
    # VAD ANALYSIS
    # --------------------------------------------------

    def _analyze_speech(self, audio_chunk: np.ndarray) -> dict:
        rms = self._calculate_rms(audio_chunk)

        speech_frames = 0
        total_frames = 0

        for frame in self._frame_audio(audio_chunk):
            pcm_frame = self._float_to_pcm16(frame)

            is_speech = self.vad.is_speech(pcm_frame)

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

    def _is_speech_start(self, analysis: dict) -> bool:
        if analysis["rms"] < self.SPEECH_START_RMS:
            return False

        return analysis["speech_frames"] >= 2

    # --------------------------------------------------
    # SPEECH CONTINUATION
    # --------------------------------------------------

    def _is_speech_continuation(self, analysis: dict) -> bool:
        if analysis["speech_frames"] >= 1:
            return True

        return (
            analysis["rms"]
            >= self.SPEECH_CONTINUATION_RMS
        )

    # --------------------------------------------------
    # RECORDING
    # --------------------------------------------------

    def record_until_silence(self):
        silence_blocks_required = max(
            1,
            ceil(
                self.silence_duration
                / self.block_duration
            ),
        )

        max_blocks = max(
            1,
            ceil(
                self.max_recording_seconds
                / self.block_duration
            ),
        )

        initial_silence_blocks = max(
            1,
            ceil(
                self.initial_silence_timeout
                / self.block_duration
            ),
        )

        pre_buffer_blocks = max(
            1,
            round(
                self.PRE_BUFFER_SECONDS
                / self.block_duration
            ),
        )

        pre_buffer = deque(
            maxlen=pre_buffer_blocks
        )

        recorded_chunks = []

        speaking = False
        silent_blocks = 0

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            blocksize=self.block_size,
        ) as stream:

            for block_index in range(max_blocks):

                audio_chunk, overflowed = stream.read(
                    self.block_size
                )

                if overflowed:
                    print(
                        "[AUDIO] Microphone buffer overflow."
                    )

                mono_chunk = audio_chunk[:, 0].copy()

                analysis = self._analyze_speech(
                    mono_chunk
                )

                pre_buffer.append(mono_chunk)

                # ----------------------------------
                # WAITING FOR SPEECH
                # ----------------------------------

                if not speaking:

                    if self._is_speech_start(analysis):

                        speaking = True

                        recorded_chunks.extend(
                            pre_buffer
                        )

                        silent_blocks = 0

                    elif (
                        block_index + 1
                        >= initial_silence_blocks
                    ):
                        return None

                    continue

                # ----------------------------------
                # RECORDING SPEECH
                # ----------------------------------

                recorded_chunks.append(mono_chunk)

                if self._is_speech_continuation(analysis):

                    silent_blocks = 0

                else:

                    silent_blocks += 1

                    if (
                        silent_blocks
                        >= silence_blocks_required
                    ):
                        break

        if not speaking or not recorded_chunks:
            return None

        return np.concatenate(
            recorded_chunks
        )

    # --------------------------------------------------
    # WAV CREATION
    # --------------------------------------------------

    def save_wav(self, audio: np.ndarray) -> str:
        """
        Save mono float32 audio as a temporary PCM16 WAV.
        """

        audio = np.asarray(
            audio,
            dtype=np.float32,
        ).reshape(-1)

        if audio.size == 0:
            raise ValueError("Cannot save empty audio.")

        pcm_audio = (
            np.clip(audio, -1.0, 1.0) * 32767
        ).astype(np.int16)

        temporary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
            ) as temporary_file:

                temporary_path = temporary_file.name

            with wave.open(
                temporary_path,
                "wb",
            ) as wav_file:

                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.sample_rate)

                wav_file.writeframes(
                    pcm_audio.tobytes()
                )

            return temporary_path

        except Exception:

            if temporary_path:
                Path(temporary_path).unlink(
                    missing_ok=True
                )

            raise