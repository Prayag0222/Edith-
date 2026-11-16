import sounddevice as sd


def list_input_devices() -> list[dict]:
    result = []
    for index, device in enumerate(sd.query_devices()):
        if int(device.get("max_input_channels", 0)) > 0:
            result.append({
                "index": index,
                "name": device.get("name", "Unknown"),
                "max_input_channels": int(device["max_input_channels"]),
                "default_samplerate": int(device.get("default_samplerate", 0)),
            })
    return result
