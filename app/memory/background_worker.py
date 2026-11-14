import logging
import queue
import threading
from typing import Optional

from app.memory.message_store import save_message
from app.memory.vector_store import save_embedding

logger = logging.getLogger(__name__)


class BackgroundMemoryWorker:

    def __init__(self, memory_service, memory_manager, llm=None):
        self.memory_service = memory_service
        self.memory_manager = memory_manager
        self.llm = llm

        self.persistence_queue = queue.Queue()
        self.extraction_queue = queue.Queue()

        self.shutdown_event = threading.Event()
        self.submission_lock = threading.Lock()

        self.llm_lock = (
            getattr(llm, "request_lock", None)
            or threading.RLock()
        )

        self.persistence_thread = threading.Thread(
            target=self._persistence_loop,
            name="EDITH-Persistence-Worker",
            daemon=False,
        )

        self.extraction_thread = threading.Thread(
            target=self._extraction_loop,
            name="EDITH-Extraction-Worker",
            daemon=False,
        )

        self.persistence_thread.start()
        self.extraction_thread.start()

        logger.info("[MEMORY] Background workers started")

    # ---------------- TASK SUBMISSION ----------------

    def _ensure_running(self):
        if self.shutdown_event.is_set():
            raise RuntimeError("Memory worker is shutting down")

    def submit_message(self, session_id, role, content):

        with self.submission_lock:
            self._ensure_running()

            self.persistence_queue.put({
                "session_id": session_id,
                "role": role,
                "content": content,
            })

    def submit_extraction(self, user_message):

        with self.submission_lock:
            self._ensure_running()
            self.extraction_queue.put(user_message)

    # ---------------- PERSISTENCE ----------------

    def _persistence_loop(self):

        while True:
            task = self.persistence_queue.get()

            try:
                if task is None:
                    break

                self._save_message(task)

            except Exception:
                logger.exception("[MEMORY] Persistence failed")

            finally:
                self.persistence_queue.task_done()

        logger.info("[MEMORY] Persistence worker stopped")

    def _save_message(self, task):

        message_id = save_message(
            task["session_id"],
            task["role"],
            task["content"],
        )

        if task["role"] == "user":
            embedding = self.memory_service.embedding_service.encode(
                task["content"]
            )

            save_embedding(message_id, embedding)

        logger.info(
            "[MEMORY] Message persisted | role=%s | id=%s",
            task["role"],
            message_id,
        )

    # ---------------- EXTRACTION ----------------

    def _extraction_loop(self):

        while True:
            user_message = self.extraction_queue.get()

            try:
                if user_message is None:
                    break

                self._extract_memory(user_message)

            except Exception:
                logger.exception("[MEMORY] Extraction failed")

            finally:
                self.extraction_queue.task_done()

        logger.info("[MEMORY] Extraction worker stopped")

    def _extract_memory(self, user_message):

        with self.llm_lock:
            result = self.memory_manager.process_message(
                user_message
            )

        saved_count = len(result) if result is not None else 0

        logger.info(
            "[MEMORY] Extraction completed | saved=%s",
            saved_count,
        )

    # ---------------- STATUS ----------------

    def get_status(self):

        return {
            "persistence_pending": self.persistence_queue.qsize(),
            "extraction_pending": self.extraction_queue.qsize(),
            "persistence_running": self.persistence_thread.is_alive(),
            "extraction_running": self.extraction_thread.is_alive(),
        }

    def wait_until_idle(self):
        self.wait_for_persistence()
        self.extraction_queue.join()

    def wait_for_persistence(self):
        self.persistence_queue.join()

    # ---------------- SHUTDOWN ----------------

    def close(self, timeout: Optional[float] = 30):

        with self.submission_lock:
            if self.shutdown_event.is_set():
                return

            self.shutdown_event.set()

        logger.info("[MEMORY] Draining background tasks")

        self.persistence_queue.join()
        self.extraction_queue.join()

        self.persistence_queue.put(None)
        self.extraction_queue.put(None)

        self.persistence_thread.join(timeout)
        self.extraction_thread.join(timeout)

        if self.persistence_thread.is_alive():
            raise TimeoutError("Persistence worker did not stop")

        if self.extraction_thread.is_alive():
            raise TimeoutError("Extraction worker did not stop")

        logger.info("[MEMORY] Shutdown complete")