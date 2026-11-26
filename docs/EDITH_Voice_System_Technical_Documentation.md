# EDITH Voice System --- Technical Architecture & Developer Documentation

**Subsystem:** Voice Engine v2\
**Checkpoint:** Stable integration, November 2026\
**Project root:** `D:\Edith`\
**Runtime:** Windows 11, Python 3.13.2, project `.venv`\
**Audience:** Future maintainers and engineers debugging or extending
EDITH.

> This document records the architecture, configuration, test
> observations and decisions from the implemented checkpoint. The
> checked-out source code and tests remain authoritative if a value here
> differs from the current repository.

------------------------------------------------------------------------

# 1. Executive overview

EDITH's voice system implements this local voice interaction loop:

1.  Continuously capture microphone audio.
2.  Detect **"Hey EDITH"**.
3.  Capture a complete user utterance.
4.  Detect speech boundaries with Silero VAD and adaptive endpointing.
5.  Transcribe the completed audio using Faster-Whisper.
6.  Pass text to the existing assistant, conversation and LLM pipeline.
7.  Stream generated response text to Piper TTS.
8.  Remove microphone audio captured during EDITH's own playback.
9.  Continue the conversation without another wake phrase.
10. Return to wake-word mode after seven seconds without new speech.

The central architectural decision is **one persistent microphone
stream**. Wake detection and speech capture use audio distributed by the
same `AudioInputService`; neither opens a second microphone stream.

The system is modular: capture, wake detection, VAD, endpointing, STT,
conversation lifecycle, LLM orchestration and TTS have separate
responsibilities.

## Completed and tested at this checkpoint

The user reported successful runtime tests for wake detection,
first-turn capture, multiple conversation turns, short commands such as
`Exit`, natural pauses, seven-second idle timeout, return to wake mode,
post-TTS microphone cleanup and clean shutdown.

This is evidence from the user's machine and tests, not a guarantee
across every microphone, room or acoustic environment.

# 2. Scope and non-goals

## Included

-   Shared microphone capture and audio distribution.
-   Audio buffering and basic processing.
-   Wake-word adapter around the existing detector.
-   Silero VAD.
-   Adaptive endpoint detection and speech segments.
-   Faster-Whisper integration and model selection.
-   `VoiceEngine` wake/conversation state.
-   Seven-second speech-start timeout.
-   Existing Piper TTS orchestration in `main.py`.
-   Post-TTS audio cleanup.
-   Startup, shutdown, diagnostics and test procedure.

## Explicitly not included

-   Replacing the LLM or changing its model.
-   Rebuilding memory or conversation services.
-   Speaker verification.
-   Barge-in / interrupting Piper playback.
-   Partial or streaming STT.
-   Wake-word retraining or threshold tuning.
-   GPU model unloading/reloading coordination between Ollama and
    Whisper.
-   Full acoustic echo cancellation (AEC).

Do not accidentally treat future ideas as capabilities already
implemented.

# 3. High-level architecture

``` text
                         app.main
                  Application orchestration
                           |
              +------------+-------------+
              |                          |
        User input path            Response path
              |                          |
              v                          v
         VoiceEngine               EdithAssistant
              |                    respond_stream()
              |                          |
              v                          v
       AudioInputService              OllamaClient
       ONE microphone stream          Local LLM
              |
       Shared float32 blocks
              |
       +------+-------------------+
       |                          |
       v                          v
 WakeWordAdapter            AudioSubscription
 Legacy detector                  |
                                  v
                         AdaptiveEndpointDetector
                                  |
                                  v
                              SileroVAD
                                  |
                          Completed SpeechSegment
                                  |
                                  v
                         SpeechToTextEngine
                          Faster-Whisper
                                  |
                              Transcript
                                  |
                                  v
                            app.main
                                  |
                          Streamed response text
                                  |
                             speech_queue
                                  |
                         speech_worker thread
                                  |
                           TextToSpeech / Piper
                                  |
                               Speakers
                                  |
                         Microphone hears room
                                  |
                         prepare_for_next_turn()
                       discard -> settle -> discard
                              -> reset VAD
```

**Critical:** The wake adapter and endpoint detector consume audio
originating from the same audio service. They do not independently open
the microphone.

# 4. Repository layout and component ownership

The following paths reflect the recorded project structure. Verify exact
filenames in the current checkout before refactoring.

