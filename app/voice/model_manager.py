class WhisperModelManager:
    """
    Manages Whisper model loading and caching.

    Models:

        CPU:
            small + int8

        GPU:
            medium + float16

    Whisper and Faster-Whisper are imported lazily so that
    EDITH does not initialize the Whisper stack during startup.
    """

    def __init__(self):
        self.cpu_model = None
        self.gpu_model = None

    def get_cpu_model(self):
        """
        Return the cached CPU Whisper model.

        The model is loaded only when it is first requested.
        """

        if self.cpu_model is not None:
            return self.cpu_model

        from faster_whisper import WhisperModel

        print("[STT] Loading small model on CPU...")

        self.cpu_model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8",
        )

        print("[STT] CPU small model ready.")

        return self.cpu_model

    def get_gpu_model(self):
        """
        Return the cached GPU Whisper model.

        The model is loaded only when it is first requested.
        """

        if self.gpu_model is not None:
            return self.gpu_model

        from faster_whisper import WhisperModel

        print("[STT] Loading medium model on CUDA...")

        self.gpu_model = WhisperModel(
            "medium",
            device="cuda",
            compute_type="float16",
        )

        print("[STT] CUDA medium model ready.")

        return self.gpu_model

    def is_cpu_model_loaded(self) -> bool:
        """Return True if the CPU model is already loaded."""
        return self.cpu_model is not None

    def is_gpu_model_loaded(self) -> bool:
        """Return True if the GPU model is already loaded."""
        return self.gpu_model is not None