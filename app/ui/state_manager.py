import logging
import threading

from app.ui.desktop_window import EdithDesktopWindow


logger = logging.getLogger(__name__)


class EdithUIController:
    """
    Controls communication between EDITH's Python backend
    and its React desktop interface.
    """

    SLEEP_HIDE_DELAY = 0.55  # Matches the React fade-out duration

    def __init__(self, desktop: EdithDesktopWindow):
        self.desktop = desktop
        self.current_state = "SLEEPING"
        self._hide_timer = None
        self._lock = threading.Lock()

    def _cancel_pending_hide(self):
        if self._hide_timer is not None:
            self._hide_timer.cancel()
            self._hide_timer = None

    def set_state(self, state: str):
        """
        Update EDITH's state and synchronize the desktop UI.
        """
        with self._lock:
            if state == self.current_state:
                return
            self.current_state = state

        logger.info("EDITH state changed: %s", state)
        self.desktop.set_state(state)

    def activate(self, state: str = "LISTENING"):
        """
        Display the overlay and activate the requested state.
        Called when the wake word is detected.
        """
        with self._lock:
            self._cancel_pending_hide()

        self.desktop.show()
        self.set_state(state)

    def sleep(self):
        """
        Transition EDITH to SLEEPING, then hide the native window
        once the dissolve animation completes.
        """
        self.set_state("SLEEPING")

        with self._lock:
            self._cancel_pending_hide()
            self._hide_timer = threading.Timer(
                self.SLEEP_HIDE_DELAY,
                self._hide_if_still_sleeping,
            )
            self._hide_timer.daemon = True
            self._hide_timer.start()

    def _hide_if_still_sleeping(self):
        with self._lock:
            if self.current_state != "SLEEPING":
                return
            self._hide_timer = None

        self.desktop.hide()

    def close(self):
        """
        Close the desktop interface completely.
        """
        with self._lock:
            self._cancel_pending_hide()

        self.desktop.close()