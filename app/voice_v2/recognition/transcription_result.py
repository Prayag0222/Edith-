from dataclasses import asdict, dataclass
@dataclass(frozen=True, slots=True)
class TranscriptionSegment:
    start: float
    end: float
    text: str
@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    text: str
    language: str | None
    language_probability: float | None
    model_size: str
    device: str
    compute_type: str
    selection_reason: str
    processing_seconds: float
    audio_duration_seconds: float | None
    task_type: str
    classification_confidence: float
    classification_reason: str
    segments: tuple[TranscriptionSegment, ...]
    def to_dict(self):
        return asdict(self)
