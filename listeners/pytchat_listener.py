# ========== PYTCHAT IMPORT WITH PATH HANDLING ==========
import sys
import os
from pathlib import Path

# Handle pytchat import for both development and frozen executable
try:
    import pytchat
    print("[DEBUG] PyTchat imported directly")
except ImportError:
    print("[DEBUG] Direct pytchat import failed, trying thirdparty...")
    
    # Get correct application path
    if getattr(sys, 'frozen', False):
        # Running as executable
        application_path = Path(sys.executable).parent
    else:
        # Running as script
        application_path = Path(__file__).resolve().parent.parent
    
    # Add thirdparty path
    thirdparty_path = application_path / "thirdparty" / "pytchat_ng"
    if thirdparty_path.exists():
        sys.path.insert(0, str(thirdparty_path))
        print(f"[DEBUG] Added thirdparty path: {thirdparty_path}")
        try:
            import pytchat
            print("[DEBUG] PyTchat imported from thirdparty successfully")
        except ImportError as e:
            print(f"[ERROR] Failed to import pytchat from thirdparty: {e}")
            raise
    else:
        print(f"[ERROR] Thirdparty path not found: {thirdparty_path}")
        raise ImportError("PyTchat not found in both system and thirdparty paths")

import threading
import time
import json

# ========== PATH HANDLING FOR FROZEN EXE ==========
def get_application_path():
    """Get the correct application path for both dev and exe modes"""
    if getattr(sys, 'frozen', False):
        # Running as executable
        application_path = Path(sys.executable).parent
    else:
        # Running as script
        application_path = Path(__file__).resolve().parent.parent
    return application_path

# Variabel global untuk menyimpan pesan terbaru (untuk Delay mode)
latest_message = {"username": None, "message": None}

def start_pytchat_listener(video_id, callback):
    try:
        print(f"[DEBUG] Starting pytchat listener for video_id: {video_id}")
        chat = pytchat.create(video_id=video_id)
        print(f"[DEBUG] PyTchat chat object created successfully")

        # Muat konfigurasi reply mode dari file config (dengan path handling yang benar)
        ROOT_PATH = get_application_path()
        config_path = ROOT_PATH / "config" / "live_state.json"
        
        print(f"[DEBUG] Looking for config at: {config_path}")
        
        try:
            with open(config_path, "r", encoding='utf-8') as f:
                config = json.load(f)
            print(f"[DEBUG] Config loaded successfully: {config}")
        except Exception as e:
            print(f"[DEBUG] Failed to load config: {e}")
            # Default config if file not found
            config = {
                "reply_mode": "Trigger",
                "delay_seconds": 5,
                "custom_cohost_name": "halo,bang,min"
            }
            
        reply_mode = config.get("reply_mode", "Trigger")
        delay_seconds = config.get("delay_seconds", 5)
        custom_trigger = config.get("custom_cohost_name", "").strip().lower()
        
        print(f"[DEBUG] Reply mode: {reply_mode}")
        print(f"[DEBUG] Custom trigger: {custom_trigger}")

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
            print(f"[DEBUG] Starting pytchat run loop...")
            try:
                while chat.is_alive():
                    for c in chat.get().sync_items():
                        username = c.author.name
                        message = c.message
                        print(f"[DEBUG] Received message: {username}: {message}")

                        if reply_mode == "Trigger":
                            # Jika mode Trigger, cek apakah pesan mengandung trigger word
                            trigger_words = [word.strip() for word in custom_trigger.split(',') if word.strip()]
                            message_lower = message.lower()
                            
                            for trigger in trigger_words:
                                if trigger and trigger in message_lower:
                                    print(f"[DEBUG] Trigger '{trigger}' detected in message")
                                    callback(username, message)
                                    break
                        elif reply_mode == "Delay":
                            # Di mode Delay, perbarui latest_message (ganti dengan pesan terbaru)
                            latest_message["username"] = username
                            latest_message["message"] = message
                        elif reply_mode == "Sequential":
                            # Mode Sequential: panggil callback untuk setiap pesan
                            callback(username, message)
                        else:
                            # Default: perlakukan sebagai mode Trigger
                            trigger_words = [word.strip() for word in custom_trigger.split(',') if word.strip()]
                            message_lower = message.lower()
                            
                            for trigger in trigger_words:
                                if trigger and trigger in message_lower:
                                    print(f"[DEBUG] Trigger '{trigger}' detected in message")
                                    callback(username, message)
                                    break
                    time.sleep(0.5)  # supaya tidak overload CPU
            except Exception as e:
                print(f"[ERROR] Error in pytchat run loop: {e}")
                import traceback
                print(f"[ERROR] Full traceback: {traceback.format_exc()}")

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        print(f"[DEBUG] PyTchat listener thread started successfully")
        
    except Exception as e:
        print(f"[ERROR] Failed to start pytchat listener: {e}")
        import traceback
        print(f"[ERROR] Full traceback: {traceback.format_exc()}")
        raise

