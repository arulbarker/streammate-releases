import os
import subprocess
import time
import tempfile
import re
from pathlib import Path

import sounddevice as sd
import soundfile as sf
import logging
logger = logging.getLogger('StreamMate')

# ─── Paths Whisper ────────────────────────────────────────────────
TRIGGER_FILE = Path("temp/trigger.txt")
WHISPER_EXE  = Path(__file__).resolve().parent.parent / "thirdparty" / "whisper_bin" / "main.exe"
MODEL_BIN    = WHISPER_EXE.parent / "ggml-medium.bin"

# ─── Whisper: Rekam & Transkrip Sekaligus (Mode Lama) ───────────────
def record_and_transcribe(mode="historical"):
    # (fungsi lama jika diperlukan; tidak diubah)
    pass

# ─── Whisper: Transkrip File WAV (Hold-to-Talk) ──────────────────────
def _whisper_transcribe(wav_path: str) -> str | None:
    """
    Transkrip file WAV menggunakan whisper.cpp (offline).
    """
    out_txt = str(wav_path) + ".txt"
    try:
        cmd = [
            str(WHISPER_EXE),
            "-m", str(MODEL_BIN),
            "-f", str(wav_path),
            "-otxt",
            "-l", "id"  # TAMBAHKAN: Force Indonesian language
        ]
        subprocess.run(cmd, check=True)
        if not os.path.exists(out_txt):
            return None

        lines = open(out_txt, encoding="utf-8").readlines()
        texts = [re.sub(r"\[.*?\]", "", l).strip() for l in lines if l.strip()]
        return " ".join(texts).strip()
    except Exception as e:
        print(f"Whisper Error: {e}")
        return None
    finally:
        if os.path.exists(out_txt):
            os.remove(out_txt)

# ─── Google STT Integration ────────────────────────────────────────
from google.cloud import speech

# mapping kode BCP-47 ke Google Speech
_GOOGLE_LANG_MAP = {
    "ind_Latn": "id-ID",
    "jpn_Jpan": "ja-JP",
    "zho_Hans": "zh",
    "kor_Hang": "ko-KR",
    "arb_Arab": "ar-XA",
}

def _google_transcribe(wav_path: str, src_lang: str = "ind_Latn") -> str | None:
    """
    Transkrip file WAV menggunakan Google Cloud Speech-to-Text.
    Pastikan env var GOOGLE_APPLICATION_CREDENTIALS sudah diset.
    """
    try:
        client = speech.SpeechClient()
        with open(wav_path, "rb") as f:
            content = f.read()
        audio = speech.RecognitionAudio(content=content)
        language_code = _GOOGLE_LANG_MAP.get(src_lang, "en-US")
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code,
        )
        response = client.recognize(config=config, audio=audio)
        texts = [res.alternatives[0].transcript for res in response.results]
        return " ".join(texts) if texts else None
    except Exception as e:
        print(f"Google STT Error: {e}")
        return None

# ─── Wrapper Pemilihan STT ─────────────────────────────────────────
def transcribe(wav_path: str, src_lang: str = "ind_Latn", use_google: bool = False) -> str | None:
    """
    Pilih engine STT:
      - use_google=True → Google Speech-to-Text
      - use_google=False → whisper.cpp offline
    """
    logger.info(f"STT started: {wav_path} (lang={src_lang}, google={use_google})")
    
    try:
        if use_google:
            txt = _google_transcribe(wav_path, src_lang)
            if txt:
                logger.info(f"STT completed (Google): {txt[:50]}...")
                return txt
            # fallback ke Whisper kalau Google gagal
            logger.warning("Google STT failed, falling back to Whisper")
        
        # Use Whisper
        result = _whisper_transcribe(wav_path)
        if result:
            logger.info(f"STT completed (Whisper): {result[:50]}...")
        else:
            logger.warning("Whisper STT returned empty result")
        return result
        
    except Exception as e:
        logger.error(f"STT failed: {str(e)}")
        return None
