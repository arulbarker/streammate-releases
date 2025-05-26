import requests
import threading
import time
from modules.config_manager import ConfigManager
from modules.deepseek_ai    import generate_reply
from modules.tts_engine     import speak

_last_donation_id = None

def monitor_trakteer():
    global _last_donation_id

    cfg = ConfigManager("config/settings.json")
    api_key  = cfg.get("tr_api_key", "").strip()
    interval = cfg.get("trakteer_poll_interval", 5)

    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    url = "https://api.trakteer.id/v2/transactions"

    print("🎁 Trakteer listener aktif…")
    while True:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"❌ Trakteer API error {resp.status_code}: {resp.text}")
                time.sleep(interval)
                continue

            data = resp.json()
            items = data.get("data", {}).get("transactions", [])

            if not items:
                time.sleep(interval)
                continue

            latest = items[0]
            trx_id  = latest.get("id")
            name    = latest.get("supporter_name", "Anonim")
            amount  = latest.get("amount", "Rp0")
            message = latest.get("message", "")

            if trx_id != _last_donation_id:
                _last_donation_id = trx_id

                prompt = (
                    f"Ada donasi dari {name} sebesar {amount}. "
                    f"Pesan: {message}. Ucapkan terima kasih sebagai co-host."
                )

                try:
                    reply = generate_reply(prompt) or f"Terima kasih banyak, {name}!"
                except Exception as e:
                    print(f"❌ Error generate_reply: {e}")
                    reply = f"Terima kasih banyak, {name}!"

                print(f"🗣️ Balas: {reply}")
                try:
                    speak(reply,
                          language_code=cfg.get("voice_lang", "id-ID"),
                          voice_name=cfg.get("voice_model"))
                except Exception as e:
                    print(f"❌ Error speak: {e}")

        except Exception as e:
            print(f"⚠️ Gagal fetch donasi Trakteer: {e}")

        time.sleep(interval)

def run_trakteer_listener():
    threading.Thread(target=monitor_trakteer, daemon=True).start()
