import keyboard
import json
import time
from pathlib import Path

CONFIG_PATH       = "config/settings.json"
TRIGGER_TRANSLATE = Path("temp/trigger_translate.txt")
TRIGGER_COHOST    = Path("temp/trigger_cohost.txt")

# Pastikan folder temp ada
Path("temp").mkdir(exist_ok=True)
# Inisialisasi file trigger
TRIGGER_TRANSLATE.write_text("OFF")
TRIGGER_COHOST.write_text("OFF")

def load_hotkeys():
    """Baca dua hotkey dari config: translate_hotkey & cohost_hotkey."""
    default = {"translate_hotkey": "ctrl+a", "cohost_hotkey": "ctrl+b"}
    if Path(CONFIG_PATH).exists():
        cfg = json.loads(open(CONFIG_PATH, encoding="utf-8").read())
        return {
            "translate_hotkey": cfg.get("translate_hotkey", default["translate_hotkey"]).lower(),
            "cohost_hotkey":   cfg.get("cohost_hotkey",   default["cohost_hotkey"]).lower(),
        }
    return default

def write_trigger(file: Path, status: str):
    file.write_text(status)

def hotkey_loop():
    keys = load_hotkeys()
    t_key = keys["translate_hotkey"]
    c_key = keys["cohost_hotkey"]
    t_active = False
    c_active = False

    print(f"▶️ Hotkey Translate: {t_key.upper()}  |  Hotkey Cohost: {c_key.upper()}")

    while True:
        # — Translate (hold-to-talk) —
        if keyboard.is_pressed(t_key) and not t_active:
            t_active = True
            write_trigger(TRIGGER_TRANSLATE, "ON")
        elif not keyboard.is_pressed(t_key) and t_active:
            t_active = False
            write_trigger(TRIGGER_TRANSLATE, "OFF")

        # — Cohost/Ngobrol (hold-to-talk) —
        if keyboard.is_pressed(c_key) and not c_active:
            c_active = True
            write_trigger(TRIGGER_COHOST, "ON")
        elif not keyboard.is_pressed(c_key) and c_active:
            c_active = False
            write_trigger(TRIGGER_COHOST, "OFF")

        time.sleep(0.05)

if __name__ == "__main__":
    hotkey_loop()
