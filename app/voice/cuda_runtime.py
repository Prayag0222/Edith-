import os


def setup_cuda_runtime():
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

        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(cublas_path)
            os.add_dll_directory(cudnn_path)

        os.environ["PATH"] = (
            cublas_path
            + os.pathsep
            + cudnn_path
            + os.pathsep
            + os.environ.get("PATH", "")
        )

        print("CUDA runtime libraries configured.")

        return True

    except Exception as e:
        print(f"CUDA runtime setup failed: {e}")
        return False