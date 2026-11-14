import threading
import time
import unittest
from unittest.mock import patch

from app.conversation.service import ConversationService
from app.core.assistant import EdithAssistant
from app.llm.client import OllamaClient
from app.memory.background_worker import BackgroundMemoryWorker


class _Vector:
    def tolist(self):
        return [0.0, 1.0]


class _Embeddings:
    def encode(self, text):
        return _Vector()


class _MemoryService:
    def __init__(self):
        self.embedding_service = _Embeddings()
        self.sync_writes = []

    def store_message(self, *args):
        self.sync_writes.append(args)

    def get_context(self, text):
        return "memory context"


class _MemoryManager:
    def __init__(self):
        self.messages = []

    def process_message(self, message):
        self.messages.append(message)
        return []


class _LLM:
    def generate_stream(self, messages, memory_context=""):
        yield "Reply."


class BackgroundMemoryWorkerTests(unittest.TestCase):
    def test_synchronous_fallback_and_conversation_trimming_remain(self):
        memory = _MemoryService()
        manager = _MemoryManager()
        conversation = ConversationService(memory)

        for index in range(conversation.max_messages + 1):
            conversation.add_assistant_message(str(index))

        conversation.process_user_memory("remember me", manager)

        self.assertEqual(len(conversation.get_messages()), 20)
        self.assertEqual(len(memory.sync_writes), 21)
        self.assertEqual(manager.messages, ["remember me"])

    def test_assistant_routes_messages_and_extraction_to_worker(self):
        memory = _MemoryService()
        manager = _MemoryManager()
        worker = BackgroundMemoryWorker(memory, manager)
        conversation = ConversationService(memory, worker)

        with patch(
            "app.memory.background_worker.save_message",
            side_effect=[1, 2],
        ) as save_message, patch(
            "app.memory.background_worker.save_embedding",
        ) as save_embedding:
            try:
                response = EdithAssistant().respond(
                    conversation,
                    _LLM(),
                    manager,
                    "Remember this.",
                )
                worker.close()
            finally:
                if not worker.shutdown_event.is_set():
                    worker.close()

        self.assertEqual(response, "Reply.")
        self.assertEqual(memory.sync_writes, [])
        self.assertEqual(save_message.call_count, 2)
        self.assertEqual(save_embedding.call_count, 1)
        self.assertEqual(manager.messages, ["Remember this."])

    def test_foreground_streams_share_worker_request_lock(self):
        class Edith:
            def get_identity(self):
                return {
                    "name": "EDITH",
                    "creator": "Prayag",
                    "administrator": "Prayag",
                }

            def get_self_description(self):
                return "assistant"

        client = OllamaClient(Edith())
        worker = BackgroundMemoryWorker(object(), object(), client)
        self.assertIs(worker.llm_lock, client.request_lock)
        worker.close()

        active = 0
        maximum_active = 0
        active_lock = threading.Lock()
        start = threading.Barrier(3)

        def fake_stream(messages, memory_context=""):
            nonlocal active, maximum_active
            with active_lock:
                active += 1
                maximum_active = max(maximum_active, active)
            time.sleep(0.05)
            yield "ok"
            with active_lock:
                active -= 1

        client._generate_stream = fake_stream

        def generate():
            start.wait()
            self.assertEqual("".join(client.generate_stream([])), "ok")

        threads = [threading.Thread(target=generate) for _ in range(2)]
        for thread in threads:
            thread.start()

        start.wait()

        for thread in threads:
            thread.join()

        self.assertEqual(maximum_active, 1)


if __name__ == "__main__":
    unittest.main()
