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

    # EDITH will avoid using the GPU when utilization reaches this level.
    GPU_BUSY_THRESHOLD = 40.0

    # EDITH will avoid loading the medium model when VRAM usage
    # reaches this percentage.
    VRAM_BUSY_THRESHOLD = 60.0

    def __init__(self):
        self.gpu_available = self._check_gpu()

    def _check_gpu(self) -> bool:
        """
        Check whether CTranslate2 can see an NVIDIA CUDA device.
        """

        try:
            return (
                ctranslate2.get_cuda_device_count()
                > 0
            )

        except Exception:
            return False

    def get_gpu_stats(self) -> dict:
        """
        Read the current GPU utilization and VRAM usage.

        Returns:

            {
                "gpu_usage": 0.0,
                "vram_used": 500.0,
                "vram_total": 4096.0,
                "vram_usage": 12.2
            }

        If monitoring fails, we return conservative values
        that force EDITH toward CPU inference.
        """

        try:

            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu="
                    "utilization.gpu,"
                    "memory.used,"
                    "memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )

            if result.returncode != 0:
                return {
                    "gpu_usage": 100.0,
                    "vram_used": 100.0,
                    "vram_total": 100.0,
                    "vram_usage": 100.0,
                }

            line = (
                result.stdout
                .strip()
                .splitlines()[0]
            )

            values = [
                float(value.strip())
                for value in line.split(",")
            ]

            gpu_usage = values[0]
            vram_used = values[1]
            vram_total = values[2]

            if vram_total <= 0:
                vram_usage = 100.0

            else:
                vram_usage = (
                    vram_used
                    / vram_total
                ) * 100.0

            return {
                "gpu_usage": gpu_usage,
                "vram_used": vram_used,
                "vram_total": vram_total,
                "vram_usage": vram_usage,
            }

        except Exception:

            return {
                "gpu_usage": 100.0,
                "vram_used": 100.0,
                "vram_total": 100.0,
                "vram_usage": 100.0,
            }

    def get_gpu_usage(self) -> float:
        """
        Backward-compatible helper.

        Returns GPU compute utilization percentage.
        """

        stats = self.get_gpu_stats()

        return stats["gpu_usage"]

    def get_vram_usage(self) -> float:
        """
        Return current VRAM usage percentage.
        """

        stats = self.get_gpu_stats()

        return stats["vram_usage"]

    def is_gpu_busy(self) -> bool:
        """
        Determine whether the GPU is too busy for EDITH.

        EDITH considers the GPU busy when either:

            GPU compute utilization >= 40%

        OR:

            VRAM usage >= 60%
        """

        stats = self.get_gpu_stats()

        gpu_busy = (
            stats["gpu_usage"]
            >= self.GPU_BUSY_THRESHOLD
        )

        vram_busy = (
            stats["vram_usage"]
            >= self.VRAM_BUSY_THRESHOLD
        )

        return gpu_busy or vram_busy

    def choose_model(
        self,
        task_type: str = "conversation",
    ) -> VoiceDecision:

        # --------------------------------
        # 1. No CUDA GPU
        # --------------------------------

        if not self.gpu_available:

            return VoiceDecision(
                model_size="small",
                device="cpu",
                compute_type="int8",
                reason="GPU unavailable",
            )

        # --------------------------------
        # 2. Simple command
        # --------------------------------

        if task_type == "command":

            return VoiceDecision(
                model_size="small",
                device="cpu",
                compute_type="int8",
                reason="Simple command",
            )

        # --------------------------------
        # 3. Check GPU resources
        # --------------------------------

        stats = self.get_gpu_stats()

        gpu_usage = stats["gpu_usage"]
        vram_usage = stats["vram_usage"]

        # --------------------------------
        # 4. GPU too busy
        # --------------------------------

        if (
            gpu_usage
            >= self.GPU_BUSY_THRESHOLD
        ):

            return VoiceDecision(
                model_size="small",
                device="cpu",
                compute_type="int8",
                reason=(
                    f"GPU busy "
                    f"({gpu_usage:.1f}%)"
                ),
            )

        # --------------------------------
        # 5. VRAM too full
        # --------------------------------

        if (
            vram_usage
            >= self.VRAM_BUSY_THRESHOLD
        ):

            return VoiceDecision(
                model_size="small",
                device="cpu",
                compute_type="int8",
                reason=(
                    f"VRAM busy "
                    f"({vram_usage:.1f}%)"
                ),
            )

        # --------------------------------
        # 6. GPU has enough resources
        # --------------------------------

        return VoiceDecision(
            model_size="medium",
            device="cuda",
            compute_type="float16",
            reason=(
                f"GPU resources available "
                f"(GPU {gpu_usage:.1f}%, "
                f"VRAM {vram_usage:.1f}%)"
            ),
        )

    def get_decision(
        self,
        task_type: str = "conversation",
    ) -> VoiceDecision:

        return self.choose_model(
            task_type
        )


if __name__ == "__main__":

    engine = AdaptiveVoiceEngine()

    print()
    print("=" * 50)
    print("EDITH GPU RESOURCE TEST")
    print("=" * 50)

    print()

    print(
        f"GPU available: "
        f"{engine.gpu_available}"
    )

    stats = engine.get_gpu_stats()

    print(
        f"GPU usage: "
        f"{stats['gpu_usage']:.1f}%"
    )

    print(
        f"VRAM used: "
        f"{stats['vram_used']:.0f} MB"
    )

    print(
        f"VRAM total: "
        f"{stats['vram_total']:.0f} MB"
    )

    print(
        f"VRAM usage: "
        f"{stats['vram_usage']:.1f}%"
    )

    print()

    command_decision = (
        engine.get_decision(
            "command"
        )
    )

    print("--- COMMAND ---")

    print(
        f"Model: "
        f"{command_decision.model_size}"
    )

    print(
        f"Device: "
        f"{command_decision.device}"
    )

    print(
        f"Compute: "
        f"{command_decision.compute_type}"
    )

    print(
        f"Reason: "
        f"{command_decision.reason}"
    )

    print()

    conversation_decision = (
        engine.get_decision(
            "conversation"
        )
    )

    print("--- CONVERSATION ---")

    print(
        f"Model: "
        f"{conversation_decision.model_size}"
    )

    print(
        f"Device: "
        f"{conversation_decision.device}"
    )

    print(
        f"Compute: "
        f"{conversation_decision.compute_type}"
    )

    print(
        f"Reason: "
        f"{conversation_decision.reason}"
    )