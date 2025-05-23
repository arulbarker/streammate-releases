import sounddevice as sd

print("\n🔊 Daftar Output Device (Speaker):\n")
for i, dev in enumerate(sd.query_devices()):
    if dev['max_output_channels'] > 0:
        print(f"[{i}] {dev['name']}")
