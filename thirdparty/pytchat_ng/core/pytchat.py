
import time, json, re, threading
from httpx import get

class LiveChat:
    def __init__(self, video_id, topchat_only=False):
        self.video_id = video_id
        self.topchat_only = topchat_only
        self._is_alive = True
        self.chat_items = []
        self._thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self._thread.start()

    def is_alive(self):
        return self._is_alive

    def get(self):
        class Container:
            def __init__(self, items):
                self._items = items
            def sync_items(self):
                items = self._items[:]
                self._items.clear()
                return items
        return Container(self.chat_items)

    def terminate(self):
        self._is_alive = False

    def _fetch_loop(self):
        while self._is_alive:
            try:
                url = f"https://ytlivecomments.streammate.my.id/livechat/{self.video_id}"
                res = get(url)
                if res.status_code == 200:
                    data = res.json()
                    for c in data.get("comments", []):
                        class DummyAuthor: name = c["author"]
                        class DummyItem:
                            author = DummyAuthor()
                            message = c["message"]
                        self.chat_items.append(DummyItem())
            except Exception as e:
                print("[LiveChat Error]", e)
            time.sleep(3)

