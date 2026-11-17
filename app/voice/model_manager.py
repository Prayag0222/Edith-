from threading import Lock


class WhisperModelManager:
    """
    Manages Whisper model loading and caching.

    CPU:
        small + int8

    GPU:
        medium + float16

    Models are loaded lazily and cached.
    Thread-safe loading prevents duplicate initialization.
    """

    def __init__(self):
        self.cpu_model = None
        self.gpu_model = None

        self._cpu_lock = Lock()
        self._gpu_lock = Lock()

    # --------------------------------------------------
    # CPU MODEL
    # --------------------------------------------------

    def get_cpu_model(self):
        """Return the cached CPU Whisper model."""

        if self.cpu_model is not None:
            return self.cpu_model

        with self._cpu_lock:
            # Check again after acquiring the lock.
            if self.cpu_model is not None:
                return self.cpu_model

            from faster_whisper import WhisperModel

            print("[STT] Loading small model on CPU...")

            model = WhisperModel(
                "small",
                device="cpu",
                compute_type="int8",
                local_files_only=True,
            )

            self.cpu_model = model

            print("[STT] CPU small model ready.")

            return self.cpu_model

    # --------------------------------------------------
    # GPU MODEL
    # --------------------------------------------------

    def get_gpu_model(self):
        """Return the cached GPU Whisper model."""

        if self.gpu_model is not None:
            return self.gpu_model

        with self._gpu_lock:
            # Check again after acquiring the lock.
            if self.gpu_model is not None:
                return self.gpu_model

            from faster_whisper import WhisperModel

            print("[STT] Loading medium model on CUDA...")

            model = WhisperModel(
                "medium",
                device="cuda",
                compute_type="float16",
                local_files_only=True,
            )

            self.gpu_model = model

            print("[STT] CUDA medium model ready.")

            return self.gpu_model

    # --------------------------------------------------
    # MODEL STATUS
    # --------------------------------------------------

    def is_cpu_model_loaded(self) -> bool:
        return self.cpu_model is not None

    def is_gpu_model_loaded(self) -> bool:
        return self.gpu_model is not None