import json
from pathlib import Path
import os
from dotenv import load_dotenv

class ConfigManager:
    """
    Manages application settings (settings.json), available voices (voices.json),
    and environment variables (.env files).
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
        self.env_data = {}

        # Load environment variables
        self._load_env()

        # muat dari disk
        self.load_settings()
        self.load_voices()

    def _load_env(self):
        """Load environment variables from .env files"""
        # Try to load local env first (development)
        if os.path.exists('.env.local'):
            load_dotenv('.env.local')
        # Then try production env
        elif os.path.exists('.env.production'):
            load_dotenv('.env.production')
        # Finally try default .env
        elif os.path.exists('.env'):
            load_dotenv('.env')

        # Store environment variables
        self.env_data = {
            'API_BASE_URL': os.getenv('API_BASE_URL'),
            'API_TIMEOUT': int(os.getenv('API_TIMEOUT', 10)),
            'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
            'DEEPSEEK_API_KEY': os.getenv('DEEPSEEK_API_KEY'),
            'STREAMMATE_DEV': os.getenv('STREAMMATE_DEV', 'false').lower() == 'true',
            'DEBUG_MODE': os.getenv('DEBUG_MODE', 'false').lower() == 'true',
            'DB_HOST': os.getenv('DB_HOST'),
            'DB_PORT': os.getenv('DB_PORT'),
            'DB_NAME': os.getenv('DB_NAME'),
            'DB_USER': os.getenv('DB_USER'),
            'DB_PASSWORD': os.getenv('DB_PASSWORD')
        }

    def get_env(self, key: str, default=None):
        """Get environment variable value"""
        return self.env_data.get(key, default)

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

    def force_production_mode(self):
        """Paksa aplikasi ke production mode"""
        self.set("debug_mode", False)
        self.set("testing_mode", False)
        
        # Hapus flag developer
        user_data = self.get("user_data", {})
        if "dev_mode" in user_data:
            del user_data["dev_mode"]
            self.set("user_data", user_data)
        
        print("[CONFIG] Forced production mode settings")

