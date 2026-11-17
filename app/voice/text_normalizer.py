import re
import html


# Precompiled patterns for faster repeated processing.
_CODE_BLOCK = re.compile(r"```[\s\S]*?```")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_BLOCKQUOTE = re.compile(r"^\s*>\s?", re.MULTILINE)
_LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+", re.MULTILINE)

_BOLD = re.compile(r"\*\*(.*?)\*\*|__(.*?)__", re.DOTALL)
_ITALIC = re.compile(
    r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)"
    r"|(?<!_)_(?!\s)(.+?)(?<!\s)_(?!_)",
    re.DOTALL,
)

_HTML_TAG = re.compile(r"<[^>]*>")
_DECORATIVE = re.compile(r"[#*_~`]")
_WHITESPACE = re.compile(r"[ \t]+")
_NEWLINES = re.compile(r"\s*\n+\s*")


def normalize_for_speech(text: str) -> str:
    """
    Convert Markdown and HTML-containing text into
    clean speech-friendly plain text.

    Preserves readable content while removing
    formatting that should not be spoken.
    """

    if not isinstance(text, str) or not text:
        return ""

    text = html.unescape(text)

    # Remove code blocks completely.
    text = _CODE_BLOCK.sub(" ", text)

    # Preserve inline code content.
    text = _INLINE_CODE.sub(r"\1", text)

    # Preserve readable Markdown link labels.
    text = _MARKDOWN_LINK.sub(r"\1", text)

    # Remove Markdown structural markers.
    text = _HEADING.sub("", text)
    text = _BLOCKQUOTE.sub("", text)
    text = _LIST_MARKER.sub("", text)

    # Preserve content inside emphasis formatting.
    text = _BOLD.sub(
        lambda match: match.group(1) or match.group(2),
        text,
    )

    text = _ITALIC.sub(
        lambda match: match.group(1) or match.group(2),
        text,
    )

    # Remove HTML tags.
    text = _HTML_TAG.sub(" ", text)

    # Remove remaining decorative Markdown characters.
    text = _DECORATIVE.sub("", text)

    # Normalize whitespace and line breaks.
    text = _WHITESPACE.sub(" ", text)
    text = _NEWLINES.sub(" ", text)

    return text.strip()