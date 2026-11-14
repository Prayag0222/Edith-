import unittest

from app.conversation.service import ConversationService
from app.core.assistant import EdithAssistant
from app.memory.service import MemoryService


class _MemoryService:
    def __init__(self, events):
        self.events = events

    def get_context(self, text):
        self.events.append("retrieve")
        return "memory context"

    def store_message(self, *args):
        pass


class _BackgroundWorker:
    def __init__(self, events):
        self.events = events

    def wait_for_persistence(self):
        self.events.append("flush")

    def submit_message(self, *args):
        pass

    def submit_extraction(self, *args):
        pass


class _StructuredMemory:
    def __init__(self, memories):
        self.memories = memories

    def get_all(self):
        return self.memories


class PersonalAssistantRecallTests(unittest.TestCase):
    def test_persisted_history_is_flushed_before_memory_lookup(self):
        events = []
        conversation = ConversationService(
            _MemoryService(events),
            _BackgroundWorker(events),
        )

        class LLM:
            def generate_stream(self, messages, memory_context=""):
                events.append("generate")
                yield "Reply."

        EdithAssistant().respond(
            conversation,
            LLM(),
            object(),
            "What did we discuss earlier?",
        )

        self.assertEqual(events[:3], ["flush", "retrieve", "generate"])

    def test_structured_memory_search_prefers_specific_term_matches(self):
        service = MemoryService.__new__(MemoryService)
        editor_memory = {
            "type": "preference",
            "key": "preferred_editor",
            "value": "Visual Studio Code",
        }
        language_memory = {
            "type": "preference",
            "key": "preferred_language",
            "value": "Python",
        }
        service.structured_memory = _StructuredMemory(
            [editor_memory, language_memory]
        )

        result = service.search_structured_memories(
            "What is my preferred editor?"
        )

        self.assertEqual(result, [editor_memory])

    def test_structured_memory_search_uses_whole_terms(self):
        service = MemoryService.__new__(MemoryService)
        unrelated_memory = {
            "type": "fact",
            "key": "cartoon_preferences",
            "value": "smart characters",
        }
        service.structured_memory = _StructuredMemory(
            [unrelated_memory]
        )

        self.assertEqual(
            service.search_structured_memories("art"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