``` text
D:\Edith\
├── app\
│   ├── main.py
│   ├── voice\
│   │   ├── tts.py
│   │   └── wake_word.py
│   ├── voice_v2\
│   │   ├── core\
│   │   │   ├── audio_input.py
│   │   │   ├── audio_device.py
│   │   │   └── audio_buffer.py
│   │   ├── processing\
│   │   │   ├── audio_processor.py
│   │   │   └── resampler.py
│   │   ├── detection\
│   │   │   ├── silero_vad.py
│   │   │   └── endpoint_detector.py
│   │   ├── recognition\
│   │   │   ├── base.py
│   │   │   ├── config.py
│   │   │   ├── model_manager.py
│   │   │   ├── stt_engine.py
│   │   │   └── transcription_result.py
│   │   ├── integration\
│   │   │   ├── wake_word_adapter.py
│   │   │   └── engine.py
│   │   └── tests\
│   └── ... assistant, LLM, conversation and memory modules
└── models\
    └── wakeword\
        └── hey_edith.onnx
```

  ----------------------------------------------------------------------------
  Component                    Owns                    Must not own
  ---------------------------- ----------------------- -----------------------
  `AudioInputService`          One microphone stream;  VAD, STT, LLM, TTS
                               block distribution      

  `AudioSubscription`          Consumer-specific       A second microphone
                               bounded queue           

  `WakeWordAdapter`            Audio conversion and    Microphone capture
                               wake detector adapter   

  `SileroVAD`                  Per-frame speech        Conversation state
                               probability             

  `AdaptiveEndpointDetector`   Start/end decision and  Transcription
                               segment creation        

  `SpeechToTextEngine`         Audio-to-text inference Wake/idle lifecycle
                               and model lifecycle     

  `VoiceEngine`                Wake mode, listening,   LLM response and TTS
                               endpointing, STT, turn  
                               state                   

  `main.py`                    Assistant orchestration Duplicate audio capture
                               and TTS lifecycle       

  `TextToSpeech`               Piper                   Decide conversation
                               synthesis/playback      state
  ----------------------------------------------------------------------------

# 5. Audio capture and distribution

## 5.1 Why one persistent stream

Opening multiple streams for one physical microphone can cause device
contention, inconsistent timing and duplicated capture state. EDITH
starts one stream and keeps it alive while moving between wake
detection, listening, inference and playback.

The capture callback should do minimal work:

1.  Receive the device block.
2.  Copy or safely retain samples.
3.  Enqueue the block.
4.  Return immediately.

A background dispatcher publishes blocks to subscriber queues. Expensive
model inference must not run in the real-time audio callback.

## 5.2 Recorded audio format

  Setting                   Value
  ------------------- -----------
  Sample rate           16,000 Hz
  Channels               1 / mono
  Data type               float32
  Block duration            20 ms
  Samples per block           320

Calculation: `16,000 × 0.020 = 320 samples`.

Float32 mono uses approximately 64,000 bytes/second of raw samples. One
20 ms block is about 1,280 bytes, excluding Python/object overhead.

## 5.3 Bounded queues and health counters

Subscriber queues are bounded. When a consumer falls behind, the queue
policy drops older blocks rather than allowing unbounded memory growth
and increasing latency.

Audio statistics include:

-   Stream running state.
-   Sequence/block count.
-   Callback overflows.
-   Dropped input blocks.
-   Input queue depth.
-   Subscriber count.
-   Per-subscriber dropped blocks.

A Phase 1 hardware test captured approximately 9.98 seconds / 499 blocks
/ 159,680 samples with zero callback overflows and zero dropped blocks.
This was a specific test run, not a universal guarantee.

When diagnosing missing or delayed speech, inspect these counters before
changing VAD or STT.

# 6. Buffering and audio processing

## 6.1 `AudioRingBuffer`

Stores a rolling window of recent audio. Its key use is pre-roll: when
speech is confirmed, the beginning of the utterance includes a short
amount of audio from before confirmation. This reduces clipping of
initial consonants and syllables.

Recorded pre-roll: `0.5 seconds`, equivalent to 8,000 samples at 16 kHz.

## 6.2 `AudioAccumulator`

Stores the active utterance until endpointing completes it. Recorded
maximum utterance duration: 600 seconds.

Raw float32 mono storage for ten minutes at 16 kHz is approximately 38.4
MB (about 36.6 MiB), excluding Python overhead and allocation strategy.

## 6.3 Audio processor

The audio processor exposes non-destructive measurements such as RMS,
peak amplitude, clipping ratio and silence/low-energy indication.
Aggressive denoising is not automatically beneficial: quieter audio is
not necessarily more intelligible to STT.

