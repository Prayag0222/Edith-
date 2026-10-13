import subprocess
from dataclasses import dataclass

import ctranslate2


@dataclass
class VoiceDecision:
    model_size: str
    device: str
    compute_type: str
    reason: str


class AdaptiveVoiceEngine:
    GPU_BUSY_THRESHOLD = 40.0
    MIN_FREE_VRAM_MB = 1800.0

    def __init__(self):
        self.gpu_available = self._check_gpu()

    @staticmethod
    def _check_gpu() -> bool:
        try:
            return ctranslate2.get_cuda_device_count() > 0
        except Exception:
            return False

    def get_gpu_stats(self) -> dict:
        fallback = {
            "gpu_usage": 100.0,
            "vram_used": 0.0,
            "vram_total": 0.0,
            "vram_free": 0.0,
            "vram_usage": 100.0,
            "available": False,
        }

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )

            if result.returncode != 0:
                return fallback

            line = result.stdout.strip().splitlines()[0]
            gpu_usage, vram_used, vram_total = (
                float(value.strip())
                for value in line.split(",")
            )

            if vram_total <= 0:
                return fallback

            vram_free = max(0.0, vram_total - vram_used)
            vram_usage = (vram_used / vram_total) * 100.0

            return {
                "gpu_usage": gpu_usage,
                "vram_used": vram_used,
                "vram_total": vram_total,
                "vram_free": vram_free,
                "vram_usage": vram_usage,
                "available": True,
            }

        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            return fallback

    def choose_model(
        self,
        task_type: str = "conversation",
        gpu_model_loaded: bool = False,
    ) -> VoiceDecision:
        if not self.gpu_available:
            return VoiceDecision(
                "small", "cpu", "int8", "GPU unavailable"
            )

        if task_type == "command":
            return VoiceDecision(
                "small", "cpu", "int8", "Simple command"
            )

        stats = self.get_gpu_stats()

        if not stats["available"]:
            return VoiceDecision(
                "small", "cpu", "int8",
                "GPU resource monitoring unavailable",
            )

        gpu_usage = stats["gpu_usage"]
        vram_free = stats["vram_free"]

        if gpu_usage >= self.GPU_BUSY_THRESHOLD:
            return VoiceDecision(
                "small", "cpu", "int8",
                f"GPU compute busy ({gpu_usage:.0f}%)",
            )

        # A cached model may be reusable even when little VRAM remains.
        # If it is already loaded, do not reject it based on free VRAM alone.
        if gpu_model_loaded:
            return VoiceDecision(
                "medium", "cuda", "float16",
                f"Reusing cached GPU model (GPU {gpu_usage:.0f}%)",
            )

        if vram_free < self.MIN_FREE_VRAM_MB:
            return VoiceDecision(
                "small", "cpu", "int8",
                f"Insufficient free VRAM ({vram_free:.0f} MB)",
            )

        return VoiceDecision(
            "medium", "cuda", "float16",
            f"GPU available (GPU {gpu_usage:.0f}%, free VRAM {vram_free:.0f} MB)",
        )

    def get_decision(
        self,
        task_type: str = "conversation",
        gpu_model_loaded: bool = False,
    ) -> VoiceDecision:
        return self.choose_model(
            task_type=task_type,
            gpu_model_loaded=gpu_model_loaded,
        )