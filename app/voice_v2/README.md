# EDITH Voice Engine v2 — Phase 1

Independent implementation. Existing `app/voice/` and `main.py` remain untouched.

## Included
- One persistent `sounddevice.InputStream`.
- 16 kHz mono float32 capture.
- 20 ms blocks (320 samples).
- Minimal callback that copies and enqueues audio.
- Background dispatcher thread.
- Independent bounded queues for consumers.
- Drop-oldest policy to prevent stale audio latency.
- Graceful stream shutdown and capture statistics.
- Input-device listing.

## Install in EDITH's existing venv
```powershell
python -m pip install numpy sounddevice pytest
```

## Hardware test
From the EDITH project root:
```powershell
python -m app.voice_v2.tests.test_microphone
```
Speak for 10 seconds. It prints received blocks, captured duration, queue drops and overflow count.

## API
```python
from app.voice_v2 import AudioInputService, AudioInputConfig

service = AudioInputService(AudioInputConfig())
subscription = service.subscribe()
try:
    while True:
        chunk = subscription.get(timeout=1)
        if chunk is None:
            continue
        # chunk.samples: read-only float32 mono ndarray
        # chunk.sample_rate: 16000
        # chunk.sequence: increasing sequence number
        # chunk.captured_at: monotonic timestamp
finally:
    subscription.close()
    service.stop()
```

Create one service and let wake detection, VAD and recording subscribe to it.
Those components must not open their own microphone streams.

Each subscriber queue is bounded. Slow consumers lose oldest blocks rather than
accumulating stale audio. This favors conversational latency over delayed audio.

Do not run the test simultaneously with the old EDITH voice loop.
