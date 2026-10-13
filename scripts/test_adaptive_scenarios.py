from app.voice.adaptive_engine import AdaptiveVoiceEngine


def print_decision(
    title: str,
    engine: AdaptiveVoiceEngine,
    task_type: str,
):
    decision = engine.get_decision(
        task_type
    )

    print()
    print("=" * 60)
    print(title)
    print("=" * 60)

    print(
        f"Task: {task_type}"
    )

    print(
        f"Model: {decision.model_size}"
    )

    print(
        f"Device: {decision.device}"
    )

    print(
        f"Compute: {decision.compute_type}"
    )

    print(
        f"Reason: {decision.reason}"
    )


def main():

    engine = AdaptiveVoiceEngine()

    print()
    print("=" * 60)
    print("EDITH ADAPTIVE RESOURCE SCENARIO TEST")
    print("=" * 60)

    # --------------------------------------------------
    # Scenario 1: GPU completely idle
    # --------------------------------------------------

    engine.gpu_available = True

    engine.get_gpu_stats = lambda: {
        "gpu_usage": 0.0,
        "vram_used": 113.0,
        "vram_total": 4096.0,
        "vram_usage": 2.8,
    }

    print_decision(
        "SCENARIO 1 — GPU IDLE",
        engine,
        "conversation",
    )

    # --------------------------------------------------
    # Scenario 2: GPU heavily utilized
    # --------------------------------------------------

    engine.get_gpu_stats = lambda: {
        "gpu_usage": 85.0,
        "vram_used": 1500.0,
        "vram_total": 4096.0,
        "vram_usage": 36.6,
    }

    print_decision(
        "SCENARIO 2 — GPU HEAVY LOAD",
        engine,
        "conversation",
    )

    # --------------------------------------------------
    # Scenario 3: VRAM heavily utilized
    # --------------------------------------------------

    engine.get_gpu_stats = lambda: {
        "gpu_usage": 10.0,
        "vram_used": 3600.0,
        "vram_total": 4096.0,
        "vram_usage": 87.9,
    }

    print_decision(
        "SCENARIO 3 — VRAM HEAVY LOAD",
        engine,
        "conversation",
    )

    # --------------------------------------------------
    # Scenario 4: GPU unavailable
    # --------------------------------------------------

    engine.gpu_available = False

    print_decision(
        "SCENARIO 4 — GPU UNAVAILABLE",
        engine,
        "conversation",
    )

    # --------------------------------------------------
    # Scenario 5: Command always uses CPU
    # --------------------------------------------------

    engine.gpu_available = True

    engine.get_gpu_stats = lambda: {
        "gpu_usage": 0.0,
        "vram_used": 113.0,
        "vram_total": 4096.0,
        "vram_usage": 2.8,
    }

    print_decision(
        "SCENARIO 5 — SIMPLE COMMAND",
        engine,
        "command",
    )


if __name__ == "__main__":
    main()