from dataclasses import dataclass
@dataclass(frozen=True, slots=True)
class STTConfig:
    model_size: str = "small"
    sample_rate: int = 16000
    device_preference: str = "auto"
    cpu_compute_type: str = "int8"
    language: str | None = None
    task: str = "transcribe"
    beam_size: int = 5
    vad_filter: bool = False
    condition_on_previous_text: bool = False
    local_files_only: bool = True
    download_root: str | None = None
    gpu_min_free_vram_mb: float = 1800.0
    gpu_max_utilization: float = 75.0
    inference_lock: bool = True
    def __post_init__(self):
        if self.sample_rate not in (8000, 16000, 22050, 44100, 48000): raise ValueError("Unsupported sample rate")
        if not self.model_size: raise ValueError("model_size cannot be empty")
        if self.device_preference not in {"auto", "cuda", "cpu"}: raise ValueError("Invalid device_preference")
        if self.task not in {"transcribe", "translate"}: raise ValueError("Invalid task")
        if self.beam_size < 1: raise ValueError("beam_size must be >= 1")
        if self.gpu_min_free_vram_mb < 0: raise ValueError("Invalid VRAM threshold")
        if not 0 <= self.gpu_max_utilization <= 100: raise ValueError("Invalid GPU utilization threshold")
