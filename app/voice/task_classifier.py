from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class TaskClassification:
    task_type: str
    confidence: float
    reason: str


class VoiceTaskClassifier:
    """
    Lightweight rule-based voice task classifier.

    Categories:
        command
        conversation
        unknown

    No LLM, GPU or external dependencies.
    """

    # --------------------------------------------------
    # PRECOMPILED PATTERNS
    # --------------------------------------------------

    COMMAND_PATTERN = re.compile(
        r"^(?:"
        r"open|close|launch|start|stop|play|pause|resume|"
        r"turn on|turn off|enable|disable|increase|decrease|"
        r"raise|lower|mute|unmute|set|restart|shutdown|"
        r"lock|search|go to|show|check"
        r")\b"
    )

    CONVERSATION_PATTERN = re.compile(
        r"\b(?:"
        r"why|how|what|when|where|who|explain|"
        r"tell me|can you explain|do you think|"
        r"what do you think"
        r")\b"
    )

    # --------------------------------------------------
    # CLASSIFICATION
    # --------------------------------------------------

    def classify(self, text: str) -> TaskClassification:

        if not isinstance(text, str) or not text.strip():
            return TaskClassification(
                task_type="unknown",
                confidence=0.0,
                reason="Empty transcription",
            )

        # Normalize text once.
        text = " ".join(text.lower().split())

        # ----------------------------------------------
        # COMMAND DETECTION
        # ----------------------------------------------

        if self.COMMAND_PATTERN.search(text):

            return TaskClassification(
                task_type="command",
                confidence=0.90,
                reason="Command pattern detected",
            )

        # ----------------------------------------------
        # CONVERSATION DETECTION
        # ----------------------------------------------

        if self.CONVERSATION_PATTERN.search(text):

            return TaskClassification(
                task_type="conversation",
                confidence=0.90,
                reason="Conversation pattern detected",
            )

        # ----------------------------------------------
        # SHORT UTTERANCE HEURISTIC
        # ----------------------------------------------

        word_count = len(text.split())

        if word_count <= 5:

            return TaskClassification(
                task_type="command",
                confidence=0.60,
                reason=(
                    "Short utterance with no "
                    "conversation pattern"
                ),
            )

        # ----------------------------------------------
        # DEFAULT
        # ----------------------------------------------

        return TaskClassification(
            task_type="conversation",
            confidence=0.70,
            reason=(
                "No command pattern detected; "
                "defaulting to conversation"
            ),
        )