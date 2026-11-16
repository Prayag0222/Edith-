# EDITH Voice Engine v2 — Phase 4: Speech-to-Text

## Scope
Replaceable local STT backend. It receives completed audio from Phase 3 and does
not open a microphone or run VAD.

## Default policy
- Faster-Whisper Small.
- GPU FP16 when CUDA is available and `nvidia-smi` reports at least 1800 MB free
  and less than 75% GPU utilization.
- CPU INT8 otherwise.
- Lazy loading, thread-safe cache, only one model object retained.
- GPU model-load or inference errors retry on CPU.
- Local-only model loading by default.
- Whisper internal VAD disabled because Phase 3 owns endpointing.

## Usage
```python
from app.voice_v2.recognition import SpeechToTextEngine
stt = SpeechToTextEngine()
try:
    result = stt.transcribe(completed_speech_segment.audio)
    if result is not None:
        print(result.text)
finally:
    stt.close()
```
Input must be mono float32 at 16 kHz by default, normalized approximately to [-1, 1].
Audio file input is supported through `transcribe_file(path)`.

## Tests
From `D:\Edith`:
```powershell
python -m pytest app/voice_v2/tests/ -v
```
Tests use fake models and do not download/load Whisper.

## Real-audio acceptance
Use Phase 3 WAV files: (1) short command, (2) 2–3 sentences with natural pauses,
(3) longer recording ideally 1–5 minutes. Compare expected words with actual
transcript and record language, selected model/device, processing time, omissions
and hallucinations. Unit tests do not prove recognition accuracy.

## Deliberate limits
This is utterance-based transcription, not partial streaming STT. Long waveforms
are passed whole to Faster-Whisper; no 20-second cap is imposed here. Streaming
partials can later be added behind `STTBackend`. Classification is advisory and
must never authorize actions. Speaker verification is intentionally absent in
v0.1 and can later be inserted as a separate permission gate.
