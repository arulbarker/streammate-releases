# modules_server/trakteer_api.py

import os
import requests
import threading
import time
from dotenv import load_dotenv

load_dotenv()
TRAKTEER_API_KEY = os.getenv("TRAKTEER_API_KEY")

_last_donation_id = None

def start_trakteer_listener(on_donation_callback):
    """
    Mulai polling API Trakteer setiap 5 detik.
    Panggil `on_donation_callback(name, amount, message)` jika ada donasi baru.
    """
    def worker():
        global _last_donation_id
        headers = {
            "Authorization": f"Bearer {TRAKTEER_API_KEY}"
        }
        url = "https://api.trakteer.id/v2/transactions"

        while True:
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                items = data.get("data", {}).get("transactions", [])

                if not items:
                    time.sleep(5)
                    continue

                latest = items[0]
                trx_id  = latest.get("id")
                name    = latest.get("supporter_name", "Anonim")
                amount  = latest.get("amount", "Rp0")
                message = latest.get("message", "")

                if trx_id != _last_donation_id:
                    _last_donation_id = trx_id
                    on_donation_callback(name, amount, message)
            except Exception as e:
                print(f"⚠️ Gagal fetch donasi Trakteer: {e}")

            time.sleep(5)

    threading.Thread(target=worker, daemon=True).start()
