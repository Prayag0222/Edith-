import math
import subprocess
import threading
import time

from dataclasses import dataclass

import ctranslate2


@dataclass(frozen=True, slots=True)
class VoiceDecision:
    model_size: str
    device: str
    compute_type: str
    reason: str


class AdaptiveVoiceEngine:
    """
    Resource-aware adaptive Whisper model selection.

    CPU:
        small + int8

    GPU:
        medium + float16

    Features:
        - Asynchronous GPU monitoring
        - Non-blocking model selection
        - VRAM-aware decisions
        - GPU utilization monitoring
        - Stale statistics protection
        - Hysteresis to prevent frequent switching
        - Cached GPU model reuse when resources permit
    """

    # --------------------------------------------------
    # RESOURCE CONFIGURATION
    # --------------------------------------------------

    MIN_FREE_VRAM_MB = 1800.0

    GPU_HIGH_UTILIZATION = 75.0
    GPU_RESUME_UTILIZATION = 60.0

    # Hysteresis: require extra free VRAM before
    # switching from CPU to GPU.
    GPU_ENTRY_VRAM_MB = 2000.0

    MONITOR_INTERVAL = 2.0
    MONITOR_TIMEOUT = 2.0
    MAX_STATS_AGE = 5.0

    GPU_QUERY_COMMAND = (
        "nvidia-smi",
        "--query-gpu=utilization.gpu,memory.used,memory.total",
        "--format=csv,noheader,nounits",
    )

    FALLBACK_STATS = {
        "gpu_usage": 100.0,
        "vram_used": 0.0,
        "vram_total": 0.0,
        "vram_free": 0.0,
        "vram_usage": 100.0,
        "available": False,
    }

    # --------------------------------------------------
    # INITIALIZATION
    # --------------------------------------------------

    def __init__(self):

        self.gpu_available = self._check_gpu()

        self._stats_lock = threading.Lock()
        self._decision_lock = threading.Lock()

        self._stop_event = threading.Event()

        self._gpu_stats = self.FALLBACK_STATS.copy()

        self._last_successful_update = 0.0

        # GPU is initially not preferred until
        # valid resource information is available.
        self._gpu_preferred = False

        self._monitor_thread = None

        if self.gpu_available:

            self._monitor_thread = threading.Thread(
                target=self._monitor_gpu,
                name="EDITH-GPU-Monitor",
                daemon=True,
            )

            self._monitor_thread.start()

    # --------------------------------------------------
    # CUDA DETECTION
    # --------------------------------------------------

    @staticmethod
    def _check_gpu() -> bool:

        try:
            return ctranslate2.get_cuda_device_count() > 0

        except Exception:
            return False

    # --------------------------------------------------
    # GPU MONITORING
    # --------------------------------------------------

    def _monitor_gpu(self):
        """
        Continuously monitor GPU resources.

        Runs independently of the main application thread.
        """

        while not self._stop_event.is_set():

            stats = self._query_gpu_stats()

            if stats["available"]:

                current_time = time.monotonic()

                with self._stats_lock:

                    self._gpu_stats = stats
                    self._last_successful_update = current_time

                self._update_gpu_preference(stats)

            self._stop_event.wait(
                self.MONITOR_INTERVAL
            )

    # --------------------------------------------------
    # GPU STATISTICS QUERY
    # --------------------------------------------------

    def _query_gpu_stats(self) -> dict:

        try:

            result = subprocess.run(
                self.GPU_QUERY_COMMAND,
                capture_output=True,
                text=True,
                timeout=self.MONITOR_TIMEOUT,
                check=False,
            )

            if result.returncode != 0:
                return self.FALLBACK_STATS.copy()

            lines = result.stdout.strip().splitlines()

            if not lines:
                return self.FALLBACK_STATS.copy()

            values = [
                float(value.strip())
                for value in lines[0].split(",")
            ]

            if len(values) != 3:
                return self.FALLBACK_STATS.copy()

            gpu_usage, vram_used, vram_total = values

            if not all(
                math.isfinite(value)
                for value in values
            ):
                return self.FALLBACK_STATS.copy()

            if (
                gpu_usage < 0
                or gpu_usage > 100
                or vram_used < 0
                or vram_total <= 0
                or vram_used > vram_total
            ):
                return self.FALLBACK_STATS.copy()

            vram_free = vram_total - vram_used

            vram_usage = (
                vram_used / vram_total
            ) * 100.0

            return {
                "gpu_usage": gpu_usage,
                "vram_used": vram_used,
                "vram_total": vram_total,
                "vram_free": vram_free,
                "vram_usage": vram_usage,
                "available": True,
            }

        except (
            OSError,
            ValueError,
            IndexError,
            subprocess.SubprocessError,
        ):

            return self.FALLBACK_STATS.copy()

    # --------------------------------------------------
    # GPU PREFERENCE / HYSTERESIS
    # --------------------------------------------------

    def _update_gpu_preference(self, stats: dict):
        """
        Prevent rapid switching between CPU and GPU.

        GPU entry requires:
            - At least 2000 MB free VRAM
            - GPU utilization <= 60%

        GPU exit occurs when:
            - Free VRAM falls below 1800 MB
            - GPU utilization reaches 75%
        """

        gpu_usage = stats["gpu_usage"]
        vram_free = stats["vram_free"]

        with self._decision_lock:

            if self._gpu_preferred:

                if (
                    vram_free < self.MIN_FREE_VRAM_MB
                    or gpu_usage >= self.GPU_HIGH_UTILIZATION
                ):
                    self._gpu_preferred = False

            else:

                if (
                    vram_free >= self.GPU_ENTRY_VRAM_MB
                    and gpu_usage <= self.GPU_RESUME_UTILIZATION
                ):
                    self._gpu_preferred = True

    # --------------------------------------------------
    # GPU STATISTICS
    # --------------------------------------------------

    def get_gpu_stats(self) -> dict:
        """
        Return the latest GPU snapshot.

        Never launches a subprocess.
        Never waits for GPU monitoring.
        """

        with self._stats_lock:

            stats = self._gpu_stats.copy()

            last_update = self._last_successful_update

        if last_update == 0.0:

            stats["available"] = False
            stats["stale"] = True
            stats["age_seconds"] = None

            return stats

        age = time.monotonic() - last_update

        stats["age_seconds"] = round(age, 2)
        stats["stale"] = age > self.MAX_STATS_AGE

        if stats["stale"]:
            stats["available"] = False

        return stats

    # --------------------------------------------------
    # MODEL SELECTION
    # --------------------------------------------------

    def choose_model(
        self,
        task_type: str = "conversation",
        gpu_model_loaded: bool = False,
    ) -> VoiceDecision:

        # CUDA unavailable.
        if not self.gpu_available:

            return VoiceDecision(
                "small",
                "cpu",
                "int8",
                "GPU unavailable",
            )

        stats = self.get_gpu_stats()

        # No valid or sufficiently recent GPU statistics.
        if not stats["available"]:

            return VoiceDecision(
                "small",
                "cpu",
                "int8",
                "GPU statistics unavailable or stale",
            )

        gpu_usage = stats["gpu_usage"]
        vram_free = stats["vram_free"]

        # Immediate protection against GPU pressure.
        if vram_free < self.MIN_FREE_VRAM_MB:

            return VoiceDecision(
                "small",
                "cpu",
                "int8",
                f"Insufficient free VRAM ({vram_free:.0f} MB)",
            )

        if gpu_usage >= self.GPU_HIGH_UTILIZATION:

            return VoiceDecision(
                "small",
                "cpu",
                "int8",
                f"GPU busy ({gpu_usage:.0f}%)",
            )

        # Apply hysteresis state.
        with self._decision_lock:

            gpu_preferred = self._gpu_preferred

        if not gpu_preferred:

            return VoiceDecision(
                "small",
                "cpu",
                "int8",
                "GPU resources not sufficiently idle",
            )

        # Reuse the already-loaded GPU model.
        if gpu_model_loaded:

            return VoiceDecision(
                "medium",
                "cuda",
                "float16",
                "Reusing cached GPU model",
            )

        # Sufficient GPU resources.
        return VoiceDecision(
            "medium",
            "cuda",
            "float16",
            (
                f"GPU available for {task_type} "
                f"({gpu_usage:.0f}% utilization, "
                f"{vram_free:.0f} MB free VRAM)"
            ),
        )

    # --------------------------------------------------
    # PUBLIC INTERFACE
    # --------------------------------------------------

    def get_decision(
        self,
        task_type: str = "conversation",
        gpu_model_loaded: bool = False,
    ) -> VoiceDecision:

        return self.choose_model(
            task_type=task_type,
            gpu_model_loaded=gpu_model_loaded,
        )

    # --------------------------------------------------
    # SHUTDOWN
    # --------------------------------------------------

    def close(self):
        """Stop the background GPU monitoring thread."""

        self._stop_event.set()

        if (
            self._monitor_thread is not None
            and self._monitor_thread.is_alive()
        ):

            self._monitor_thread.join(timeout=0.5)