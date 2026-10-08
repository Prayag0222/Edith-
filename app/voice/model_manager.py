from faster_whisper import WhisperModel


class WhisperModelManager:
    """
    Manages Whisper model loading and caching.

    Available configurations:

        CPU:
            small + int8

        GPU:
            medium + float16
    """

    def __init__(self):
        self.cpu_model = None
        self.gpu_model = None

    def get_cpu_model(self):
        """
        Return the cached CPU Whisper model.

        If it hasn't been loaded yet, load it first.
        """

        if self.cpu_model is not None:
            return self.cpu_model

        print(
            "\nLoading Whisper model 'small' using CPU..."
        )

        self.cpu_model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8",
        )

        print(
            "Whisper STT: CPU small model ready"
        )

        return self.cpu_model

    def get_gpu_model(self):
        """
        Return the cached GPU Whisper model.

        If it hasn't been loaded yet, load it first.
        """

        if self.gpu_model is not None:
            return self.gpu_model

        print(
            "\nLoading Whisper model 'medium' using CUDA..."
        )

        self.gpu_model = WhisperModel(
            "medium",
            device="cuda",
            compute_type="float16",
        )

        print(
            "Whisper STT: CUDA medium model ready"
        )

        return self.gpu_model   