## 6.4 Resampling

A `python-soxr` wrapper is available where sample-rate conversion is
needed. The main path is configured around 16 kHz; avoid unnecessary
resampling in the hot path.

# 7. Wake-word detection

## 7.1 Model and asset

Wake phrase: **"Hey EDITH"**.

The final ONNX wake model was trained in a separate reusable wake-word
project and copied into the application model directory as:

`models/wakeword/hey_edith.onnx`

The integration adapts the existing `WakeWordDetector`; it does not
retrain or replace the model.

## 7.2 Recorded validation

The frozen candidate was reported to pass:

-   20/20 intentional live-microphone detections.
-   Scores 0.9750--1.0000 at threshold 0.90.
-   0/30 false activations in a held-out silence test.

These are the recorded test results for that model and setup, not a
universal accuracy guarantee.

## 7.3 `WakeWordAdapter`

The adapter:

1.  Receives shared float32 samples.
2.  Validates finite values.
3.  Converts to clipped int16 PCM.
4.  Feeds the legacy detector's audio buffer.
5.  Checks at its configured interval.
6.  Applies the detector's RMS gate, threshold and cooldown.
7.  Returns `True` on detection.

The adapter does not open a microphone. It currently uses private
methods on the legacy detector (`_add_audio`, `_get_audio_window`,
`_calculate_rms`, `_detect`). This is a coupling point: if those methods
change, update and test the adapter in the same change.

## 7.4 Wake mode sequence

`wait_for_wake_word()`:

1.  Ensures engine startup.
2.  Validates subscription and adapter.
3.  Returns immediately if a wake activation is already pending.
4.  Rejects wake-wait entry during an active conversation.
5.  Discards stale queued audio.
6.  Resets the wake adapter's rolling state.
7.  Reads shared microphone blocks.
8.  Sends blocks to the adapter.
9.  Sets `_wake_detected = True` and returns on detection.

# 8. Silero VAD

## 8.1 Responsibility

VAD answers: **"Does this short frame resemble speech?"** It does not
produce words or independently decide the complete utterance boundary.

The wrapper loads Silero with `load_silero_vad(onnx=True)`. The observed
runtime type was `silero_vad.utils_vad.OnnxWrapper`, and a diagnostic
confirmed it was callable. A Pylance warning about a `SileroVADSequence`
not being callable was a static typing mismatch in the user's
environment; the runtime diagnostic showed `callable(model) == True`. Do
not replace a working inference call based only on that IDE warning.

## 8.2 Frame sizes

  Sample rate     Samples/frame   Duration
  ------------- --------------- ----------
  16 kHz                    512      32 ms
  8 kHz                     256      32 ms

The wrapper buffers incomplete samples until a full frame is available.
It returns one probability per complete frame.

## 8.3 Stateful behaviour

Silero maintains state. `reset()` clears pending samples and calls
`reset_states()` when available. This is important when starting a new
utterance or clearing state after TTS playback.

## 8.4 Recorded `SileroVADConfig`

  Field                          Value
  --------------------------- --------
  `sample_rate`                 16,000
  `threshold`                     0.55
  `min_speech_duration_ms`          80
  `min_silence_duration_ms`        120
  `use_onnx`                      True

**Implementation nuance:** In the supplied wrapper, `process()` performs
model inference and returns probabilities. The endpoint detector applies
its own start and continuation thresholds and silence timing. Do not
assume every config field above is independently enforced inside the
wrapper simply because it is declared there.

Invalid/non-finite samples raise `ValueError`; inference failures are
wrapped in `RuntimeError` with the underlying error.

# 9. Adaptive endpoint detection

## 9.1 Responsibility

Silero produces probabilities frame by frame. The endpoint detector
converts those probabilities into a completed `SpeechSegment`:

-   Confirm speech start.
-   Collect audio.
-   Tolerate pauses.
-   Decide when the utterance is complete.
-   Return audio plus timing/metadata.

VAD estimates activity; endpointing manages utterance lifecycle.

