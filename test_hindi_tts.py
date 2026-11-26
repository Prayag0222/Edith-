from queue import Queue

from app.voice.tts import TextToSpeech


tts = TextToSpeech()

try:
    print("Testing English...")
    tts.speak("Hello! I am EDITH. How can I help you?")

    print("Testing Hindi...")
    tts.speak("नमस्ते! मैं एडिथ हूँ। आपकी सहायता के लिए तैयार हूँ।")

    print("Testing mixed Hindi-English...")
    tts.speak("आपका scooter ready है। आपकी battery बिल्कुल ठीक है।")

    print("All tests completed.")

finally:
    tts.close()