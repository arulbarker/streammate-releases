import json
from pathlib import Path

class ConfigManager:
    """
    Manages application settings (settings.json) and available voices (voices.json).
    Supports filtering voice models by subscription tier.
    """
    # mapping package tiers ke sections di voices.json
    _TIER_SECTION = {
        "basic":   "coqui",
        "premium": "gtts_standard",
        "pro":     "chirp3",
    }

    def __init__(self,
                 config_path: str = "config/settings.json",
                 voices_path: str = "config/voices.json"):
        # path ke settings dan voices
        self.config_path = Path(config_path)
        self.voices_path = Path(voices_path)

        # data runtime
        self.data = {}
        self.voices = {}

        # muat dari disk
        self.load_settings()
        self.load_voices()

    def load_settings(self) -> dict:
        """Load settings dari settings.json."""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {}
        return self.data

    def save_settings(self) -> None:
        """Simpan data setting ke settings.json."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def get(self, key: str, default=None):
        """Dapatkan nilai setting, atau default jika tidak ada."""
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        """Perbarui setting dan simpan ke disk segera."""
        self.data[key] = value
        self.save_settings()

    def load_voices(self) -> dict:
        """Load semua voice model dari voices.json."""
        if self.voices_path.exists():
            with open(self.voices_path, "r", encoding="utf-8") as f:
                self.voices = json.load(f)
        else:
            self.voices = {}
        return self.voices

    def get_available_voices(self) -> dict:
        """
        Kembalikan subset voices.json sesuai tier saat ini.
        Keys bergantung pada 'basic', 'premium', atau 'pro'.
        """
        tier = self.get("tts_tier", "basic")
        section = self._TIER_SECTION.get(tier, "coqui")
        return self.voices.get(section, {})

    def list_voice_models(self) -> list:
        """
        Flatten available voices menjadi list.
        Masing-masing entry dict:
            {
              'language': <kode atau nama bahasa>,
              'model_id': <identifier model>,
              'gender':   <"MALE"|"FEMALE"|None>,
              'display':  <label untuk UI>
            }
        """
        models = []
        for lang, voices_dict in self.get_available_voices().items():
            for model_id, info in voices_dict.items():
                gender  = info.get("gender")
                display = info.get("display", model_id)
                models.append({
                    "language": lang,
                    "model_id":  model_id,
                    "gender":    gender,
                    "display":   display,
                })
        return models

    # helper khusus hotkey
    def get_translate_hotkey(self, default=None):
        """Ambil hotkey untuk mode translate."""
        return self.get("translate_hotkey", default)

    def get_cohost_hotkey(self, default=None):
        """Ambil hotkey untuk mode cohost/chat."""
        return self.get("cohost_hotkey", default)
