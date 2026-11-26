# EDITH Presence UI v3 — integration notes

This package is the visual layer only. It does not replace the Python voice engine, Ollama, Whisper, Piper, memory, or wake-word code.

## 1. Build the frontend

From `D:\Edith\edith-ui` after copying these files into that folder:

```powershell
npm install
npm run build
```

Preview the visual concept in a browser with `npm run dev`, then open the Vite URL with `?preview`.

## 2. Native transparent window

The React page and native window must both be transparent. EDITH's Windows host uses pywebview 6.2.1: its EdgeChromium/WebView2 backend maps `transparent=True` to a transparent WebView2 background. The WinForms host is also configured with a transparency key matching its background; otherwise WebView2 can reveal the host's opaque form color instead of the desktop. The MSHTML fallback does not support this setup, so EDITH logs an error if that renderer is selected; install the Edge WebView2 Runtime rather than changing the UI framework.

The existing host creates a frameless, fixed-size, top-right window with `transparent=True`, `focus=False`, and `hidden=False`. On this pywebview version, that selects its transparent-window startup path; `focus=False` prevents focus activation. It applies taskbar/Alt+Tab, transparency-key, and no-activation settings to `window.native.Handle`, the actual pywebview form handle. Do not locate the window by its title or set an alpha `background_color`; pywebview's transparent flag configures the WebView2 surface.

## 3. Response text bridge

Add methods to the existing desktop window class (keep its existing readiness and closed checks):

```python
import json

def set_response(self, text: str):
    if self.window is None or self._closed:
        return
    if not self._ready.wait(timeout=5):
        return
    self.window.evaluate_js(f"window.edithSetResponse({json.dumps(str(text))})")

def append_response(self, text: str):
    if self.window is None or self._closed:
        return
    if not self._ready.wait(timeout=5):
        return
    self.window.evaluate_js(f"window.edithAppendResponse({json.dumps(str(text))})")
```

In the existing LLM streaming loop:
- Clear the UI response once at the beginning of a new assistant response.
- For every text chunk already being sent to the Piper speech queue, call `ui.desktop.append_response(text_chunk)` using that same chunk.
- Do not append a second copy of the completed answer.

## 4. Speaking amplitude

The orb already exposes `window.edithSetAudioLevel(level)` where `level` is 0.0–1.0. It only becomes genuinely voice-reactive when the TTS playback pipeline supplies measured output amplitude.

Do not use microphone input amplitude during speaking: that would animate from room noise and can cause feedback. The correct source is the actual PCM/audio frames being played by Piper. If the current TTS class does not expose those frames, leave this bridge dormant until we inspect its implementation and add a small playback-level callback without changing synthesis behaviour.

## 5. Performance

- Canvas 2D only; no Three.js or WebGL.
- Fixed particle pool (42 points), capped at about 30 FPS.
- Canvas device pixel ratio capped at 1.5.
- Animation pauses when the document is hidden.
- The core uses CSS/Canvas layering; it is a visual hologram illusion, not a 3D scene.
