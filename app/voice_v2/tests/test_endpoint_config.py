import pytest
from app.voice_v2.detection.endpoint_detector import EndpointConfig


def test_defaults_allow_long_speech():
    config = EndpointConfig()
    assert config.max_utterance_seconds == 600
    assert config.end_silence_ms == 1000


def test_rejects_invalid_thresholds():
    with pytest.raises(ValueError):
        EndpointConfig(start_threshold=0.3, continue_threshold=0.6)