## 9.2 Recorded `EndpointConfig`

  ---------------------------------------------------------------------------------
  Setting                                               Value Meaning
  ------------------------------ ---------------------------- ---------------------
  `sample_rate`                                        16,000 Audio rate

  `pre_roll_seconds`                                      0.5 Recent audio retained
                                                              before speech

  `start_threshold`                                      0.55 Probability to count
                                                              as start

  `continue_threshold`                                   0.35 Probability to
                                                              continue active
                                                              speech

  `start_confirm_ms`                                       64 Required consecutive
                                                              start evidence

  `end_silence_ms`                                      1,000 Short utterance
                                                              silence endpoint

  `long_speech_end_silence_ms`                          3,500 Long utterance pause
                                                              tolerance

  `adaptive_after_speech_ms`                            1,200 Speech duration
                                                              before long mode

  `min_utterance_ms`                                      120 Minimum accepted
                                                              utterance

  `max_utterance_seconds`                                 600 Maximum utterance
                                                              duration

  `adaptive_endpointing`                                 True Enables adaptive
                                                              policy
  ---------------------------------------------------------------------------------

## 9.3 Start and continuation

At 16 kHz, each Silero frame is 32 ms.

-   Probability \>= 0.55 contributes to start confirmation.
-   A frame below 0.55 resets the start-confirmation counter.
-   After at least 64 ms of qualifying evidence, the detector begins an
    utterance and appends pre-roll.
-   During active speech, probability \>= 0.35 resets the silence
    counter and increments speech duration.
-   Probability below 0.35 increments the silence counter.

The lower continuation threshold is hysteresis: continuing an active
utterance is easier than starting a new one.

## 9.4 Adaptive endpoint

Initially, the detector uses 1 second of silence. Once at least 1.2
seconds of speech has accumulated, it uses 3.5 seconds. This permits
natural pauses in longer explanations.

When silence reaches the effective threshold:

-   If the utterance meets minimum duration, `_finish("silence")`
    returns a segment.
-   If it is too short, the detector treats it as short noise and
    resets.

If the accumulator reaches its maximum, the segment is finished with
`ended_by="max_duration"`.

## 9.5 `SpeechSegment`

Contains:

-   `audio`
-   `sample_rate`
-   `started_at`
-   `ended_at`
-   `speech_duration_seconds`
-   `ended_by`

`duration_seconds` is calculated as sample count divided by sample rate.

## 9.6 Reset and noise caution

`endpoint.reset()` clears pre-roll, pending samples, active accumulator,
start/silence/speech counters, timestamps and VAD state.

Do not lower thresholds merely because noise was transcribed. First
inspect probabilities and establish whether background noise actually
activates `_active`. VAD false activation and the conversation idle
timer are separate failure classes.

# 10. Speech-to-text: Faster-Whisper

## 10.1 Responsibility

STT runs after endpointing returns a completed segment. It does not
continuously transcribe the microphone.

The recognition layer contains a replaceable backend interface,
configuration, model manager, engine and structured transcription
result.

## 10.2 Recorded configuration

  Setting                      Recorded value
  ---------------------------- ----------------
  Model                        `small`
  Sample rate                  16 kHz
  Device preference            `auto`
  CPU compute                  `int8`
  GPU compute                  `float16`
  Task                         `transcribe`
  Beam size                    5
  VAD filter                   False
  Condition on previous text   False
  Local files only             True
  Minimum free VRAM for GPU    1,800 MB
  Maximum GPU utilization      75%
  Inference lock               Enabled

Check the current `STTConfig` for the exact live values.

## 10.3 Model manager

`WhisperModelManager`:

-   Loads lazily.
-   Keeps one active Whisper model cache entry.
-   Uses locking around model lifecycle/inference.
-   Selects CUDA FP16 when its GPU checks pass.
-   Otherwise selects CPU int8.
-   Can fall back to CPU after GPU load/inference failure.

The selector uses CTranslate2 CUDA visibility and `nvidia-smi`
information.

## 10.4 Hardware observations and deferred work

Hardware: NVIDIA RTX 3050 Laptop GPU, 4 GB VRAM.

Recorded observations:

-   CUDA FP16: roughly 0.53--0.71 seconds for 6--10 seconds of audio
    under favourable VRAM conditions.
-   Integrated runs: approximately 0.60--0.88 seconds on CUDA.
-   When Ollama occupied most VRAM, Whisper selected CPU int8; measured
    8--10 second audio took approximately 2.56--2.68 seconds.

These measurements are machine- and workload-specific. GPU coordination
and model unload/reload were explicitly deferred. Do not alter STT/GPU
policy while debugging unrelated wake or endpoint issues.

## 10.5 Result and Windows DLL handling

The result contains text, language, language probability, model/device,
processing time, audio duration, classification and segment information.
`VoiceEngine` serializes it with `to_dict()`.

