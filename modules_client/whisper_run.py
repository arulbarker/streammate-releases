# modules/whisper_run.py

import subprocess
import os

# Folder binaary whisper berada di thirdparty/whisper_bin
BIN_DIR    = os.path.join(os.path.dirname(__file__), "..", "thirdparty", "whisper_bin")
WHISPER_EXE = os.path.join(BIN_DIR, "main.exe")
MODEL_NAME = "ggml-medium.bin"

def transcribe_wav(wav_path: str) -> str | None:
    """
    Memanggil whisper.cpp untuk transkripsi offline:
    -m model -f wav_path -otxt
    Baca hasil di <wav_path>.txt, lalu kembalikan isinya.
    """
    model_path = os.path.join(BIN_DIR, MODEL_NAME)
    # Pastikan path absolut
    wav_abspath = os.path.abspath(wav_path)
    cmd = f'"{WHISPER_EXE}" -m "{model_path}" -f "{wav_abspath}" -otxt'
    try:
        # Jalankan whisper
        subprocess.run(cmd, shell=True, cwd=BIN_DIR, check=True)
        txt_file = wav_abspath + ".txt"
        if os.path.exists(txt_file):
            with open(txt_file, "r", encoding="utf-8") as f:
                text = f.read().strip()
            # (opsional) hapus file .txt jika tidak perlu disimpan
            # os.remove(txt_file)
            return text
    except Exception as e:
        print("[Whisper Error]", e)
    return None
