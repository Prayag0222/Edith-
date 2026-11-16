import os
import threading


_DLL_DIRECTORY_HANDLES = []
_SETUP_LOCK = threading.Lock()
_CONFIGURED = False


def setup_cuda_runtime() -> bool:
    """
    Configure NVIDIA CUDA DLL search paths on Windows.

    Keeps DLL directory handles alive and prevents
    duplicate PATH entries across repeated calls.
    """

    global _CONFIGURED

    with _SETUP_LOCK:

        if _CONFIGURED:
            return True

        try:
            import nvidia.cublas
            import nvidia.cudnn

            cublas_path = os.path.join(
                nvidia.cublas.__path__[0],
                "bin",
            )

            cudnn_path = os.path.join(
                nvidia.cudnn.__path__[0],
                "bin",
            )

            dll_paths = (cublas_path, cudnn_path)

            for path in dll_paths:
                if not os.path.isdir(path):
                    raise FileNotFoundError(
                        f"CUDA DLL directory not found: {path}"
                    )

            # Register DLL directories and retain handles.
            if hasattr(os, "add_dll_directory"):
                for path in dll_paths:
                    handle = os.add_dll_directory(path)
                    _DLL_DIRECTORY_HANDLES.append(handle)

            # Add directories to PATH without duplicates.
            existing_paths = os.environ.get("PATH", "").split(
                os.pathsep
            )

            existing_normalized = {
                os.path.normcase(os.path.normpath(p))
                for p in existing_paths
                if p
            }

            new_paths = [
                path
                for path in dll_paths
                if os.path.normcase(os.path.normpath(path))
                not in existing_normalized
            ]

            if new_paths:
                os.environ["PATH"] = os.pathsep.join(
                    new_paths + existing_paths
                )

            _CONFIGURED = True
            return True

        except Exception as error:
            print(f"CUDA runtime setup failed: {error}")
            return False