import numpy as np
import pytest

from app.voice_v2.core.audio_buffer import (
    AudioAccumulator, AudioRingBuffer, iter_audio_frames
)


def test_ring_buffer_returns_chronological_samples_after_wrap():
    buffer = AudioRingBuffer(capacity_seconds=1, sample_rate=4)
    buffer.append(np.array([1, 2, 3], dtype=np.float32))
    buffer.append(np.array([4, 5, 6], dtype=np.float32))
    np.testing.assert_array_equal(buffer.get_audio(), [3, 4, 5, 6])


def test_ring_buffer_keeps_only_newest_capacity():
    buffer = AudioRingBuffer(capacity_seconds=0.5, sample_rate=4)
    buffer.append(np.arange(8, dtype=np.float32))
    np.testing.assert_array_equal(buffer.get_audio(), [6, 7])
    assert buffer.duration_seconds == 0.5


def test_accumulator_keeps_five_minutes_without_truncation():
    sample_rate = 16000
    accumulator = AudioAccumulator(sample_rate, max_duration_seconds=360)
    block = np.zeros(320, dtype=np.float32)
    for _ in range(15000):  # 300 seconds at 20 ms/block
        accumulator.append(block)
    assert accumulator.duration_seconds == pytest.approx(300.0)
    assert accumulator.sample_count == sample_rate * 300
    assert not accumulator.is_full
    assert accumulator.get_audio().size == sample_rate * 300


def test_accumulator_caps_at_configured_limit():
    accumulator = AudioAccumulator(sample_rate=10, max_duration_seconds=1)
    accepted = accumulator.append(np.arange(15, dtype=np.float32))
    assert accepted == 10
    assert accumulator.is_full
    np.testing.assert_array_equal(accumulator.get_audio(), np.arange(10, dtype=np.float32))


def test_frames_and_partial_frame():
    audio = np.arange(1000, dtype=np.float32)
    frames = list(iter_audio_frames(audio, 16000, 20))
    assert len(frames) == 3
    partial = list(iter_audio_frames(audio, 16000, 20, include_partial=True))
    assert len(partial) == 4
    assert partial[-1].samples.size == 40


def test_reject_non_finite_audio():
    buffer = AudioRingBuffer(1, 16000)
    with pytest.raises(ValueError):
        buffer.append(np.array([np.nan], dtype=np.float32))
