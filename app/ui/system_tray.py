from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

from PIL import Image
import pystray


logger = logging.getLogger(__name__)


class EdithSystemTray:
    START_TIMEOUT_SECONDS = 10

    def __init__(
        self,
        icon_path: str | Path,
        open_ui: Callable[[], None],
        hide_ui: Callable[[], None],
        exit_application: Callable[[], None],
        initial_status: str = "SLEEPING",
    ):
        self.icon_path = Path(icon_path)
        if not self.icon_path.is_file():
            raise FileNotFoundError(
                f"EDITH tray icon not found: {self.icon_path}"
            )

        self._open_ui = open_ui
        self._hide_ui = hide_ui
        self._exit_application = exit_application
        self._status = self._normalize_status(initial_status)
        self._ready = threading.Event()
        self._lock = threading.RLock()
        self._starting = False
        self._started = False
        self._stopped = False
        self._startup_error: Exception | None = None

        with Image.open(self.icon_path) as source:
            image = source.convert("RGBA")

        menu = pystray.Menu(
            pystray.MenuItem("Open EDITH", self._on_open),
            pystray.MenuItem("Hide EDITH", self._on_hide),
            pystray.MenuItem(
                lambda item: f"Current status: {self._status}",
                self._on_show_status,
            ),
            pystray.MenuItem("Exit", self._on_exit),
        )
        self._icon = pystray.Icon(
            "EDITH",
            icon=image,
            title=self._title,
            menu=menu,
        )

    @staticmethod
    def _normalize_status(status) -> str:
        return str(getattr(status, "value", status)).upper()

    @property
    def is_ready(self) -> bool:
        return self._ready.is_set() and self._startup_error is None

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @property
    def _title(self) -> str:
        return f"EDITH - {self._status}"

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            if self._stopped:
                raise RuntimeError("EDITH tray has already been stopped.")
            if self._starting:
                wait_for_start = True
            else:
                self._starting = True
                wait_for_start = False

        if not wait_for_start:
            try:
                self._icon.run_detached(setup=self._on_setup)
            except Exception:
                with self._lock:
                    self._starting = False
                raise

        if not self._ready.wait(timeout=self.START_TIMEOUT_SECONDS):
            self._icon.stop()
            with self._lock:
                self._starting = False
            raise TimeoutError("EDITH tray icon did not become visible.")

        if self._startup_error is not None:
            self._icon.stop()
            with self._lock:
                self._starting = False
            raise RuntimeError("EDITH tray icon failed to start.") from self._startup_error

        with self._lock:
            self._starting = False
            self._started = True

        logger.info("EDITH system tray icon is ready")

    def _on_setup(self, icon) -> None:
        try:
            icon.title = self._title
            icon.visible = True
        except Exception as exc:
            self._startup_error = exc
            logger.exception("Could not display EDITH system tray icon")
        finally:
            self._ready.set()

    def set_status(self, status) -> None:
        with self._lock:
            self._status = self._normalize_status(status)
            started = self._started

        if not started:
            return

        try:
            self._icon.title = self._title
            self._icon.update_menu()
        except Exception:
            logger.exception("Could not update EDITH tray status")

    def _invoke(self, action: Callable[[], None], description: str) -> None:
        try:
            action()
        except Exception:
            logger.exception("EDITH tray action failed: %s", description)

    def _on_open(self, icon, item) -> None:
        self._invoke(self._open_ui, "open UI")

    def _on_hide(self, icon, item) -> None:
        self._invoke(self._hide_ui, "hide UI")

    def _on_show_status(self, icon, item) -> None:
        message = f"Current status: {self.status}"
        try:
            if icon.HAS_NOTIFICATION:
                icon.notify(message, "EDITH")
            else:
                logger.info(message)
        except Exception:
            logger.exception("Could not display EDITH tray status")

    def _on_exit(self, icon, item) -> None:
        self._invoke(self._exit_application, "exit application")

    def stop(self) -> None:
        with self._lock:
            if self._stopped:
                return
            self._stopped = True
            should_stop = self._started or self._starting
            self._started = False

        if should_stop:
            self._icon.stop()
            logger.info("EDITH system tray icon stopped")
