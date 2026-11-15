import logging
import queue

logger = logging.getLogger(__name__)


class PersistenceWorker:

    def __init__(self, memory_service):
        self.memory_service = memory_service

    def process(self, task):
        message_id = self.memory_service.store_message(
            session_id=task["session_id"],
            role=task["role"],
            content=task["content"],
        )

        if message_id is None:
            raise RuntimeError(
                "MemoryService returned no message ID"
            )

        logger.info(
            "[MEMORY] Message persisted and indexed | role=%s | id=%s",
            task["role"],
            message_id,
        )

        return message_id

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