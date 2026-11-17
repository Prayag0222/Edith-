import numpy as np
import pytest

soxr = pytest.importorskip("soxr")
from app.voice_v2.processing.resampler import AudioResampler


def test_resample_44100_to_16000():
    source = np.zeros(44100, dtype=np.float32)
    result = AudioResampler().resample(source, 44100, 16000)
    assert abs(result.size - 16000) <= 1
