from pathlib import Path

text = """नमस्ते! मेरा नाम एडिथ है।
मैं आपकी व्यक्तिगत एआई सहायक हूँ।
मैं आपकी सहायता करने के लिए तैयार हूँ।"""

print("Hindi:", text)
print("Unicode detected:", any('\u0900' <= c <= '\u097F' for c in text))

Path("hindi_test.txt").write_text(text, encoding="utf-8")