The implementation includes Windows CUDA DLL path handling using the
active environment's `purelib` and retained DLL-directory handles. If
CUDA stops working after an environment change, first verify the active
venv and DLL resolution.

# 11. VoiceEngine integration and state machine

## 11.1 Public interface

-   `start()`
-   `wait_for_wake_word()`
-   `listen()`
-   `prepare_for_next_turn()`
-   `get_stats()`
-   `close()`

`VoiceEngine` coordinates voice input. It does not generate LLM answers
or synthesize Piper audio.

## 11.2 State fields

  -----------------------------------------------------------------------
  Field                               Meaning
  ----------------------------------- -----------------------------------
  `_started`                          Engine/audio resources initialized

  `_wake_detected`                    Wake event awaiting consumption by
                                      `listen()`

  `_conversation_active`              Current conversation permits later
                                      `listen()` calls without another
                                      wake phrase

  `_closed`                           Shutdown has begun
  -----------------------------------------------------------------------

## 11.3 First turn and continuous turns

The first `listen()` requires `_wake_detected`. It consumes that flag
and sets `_conversation_active = True`.

Further calls are permitted while `_conversation_active` remains true.
This is the mechanism that allows multiple turns after one wake phrase.

## 11.4 Seven-second idle timeout

The timeout starts when EDITH is ready for the next user utterance,
after TTS playback and cleanup.

A bug was found because the timeout check originally lived only inside:

``` python
if chunk is None:
    # timeout check
```

The microphone continuously supplies chunks, including silence, so
`chunk` was usually not `None` and the timeout could be skipped.

The corrected structure checks elapsed time on every loop iteration:

``` python
if (
    not endpoint.is_speaking
    and time.monotonic() - listen_started
    >= self.config.speech_start_timeout_seconds
):
    self._conversation_active = False
    return None
```

The check is performed before processing the next chunk. Once endpoint
detection reports active speech, endpointing manages the utterance
rather than the pre-speech timeout.

Recorded setting: `speech_start_timeout_seconds = 7.0`.

**Limitation:** If background noise activates the endpoint detector,
`endpoint.is_speaking` becomes true and the pre-speech timeout is
suspended. If that occurs, inspect VAD probabilities and endpoint state
before changing timeout logic.

## 11.5 Return values

`listen()` returns:

-   A dictionary with transcription data when speech is transcribed.
-   `{"text": ""}` if STT returns no result, allowing another attempt.
-   `None` when the no-speech timeout expires or shutdown interrupts the
    loop.

`main.py` treats `None` as the end of the conversation and returns to
wake-word mode.

# 12. TTS and response orchestration

## 12.1 Existing Piper implementation

TTS remains the existing `TextToSpeech` class from `app.voice.tts`.
Recorded voice asset:

`en_US-lessac-medium.onnx`

Voice Engine v2 does not replace Piper; `main.py` coordinates it.

## 12.2 Streaming text to speech

`edith.respond_stream(...)` yields response text incrementally.
`extract_speech_chunks()` accumulates text and emits manageable pieces:

-   Prefer sentence boundaries after punctuation.
-   If a buffer reaches roughly 180 characters, split at a nearby word
    boundary.
-   Flush remaining text when generation finishes.

This lets Piper start before the entire LLM response has been generated.

## 12.3 Worker queue ordering

A worker thread calls `tts.speak_stream(speech_queue)`. The main thread
enqueues chunks. At the end it adds `None` as the sentinel, then waits
for:

1.  `speech_queue.join()`
2.  `worker.join()`

Only after both waits does it call `voice.prepare_for_next_turn()`.

This ordering is essential. Cleanup must happen after Piper has
completed playback.

## 12.4 Exit command

`is_exit_command()` case-folds text, strips punctuation and checks for
the exact normalized word `exit`. It is handled before LLM generation.
On exit, EDITH speaks "Goodbye." and the application shutdown path runs.

# 13. TTS self-transcription prevention

## 13.1 Failure mechanism

The microphone remains active while Piper plays through speakers. It
therefore captures EDITH's own response. Clearing the queue once is not
sufficient if additional playback-tail or reverberation blocks arrive
around the cleanup boundary.

## 13.2 Current `prepare_for_next_turn()` strategy

The final reported implementation:

1.  Check that a conversation is active.
2.  Get the existing subscription.
3.  Discard queued blocks captured during TTS playback.
4.  Wait for a short acoustic settling period (recorded value: 0.5
    seconds).
