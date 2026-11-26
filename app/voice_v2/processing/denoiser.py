from __future__ import annotations

import logging
from pathlib import Path
import threading

import numpy as np


logger = logging.getLogger(__name__)

DENOISE_ENABLED = True
SAMPLE_RATE = 16000
MODEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "models"
    / "denoiser"
    / "gtcrn_simple.onnx"
)


class _GTCRNDenoiser:
    def __init__(self):
        self._lock = threading.Lock()
        self._load_attempted = False
        self._model = None

    def _load(self):
        if not MODEL_PATH.is_file():
            logger.warning(
                "GTCRN model not found at %s; using raw audio",
                MODEL_PATH,
            )
            return

        try:
            import sherpa_onnx

            config = sherpa_onnx.OfflineSpeechDenoiserConfig(
                model=sherpa_onnx.OfflineSpeechDenoiserModelConfig(
                    gtcrn=sherpa_onnx.OfflineSpeechDenoiserGtcrnModelConfig(
                        model=str(MODEL_PATH)
                    ),
                    debug=False,
                    num_threads=1,
                    provider="cpu",
                )
            )
            if not config.validate():
                logger.error("Invalid GTCRN configuration; using raw audio")
                return

            self._model = sherpa_onnx.OfflineSpeechDenoiser(config)
            logger.info("GTCRN speech denoiser loaded on CPU")
        except Exception:
            logger.exception("Could not load GTCRN; using raw audio")

    def process(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        samples = np.ascontiguousarray(audio, dtype=np.float32).reshape(-1)
        if not DENOISE_ENABLED or sample_rate != SAMPLE_RATE or not samples.size:
            return samples

        with self._lock:
            if not self._load_attempted:
                self._load_attempted = True
                self._load()

            if self._model is None:
                return samples

            try:
                result = self._model(samples, sample_rate)
                enhanced = np.asarray(
                    result.samples,
                    dtype=np.float32,
                ).reshape(-1)
                if (
                    result.sample_rate != SAMPLE_RATE
                    or not enhanced.size
                    or not np.all(np.isfinite(enhanced))
                ):
                    logger.warning(
                        "GTCRN returned invalid audio; using raw audio"
                    )
                    return samples
                return enhanced
            except Exception:
                logger.exception("GTCRN inference failed; using raw audio")
                self._model = None
                return samples


_denoiser = _GTCRNDenoiser()


def denoise_audio(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    return _denoiser.process(audio, sample_rate)
