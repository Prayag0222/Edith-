# EDITH Voice Engine v2 — Phase 3: VAD and Endpointing

## Install

Use EDITH's existing virtual environment:

```powershell
python -m pip install silero-vad onnxruntime
```

The Silero Python wrapper also uses PyTorch tensors. If `torch` is not installed
in this environment, install a build compatible with your Python version and
hardware using the official PyTorch installation selector. Do not copy the
wake-word trainer's virtual environment into EDITH.

## What this phase adds

- Silero VAD inference on 512-sample frames at 16 kHz.
- Streaming input buffering for arbitrary 20 ms microphone blocks.
- Separate start and continuation thresholds (hysteresis).
- Speech-start confirmation to reject brief noise spikes.
- 500 ms pre-roll to preserve the beginning of speech.
- Adaptive end-of-speech silence window.
- 10-minute utterance safety cap (configurable).
- Complete utterance audio returned as a `SpeechSegment`.

## Basic usage

```python
from app.voice_v2 import AudioInputService, AudioInputConfig
from app.voice_v2.detection import (
    SileroVAD, SileroVADConfig,
    AdaptiveEndpointDetector, EndpointConfig,
)

audio_service = AudioInputService(AudioInputConfig())
subscription = audio_service.subscribe()

vad = SileroVAD(SileroVADConfig(sample_rate=16000, use_onnx=True))
endpoint = AdaptiveEndpointDetector(
    vad,
    EndpointConfig(
        sample_rate=16000,
        max_utterance_seconds=600,
    ),
)

try:
    while True:
        chunk = subscription.get(timeout=1.0)
        if chunk is None:
            continue
        segment = endpoint.process(chunk.samples)
        if segment is not None:
            print(
                f"Speech: {segment.duration_seconds:.2f}s; "
                f"ended by {segment.ended_by}"
            )
            # Pass segment.audio to STT in the recognition phase.
finally:
    subscription.close()
    audio_service.stop()
```

## Long speech behavior

The endpoint detector does not stop because speech reaches 5 minutes. Its default
maximum utterance duration is 600 seconds. It finalizes when it detects the
configured silence interval or reaches that safety cap.

The silence threshold is 480 ms by default. Long sustained speech receives an
additional 150 ms of pause tolerance, capped at 750 ms.

## Important testing note

Test in your normal room and microphone position. VAD thresholds are starting
values, not universal truths. Phase 3 should be validated with quiet speech,
normal speech, background TV/people, keyboard noise, and natural pauses before
speaker verification is added.
