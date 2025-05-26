import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Muat variabel dari .env
load_dotenv()

class ConfigManager:
    """
    Manages settings split between local (settings_local.json) and remote (settings_remote.json).
    Values in remote override local during read (get), lalu fallback ke .env.
    """

    _TIER_SECTION = {
        "basic":   "coqui",
        "premium": "gtts_standard",
        "pro":     "chirp3",
    }

    def __init__(self,
                 local_path: str = "settings_local.json",
                 remote_path: str = "settings_remote.json",
                 voices_path: str = "voices.json"):
        self.local_path = Path(local_path)
        self.remote_path = Path(remote_path)
        self.voices_path = Path(voices_path)

        self.local_data = {}
        self.remote_data = {}
        self.voices = {}

        self.load_settings()
        self.load_voices()

    def load_settings(self):
        if self.local_path.exists():
            with open(self.local_path, "r", encoding="utf-8") as f:
                self.local_data = json.load(f)
        else:
            self.local_data = {}

        if self.remote_path.exists():
            with open(self.remote_path, "r", encoding="utf-8") as f:
                self.remote_data = json.load(f)
        else:
            self.remote_data = {}

    def save_settings(self):
        self.local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.local_path, "w", encoding="utf-8") as f:
            json.dump(self.local_data, f, indent=2)

    def get(self, key: str, default=None):
        if key in self.remote_data:
            return self.remote_data[key]
        elif key in self.local_data:
            return self.local_data[key]
        else:
            return os.getenv(key.upper(), default)

    def set(self, key: str, value):
        self.local_data[key] = value
        self.save_settings()

    def load_voices(self):
        if self.voices_path.exists():
            with open(self.voices_path, "r", encoding="utf-8") as f:
                self.voices = json.load(f)
        else:
            self.voices = {}
        return self.voices

    def get_available_voices(self):
        tier = self.get("tts_tier", "basic")
        section = self._TIER_SECTION.get(tier, "coqui")
        return self.voices.get(section, {})

    def list_voice_models(self):
        available = self.get_available_voices()
        models = []
        if isinstance(available, dict):
            for lang, specs in available.items():
                if isinstance(specs, dict):
                    for model_id, meta in specs.items():
                        models.append({
                            'language': lang,
                            'model_id': model_id,
                            'gender': meta.get("gender"),
                            'display': f"{lang} / {model_id}"
                        })
                else:
                    for voice in specs:
                        models.append({
                            'language': lang,
                            'model_id': voice.get("model"),
                            'gender': voice.get("gender"),
                            'display': voice.get("display", f"{lang} / {voice.get('model')}")
                        })
        return models

    def get_translate_hotkey(self, default=None):
        return self.get("translate_hotkey", default)

    def get_cohost_hotkey(self, default=None):
        return self.get("cohost_hotkey", default)


# Fungsi tambahan untuk VPS: load config dari file remote
def load_remote_config():
    return ConfigManager(
        local_path="settings_local.json",
        remote_path="settings_remote.json",
        voices_path="voices.json"
    )
