import sounddevice as sd

def list_output_devices():
    devices = sd.query_devices()
    output_devices = []
    for i, device in enumerate(devices):
        if device['max_output_channels'] > 0:
            output_devices.append({
                'index': i,
                'name': device['name'],
                'channels': device['max_output_channels']
            })
    return output_devices

