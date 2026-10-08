from openwakeword.model import Model
from openwakeword.utils import download_models


print("Downloading wake-word models...")

download_models()
print("Loading wake-word engine...")

model = Model(inference_framework="onnx")

print("Wake-word engine loaded successfully.")
print("Available models:")

for name in model.models:
    print(f" - {name}")