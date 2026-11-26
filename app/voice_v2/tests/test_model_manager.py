from app.voice_v2.recognition.config import STTConfig
from app.voice_v2.recognition.model_manager import ModelDecision,WhisperModelManager
class Selector:
    def __init__(self,d): self.d=d
    def choose(self,size,preference): return self.d
def test_lazy_cache():
    calls=[]
    def factory(size,**kwargs): calls.append(kwargs); return object()
    m=WhisperModelManager(STTConfig(),Selector(ModelDecision("small","cpu","int8","test")),factory)
    a,_=m.get_model(); b,_=m.get_model()
    assert a is b and len(calls)==1
    m.close()

def test_model_reloads_after_cache_is_released():
    calls=[]
    def factory(size,**kwargs): calls.append(kwargs); return object()
    m=WhisperModelManager(STTConfig(),Selector(ModelDecision("small","cpu","int8","test")),factory)
    first,_=m.get_model()
    m.close()
    second,_=m.get_model()
    assert second is not first and len(calls)==2
    m.close()

def test_gpu_load_fallback():
    calls=[]
    def factory(size,**kwargs):
        calls.append(kwargs["device"])
        if kwargs["device"]=="cuda": raise RuntimeError("GPU load failed")
        return object()
    m=WhisperModelManager(STTConfig(),Selector(ModelDecision("small","cuda","float16","test")),factory)
    model,d=m.get_model()
    assert model is not None and d.device=="cpu" and calls==["cuda","cpu"]
    m.close()
