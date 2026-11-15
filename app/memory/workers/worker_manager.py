import logging
import queue
import threading

from app.memory.workers.persistence_worker import PersistenceWorker
from app.memory.workers.extraction_worker import ExtractionWorker

logger = logging.getLogger(__name__)


class BackgroundMemoryWorker:

    def __init__(self, memory_service, memory_manager, llm=None):

        self.persistence_queue = queue.Queue()
        self.extraction_queue = queue.Queue()

        self.shutdown_event = threading.Event()
        self.submission_lock = threading.Lock()
        self.error_lock = threading.Lock()

        self.persistence_errors = []
        self.extraction_errors = []

        self._stop_signals_sent = False

        # Workers delegate actual operations to existing services.
        self.persistence_worker = PersistenceWorker(
            memory_service
        )

        self.extraction_worker = ExtractionWorker(
            memory_manager,
            llm,
        )

        # Independent worker threads.
        self.persistence_thread = threading.Thread(
            target=self.persistence_worker.run,
            args=(
                self.persistence_queue,
                self._record_persistence_error,
            ),
            name="EDITH-Persistence-Worker",
            daemon=False,
        )

        self.extraction_thread = threading.Thread(
            target=self.extraction_worker.run,
            args=(
                self.extraction_queue,
                self._record_extraction_error,
            ),
            name="EDITH-Extraction-Worker",
            daemon=False,
        )

        self.persistence_thread.start()
        self.extraction_thread.start()

        logger.info("[MEMORY] Background workers started")

    # ================================================
    # ERROR MANAGEMENT
    # ================================================

    def _record_error(self, error_list, task, error):

        with self.error_lock:
            error_list.append({
                "task": task,
                "error": error,
            })

        logger.error(
            "[MEMORY] Background task failed | task=%r",
            task,
            exc_info=(
                type(error),
                error,
                error.__traceback__,
            ),
        )

    def _record_persistence_error(self, task, error):
        self._record_error(
            self.persistence_errors,
            task,
            error,
        )

    def _record_extraction_error(self, task, error):
        self._record_error(
            self.extraction_errors,
            task,
            error,
        )

    def _raise_errors(self, error_list, worker_name):

        with self.error_lock:
            errors = list(error_list)
            error_list.clear()

        if not errors:
            return

        details = [
            str(item["error"])
            for item in errors
        ]

        raise RuntimeError(
            f"{worker_name} encountered "
            f"{len(errors)} failure(s): "
            + " | ".join(details)
        ) from errors[0]["error"]

    # ================================================
    # TASK SUBMISSION
    # ================================================

    def _ensure_running(self):

        if self.shutdown_event.is_set():
            raise RuntimeError(
                "Memory worker is shutting down"
            )

    def submit_message(self, session_id, role, content):

        if role not in {"user", "assistant"}:
            raise ValueError(
                f"Unsupported message role: {role}"
            )

        if not content or not content.strip():
            raise ValueError(
                "Cannot submit an empty message"
            )

        with self.submission_lock:

            self._ensure_running()

            self.persistence_queue.put({
                "session_id": session_id,
                "role": role,
                "content": content,
            })

    def submit_extraction(self, user_message):

        if not user_message or not user_message.strip():
            return

        with self.submission_lock:

            self._ensure_running()

            self.extraction_queue.put(user_message)

    # ================================================
    # WAIT OPERATIONS
    # ================================================

    def wait_for_persistence(self):

        self.persistence_queue.join()

        self._raise_errors(
            self.persistence_errors,
            "Persistence worker",
        )

    def wait_for_extraction(self):

        self.extraction_queue.join()

        self._raise_errors(
            self.extraction_errors,
            "Extraction worker",
        )

    def wait_until_idle(self):

        self.persistence_queue.join()
        self.extraction_queue.join()

        self._raise_errors(
            self.persistence_errors,
            "Persistence worker",
        )

        self._raise_errors(
            self.extraction_errors,
            "Extraction worker",
        )

    # ================================================
    # STATUS
    # ================================================

    def get_status(self):

        return {
            "persistence_pending": self.persistence_queue.qsize(),
            "extraction_pending": self.extraction_queue.qsize(),
            "persistence_running": self.persistence_thread.is_alive(),
            "extraction_running": self.extraction_thread.is_alive(),
            "shutting_down": self.shutdown_event.is_set(),
        }

    # ================================================
    # SHUTDOWN
    # ================================================

    def close(self, timeout=30):

        with self.submission_lock:

            self.shutdown_event.set()

            if not self._stop_signals_sent:

                self._stop_signals_sent = True

                should_send_signals = True

            else:
                should_send_signals = False

        logger.info("[MEMORY] Draining background tasks")

        if should_send_signals:

            self.persistence_queue.join()
            self.extraction_queue.join()

            self.persistence_queue.put(None)
            self.extraction_queue.put(None)

        self.persistence_thread.join(timeout)
        self.extraction_thread.join(timeout)

        if self.persistence_thread.is_alive():
            raise TimeoutError(
                "Persistence worker did not stop"
            )

        if self.extraction_thread.is_alive():
            raise TimeoutError(
                "Extraction worker did not stop"
            )

        logger.info("[MEMORY] Shutdown complete")

        self._raise_errors(
            self.persistence_errors,
            "Persistence worker",
        )

        self._raise_errors(
            self.extraction_errors,
            "Extraction worker",
        )