5.  Discard blocks captured during that settling period.
6.  Reset endpoint/VAD state.
7.  Report that the microphone is ready for the next user turn.

This is a post-playback guard, not a change to endpoint silence
thresholds.

## 13.3 Guarantees and limits

The user reported that this fixed the observed final-word
self-transcription in their environment.

It is **not full acoustic echo cancellation**. High speaker volume,
microphone gain, close speaker/mic placement or a reverberant room may
still cause false capture.

If the issue returns, check in order:

1.  TTS worker really completed.
2.  `speech_queue.join()` and `worker.join()` both completed.
3.  Cleanup runs after those waits.
4.  First discard count.
5.  Settling interval execution.
6.  Second discard count.
7.  Endpoint/VAD reset.
8.  Whether the same subscription is retained.

If those are correct and playback is still captured, investigate
physical acoustic coupling, explicit playback gating or proper AEC. Do
not keep increasing delays blindly.

# 14. Main application lifecycle

`main.py` constructs and connects:

-   `EdithAssistant`
-   `OllamaClient`
-   `VoiceEngine`
-   `TextToSpeech`
-   `MemoryService`
-   `MemoryManager`
-   `BackgroundMemoryWorker`
-   `ConversationService`

Simplified flow:

``` python
while app_is_running:
    voice.wait_for_wake_word()

    while conversation_active:
        result = voice.listen()

        if result is None:
            break

        user_text = result["text"]

        if is_exit_command(user_text):
            tts.speak("Goodbye.")
            stop()
            break

        start_tts_worker()
        for text_chunk in edith.respond_stream(user_text):
            enqueue_tts(text_chunk)

        signal_worker_finished()
        wait_for_queue_and_worker()
        voice.prepare_for_next_turn()
```

Shutdown uses nested `try/finally` blocks to attempt closure of all
resources:

1.  `voice.close()`
2.  `tts.close()`
3.  `memory_worker.close()`

`VoiceEngine.close()` marks the engine closed, clears conversation/wake
flags, closes its subscription, stops the audio service only if it owns
that service, closes STT and clears started state. The ownership flag
matters: injected external audio services should not be stopped by an
engine that does not own them.

# 15. Dependencies and environment

Recorded environment:

  Item            Recorded value
  --------------- ----------------------------------
  OS              Windows 11
  Python          3.13.2
  Venv            `D:\Edith\.venv`
  GPU             NVIDIA RTX 3050 Laptop GPU, 4 GB
  Audio capture   `sounddevice`
  Arrays          NumPy
  VAD             `silero-vad`, ONNX mode
  Runtime         `onnxruntime`
  STT             `faster-whisper` / CTranslate2
  GPU STT         CUDA FP16 when selected
  CPU fallback    int8
  Resampling      `python-soxr`
  TTS             Existing Piper implementation
  Wake model      ONNX `hey_edith.onnx`
  Local LLM       Ollama `llama3.2:3b`

Exact package versions in the current dependency file and active
environment are authoritative.

Useful PowerShell checks:

``` powershell
cd D:\Edith
.\.venv\Scripts\Activate.ps1

python --version
python -c "import sys; print(sys.executable)"
python -c "import numpy, sounddevice, torch, onnxruntime; print('core imports OK')"
python -c "from silero_vad import load_silero_vad; m=load_silero_vad(onnx=True); print(type(m)); print(callable(m))"
python -c "import ctranslate2; print(ctranslate2.get_cuda_device_count())"
python -m pytest app/voice_v2/tests/ -v
```

# 16. Test history and acceptance evidence

## 16.1 Audio capture

Phase 1 hardware test:

-   Approximately 9.98 seconds captured.
-   499 blocks.
-   159,680 samples.
-   Zero callback overflows.
-   Zero dropped input blocks.
-   Clean stop.

## 16.2 VAD and endpointing

A Phase 3 suite reported `17 passed in 0.48s`. Manual tests covered
silence, short command, normal speech, natural pause and long speech. A
later integration test confirmed two sentences separated by a two-second
pause were included in one transcript.

## 16.3 STT and integration

-   CTranslate2 CUDA device visibility and FP16 support confirmed.
-   Integrated wake-to-transcription test recognized a question.
-   Integration suite reported `29 passed`.
-   Manual checks: `Exit.` passed; natural pause passed; repeated wake
    passed; no audio overflow/drop in that run.

## 16.4 Continuous conversation

The user's runtime log showed:

