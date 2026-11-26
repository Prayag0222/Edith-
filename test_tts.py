from app.voice.tts import TextToSpeech

tts = TextToSpeech()

try:

    print("\n========== ENGLISH TEST ==========")

    tts.speak(
        "Hello! I am EDITH, your personal artificial "
        "intelligence assistant. I can help you manage "
        "your projects, answer questions, and perform "
        "your daily tasks. I am ready to assist you."
    )

    print("\n========== HINDI TEST ==========")

    tts.speak(
        "नमस्ते! मैं एडिथ हूँ, आपकी व्यक्तिगत सहायक। "
        "मैं आपकी बातों को समझ सकती हूँ और आपके सवालों "
        "के जवाब दे सकती हूँ। मैं आपके निर्देशों का "
        "इंतज़ार कर रही हूँ।"
    )

finally:
    tts.close()