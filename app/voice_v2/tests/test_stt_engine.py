from types import SimpleNamespace
import numpy as np
import pytest
from app.voice_v2.recognition.config import STTConfig
from app.voice_v2.recognition.stt_engine import SpeechToTextEngine
from app.voice_v2.recognition.model_manager import ModelDecision
class FakeModel:
    def __init__(self, text="Open Chrome"): self.text = text
    def transcribe(self, audio, **kwargs):
        return iter([SimpleNamespace(start=0,end=1.1,text=self.text)]), SimpleNamespace(
            language="en",language_probability=.98,duration=1.2)
class FakeManager:
    def __init__(self, model): self.model=model
    def get_model(self): return self.model,ModelDecision("small","cpu","int8","test")
    def get_cpu_model(self): return self.model,ModelDecision("small","cpu","int8","fallback")
    def close(self): pass
def test_numpy_transcription():
    e=SpeechToTextEngine(STTConfig(),FakeManager(FakeModel()))
    r=e.transcribe(np.zeros(16000,np.float32))
    assert r.text=="Open Chrome" and r.language=="en" and r.audio_duration_seconds==1.2
    assert len(r.segments)==1
def test_empty_transcript():
    e=SpeechToTextEngine(STTConfig(),FakeManager(FakeModel("")))
    assert e.transcribe(np.zeros(16000,np.float32)) is None
def test_rejects_nan():
    e=SpeechToTextEngine(STTConfig(),FakeManager(FakeModel()))
    a=np.zeros(1000,np.float32); a[3]=np.nan
    with pytest.raises(ValueError,match="NaN"): e.transcribe(a)
def test_missing_file(tmp_path):
    e=SpeechToTextEngine(STTConfig(),FakeManager(FakeModel()))
    with pytest.raises(FileNotFoundError): e.transcribe_file(tmp_path/"missing.wav")