-   Wake detected.
-   First question transcribed and answered.
-   Further turns accepted without another wake phrase.
-   Seven seconds of no speech caused sleep/return to wake mode.
-   A later wake phrase was detected.
-   `Exit.` was recognized.
-   Shutdown completed.

## 16.5 TTS cleanup

The user reported that the post-playback cleanup change resolved the
observed final-word self-transcription issue.

## 16.6 Regression checklist

-   [ ] Correct `.venv` interpreter.
-   [ ] Only one microphone stream.
-   [ ] Wake phrase detected.
-   [ ] First utterance captured without clipping.
-   [ ] Short command captured.
-   [ ] Natural pause does not split intended utterance.
-   [ ] STT result is usable.
-   [ ] Second turn works without another wake phrase.
-   [ ] More than seven seconds of silence returns to wake mode.
-   [ ] EDITH's playback is not transcribed as user speech.
-   [ ] A real question immediately after cleanup is captured.
-   [ ] `Exit.` works.
-   [ ] Voice, TTS and memory worker close cleanly.
-   [ ] No unexpected audio overflow/drop growth.

# 17. Troubleshooting

## A. Wake phrase not detected

Check microphone stream state, subscription block count, model path,
sample format, RMS gate, threshold and cooldown. Confirm the adapter
receives 16 kHz mono float32 before conversion to int16. Do not retrain
the frozen model without a reproducible controlled failure.

## B. Wake detected but no transcription

Trace the pipeline in order:

1.  `wait_for_wake_word()` returns.
2.  `_wake_detected` is consumed.
3.  `_conversation_active` becomes true.
4.  `endpoint.process()` receives blocks.
5.  Silero produces probabilities.
6.  Endpoint detector returns a `SpeechSegment`.
7.  STT model loads and transcribes.

Log segment duration and `ended_by`.

## C. First syllable clipped

Inspect pre-roll, start confirmation, pre-roll append logic and audio
drop counters. The recorded pre-roll is 0.5 seconds. Clipping is
upstream of STT; do not begin by increasing Whisper beam size.

## D. Natural pause splits utterance

Inspect adaptive endpointing, `_speech_samples`, the 1.2-second adaptive
threshold and 3.5-second long-speech silence threshold. Reducing long
silence can split thoughtful speech; increasing it adds endpoint
latency.

## E. EDITH never sleeps during silence

Verify timeout is checked on every loop iteration, not only when
`chunk is None`. Then inspect `endpoint.is_speaking`. If noise activates
VAD, the pre-speech timeout is suspended by design. Log probabilities
and endpoint state before changing thresholds.

## F. EDITH transcribes its own final word

Verify TTS completion, queue join, worker join, cleanup order,
first/second discard, settling interval, endpoint reset and subscription
identity. If all are correct, investigate acoustic coupling or AEC. Do
not add arbitrary delays without measuring.

## G. STT moves from CUDA to CPU

Inspect free VRAM, GPU utilization, Ollama usage, model manager's
selection reason, CTranslate2 CUDA visibility and Windows DLL paths. CPU
selection may be expected below the configured 1,800 MB free-VRAM
threshold. Do not unload/reload models as an unrelated fix.

## H. Audio overflows or drops

Inspect `AudioInputService.get_stats()`. Look for slow consumers,
blocked dispatcher, inference inside callbacks, CPU saturation or
unsupported device settings. Larger queues can hide a throughput issue
while adding latency; do not increase them indefinitely.

## I. Pylance says Silero model is not callable

The runtime diagnostic showed `OnnxWrapper` and
`callable(model) == True`. Verify installed package/runtime. Treat it as
a typing issue unless runtime inference actually fails.

# 18. Safe change protocol

Debug from the earliest failing boundary:

1.  Capture: are valid blocks arriving?
2.  Distribution: is the correct subscription receiving them?
3.  Wake/VAD: are detections/probabilities sensible?
4.  Endpoint: is a segment produced?
5.  STT: does audio become correct text?
6.  Main loop: is transcript routed correctly?
7.  LLM: is response generated correctly?
8.  TTS: does playback complete?
9.  Cleanup: is stale playback removed before the next turn?

Rules:

-   Preserve the single-microphone-stream design.
-   Never add a second microphone stream for wake detection.
-   Do not tune VAD to compensate for a main-loop state bug.
-   Do not modify STT/GPU policy while debugging endpointing.
-   Do not modify Piper while debugging capture unless evidence points
    to TTS.
