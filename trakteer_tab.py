# ui/trakteer_tab.py
import time, threading, requests
from PyQt6.QtCore    import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QCheckBox
)

# Selalu pakai modul "server" (lebih lengkap & stabil)
from modules_server.config_manager import ConfigManager
from modules_server.deepseek_ai    import generate_reply
from modules_server.tts_engine     import speak     # <= pastikan voice engine sama di semua mesin

# ──────────────────────────────────────────────────────
class TrakteerThread(QThread):
    newSupport = pyqtSignal(dict)

    def __init__(self, api_key: str, interval: int = 5):
        super().__init__()
        self.api_key  = api_key.strip()
        self.interval = interval
        self._running = True

    def run(self):
        url = "https://api.trakteer.id/v1/public/supports"
        hdr = {"Accept":"application/json","X-Requested-With":"XMLHttpRequest","key":self.api_key}
        prm = {"limit":1,"page":1,"include":"order_id"}

        while self._running:
            try:
                r = requests.get(url, headers=hdr, params=prm, timeout=5)
                if r.status_code == 200:
                    data = r.json().get("result", {}).get("data", [])
                    if data:
                        self.newSupport.emit(data[0])
            except Exception as e:
                print("⚠️ Trakteer polling error:", e)
            time.sleep(self.interval)

    def stop(self):
        self._running = False
        self.wait()

# ──────────────────────────────────────────────────────
class TrakteerTab(QWidget):
    muteRequested = pyqtSignal()
    muteReleased  = pyqtSignal()
    # Tambahkan signal baru untuk update log
    logUpdated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.cfg           = ConfigManager("config/settings.json")
        self.thread        = None
        self.last_order_id = None

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("💰 Trakteer Auto‑Reply"))

        lay.addWidget(QLabel("API Key Trakteer:"))
        self.key_in = QLineEdit(self.cfg.get("tr_api_key",""))
        lay.addWidget(self.key_in)
        btn = QPushButton("💾 Simpan API Key")
        btn.clicked.connect(self.save_api_key)
        lay.addWidget(btn)

        self.chk = QCheckBox("Aktifkan Listener Donasi")
        self.chk.stateChanged.connect(self._toggle)
        lay.addWidget(self.chk)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        lay.addWidget(self.log)
        
        # Hubungkan signal ke slot untuk update log
        self.logUpdated.connect(self.updateLog)

    # Tambahkan metode update log yang berjalan di thread UI
    def updateLog(self, message):
        self.log.append(message)
        # Auto-scroll ke bawah
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    # ---------------- helpers ----------------
    def save_api_key(self):
        self.cfg.set("tr_api_key", self.key_in.text().strip())
        self.logUpdated.emit("[INFO] API Key disimpan")

    def _toggle(self, state):
        if state:   self._start_listener()
        else:       self._stop_listener()

    def _start_listener(self):
        key = self.cfg.get("tr_api_key","").strip()
        if not key:
            self.logUpdated.emit("[ERROR] API Key belum diset!")
            self.chk.setChecked(False)
            return
            
        self.thread = TrakteerThread(key, self.cfg.get("trakteer_poll_interval",5))
        self.thread.newSupport.connect(self._on_support)
        self.thread.start()
        self.logUpdated.emit("[INFO] Listener diaktifkan")

    def _stop_listener(self):
        if self.thread: 
            self.thread.stop()
            self.thread = None
        self.logUpdated.emit("[INFO] Listener dihentikan")

    # ---------------- event: donasi masuk ----------------
    def _on_support(self, item: dict):
        oid = item.get("order_id")
        if oid == self.last_order_id:     # duplikat
            return
        self.last_order_id = oid

        name    = item.get("supporter_name") or item.get("creator_name","Anonim")
        amount  = item.get("amount",0)
        unit    = item.get("unit_name","")
        msg     = item.get("support_message") or ""

        # Log donasi masuk menggunakan signal
        self.logUpdated.emit(f"🎁 {name} → Rp{amount:,}×{item.get('quantity',1)} {unit}: {msg}")
        self.muteRequested.emit()

        # Jalankan pembangkitan balasan + tts di thread,
        # supaya GUI tidak freeze.
        def _worker():
            try:
                # Prompt baru yang memasukkan pesan donasi dan meminta AI menjawab pertanyaan
                prompt = f"""
                Donasi dari {name} sebesar Rp{amount:,} dengan pesan: "{msg}".
                
                Kamu adalah co-host AI livestreaming. Jawablah dengan format berikut:
                Sapa {name} dengan hangat dan menyebut namanya
                jawab pertanyaan tersebut {msg} dengan baik
                Ucapkan terima kasih atas donasinya dan
                Berikan doa terbaik dan harapan positif untuk {name}
                
                Jawablah jangan terlalu panjang tanpa huruf tebal tanda baca apapun dan tanpa emoji.
                """
                reply = generate_reply(prompt) or f"Terima kasih banyak atas donasinya, {name}! Semoga sukses selalu."
            except Exception as e:
                print("❌ generate_reply error:", e)
                reply = f"Terima kasih banyak atas donasinya, {name}! Semoga sukses selalu."

            # Catat balasan AI di log menggunakan signal
            self.logUpdated.emit(f"🤖 {reply}")

            # TTS
            try:
                voice_model   = self.cfg.get("cohost_voice_model") or self.cfg.get("voice_model")
                language_code = self.cfg.get("voice_lang") or "id-ID"
                speak(reply, language_code, voice_model)
            except Exception as e:
                print("❌ speak error:", e)
                self.logUpdated.emit(f"❌ TTS error: {e}")

            # un‑mute setelah 3 detik (di UI‑thread)
            QTimer.singleShot(3000, self.muteReleased.emit)

        threading.Thread(target=_worker, daemon=True).start()