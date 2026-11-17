import numpy as np
from app.voice_v2.processing.audio_processor import AudioProcessor


def test_audio_metrics():
    processor = AudioProcessor()
    metrics = processor.analyze(np.array([0.0, 0.5, -0.5, 1.0], dtype=np.float32))
    assert metrics.peak == 1.0
    assert metrics.clipping_ratio == 0.25
    assert not metrics.is_silent


def test_empty_audio_is_silent():
    metrics = AudioProcessor().analyze(np.array([], dtype=np.float32))
    assert metrics.is_silent
    assert metrics.rms == 0.0
