import pytest
from app.voice_v2.recognition.config import STTConfig
def test_defaults():
    c = STTConfig()
    assert c.model_size == "small" and c.device_preference == "auto"
    assert c.local_files_only and not c.vad_filter
@pytest.mark.parametrize("kwargs", [{"device_preference":"tpu"},{"task":"summarize"},{"beam_size":0},{"gpu_max_utilization":101}])
def test_invalid_config(kwargs):
    with pytest.raises(ValueError): STTConfig(**kwargs)
