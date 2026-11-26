import logging
import os
from pathlib import Path
import threading
import time
import numpy as np
from .base import STTBackend
from .config import STTConfig
from .model_manager import WhisperModelManager
from .transcription_result import TranscriptionResult, TranscriptionSegment
from app.voice_v2.processing.audio_processor import AudioProcessor


logger = logging.getLogger(__name__)


def setup_cuda_dll_paths():
    import sysconfig
    import os

    if not hasattr(os, "add_dll_directory"):
        return []

    handles = []
    site_packages = sysconfig.get_path("purelib")
    nvidia_path = os.path.join(site_packages, "nvidia")

    dll_directories = [
        os.path.join(nvidia_path, "cublas", "bin"),
        os.path.join(nvidia_path, "cudnn", "bin"),
    ]

    existing_path = os.environ.get("PATH", "")
    existing_entries = {
        os.path.normcase(os.path.abspath(entry))
        for entry in existing_path.split(os.pathsep)
        if entry
    }
    path_entries = []
    for directory in dll_directories:
        if os.path.isdir(directory):
            handles.append(os.add_dll_directory(directory))
            if os.path.normcase(os.path.abspath(directory)) not in existing_entries:
                path_entries.append(directory)

    if path_entries:
        if existing_path:
            path_entries.append(existing_path)
        os.environ["PATH"] = os.pathsep.join(path_entries)

    return handles


_CUDA_DLL_HANDLES = setup_cuda_dll_paths()

class SpeechToTextEngine(STTBackend):
    # Accepts completed Phase 3 audio; never opens a microphone or runs VAD.
    def __init__(self, config=None, model_manager=None, task_classifier=None):
        self.config = config or STTConfig()
        self.model_manager = model_manager or WhisperModelManager(self.config)
        self.task_classifier = task_classifier
        self.audio_processor = AudioProcessor()
        self._lock = threading.Lock()

    def _prepare_audio(self, audio):
        a = np.asarray(audio, dtype=np.float32)
        if a.ndim == 2:
            a = a.mean(axis=0 if a.shape[0] <= 8 and a.shape[1] > a.shape[0] else 1)
        elif a.ndim != 1:
            raise ValueError("Audio must be 1-D mono or 2-D multichannel")
        a = np.ascontiguousarray(a.reshape(-1), dtype=np.float32)
        if not a.size: raise ValueError("Audio array is empty")
        if not np.all(np.isfinite(a)): raise ValueError("Audio contains NaN or infinite values")
        if float(np.max(np.abs(a))) > 1.5:
            raise ValueError("Expected normalized float32 waveform approximately in [-1, 1]")
        return a

    def _classify(self, text):
        if self.task_classifier is None:
            try:
                from app.voice.task_classifier import VoiceTaskClassifier
                self.task_classifier = VoiceTaskClassifier()
            except Exception:
                return "conversation", 0.5, "Default classification"
        c = self.task_classifier.classify(text)
        return (getattr(c, "task_type", "unknown"), float(getattr(c, "confidence", 0.0)),
                str(getattr(c, "reason", "")))

    def _run(self, model, source, language, beam):
        segments, info = model.transcribe(
            source, beam_size=beam, language=language, task=self.config.task,
            vad_filter=self.config.vad_filter,
            condition_on_previous_text=self.config.condition_on_previous_text,
            temperature=self.config.temperature,
            initial_prompt=self.config.initial_prompt,
            no_speech_threshold=self.config.no_speech_threshold)
        texts, out = [], []
        # Faster-Whisper returns a lazy generator; consume it exactly once.
        for s in segments:
            no_speech_prob = getattr(s, "no_speech_prob", None)
            if (
                no_speech_prob is not None
                and no_speech_prob >= self.config.no_speech_threshold
            ):
                continue
            text = (s.text or "").strip()
            if text:
                texts.append(text)
                out.append(TranscriptionSegment(float(s.start), float(s.end), text))
        p = getattr(info, "language_probability", None)
        duration = getattr(info, "duration", None)
        return (" ".join(texts).strip(), getattr(info, "language", None),
                float(p) if p is not None else None,
                float(duration) if duration is not None else None, tuple(out))

    def transcribe(self, audio, *, language=None, beam_size=None):
        denoise_ms = 0.0
        if isinstance(audio, (str, os.PathLike)):
            path = Path(audio)
            if not path.is_file(): raise FileNotFoundError(f"Audio file not found: {path}")
            source, input_duration = str(path), None
        else:
            source = self._prepare_audio(audio)
            denoise_started = time.perf_counter()
            source = self.audio_processor.process(
                source,
                sample_rate=self.config.sample_rate,
            )
            source = self._prepare_audio(source)
            denoise_ms = (time.perf_counter() - denoise_started) * 1000
            input_duration = source.size / self.config.sample_rate
            if self.audio_processor.analyze(source).is_silent:
                logger.info(
                    "STT skipped silent audio | denoise_ms=%.2f stt_ms=0.00",
                    denoise_ms,
                )
                return None
        beam = self.config.beam_size if beam_size is None else beam_size
        if beam < 1: raise ValueError("beam_size must be >= 1")

        lock = self._lock if self.config.inference_lock else _NullLock()
        with lock:
            started = time.perf_counter()
            model, decision = self.model_manager.get_cpu_model()
            print(f"[STT DEBUG] Selected device: {decision.device}")
            print(f"[STT DEBUG] Selected model: {decision.model_size}")
            print(f"[STT DEBUG] Selection reason: {decision.reason}")
            status = getattr(self.model_manager, "status", None)
            if callable(status):
                print(f"[STT DEBUG] Model manager status: {status()}")
            try:
                values = self._run(model, source, language or self.config.language, beam)
            except Exception as exc:
                logger.exception("CPU STT inference failed")
                raise
            stt_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "STT timings | denoise_ms=%.2f stt_ms=%.2f",
                denoise_ms,
                stt_ms,
            )

        text, lang, probability, duration, segments = values
        if not text: return None
        task_type, confidence, reason = self._classify(text)
        return TranscriptionResult(
            text=text, language=lang, language_probability=probability,
            model_size=decision.model_size, device=decision.device,
            compute_type=decision.compute_type, selection_reason=decision.reason,
            processing_seconds=stt_ms / 1000,
            audio_duration_seconds=duration if duration is not None else input_duration,
            task_type=task_type, classification_confidence=confidence,
            classification_reason=reason, segments=segments)

    def transcribe_file(self, audio_path, *, language=None, beam_size=None):
        return self.transcribe(audio_path, language=language, beam_size=beam_size)

    def close(self):
        self.model_manager.close()

class _NullLock:
    def __enter__(self): return self
    def __exit__(self, *args): return False
