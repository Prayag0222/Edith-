from __future__ import annotations

import ctypes
import logging
import math
import os
import threading
import time
from enum import Enum
from typing import Callable


logger = logging.getLogger(__name__)


class ApplicationMode(str, Enum):
    ACTIVE = "ACTIVE"
    SLEEPING = "SLEEPING"
    HIBERNATING = "HIBERNATING"
    SHUTTING_DOWN = "SHUTTING_DOWN"


class SingleInstanceGuard:
    ERROR_ALREADY_EXISTS = 183
    MUTEX_NAME = r"Local\EDITH.Assistant.Singleton"

    def __init__(self, name: str | None = None):
        self.name = name or self.MUTEX_NAME
        self._handle = None
        self._kernel32 = None
        self._owner_thread: int | None = None

    def acquire(self) -> bool:
        if os.name != "nt":
            raise OSError("EDITH's single-instance guard requires Windows.")

        if self._handle is not None:
            return True

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_wchar_p,
        ]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]
        kernel32.ReleaseMutex.restype = ctypes.c_int

        ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, True, self.name)
        last_error = ctypes.get_last_error()
        if not handle:
            raise ctypes.WinError(last_error)

        if last_error == self.ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False

        self._handle = handle
        self._kernel32 = kernel32
        self._owner_thread = threading.get_ident()
        return True

    def close(self) -> None:
        if self._handle is None:
            return

        if threading.get_ident() != self._owner_thread:
            raise RuntimeError(
                "The single-instance guard must be released by its owner thread."
            )

        handle = self._handle
        kernel32 = self._kernel32
        self._handle = None
        self._kernel32 = None
        self._owner_thread = None

        if kernel32 is None:
            raise RuntimeError("Single-instance guard handle is incomplete.")

        if not kernel32.ReleaseMutex(handle):
            release_error = ctypes.WinError(ctypes.get_last_error())
            kernel32.CloseHandle(handle)
            raise release_error

        if not kernel32.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())


class ApplicationLifecycle:
    def __init__(
        self,
        hibernate_after_seconds: float,
        hibernate_action: Callable[[], None],
        on_mode_change: Callable[[ApplicationMode], None] | None = None,
    ):
        if not math.isfinite(hibernate_after_seconds) or hibernate_after_seconds <= 0:
            raise ValueError("Hibernate timeout must be a positive finite number.")

        if not callable(hibernate_action):
            raise TypeError("hibernate_action must be callable.")

        self.hibernate_after_seconds = hibernate_after_seconds
        self._hibernate_action = hibernate_action
        self._on_mode_change = on_mode_change
        self._condition = threading.Condition()
        self._mode = ApplicationMode.SLEEPING
        self._last_interaction = time.monotonic()
        self._retry_at = 0.0
        self._stopping = False
        self._monitor_thread: threading.Thread | None = None

    @property
    def mode(self) -> ApplicationMode:
        with self._condition:
            return self._mode

    @property
    def is_shutting_down(self) -> bool:
        with self._condition:
            return self._mode is ApplicationMode.SHUTTING_DOWN

    def start(self) -> None:
        with self._condition:
            if self._stopping:
                raise RuntimeError("Lifecycle controller is closed.")
            if self._monitor_thread is not None:
                raise RuntimeError("Lifecycle monitor is already running.")

            monitor = threading.Thread(
                target=self._monitor_inactivity,
                name="EDITH-Lifecycle-Monitor",
                daemon=False,
            )
            monitor.start()
            self._monitor_thread = monitor

    def activate(self) -> bool:
        with self._condition:
            if self._mode is ApplicationMode.SHUTTING_DOWN:
                return False

            self._set_mode_locked(ApplicationMode.ACTIVE)
            self._last_interaction = time.monotonic()
            self._retry_at = 0.0
            self._condition.notify_all()
            return True

    def note_interaction(self) -> None:
        with self._condition:
            if self._mode is ApplicationMode.SHUTTING_DOWN:
                return

            self._last_interaction = time.monotonic()
            self._retry_at = 0.0
            self._condition.notify_all()

    def sleep(self) -> bool:
        with self._condition:
            if self._mode is ApplicationMode.SHUTTING_DOWN:
                return False

            self._set_mode_locked(ApplicationMode.SLEEPING)
            self._condition.notify_all()
            return True

    def hibernate_now(self) -> bool:
        with self._condition:
            if self._mode is ApplicationMode.SHUTTING_DOWN:
                return False
            if self._mode is ApplicationMode.ACTIVE:
                raise RuntimeError(
                    "EDITH must be sleeping before hibernation can begin."
                )
            if self._mode is ApplicationMode.HIBERNATING:
                return False

            self._enter_hibernation_locked()
            return True

    def _enter_hibernation_locked(self) -> None:
        self._set_mode_locked(ApplicationMode.HIBERNATING)
        self._condition.notify_all()

        try:
            self._hibernate_action()
        except Exception:
            self._set_mode_locked(ApplicationMode.SLEEPING)
            self._retry_at = time.monotonic() + min(
                60.0,
                self.hibernate_after_seconds,
            )
            self._condition.notify_all()
            logger.exception(
                "EDITH hibernation failed; remaining in SLEEPING mode"
            )
            raise

        self._condition.notify_all()
        logger.info("EDITH entered HIBERNATING mode")

    def shutdown(self) -> None:
        with self._condition:
            self._set_mode_locked(ApplicationMode.SHUTTING_DOWN)
            self._stopping = True
            self._condition.notify_all()

        monitor = self._monitor_thread
        if monitor is not None and monitor is not threading.current_thread():
            if monitor.ident is not None:
                monitor.join()
            self._monitor_thread = None

    def _monitor_inactivity(self) -> None:
        with self._condition:
            while not self._stopping:
                if self._mode is not ApplicationMode.SLEEPING:
                    self._condition.wait()
                    continue

                deadline = max(
                    self._last_interaction + self.hibernate_after_seconds,
                    self._retry_at,
                )
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    self._condition.wait(timeout=remaining)
                    continue

                try:
                    self._enter_hibernation_locked()
                except Exception:
                    continue

    def _set_mode_locked(self, mode: ApplicationMode) -> None:
        if self._mode is mode:
            return

        self._mode = mode
        if self._on_mode_change is not None:
            try:
                self._on_mode_change(mode)
            except Exception:
                logger.exception("EDITH lifecycle status callback failed")


