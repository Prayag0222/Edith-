import pytest
from app.voice_v2.core.audio_input import AudioInputConfig


def test_default_config():
    config = AudioInputConfig(start=False)
    assert config.sample_rate == 16000
    assert config.block_size == 320
    assert config.channels == 1


@pytest.mark.parametrize("duration", [10, 20, 30])
def test_block_sizes(duration):
    config = AudioInputConfig(block_duration_ms=duration, start=False)
    assert config.block_size == 16000 * duration // 1000


def test_rejects_stereo():
    with pytest.raises(ValueError):
        AudioInputConfig(channels=2, start=False)


def test_rejects_invalid_duration():
    with pytest.raises(ValueError):
        AudioInputConfig(block_duration_ms=15, start=False)
