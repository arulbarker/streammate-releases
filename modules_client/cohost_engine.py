# modules/cohost_engine.py

import json
import os
from modules.tts_google import speak_with_google_cloud

def respond_with_voice(prompt):
    print(f"🧠 Co-Host menjawab dengan suara: {prompt}")
    config_path = "config/live_state.json"
    if not os.path.exists(config_path):
        print("⚠️ Config belum ada.")
        return

    with open(config_path, "r") as f:
        config = json.load(f)

    # Gunakan voice dari config atau gunakan default
    voice = config.get("voice", "id-ID-Wavenet-A")
    use_virtual_mic = config.get("virtual_mic_active", False)
    device_index = config.get("virtual_mic_device_index", None)

    if use_virtual_mic and device_index is not None:
        speak_with_google_cloud(prompt, voice, device_index=device_index, also_play_on_speaker=True)
    else:
        speak_with_google_cloud(prompt, voice, also_play_on_speaker=True)
