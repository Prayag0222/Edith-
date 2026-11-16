from abc import ABC, abstractmethod
class STTBackend(ABC):
    @abstractmethod
    def transcribe(self, audio, **kwargs): raise NotImplementedError
    @abstractmethod
    def close(self): raise NotImplementedError
