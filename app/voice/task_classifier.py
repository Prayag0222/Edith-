from dataclasses import dataclass
import re


@dataclass
class TaskClassification:
    task_type: str
    confidence: float
    reason: str


class VoiceTaskClassifier:
    """
    Classifies transcribed speech into:

        command
        conversation

    This is intentionally lightweight.

    It does NOT use an LLM or GPU.
    """

    COMMAND_PATTERNS = [
        r"^open\b",
        r"^close\b",
        r"^launch\b",
        r"^start\b",
        r"^stop\b",
        r"^play\b",
        r"^pause\b",
        r"^resume\b",
        r"^turn on\b",
        r"^turn off\b",
        r"^enable\b",
        r"^disable\b",
        r"^increase\b",
        r"^decrease\b",
        r"^raise\b",
        r"^lower\b",
        r"^mute\b",
        r"^unmute\b",
        r"^set\b",
        r"^restart\b",
        r"^shutdown\b",
        r"^lock\b",
        r"^search\b",
        r"^go to\b",
        r"^show\b",
        r"^check\b",
    ]

    CONVERSATION_PATTERNS = [
        r"\bwhy\b",
        r"\bhow\b",
        r"\bwhat\b",
        r"\bwhen\b",
        r"\bwhere\b",
        r"\bwho\b",
        r"\bexplain\b",
        r"\btell me\b",
        r"\bcan you explain\b",
        r"\bdo you think\b",
        r"\bwhat do you think\b",
    ]

    def classify(
        self,
        text: str,
    ) -> TaskClassification:

        if not text:
            return TaskClassification(
                task_type="unknown",
                confidence=0.0,
                reason="Empty transcription",
            )

        text = text.strip().lower()

        # Remove excessive whitespace.
        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        # -----------------------------------------
        # COMMAND DETECTION
        # -----------------------------------------

        for pattern in self.COMMAND_PATTERNS:

            if re.search(
                pattern,
                text,
            ):
                return TaskClassification(
                    task_type="command",
                    confidence=0.90,
                    reason=(
                        "Command pattern detected"
                    ),
                )

        # -----------------------------------------
        # CONVERSATION DETECTION
        # -----------------------------------------

        for pattern in self.CONVERSATION_PATTERNS:

            if re.search(
                pattern,
                text,
            ):
                return TaskClassification(
                    task_type="conversation",
                    confidence=0.90,
                    reason=(
                        "Conversation pattern detected"
                    ),
                )

        # -----------------------------------------
        # SHORT UTTERANCE HEURISTIC
        # -----------------------------------------

        words = text.split()

        if len(words) <= 5:

            return TaskClassification(
                task_type="command",
                confidence=0.60,
                reason=(
                    "Short utterance with no "
                    "conversation pattern"
                ),
            )

        # -----------------------------------------
        # DEFAULT
        # -----------------------------------------

        return TaskClassification(
            task_type="conversation",
            confidence=0.70,
            reason=(
                "No command pattern detected; "
                "defaulting to conversation"
            ),
        )