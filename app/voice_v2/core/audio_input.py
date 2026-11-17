from __future__ import annotations
import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AudioInputConfig:
    sample_rate: int = 16000
    channels: int = 1
    block_duration_ms: int = 20
    dtype: str = "float32"
    device: Optional[int | str] = None
    input_queue_blocks: int = 100
    subscriber_queue_blocks: int = 50
    start: bool = True

    def __post_init__(self):
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if self.channels != 1:
            raise ValueError("Phase 1 supports mono input only")
        if self.block_duration_ms not in (10, 20, 30):
            raise ValueError("block_duration_ms must be 10, 20, or 30")
        if self.dtype != "float32":
            raise ValueError("Only float32 input is supported")
        if self.input_queue_blocks < 2 or self.subscriber_queue_blocks < 2:
            raise ValueError("Queue capacities must be at least 2")

    @property
    def block_size(self) -> int:
        return self.sample_rate * self.block_duration_ms // 1000


@dataclass(frozen=True, slots=True)
class AudioChunk:
    samples: np.ndarray
    sample_rate: int
    sequence: int
    captured_at: float
    overflow_before_capture: bool = False

    @property
    def duration_seconds(self) -> float:
        return self.samples.size / self.sample_rate


class AudioSubscription:
    def __init__(self, owner: "AudioInputService", max_blocks: int):
        self._owner = owner
        self._queue: queue.Queue[AudioChunk | None] = queue.Queue(maxsize=max_blocks)
        self._closed = False
        self.dropped_blocks = 0

    def get(self, timeout: Optional[float] = None) -> Optional[AudioChunk]:
        if self._closed and self._queue.empty():
            return None
        try:
            item = self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
        return item

    def close(self):
        if not self._closed:
            self._closed = True
            self._owner.unsubscribe(self)

    def _publish(self, chunk: AudioChunk):
        if self._closed:
            return
        try:
            self._queue.put_nowait(chunk)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self.dropped_blocks += 1
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(chunk)
            except queue.Full:
                self.dropped_blocks += 1

    def _signal_closed(self):
        self._closed = True
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass

    def discard_pending(self) -> int:
        """
        Remove audio captured before the next listening session.

        This is important after TTS playback because the microphone
        continues capturing EDITH's own spoken response.

        Returns the number of discarded audio blocks.
        """
        discarded = 0

        while True:
            try:
                self._queue.get_nowait()
                discarded += 1
            except queue.Empty:
                break

        return discarded 


    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class AudioInputService:
    """Own one persistent PortAudio stream and fan out blocks to subscribers."""

    def __init__(self, config: Optional[AudioInputConfig] = None):
        self.config = config or AudioInputConfig()
        self._input_queue: queue.Queue[AudioChunk | None] = queue.Queue(
            maxsize=self.config.input_queue_blocks
        )
        self._subscriptions: set[AudioSubscription] = set()
        self._subscriptions_lock = threading.RLock()
        self._state_lock = threading.RLock()
        self._stream: Optional[sd.InputStream] = None
        self._dispatcher: Optional[threading.Thread] = None
        self._running = False
        self._sequence = 0
        self._callback_overflows = 0
        self._dropped_input_blocks = 0

        if self.config.start:
            self.start()

    @property
    def is_running(self):
        with self._state_lock:
            return self._running

    def subscribe(self, max_blocks: Optional[int] = None) -> AudioSubscription:
        sub = AudioSubscription(self, max_blocks or self.config.subscriber_queue_blocks)
        with self._subscriptions_lock:
            self._subscriptions.add(sub)
        return sub

    def unsubscribe(self, subscription: AudioSubscription):
        with self._subscriptions_lock:
            self._subscriptions.discard(subscription)

    def start(self):
        with self._state_lock:
            if self._running:
                return
            sd.check_input_settings(
                device=self.config.device,
                channels=self.config.channels,
                dtype=self.config.dtype,
                samplerate=self.config.sample_rate,
            )
            self._running = True
            self._dispatcher = threading.Thread(
                target=self._dispatch_loop,
                name="edith-audio-dispatcher",
                daemon=True,
            )
            self._dispatcher.start()
            try:
                self._stream = sd.InputStream(
                    device=self.config.device,
                    samplerate=self.config.sample_rate,
                    channels=self.config.channels,
                    dtype=self.config.dtype,
                    blocksize=self.config.block_size,
                    callback=self._audio_callback,
                )
                self._stream.start()
            except Exception:
                self._running = False
                self._enqueue_shutdown()
                self._dispatcher.join(timeout=2)
                self._dispatcher = None
                self._stream = None
                raise
        logger.info("Microphone started: %s Hz, %s ms blocks",
                    self.config.sample_rate, self.config.block_duration_ms)

    def _audio_callback(self, indata, frames, time_info, status):
        # Keep callback work minimal: copy samples and enqueue only.
        if status and getattr(status, "input_overflow", False):
            self._callback_overflows += 1
        samples = np.asarray(indata[:, 0], dtype=np.float32).copy()
        if samples.size == 0:
            return
        samples.setflags(write=False)
        self._sequence += 1
        chunk = AudioChunk(
            samples=samples,
            sample_rate=self.config.sample_rate,
            sequence=self._sequence,
            captured_at=time.monotonic(),
            overflow_before_capture=bool(status),
        )
        try:
            self._input_queue.put_nowait(chunk)
        except queue.Full:
            # Drop oldest audio rather than build up latency.
            try:
                self._input_queue.get_nowait()
                self._dropped_input_blocks += 1
            except queue.Empty:
                pass
            try:
                self._input_queue.put_nowait(chunk)
            except queue.Full:
                self._dropped_input_blocks += 1

    def _dispatch_loop(self):
        while True:
            item = self._input_queue.get()
            if item is None:
                break
            with self._subscriptions_lock:
                subscribers = tuple(self._subscriptions)
            for sub in subscribers:
                sub._publish(item)
        with self._subscriptions_lock:
            subscribers = tuple(self._subscriptions)
        for sub in subscribers:
            sub._signal_closed()

    def _enqueue_shutdown(self):
        try:
            self._input_queue.put_nowait(None)
        except queue.Full:
            try:
                self._input_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._input_queue.put_nowait(None)
            except queue.Full:
                pass

    def get_stats(self) -> dict:
        with self._subscriptions_lock:
            subscribers = tuple(self._subscriptions)
        return {
            "running": self.is_running,
            "sequence": self._sequence,
            "callback_overflows": self._callback_overflows,
            "dropped_input_blocks": self._dropped_input_blocks,
            "input_queue_depth": self._input_queue.qsize(),
            "subscriber_count": len(subscribers),
            "subscriber_dropped_blocks": [s.dropped_blocks for s in subscribers],
        }

    def stop(self):
        with self._state_lock:
            if not self._running and self._stream is None:
                return
            self._running = False
            stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
        self._enqueue_shutdown()
        dispatcher, self._dispatcher = self._dispatcher, None
        if dispatcher and dispatcher.is_alive():
            dispatcher.join(timeout=3)
            if dispatcher.is_alive():
                logger.warning("Audio dispatcher did not stop within timeout")
        logger.info("Microphone stopped")

    def __enter__(self):
        if not self.is_running:
            self.start()
        return self

    def __exit__(self, *_):
        self.stop()
