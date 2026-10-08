from app.voice.adaptive_engine import AdaptiveVoiceEngine


engine = AdaptiveVoiceEngine()

print("\n==============================")
print("EDITH ADAPTIVE VOICE TEST")
print("==============================")

print(
    f"\nGPU available: {engine.gpu_available}"
)

print(
    f"GPU usage: {engine.get_gpu_usage()}%"
)


print("\n--- COMMAND ---")

decision = engine.get_decision("command")

print(f"Model: {decision.model_size}")
print(f"Device: {decision.device}")
print(f"Compute: {decision.compute_type}")
print(f"Reason: {decision.reason}")


print("\n--- CONVERSATION ---")

decision = engine.get_decision("conversation")

print(f"Model: {decision.model_size}")
print(f"Device: {decision.device}")
print(f"Compute: {decision.compute_type}")
print(f"Reason: {decision.reason}")

print()