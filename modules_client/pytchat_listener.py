import pytchat
import threading
import time
import json

# Variabel global untuk menyimpan pesan terbaru (untuk Delay mode)
latest_message = {"username": None, "message": None}

def start_pytchat_listener(video_id, callback):
    chat = pytchat.create(video_id=video_id)

    # Muat konfigurasi reply mode dari file config (atau diteruskan sebagai parameter tambahan)
    with open("config/live_state.json", "r") as f:
        config = json.load(f)
    reply_mode = config.get("reply_mode", "Trigger")
    delay_seconds = config.get("delay_seconds", 5)
    custom_trigger = config.get("custom_cohost_name", "").strip().lower()

    def process_delay_mode():
        # Loop terpisah untuk mode Delay
        while True:
            time.sleep(delay_seconds)
            if latest_message["message"]:
                # Proses pesan terbaru
                callback(latest_message["username"], latest_message["message"])
                # Reset pesan setelah diproses
                latest_message["username"] = None
                latest_message["message"] = None

    if reply_mode == "Delay":
        # Mulai thread untuk memproses Delay mode
        threading.Thread(target=process_delay_mode, daemon=True).start()

    def run():
        while chat.is_alive():
            for c in chat.get().sync_items():
                username = c.author.name
                message = c.message

                if reply_mode == "Trigger":
                    # Jika mode Trigger, cek apakah pesan mengandung trigger word
                    if custom_trigger and custom_trigger in message.lower():
                        callback(username, message)
                elif reply_mode == "Delay":
                    # Di mode Delay, perbarui latest_message (ganti dengan pesan terbaru)
                    latest_message["username"] = username
                    latest_message["message"] = message
                elif reply_mode == "Sequential":
                    # Mode Sequential: panggil callback untuk setiap pesan
                    callback(username, message)
                else:
                    # Default: perlakukan sebagai mode Trigger
                    if custom_trigger and custom_trigger in message.lower():
                        callback(username, message)
            time.sleep(0.5)  # supaya tidak overload CPU

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