-   Keep orchestration in `main.py` and voice-input lifecycle in
    `VoiceEngine`.
-   Comment non-obvious state transitions and concurrency logic.
-   Add a focused regression test for each fix.
-   Run `python -m pytest app/voice_v2/tests/ -v`.
-   Preserve a known-good Git checkpoint before architectural changes.

# 19. Known limitations

1.  No barge-in while Piper is speaking.
2.  No partial/streaming STT.
3.  No speaker verification.
4.  Queue discard plus settling is not full AEC.
5.  Background noise can still trigger VAD.
6.  Ollama and Whisper share limited VRAM; Whisper may fall back to CPU.
7.  Wake adapter depends on private methods in the legacy detector.
8.  Microphone gain, speaker volume, room echo and drivers affect
    results.
9.  Short/noisy/multilingual speech can be misrecognized; low-confidence
    or noise-like transcripts should not be blindly stored as memory.

# 20. Future extension points (not implemented)

-   Acoustic echo cancellation using playback reference.
-   Explicit TTS playback-state gate.
-   Barge-in and cancellation.
-   Optional speaker verification/authorization.
-   Partial/streaming STT.
-   VAD probability tracing/diagnostic mode.
-   Audio device selection UI.
-   Long-duration soak tests.
-   Configurable wake phrase/model provider.
-   Better handling of low-confidence or language-mismatched transcripts
    before memory ingestion.

These should be isolated extensions, not bundled into routine bug fixes.

# 21. Quick configuration reference

  Area           Setting                   Recorded value
  -------------- ----------------------- ----------------
  Audio          Sample rate                    16,000 Hz
  Audio          Channels                               1
  Audio          Block duration                     20 ms
  Audio          Samples/block                        320
  Wake adapter   Check interval                    0.25 s
  Endpoint       Pre-roll                           0.5 s
  Endpoint       Start threshold                     0.55
  Endpoint       Continue threshold                  0.35
  Endpoint       Start confirm                      64 ms
  Endpoint       Short end silence               1,000 ms
  Endpoint       Long end silence                3,500 ms
  Endpoint       Adaptive after speech           1,200 ms
  Endpoint       Minimum utterance                 120 ms
  Endpoint       Maximum utterance                  600 s
  VoiceEngine    Wake queue timeout                 0.5 s
  VoiceEngine    Speech-start timeout                 7 s
  TTS cleanup    Settling period                    0.5 s
  STT            Model                              small
  STT            GPU compute                      float16
  STT            CPU compute                         int8
  STT            Minimum free VRAM               1,800 MB

If the repository differs, trust the current source/config.

# 22. Quick-start and smoke test

``` powershell
cd D:\Edith
.\.venv\Scripts\Activate.ps1
python -m app.main
```

Expected startup:

``` text
EDITH is ready — Local AI: Online

Continuous Conversation Mode enabled.
Say 'Hey EDITH' to start.
Say 'exit' to stop.

[READY] Waiting for wake word...
```

Smoke test:

1.  Say "Hey EDITH".
2.  Ask a short question.
3.  Wait for the answer.
4.  Ask another question without repeating the wake phrase.
5.  Stay silent for more than seven seconds.
6.  Confirm return to wake-word mode.
7.  Say "Hey EDITH" again.
8.  Say "Exit."
9.  Confirm clean shutdown.

Test suite:

``` powershell
python -m pytest app/voice_v2/tests/ -v
```

# 23. Final architecture summary

-   `AudioInputService` owns the one persistent microphone stream.
-   `AudioSubscription` distributes captured blocks.
-   `WakeWordAdapter` adapts the existing detector to shared audio.
-   `SileroVAD` estimates speech probability on fixed-size frames.
-   `AdaptiveEndpointDetector` turns probabilities into complete speech
    segments.
-   `SpeechToTextEngine` converts those segments into structured text.
-   `VoiceEngine` manages wake state, conversation state, listening and
    idle timeout.
-   `main.py` routes text through the assistant and streams the
    response.
-   `TextToSpeech`/Piper speaks on a worker thread.
-   `prepare_for_next_turn()` discards playback audio, waits for
    acoustic settling, discards again and resets endpoint/VAD state.

The key maintenance principle is separation of responsibility: capture
once, distribute safely, detect utterance boundaries before
transcription, keep application orchestration outside the voice engine,
and clean up playback audio before accepting the next user turn.

This document captures the stable implementation checkpoint and recorded
evidence. Exact source code and tests in the checked-out repository
remain authoritative.
