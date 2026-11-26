from dataclasses import dataclass
import gc
import subprocess
import threading
import numpy as np

@dataclass(frozen=True, slots=True)
class ModelDecision:
    model_size: str
    device: str
    compute_type: str
    reason: str

class GPUResourceSelector:
    def __init__(self, min_free_vram_mb=1800.0, max_gpu_utilization=75.0):
        self.min_free_vram_mb = min_free_vram_mb
        self.max_gpu_utilization = max_gpu_utilization

    @staticmethod
    def cuda_available():
        try:
            import ctranslate2
            return ctranslate2.get_cuda_device_count() > 0
        except Exception:
            return False

    @staticmethod
    def query_stats():
        cmd = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.free,memory.total", "--format=csv,noheader,nounits"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=2, check=False)
            if r.returncode: return None
            v = [float(x.strip()) for x in r.stdout.strip().splitlines()[0].split(",")]
            if len(v) != 3 or not all(np.isfinite(x) for x in v): return None
            util, free, total = v
            if not (0 <= util <= 100 and 0 <= free <= total and total > 0): return None
            return {"gpu_utilization": util, "free_vram_mb": free, "total_vram_mb": total}
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            return None

    def choose(self, model_size, preference):
        if preference == "cpu":
            return ModelDecision(model_size, "cpu", "int8", "CPU explicitly selected")
        if not self.cuda_available():
            return ModelDecision(model_size, "cpu", "int8", "CUDA unavailable")
        stats = self.query_stats()
        if stats is None:
            if preference == "cuda":
                return ModelDecision(model_size, "cuda", "float16", "CUDA forced; GPU stats unavailable")
            return ModelDecision(model_size, "cpu", "int8", "GPU stats unavailable; CPU fallback")
        if stats["free_vram_mb"] < self.min_free_vram_mb:
            if preference == "cuda":
                return ModelDecision(model_size, "cuda", "float16", "CUDA forced despite low free VRAM")
            return ModelDecision(model_size, "cpu", "int8", f"Insufficient free VRAM ({stats['free_vram_mb']:.0f} MB)")
        if stats["gpu_utilization"] >= self.max_gpu_utilization:
            if preference == "cuda":
                return ModelDecision(model_size, "cuda", "float16", "CUDA forced while GPU is busy")
            return ModelDecision(model_size, "cpu", "int8", f"GPU busy ({stats['gpu_utilization']:.0f}%)")
        return ModelDecision(model_size, "cuda", "float16", f"GPU available ({stats['gpu_utilization']:.0f}%, {stats['free_vram_mb']:.0f} MB free)")

class WhisperModelManager:
    # Lazy, thread-safe cache. Only one model object is retained at a time.
    def __init__(self, config, resource_selector=None, model_factory=None):
        self.config = config
        self.selector = resource_selector or GPUResourceSelector(config.gpu_min_free_vram_mb, config.gpu_max_utilization)
        self.model_factory = model_factory
        self._model = None
        self._key = None
        self._lock = threading.RLock()
        self.last_decision = None
        self.last_load_error = None

    def _create(self, decision):
        factory = self.model_factory
        if factory is None:
            from faster_whisper import WhisperModel
            factory = WhisperModel
        kwargs = {"device": decision.device, "compute_type": decision.compute_type,
                  "local_files_only": self.config.local_files_only,
                  "cpu_threads": self.config.cpu_threads}
        if self.config.download_root:
            kwargs["download_root"] = self.config.download_root
        return factory(decision.model_size, **kwargs)

    def _load(self, decision):
        key = (decision.model_size, decision.device, decision.compute_type)
        if self._model is not None and self._key == key:
            self.last_decision = decision
            return self._model
        self._model = self._key = None
        gc.collect()
        model = self._create(decision)
        self._model, self._key = model, key
        self.last_decision, self.last_load_error = decision, None
        return model

    def get_model(self):
        with self._lock:
            decision = self.selector.choose(self.config.model_size, self.config.device_preference)
            try:
                return self._load(decision), decision
            except Exception as exc:
                self.last_load_error = f"{type(exc).__name__}: {exc}"
                if decision.device != "cuda": raise
                fallback = ModelDecision(self.config.model_size, "cpu", self.config.cpu_compute_type,
                                          f"GPU load failed; CPU fallback: {self.last_load_error}")
                return self._load(fallback), fallback

    def get_cpu_model(self):
        decision = ModelDecision(self.config.model_size, "cpu", self.config.cpu_compute_type, "CPU fallback requested")
        with self._lock:
            return self._load(decision), decision

    def status(self):
        with self._lock:
            return {"loaded": self._model is not None, "cache_key": self._key,
                    "last_decision": self.last_decision, "last_load_error": self.last_load_error}

    def close(self):
        with self._lock:
            self._model = self._key = self.last_decision = None
            gc.collect()
