import tempfile
import requests, sounddevice as sd, soundfile as sf
from modules_client.config_manager import ConfigManager

_cfg       = ConfigManager()
USE_REMOTE = _cfg.get("use_remote_api", False)
BASE_URL   = _cfg.get("api_base_url",  "http://localhost:8000").rstrip("/")

def generate_reply(prompt: str) -> str:
    if USE_REMOTE:
        resp = requests.post(f"{BASE_URL}/ai_reply", json={"text": prompt})
        resp.raise_for_status()
        return resp.json().get("reply", "")
    else:
        from modules_server.deepseek_ai import generate_reply as local_gen
        return local_gen(prompt)

def speak(text: str, voice: str = None) -> None:
    if USE_REMOTE:
        payload = {"text": text}
        if voice: payload["voice"] = voice
        resp = requests.post(f"{BASE_URL}/speak", json=payload)
        resp.raise_for_status()
        # simpan byte audio dan mainkan
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp.write(resp.content); tmp.flush(); tmp.close()
        data, sr = sf.read(tmp.name)
        sd.play(data, sr); sd.wait()
    else:
        from modules_server.tts_engine import speak as local_speak
        local_speak(text, voice_name=voice)
