from app.voice.task_classifier import VoiceTaskClassifier
classifier = VoiceTaskClassifier()


tests = [
    "open calculator",
    "close chrome",
    "increase laptop volume",
    "mute my laptop",
    "turn off wifi",
    "why is my GPU usage high",
    "explain how CUDA works",
    "what is a transformer model",
    "tell me about my EV battery",
    "I am building a personal AI assistant",
]


print()
print("=" * 60)
print("EDITH VOICE TASK CLASSIFIER TEST")
print("=" * 60)
print()


for text in tests:

    result = classifier.classify(
        text
    )

    print(
        f"TEXT: {text}"
    )

    print(
        f"TASK: {result.task_type}"
    )

    print(
        f"CONFIDENCE: {result.confidence:.2f}"
    )

    print(
        f"REASON: {result.reason}"
    )

    print("-" * 60)