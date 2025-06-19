# listeners/tiktok_runner.py
#!/usr/bin/env python3
import sys
from pathlib import Path
import json

# tambahkan root project ke path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def main():
    from modules.config_manager import ConfigManager
    try:
        from TikTokLive import TikTokLiveClient
        from TikTokLive.events import ConnectEvent, CommentEvent
    except ImportError:
        print("❌ Modul TikTokLive tidak ditemukan. Jalankan: pip install TikTokLive")
        return

    # … lalu setup client dan buffer seperti sebelumnya …
    client = TikTokLiveClient(unique_id=ConfigManager("config/settings.json").get("tiktok_nickname", ""))
    @client.on(ConnectEvent)
    async def on_connect(evt):
        print(f"[TIKTOK] Terhubung ke {evt.unique_id}")
    @client.on(CommentEvent)
    async def on_comment(evt):
        entry = {"author": evt.user.nickname, "message": evt.comment}
        buffer_file = ROOT / "temp" / "chat_buffer.jsonl"
        with open(buffer_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    client.run()

if __name__ == "__main__":
    main()

