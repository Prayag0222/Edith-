import queue
import threading
from types import SimpleNamespace

import numpy as np

from app.voice.tts import SpeechChunk, TextToSpeech


class _FakeVoice:
    def synthesize(self, text):
        yield SimpleNamespace(
            audio_float_array=np.ones(32, dtype=np.float32)
        )


class _FakeOutputStream:
    def __init__(self, progress):
        self.progress = progress
        self.progress_at_write = []
        self.audio = []

    def write(self, audio):
        self.progress_at_write.append(list(self.progress))
        self.audio.append(audio.copy())


def test_speak_stream_reports_chunk_when_its_audio_starts():
    progress = []
    tts = object.__new__(TextToSpeech)
    tts._closed = False
    tts._speech_lock = threading.Lock()
    tts.AUDIO_QUEUE_SIZE = 4
    tts.QUEUE_TIMEOUT = 0.1
    tts.sample_rate = 16000
    tts.output_stream = _FakeOutputStream(progress)
    tts._select_voice = lambda text: (_FakeVoice(), 16000, "English")

    speech_queue = queue.Queue()
    speech_queue.put(SpeechChunk("Hello there.", 13, 25))
    speech_queue.put(None)

    tts.speak_stream(
        speech_queue,
        on_speech_progress=lambda start, end: progress.append((start, end)),
    )

    assert progress == [(13, 25)]
    assert tts.output_stream.progress_at_write == [[(13, 25)]]
    assert len(tts.output_stream.audio) == 1
