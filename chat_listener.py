#!/usr/bin/env python3
import sys
import json
import time
from pathlib import Path
import pytchat
from datetime import datetime

# tambahkan project root ke path agar modules terdeteksi (jika diperlukan)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Paths
CONFIG_PATH = ROOT / "config" / "settings.json"
BUFFER_FILE = ROOT / "temp" / "chat_buffer.jsonl"

# Referensi ke CohostTab (akan diatur dari luar)
cohost_tab = None
last_active_time = 0
tts_active = False

# Tambahan untuk debug dan pemantauan mode
current_mode = "Sequential"  # default
last_processed_comment = None

def set_cohost_tab(tab):
    """Set referensi ke CohostTab dari main_window."""
    global cohost_tab
    cohost_tab = tab
    print(f"[DEBUG] Chat listener connected to CohostTab")
    # Segera ambil mode setelah terhubung
    update_processing_mode()

def update_processing_mode():
    """Update mode pemrosesan dari pengaturan."""
    global current_mode
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        new_mode = cfg.get("reply_mode", "Sequential")
        if new_mode != current_mode:
            current_mode = new_mode
            print(f"[INFO] Mode pemrosesan diperbarui ke: {current_mode}")
    except Exception as e:
        print(f"[ERROR] Gagal memperbarui mode: {e}")

def notify_tts_start():
    """Tandai bahwa TTS dimulai."""
    global tts_active, last_active_time
    tts_active = True
    last_active_time = time.time()
    print(f"[DEBUG] Chat listener notified of TTS start")

def notify_tts_end():
    """Tandai bahwa TTS berakhir."""
    global tts_active
    tts_active = False
    print(f"[DEBUG] Chat listener notified of TTS end")

# util: load video_id dari config
def load_video_id() -> str:
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return cfg.get("video_id", "").strip()
    except Exception:
        return ""

# util: pastikan file buffer ada
def ensure_buffer_file():
    BUFFER_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not BUFFER_FILE.exists():
        BUFFER_FILE.write_text("")

# Function untuk memproses komentar berdasarkan mode
def process_comment(author, message):
    global last_processed_comment
    
    # Baca config untuk cek mode
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    paket = cfg.get("paket", "")
    
    # Jika Basic, FORCE Trigger mode
    if paket == "basic":
        current_mode = "Trigger"
        print(f"[INFO] Basic mode detected - forcing Trigger mode")
    else:
        current_mode = cfg.get("reply_mode", "Sequential")
    
    # Update mode processing
    print(f"[DEBUG] Processing comment in mode {current_mode}: {author}: {message}")
    
    # Cek duplikasi
    if last_processed_comment == (author, message):
        print(f"[DEBUG] Skipping duplicate comment: {author}: {message}")
        return
    
    # Simpan ke buffer file selalu (untuk kompatibilitas)
    with open(BUFFER_FILE, "a", encoding="utf-8") as f:
        entry = {"author": author, "message": message}
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    # Untuk Basic mode, HANYA kirim ke cohost_tab, jangan proses di sini
    if paket == "basic" and current_mode == "Trigger":
        print(f"[INFO] Basic Trigger mode - delegating to cohost_tab")
        return
    
    # Mode Sequential atau Pro - proses normal
    if current_mode == "Sequential":
        if cohost_tab and hasattr(cohost_tab, "_enqueue"):
            cohost_tab._enqueue(author, message)
            last_processed_comment = (author, message)

# main listener loop
def main():
    global last_active_time, tts_active, cohost_tab
    
    video_id = load_video_id()
    if not (isinstance(video_id, str) and len(video_id) == 11):
        print(f"❌ VIDEO_ID tidak valid: '{video_id}' (harus 11 karakter)")
        return

    ensure_buffer_file()
    try:
        chat = pytchat.create(video_id=video_id, topchat_only=False)
        print(f"▶️ Chat listener YouTube dimulai untuk: {video_id}")
    except Exception as e:
        print(f"❌ Gagal koneksi YouTube Live: {e}")
        return

    # Perbarui mode sebelum memulai loop utama
    update_processing_mode()
    print(f"[INFO] Mode pemrosesan awal: {current_mode}")

    while chat.is_alive():
        # Deteksi jika mulai membaca kembali setelah TTS
        current_time = time.time()
        if tts_active and current_time - last_active_time > 2.0:  # 2 detik inaktif
            tts_active = False
            print(f"[DEBUG] Detected resumed chat reading after TTS")
            
            # Panggil metode pada CohostTab untuk mengakhiri TTS jika ada
            if cohost_tab and hasattr(cohost_tab, "finish_tts"):
                try:
                    cohost_tab.finish_tts()
                    print(f"[DEBUG] Called finish_tts on CohostTab")
                except Exception as e:
                    print(f"[ERROR] Failed to call finish_tts: {e}")
        
        # Update waktu aktivitas terakhir
        last_active_time = current_time
        
        # Perbarui mode secara periodic (setiap 10 detik)
        if int(current_time) % 10 == 0:
            update_processing_mode()
        
        try:
            items = chat.get().sync_items()
        except Exception:
            data = chat.get()
            items = data if isinstance(data, list) else []

        for c in items:
            author = c.author.name
            message = c.message
            
            print(f"👤 {author}: {message}")
            
            # Proses komentar berdasarkan mode aktif
            process_comment(author, message)

        time.sleep(1)

if __name__ == "__main__":
    main()