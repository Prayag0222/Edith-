from pathlib import Path
import threading
import logging
import json
import time
import ctypes
import ctypes.wintypes

import webview


logger = logging.getLogger(__name__)


# Windows API constants
GWL_EXSTYLE = -20

WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

HWND_TOPMOST = -1


class EdithDesktopWindow:

    WINDOW_WIDTH = 560
    WINDOW_HEIGHT = 240

    RIGHT_MARGIN = 24
    TOP_MARGIN = 32
    BRIDGE_TIMEOUT = 10

    def __init__(self):
        project_root = Path(__file__).resolve().parents[2]

        self.frontend_path = (
            project_root / "edith-ui" / "dist" / "index.html"
        )

        if not self.frontend_path.is_file():
            raise FileNotFoundError(
                f"React production build not found: {self.frontend_path}"
            )

        self.window = None
        self._ready = threading.Event()
        self._closed = False
        self._allow_close = False

    def _get_window_position(self):
        user32 = ctypes.windll.user32
        screen_width = user32.GetSystemMetrics(0)
        x = max(0, screen_width - self.WINDOW_WIDTH - self.RIGHT_MARGIN)
        return x, self.TOP_MARGIN

    def create(self):
        if self.window is not None:
            return

        x, y = self._get_window_position()

        self.window = webview.create_window(
            title="EDITH",
            url=self.frontend_path.as_uri(),
            width=self.WINDOW_WIDTH,
            height=self.WINDOW_HEIGHT,
            x=x,
            y=y,
            resizable=False,
            frameless=True,
            on_top=True,
            focus=False,
            easy_drag=False,
            transparent=True,
            # Near-black chroma key avoids white edges or punching holes in white HUD text.
            background_color="#010101",
            hidden=False,
        )

        if self.window is None:
            raise RuntimeError("Failed to create EDITH desktop window.")

        self.window.events.loaded += self._on_loaded
        self.window.events.closing += self._on_closing
        self.window.events.closed += self._on_closed

        logger.info("EDITH overlay created at (%s, %s)", x, y)

    def _on_loaded(self):
        logger.info("EDITH interface loaded")
        threading.Thread(
            target=self._apply_windows_overlay_styles,
            daemon=True,
        ).start()

    def _apply_winforms_transparency(self, native_window):
            """
            Configure WinForms chroma-key transparency and WebView2 transparent
            background on the WinForms UI thread.
            """
            try:
                import clr  # type: ignore[import-not-found]
                getattr(clr, "AddReference")("System.Drawing")
                from System import Action  # type: ignore[import-not-found]
                from System.Drawing import Color  # type: ignore[import-not-found]
            except Exception:
                logger.exception("Could not load .NET System/Drawing helpers")
                return

            def _configure():
                key_color = Color.FromArgb(1, 1, 1)
                native_window.BackColor = key_color
                native_window.TransparencyKey = key_color
                native_window.ShowInTaskbar = False

                browser = getattr(native_window, "browser", None)
                webview_ctrl = getattr(browser, "webview", None) if browser else None
                if webview_ctrl is not None:
                    webview_ctrl.DefaultBackgroundColor = Color.Transparent

            try:
                if getattr(native_window, "InvokeRequired", False):
                    native_window.Invoke(Action(_configure))
                else:
                    _configure()
            except Exception:
                logger.exception("Failed to apply WinForms transparency on UI thread")
                
    def _apply_windows_overlay_styles(self):
        """
        Apply click-through, no-taskbar, no-focus-stealing, and native
        WebView2 transparency, then wait for the JS bridge.
        """
        window = self.window
        if window is None or self._closed:
            return

        native_window = getattr(window, "native", None)
        if native_window is None:
            logger.warning("Could not access EDITH's pywebview native window")
            return

        # 1. Apply WinForms + WebView2 transparency on the UI thread.
        self._apply_winforms_transparency(native_window)

        # 2. Apply Win32 extended styles (tool window, no focus, click-through).
        hwnd = int(native_window.Handle.ToInt64())
        if not hwnd:
            logger.error("EDITH's native window handle is invalid")
            return

        user32 = ctypes.windll.user32
        get_window_long = user32.GetWindowLongW
        set_window_long = user32.SetWindowLongW

        get_window_long.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
        get_window_long.restype = ctypes.c_long

        set_window_long.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.c_int,
            ctypes.c_long,
        ]
        set_window_long.restype = ctypes.c_long

        extended_style = get_window_long(hwnd, GWL_EXSTYLE)
        extended_style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT
        extended_style &= ~WS_EX_APPWINDOW

        set_window_long(hwnd, GWL_EXSTYLE, extended_style)

        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )

        logger.info("EDITH native transparency and click-through styles applied")

        renderer = getattr(window.gui, "renderer", None)
        if renderer != "edgechromium":
            logger.error(
                "Transparent EDITH overlay requires pywebview's Edge/WebView2 "
                "renderer; active renderer is %r",
                renderer,
            )

        # 3. Verify the React JS bridge is registered.
        bridge_check = (
            "typeof window.edithSetState === 'function' && "
            "typeof window.edithSetResponse === 'function' && "
            "typeof window.edithAppendResponse === 'function' && "
            "typeof window.edithClearResponse === 'function' && "
            "typeof window.edithSetAudioLevel === 'function'"
        )
        deadline = time.monotonic() + self.BRIDGE_TIMEOUT

        while not self._closed and time.monotonic() < deadline:
            try:
                if window.evaluate_js(f"Boolean({bridge_check})"):
                    self._ready.set()
                    logger.info("EDITH JavaScript bridge is ready")
                    return
            except Exception:
                logger.exception("Failed while checking EDITH's JavaScript bridge")
                return
            time.sleep(0.1)

        if not self._closed:
            logger.error("EDITH JavaScript bridge did not register after page load")

    def _on_closed(self):
        self._closed = True
        logger.info("EDITH desktop interface closed")

    def _on_closing(self):
        if self._allow_close:
            return True

        if self.window is not None and not self._closed:
            try:
                self.window.hide()
                logger.info(
                    "EDITH desktop window hidden; assistant remains running"
                )
            except Exception:
                logger.exception("Could not hide EDITH desktop window on close")

        return False

    def show(self):
        if self.window is None or self._closed:
            return
        self.window.show()

    def hide(self):
        if self.window is None or self._closed:
            return
        self.window.hide()

    def _execute_js(self, javascript: str):
        window = self.window
        if window is None or self._closed:
            return

        if not self._ready.wait(timeout=self.BRIDGE_TIMEOUT):
            logger.warning("EDITH UI is not ready")
            return

        try:
            window.evaluate_js(javascript)
        except Exception:
            logger.exception("Failed to communicate with EDITH interface")

    def set_state(self, state: str):
        allowed_states = {
            "READY",
            "LISTENING",
            "THINKING",
            "SPEAKING",
            "SLEEPING",
        }
        if state not in allowed_states:
            logger.warning("Invalid EDITH UI state: %s", state)
            return

        payload = json.dumps(state)
        self._execute_js(f"window.edithSetState({payload})")

    def set_response(self, text: str):
        payload = json.dumps(str(text))
        self._execute_js(f"window.edithSetResponse({payload})")

    def append_response(self, text: str):
        payload = json.dumps(str(text))
        self._execute_js(f"window.edithAppendResponse({payload})")

    def clear_response(self):
        self._execute_js("window.edithClearResponse()")

    def set_audio_level(self, level: float):
        normalized = max(0.0, min(1.0, float(level)))
        self._execute_js(f"window.edithSetAudioLevel({normalized})")

    def close(self):
        if self.window is None or self._closed:
            return
        self._allow_close = True
        self._closed = True
        try:
            self.window.destroy()
        except Exception:
            logger.exception("Failed to close EDITH desktop window")