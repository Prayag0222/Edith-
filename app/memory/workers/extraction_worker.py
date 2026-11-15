import logging
import queue
import threading

logger = logging.getLogger(__name__)


class ExtractionWorker:

    def __init__(self, memory_manager, llm=None):

        self.memory_manager = memory_manager

        self.llm_lock = (
            getattr(llm, "request_lock", None)
            or threading.RLock()
        )

    def process(self, user_message):

        with self.llm_lock:
            result = self.memory_manager.process_message(
                user_message
            )

        saved_count = len(result) if result is not None else 0

        logger.info(
            "[MEMORY] Extraction completed | saved=%s",
            saved_count,
        )

        return saved_count

    def run(self, task_queue, error_callback):

        while True:
            task = task_queue.get()

            try:
                if task is None:
                    return

                self.process(task)

            except Exception as error:
                error_callback(task, error)

            finally:
                task_queue.task_done()