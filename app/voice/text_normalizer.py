import re
import html


def normalize_for_speech(text: str) -> str:
    if not text:
        return ""

    text = html.unescape(text)

    # Remove code blocks.
    text = re.sub(r"```[\s\S]*?```", " ", text)

    # Remove inline code formatting, preserve its content.
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Convert Markdown links to their readable labels.
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove Markdown headings.
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)

    # Remove blockquote markers.
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)

    # Remove bullet and numbered-list markers.
    text = re.sub(
        r"^\s*(?:[-*+]|\d+[.)])\s+",
        "",
        text,
        flags=re.MULTILINE,
    )

    # Preserve text inside brackets and parentheses.
    # Remove only the surrounding formatting symbols.
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"__(.*?)__", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"(?<!\*)\*(?!\s)(.*?)\*(?!\*)", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"(?<!_)_(?!\s)(.*?)_(?!_)", r"\1", text, flags=re.DOTALL)

    # Remove HTML tags.
    text = re.sub(r"<[^>]+>", " ", text)

    # Remove decorative symbols that should not be spoken.
    text = re.sub(r"[#*_~`]", "", text)

    # Normalize whitespace.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", " ", text)

    return text.strip()