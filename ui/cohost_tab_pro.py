# ui/cohost_tab_pro.py
# Di bagian import pada cohost_tab_pro.py
import sys
import json
import subprocess
import threading
import time
import re
import json  # TAMBAHAN
import sounddevice as sd
import soundfile as sf
# Di awal file, setelah import
import logging
logging.basicConfig(
    filename="logs/cohost_pro.log",
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
from pathlib import Path

import keyboard
from PyQt6.QtCore    import QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QTextEdit, QHBoxLayout, QCheckBox, QSpinBox
)
from datetime import datetime
from modules_server.tts_google import speak_with_google_cloud
from modules_client.subscription_checker import get_today_usage, add_usage, time_until_next_day
from PyQt6.QtWidgets import QMessageBox

# ─── fallback modules_client & modules_server ───────────────────────
# Lebih konsisten import TTS
try:
    from modules_client.config_manager import ConfigManager
    from modules_client.api import generate_reply
    from modules_client.translate_stt import transcribe
    from modules_server.tts_engine import speak
    from modules_server.tts_google import speak_with_google_cloud
    USE_GOOGLE_TTS = True
except ImportError:
    from modules_server.config_manager import ConfigManager
    from modules_server.deepseek_ai import generate_reply
    from modules_server.tts_engine import speak
    # STT hanya ada di client; jika tidak ada, stub error:
    def transcribe(*args, **kwargs):
        raise NotImplementedError("Fitur STT hanya tersedia di environment client")
    USE_GOOGLE_TTS = False

print(f"[DEBUG] TTS Engine loaded: {'Google TTS' if USE_GOOGLE_TTS else 'Default TTS'}")

    

# Paths
ROOT         = Path(__file__).resolve().parent.parent
SCRIPT_PATH  = ROOT / "listeners" / "chat_listener.py"
CHAT_BUFFER  = ROOT / "temp" / "chat_buffer.jsonl"
COHOST_LOG   = ROOT / "temp" / "cohost_log.txt"
TRIGGER_FILE = ROOT / "temp" / "trigger.txt"
VOICES_PATH  = ROOT / "config" / "voices.json"

class FileMonitorThread(QThread):
    newComment = pyqtSignal(str, str)

    def __init__(self, buffer_file: Path):
        super().__init__()
        self.buffer_file = buffer_file
        self._seen = set()
        self._running = True
        buffer_file.parent.mkdir(exist_ok=True)
        buffer_file.touch(exist_ok=True)

    def run(self):
        while self._running:
            try:
                lines = self.buffer_file.read_text(encoding="utf-8").splitlines()
            except:
                lines = []
            for line in lines:
                try:
                    e = json.loads(line)
                    key = (e["author"], e["message"])
                    if key not in self._seen:
                        self._seen.add(key)
                        self.newComment.emit(e["author"], e["message"])
                except:
                    continue
            time.sleep(0.5)

    def stop(self):
        self._running = False
        self.wait()


class ReplyThread(QThread):
    finished = pyqtSignal(str, str, str)

    def __init__(
        self,
        author: str,
        message: str,
        cohost_name: str,
        streamer_name: str,
        personality: str,
        lang_out: str,
        extra_prompt: str,
        voice_model: str | None
    ):
        super().__init__()
        self.author        = author
        self.message       = message
        self.cohost_name   = cohost_name
        self.streamer_name = streamer_name
        self.personality   = personality
        self.lang_out      = lang_out
        self.extra         = extra_prompt
        self.voice_model   = voice_model

    def run(self):
        prompt = (
            f"Kamu adalah AI Co-Host {self.cohost_name} dengan kepribadian {self.personality}, "
            f"siaran bersama streamer {self.streamer_name}. "
            f"Komentar penonton ({self.author}): \"{self.message}\". "
            f"Balas {self.author} dalam bahasa {self.lang_out.lower()} "
            "tanpa tanda baca, tanpa emoji, tanpa huruf tebal, sebut nama penanya."
        )
        if self.extra:
            prompt += f" {self.extra}"

        reply = generate_reply(prompt) or ""
        # hapus semua punctuation kecuali tanda tanya
        reply = re.sub(r"[^\w\s\?]", "", reply)

        try:
            code = "id-ID" if self.lang_out == "Indonesia" else "en-US"
            speak(reply, code, self.voice_model)
        except Exception as e:
            print(f"Error in TTS: {e}")

        self.finished.emit(self.author, self.message, reply)


class STTThread(QThread):
    result = pyqtSignal(str)

    def __init__(self, mic_index: int, src_lang: str, use_google: bool):
        super().__init__()
        self.mic_index = mic_index
        self.src_lang = src_lang
        self.use_google = use_google

    def run(self):
        wav_path = Path("temp/cohost_record.wav")
        record_buffer = []
        try:
            with sd.InputStream(
                samplerate=16000, channels=1, device=self.mic_index,
                callback=lambda indata, *_: record_buffer.extend(indata.copy())
            ):
                while Path("temp/trigger.txt").read_text() == "ON":
                    time.sleep(0.05)
            sf.write(str(wav_path), record_buffer, 16000)
        except Exception as e:
            print(f"Error in recording: {e}")
            self.result.emit("")
            return

        txt = transcribe(str(wav_path), self.src_lang, self.use_google) or ""
        self.result.emit(txt.strip())


class TikTokListenerThread(QThread):
    newComment = pyqtSignal(str, str)

    def __init__(self, nickname: str):
        super().__init__()
        # pastikan diawali '@'
        self.nickname = nickname if nickname.startswith("@") else "@" + nickname
        self._ready = False

    def run(self):
        from TikTokLive import TikTokLiveClient
        from TikTokLive.events import ConnectEvent, CommentEvent

        client = TikTokLiveClient(unique_id=self.nickname)

        @client.on(ConnectEvent)
        async def on_connect(evt):
            # tunggu 3 detik sebelum mulai emit komentar
            threading.Timer(3.0, lambda: setattr(self, "_ready", True)).start()

        @client.on(CommentEvent)
        async def on_comment(evt: CommentEvent):
            if not self._ready:
                return
            # kirim ke slot utama
            self.newComment.emit(evt.user.nickname, evt.comment)

        client.run()

    def stop(self):
        # tidak ada API stop, cukup tandai flag jika perlu
        self._ready = False


class CohostTab(QWidget):
    ttsAboutToStart = pyqtSignal()
    ttsFinished = pyqtSignal()
    personaChanged = pyqtSignal(str)
    speakingStarted = pyqtSignal(str, float)  # Signal baru: text, intensity
    speakingStopped = pyqtSignal()  # Signal baru
    replyGenerated = pyqtSignal(str, str, str)  # author, message, reply
    
    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager("config/settings.json")
        self.proc = None
        self.monitor = None
        self.tiktok_thread = None
        self.reply_queue = []
        self.reply_busy = False
        self.delay_timer = None
        self.hotkey_enabled = True
        self.stt_thread = None
        self.threads = []
        self.conversation_active = False
        self.usage_timer = QTimer()
        self.usage_timer.setInterval(60_000)  # 1 menit
        self.usage_timer.timeout.connect(self._track_usage)
        self.avatar_controller = None  # Placeholder for avatar controller
        self.tts_active = False
        self.reply_queue = []
        self.reply_busy = False
        self.current_tts_text = ""  # Track text untuk estimasi

        # Pastikan folder/temp dan file trigger ada
        TRIGGER_FILE.parent.mkdir(exist_ok=True)
        if not TRIGGER_FILE.exists():
            TRIGGER_FILE.write_text("OFF")

        # ─── UI Setup ──────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("🤖 Auto-Reply Chat (YouTube & TikTok)"))

        # Platform selection
        layout.addWidget(QLabel("Pilih Platform Komentar:"))
        self.platform_cb = QComboBox()
        self.platform_cb.addItems(["YouTube", "TikTok", "YouTube + TikTok"])
        layout.addWidget(self.platform_cb)

        # Input TikTok Nickname
        layout.addWidget(QLabel("Nickname TikTok:"))
        self.nickname_input = QLineEdit(self.cfg.get("tiktok_nickname", ""))
        layout.addWidget(self.nickname_input)

        # Input Video ID YouTube
        layout.addWidget(QLabel("Video ID YouTube:"))
        self.videoid_input = QLineEdit(self.cfg.get("video_id", ""))
        layout.addWidget(self.videoid_input)

        # Tombol simpan input platform
        self.save_platform_btn = QPushButton("💾 Simpan Platform & ID")
        self.save_platform_btn.clicked.connect(self.save_platform_inputs)
        layout.addWidget(self.save_platform_btn)

        # Nama Streamer
        layout.addWidget(QLabel("Nama Streamer:"))
        self.streamer_input = QLineEdit(self.cfg.get("streamer_name", "Streamer"))
        layout.addWidget(self.streamer_input)
        btn = QPushButton("💾 Simpan Nama Streamer")
        btn.clicked.connect(self.save_streamer)
        layout.addWidget(btn)

        # lalu baru pasang koneksi dan panggil update awal:
        self.platform_cb.currentTextChanged.connect(self._update_platform_ui)
        self._update_platform_ui(self.platform_cb.currentText())

        # Bahasa Output
        layout.addWidget(QLabel("Bahasa Output:"))
        self.out_lang = QComboBox()
        self.out_lang.addItems(["Indonesia", "English"])
        self.out_lang.setCurrentText(self.cfg.get("reply_language", "Indonesia"))
        self.out_lang.currentTextChanged.connect(self.on_language_change)
        layout.addWidget(self.out_lang)

        # Kepribadian
        layout.addWidget(QLabel("Kepribadian AI:"))
        self.person_cb = QComboBox()
        self.person_cb.addItems([
            "Ceria", "Pemarah", "Sombong", "Suka Bercanda", "Bijaksana",
            "Santai", "Tenang", "Bahasa Gaul Indonesia", "Bahasa Sunda", "Positive Vibe"
        ])
        self.person_cb.setCurrentText(self.cfg.get("personality", "Ceria"))
        self.person_cb.currentTextChanged.connect(self.save_personality)
        layout.addWidget(self.person_cb)

        # Prompt Tambahan
        layout.addWidget(QLabel("Prompt Tambahan (opsional):"))
        self.custom = QLineEdit(self.cfg.get("custom_context", ""))
        layout.addWidget(self.custom)
        btn = QPushButton("💾 Simpan Prompt")
        btn.clicked.connect(self.save_custom)
        layout.addWidget(btn)

        # Mode Balasan
        row = QHBoxLayout()
        row.addWidget(QLabel("Mode Balasan:"))
        self.mode_cb = QComboBox()
        self.mode_cb.addItems(["Sequential", "Delay Latest", "Trigger"])
        self.mode_cb.setCurrentText(self.cfg.get("reply_mode", "Sequential"))
        self.mode_cb.currentTextChanged.connect(self.save_mode)
        row.addWidget(self.mode_cb)
        row.addWidget(QLabel("Delay (detik):"))
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(1, 60)
        self.delay_spin.setValue(self.cfg.get("reply_delay", 5))
        row.addWidget(self.delay_spin)
        btn = QPushButton("💾 Simpan Mode")
        btn.clicked.connect(self.save_mode)
        row.addWidget(btn)
        layout.addLayout(row)

        # Trigger Word
        row = QHBoxLayout()
        row.addWidget(QLabel("Trigger Penonton (mode Trigger):"))
        self.trigger_input = QLineEdit(self.cfg.get("trigger_word", ""))
        row.addWidget(self.trigger_input)
        self.trigger_btn = QPushButton("💾 Simpan Trigger")
        self.trigger_btn.clicked.connect(self.save_trigger)
        row.addWidget(self.trigger_btn)

        layout.addLayout(row)

        # Suara CoHost
        layout.addWidget(QLabel("Suara CoHost:"))
        row = QHBoxLayout()
        self.voice_cb = QComboBox()
        row.addWidget(self.voice_cb)
        btn = QPushButton("🔈 Preview Suara")
        btn.clicked.connect(self.preview_cohost_voice)
        row.addWidget(btn)
        btn = QPushButton("💾 Simpan Suara")
        btn.clicked.connect(self.save_cohost_voice)
        row.addWidget(btn)
        layout.addLayout(row)

        # Start / Stop
        self.status = QLabel("Status: Ready")
        layout.addWidget(self.status)
        row = QHBoxLayout()
        self.btn_start = QPushButton("▶️ Start Auto-Reply")
        self.btn_start.clicked.connect(self.start)
        row.addWidget(self.btn_start)
        self.btn_stop = QPushButton("⏹️ Stop Auto-Reply")
        self.btn_stop.clicked.connect(self.stop)
        row.addWidget(self.btn_stop)
        layout.addLayout(row)

        # Log
        layout.addWidget(QLabel("📋 Log (Komentar & Balasan)"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

        # Hold-to-Talk Hotkey
        row = QHBoxLayout()
        row.addWidget(QLabel("Hold-to-Talk Hotkey:"))
        self.chk_ctrl = QCheckBox("Ctrl")
        row.addWidget(self.chk_ctrl)
        self.chk_alt = QCheckBox("Alt")
        row.addWidget(self.chk_alt)
        self.chk_shift = QCheckBox("Shift")
        row.addWidget(self.chk_shift)
        self.key_combo = QComboBox()
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
            self.key_combo.addItem(c)
        row.addWidget(self.key_combo)
        self.hk_edit = QLineEdit(self.cfg.get("cohost_hotkey", "Ctrl+Alt+X"))
        self.hk_edit.setReadOnly(True)
        row.addWidget(self.hk_edit)
        btn = QPushButton("💾 Simpan Hotkey")
        btn.clicked.connect(self.save_hotkey)
        row.addWidget(btn)
        self.toggle_btn = QPushButton("🔔 Ngobrol: ON")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(True)
        self.toggle_btn.clicked.connect(self.toggle_hotkey)
        row.addWidget(self.toggle_btn)
        layout.addLayout(row)

        # finalize UI callbacks
        self.mode_cb.currentTextChanged.connect(self.update_mode_ui)
        self.update_mode_ui(self.mode_cb.currentText())
        self._load_hotkey()
        self.load_cohost_voices(self.out_lang.currentText())

        # start hotkey listener thread
        threading.Thread(target=self._hotkey_listener, daemon=True).start()

    # Method baru untuk menghubungkan dengan avatar controller
    def set_avatar_controller(self, controller):
        """Connect to avatar controller."""
        self.avatar_controller = controller
        if hasattr(controller, 'update_animaze_persona'):
            # Connect signals
            self.personaChanged.connect(controller.update_animaze_persona)
            self.speakingStarted.connect(
                lambda text, intensity: controller.set_speaking_state(True, text, intensity))
            self.speakingStopped.connect(
                lambda: controller.set_speaking_state(False))
            
            # Initial update
            controller.update_animaze_persona(self.person_cb.currentText())
            self.log_view.append("[INFO] Avatar controller terhubung")

    # — UI helpers —
    def update_mode_ui(self, mode):
        self.delay_spin.setEnabled(mode == "Delay Latest")
        is_tr = (mode == "Trigger")
        self.trigger_input.setEnabled(is_tr)
        self.trigger_btn.setEnabled(is_tr)

    def on_language_change(self, lang):
        self.save_language(lang)
        self.load_cohost_voices(lang)

    def load_cohost_voices(self, lang):
        self.voice_cb.clear()
        try:
            voices = json.loads(Path(VOICES_PATH).read_text(encoding="utf-8")).get("chirp3", {})
            key = "id-ID" if lang == "Indonesia" else "en-US"
            for v in voices.get(key, []):
                self.voice_cb.addItem(v["model"], v["model"])
            stored = self.cfg.get("cohost_voice_model", "")
            idx = self.voice_cb.findData(stored)
            if idx >= 0:
                self.voice_cb.setCurrentIndex(idx)
        except Exception as e:
            print(f"Error loading voices: {e}")

    def preview_cohost_voice(self):
        voice = self.voice_cb.currentData()
        code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
        self.log_view.append(f"[Preview] {voice}")
        speak("Ini preview suara CoHost!", language_code=code, voice_name=voice)

    def save_cohost_voice(self):
        voice = self.voice_cb.currentData()
        self.cfg.set("cohost_voice_model", voice)
        self.log_view.append(f"[INFO] Suara CoHost disimpan: {voice}")

    def _parse(self, h): 
        return [p.lower() for p in h.split("+") if p]
    
    def _is_pressed(self, h): 
        return all(keyboard.is_pressed(p) for p in self._parse(h))

    def _load_hotkey(self):
        hot = self.cfg.get("cohost_hotkey", "Ctrl+Alt+X")
        for p in hot.split("+"):
            if p == "Ctrl":
                self.chk_ctrl.setChecked(True)
            elif p == "Alt":
                self.chk_alt.setChecked(True)
            elif p == "Shift":
                self.chk_shift.setChecked(True)
            else:
                idx = self.key_combo.findText(p)
                if idx >= 0:
                    self.key_combo.setCurrentIndex(idx)
        self.hk_edit.setText(hot)

    # — Simpan setting —
    def save_trigger(self):
        w = self.trigger_input.text().strip()
        self.cfg.set("trigger_word", w)
        self.log_view.append(f"[INFO] Trigger disimpan: {w}")

    def save_streamer(self):
        n = self.streamer_input.text().strip()
        self.cfg.set("streamer_name", n)
        self.log_view.append(f"[INFO] Streamer disimpan: {n}")

    def save_language(self, lang):
        self.cfg.set("reply_language", lang)
        self.log_view.append(f"[INFO] Bahasa output disimpan: {lang}")

    def save_personality(self, p):
        self.cfg.set("personality", p)
        self.log_view.append(f"[INFO] Personality disimpan: {p}")
        # Emit sinyal perubahan kepribadian
        self.personaChanged.emit(p)

    def save_custom(self):
        c = self.custom.text().strip()
        self.cfg.set("custom_context", c)
        self.log_view.append("[INFO] Prompt tambahan disimpan")

    def save_mode(self):
        m = self.mode_cb.currentText()
        d = self.delay_spin.value()
        self.cfg.set("reply_mode", m)
        self.cfg.set("reply_delay", d)
        self.log_view.append(f"[INFO] Mode disimpan: {m} (delay {d}s)")

    def save_hotkey(self):
        mods = [m for cb, m in [
            (self.chk_ctrl, "Ctrl"), (self.chk_alt, "Alt"), (self.chk_shift, "Shift")
        ] if cb.isChecked()]
        key = self.key_combo.currentText()
        hot = "+".join(mods + ([key] if key else []))
        self.cfg.set("cohost_hotkey", hot)
        self.hk_edit.setText(hot)
        self.log_view.append(f"[INFO] Hotkey disimpan: {hot}")

    def save_platform_inputs(self):
        # ambil input mentah
        raw_video = self.videoid_input.text().strip()
        # jika ada "youtu" di string, parsing URL → ambil param v atau path akhir
        if "youtu" in raw_video:
            from urllib.parse import urlparse, parse_qs
            p = urlparse(raw_video)
            # coba ambil query v
            vid = parse_qs(p.query).get("v", [])
            if vid:
                video_id = vid[0]
            else:
                # fallback: ambil bagian path terakhir
                video_id = p.path.rsplit("/", 1)[-1]
        else:
            video_id = raw_video

        # set ke config & update field agar terlihat ke user
        self.cfg.set("video_id", video_id)
        self.videoid_input.setText(video_id)

        # simpan TikTok nickname seperti biasa
        self.cfg.set("tiktok_nickname", self.nickname_input.text().strip())

        self.log_view.append("[INFO] Platform input disimpan.")

    def toggle_hotkey(self):
        on = self.toggle_btn.isChecked()
        # Ubah teks tombol sesuai state
        self.toggle_btn.setText("🔔 Ngobrol: ON" if on else "🔕 Ngobrol: OFF")
        # Simpan flag internal
        self.hotkey_enabled = on

    def _update_platform_ui(self, plat: str):
        is_tiktok = plat in ("TikTok", "YouTube + TikTok")
        is_youtube = plat in ("YouTube", "YouTube + TikTok")

        # show/hide field
        self.nickname_input.setVisible(is_tiktok)
        self.videoid_input.setVisible(is_youtube)

    def toggle_hotkey_off(self):
        """Mute CoHost chat (nonaktifkan hotkey)."""
        if hasattr(self, "toggle_btn"):
            self.toggle_btn.setChecked(False)
        self.hotkey_enabled = False

    def toggle_hotkey_on(self):
        """Unmute CoHost chat (aktifkan hotkey kembali)."""
        if hasattr(self, "toggle_btn"):
            self.toggle_btn.setChecked(True)
        self.hotkey_enabled = True

    # — Hold-to-Talk Listener —  
    def _hotkey_listener(self):
        prev = False
        while True:
            time.sleep(0.05)
            if not self.hotkey_enabled:
                prev = False
                continue

            hot = self.cfg.get("cohost_hotkey", "Ctrl+Alt+X")
            pressed = self._is_pressed(hot)

            if pressed and not prev:
                prev = True
                self.conversation_active = True   # mute auto-reply saat mic aktif
                TRIGGER_FILE.write_text("ON")
                self.log_view.append("🔴 Mulai merekam...")

                mic_index = self.cfg.get("selected_mic_index", 0)
                src_lang = self.cfg.get("cohost_input_lang", "ind_Latn")
                use_google = True  # karena ini Pro
                self.stt_thread = STTThread(mic_index, src_lang, use_google)
                self.stt_thread.result.connect(self._handle_speech)
                self.stt_thread.start()

            elif not pressed and prev:
                prev = False
                self.conversation_active = False  # unmute auto-reply
                TRIGGER_FILE.write_text("OFF")
                self.log_view.append("⏳ Memproses...")

    # — Handle hasil STT Hold-to-Talk —  
    def _handle_speech(self, txt: str):
        # release mute chat sehingga auto-reply jalan kembali
        self.conversation_active = False

        txt = txt.strip()
        if not txt:
            self.log_view.append("[WARN] STT kosong.")
            return

        self.log_view.append(f"🎙️ Kamu: {txt}")

        # Build prompt untuk DeepSeek
        prompt = (
            f"Kamu adalah AI Co-Host {self.cfg.get('cohost_name','CoHost')} "
            f"dengan kepribadian {self.person_cb.currentText()}. "
            f"User berkata: \"{txt}\". "
            f"Balas dalam bahasa {self.out_lang.currentText().lower()} tanpa emoji dan tanpa sebut nama cohost."
        )
        reply = generate_reply(prompt) or ""

        # Emit signal untuk avatar
        self.speakingStarted.emit(reply, 0.8)  # Asumsi intensitas 0.8

        # TTS sesuai setting bahasa output
        code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
        speak(reply, language_code=code, voice_name=self.cfg.get("cohost_voice_model"))

        # Signal bahwa sudah selesai bicara
        self.speakingStopped.emit()

        self.log_view.append(f"🤖 {reply}")

    def start(self):
        """Start auto-reply untuk mode Basic dengan validasi lengkap."""
        # TAMBAHAN: Skip usage tracking untuk test mode
        main_window = self.window()
        if hasattr(main_window, 'license_validator') and main_window.license_validator.testing_mode:
            print("[DEBUG] Test mode active - skipping usage tracking")
            # Jangan start usage timer
        else:
            # Normal flow - track usage
            self.hour_tracker.start_tracking()
            self.credit_timer.start()
        self.conversation_active = False  # pastikan reset
        self.save_platform_inputs()       # simpan nickname & video ID terbaru

        # TAMBAHKAN DI SINI - CEK KREDIT LEBIH AWAL
        # Ambil data kredit dari license_validator
        main_window = self.window()
        if hasattr(main_window, 'license_validator'):
            license_data = main_window.license_validator.validate()
            daily_usage = license_data.get("daily_usage", {})
            today = datetime.now().date().isoformat()
            used_hours = daily_usage.get(today, 0)
            
            # Tentukan limit berdasarkan tier
            tier = license_data.get("tier", "demo")
            if tier == "basic":
                limit_hours = 5
            elif tier == "pro": 
                limit_hours = 12
            else:  # demo
                limit_hours = 0.5
            
            remaining_hours = max(0, limit_hours - used_hours)
            
            # Cek kredit
            if remaining_hours <= 0:
                if hasattr(main_window, 'show_no_credit_dialog'):
                    main_window.show_no_credit_dialog()
                else:
                    QMessageBox.critical(self, "Kredit Habis", 
                                         "Kredit jam Anda telah habis.\nSilakan beli paket untuk melanjutkan.")
                return
            elif remaining_hours < 1:
                if hasattr(main_window, 'show_credit_warning'):
                    main_window.show_credit_warning(remaining_hours)
                else:
                    QMessageBox.warning(self, "Kredit Rendah",
                                        f"Sisa kredit: {remaining_hours:.1f} jam")

        platform = self.platform_cb.currentText()
        video_id = self.videoid_input.text().strip()
        nickname = self.nickname_input.text().strip()

        if platform not in ["YouTube", "TikTok", "YouTube + TikTok"]:
            self.log_view.append("[ERROR] Pilih platform komentar terlebih dahulu.")
            return
        if "YouTube" in platform and len(video_id) != 11:
            self.log_view.append("[ERROR] Video ID harus 11 karakter.")
            return
        if "TikTok" in platform and not nickname:
            self.log_view.append("[ERROR] TikTok nickname tidak boleh kosong.")
            return
        if not SCRIPT_PATH.exists():
            self.log_view.append(f"[ERROR] chat_listener tidak ditemukan: {SCRIPT_PATH}")
            return

        # Bersihkan buffer
        CHAT_BUFFER.write_text("")
        COHOST_LOG.parent.mkdir(exist_ok=True)
        COHOST_LOG.write_text("")

        # Hentikan listener lama
        if self.monitor:
            self.monitor.stop()
            self.monitor = None
        if self.tiktok_thread:
            self.tiktok_thread.terminate()
            self.tiktok_thread = None
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc = None

        # Start YouTube listener
        if "YouTube" in platform:
            try:
                self.proc = subprocess.Popen(["python", "-u", str(SCRIPT_PATH)])
                self.log_view.append("[YouTube] Listener dimulai")
                self.monitor = FileMonitorThread(CHAT_BUFFER)
                self.monitor.newComment.connect(self._enqueue)
                self.monitor.start()
            except Exception as e:
                self.log_view.append(f"[ERROR] Gagal menjalankan listener: {e}")
                return

        # Start TikTok listener
        if "TikTok" in platform:
            try:
                self.tiktok_thread = TikTokListenerThread(nickname)
                self.tiktok_thread.newComment.connect(self._enqueue)
                self.tiktok_thread.start()
                self.log_view.append("[TikTok] Listener dimulai")
            except Exception as e:
                self.log_view.append(f"[ERROR] Gagal menjalankan TikTok listener: {e}")

        self.log_view.append(f"[INFO] Auto-Reply dimulai untuk: {platform}")

        # — jika developer/debug_mode, skip kuota
        if self.cfg.get("debug_mode", False):
            self.log_view.append("[DEBUG] Developer mode: kuota tidak diberlakukan")
        else:
            # Cek batas segera, lalu jalankan timer per menit
            self._track_usage()
            self.usage_timer.start()

    def stop(self):
        # hentikan semua listener
        if self.monitor:
            self.monitor.stop()
        if self.tiktok_thread:
            self.tiktok_thread.stop()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc = None
        if hasattr(self, "delay_timer") and self.delay_timer:
            self.delay_timer.cancel()
        self.log_view.append("[INFO] Semua listener dihentikan.")

        # matikan timer pemakaian
        self.usage_timer.stop()

    def _track_usage(self):
        # jika ada demo expired_at, dan paket basic
        exp = self.cfg.get("expired_at", None)
        if self.cfg.get("paket") == "basic" and exp:
            if datetime.fromisoformat(exp) <= datetime.now():
                self.usage_timer.stop()
                self.stop()
                QMessageBox.information(
                    self,
                    "Demo Habis",
                    "Mode demo sudah berakhir."
                )
                return
            else:
                # masih demo, lewati hitung kuota harian
                remaining = datetime.fromisoformat(exp) - datetime.now()
                menit = remaining.seconds // 60
                self.log_view.append(f"[Demo] Sisa {menit} menit")
                return

        # jika bukan demo, lanjutkan cek kuota harian
        tier, used, limit = get_today_usage()
        if used >= limit:
            self.usage_timer.stop()
            self.stop()
            detik = time_until_next_day()
            jam = detik // 3600
            menit = (detik % 3600) // 60
            QMessageBox.information(
                self,
                "Waktu Habis",
                f"Waktu penggunaan harian habis.\nCoba lagi dalam {jam} jam {menit} menit."
            )
            return

        add_usage(1)
        self.log_view.append(f"[Langganan] +1 menit (tier: {tier})")

    # — Queue & Processing —  
    def _enqueue(self, author, message):
        """
        Tambahkan komentar ke antrian balasan berdasarkan mode yang dipilih.
        
        Args:
            author (str): Nama pengirim komentar
            message (str): Isi komentar yang akan diproses
            
        Proses:
            - Skip jika sedang dalam mode percakapan
            - Mode Trigger: hanya proses jika mengandung kata kunci
            - Mode Delay Latest: jadwalkan balasan setelah delay
            - Mode Sequential: proses langsung secara berurutan
        """
        if self.conversation_active:
            print(f"[DEBUG] Conversation active - skipping message from {author}")
            return

        current_mode = self.mode_cb.currentText()
        print(f"[DEBUG] Processing message | Mode: {current_mode} | Author: {author}")
        print(f"[DEBUG] Message preview: {message[:50]}{'...' if len(message) > 50 else ''}")
        
        trigger_word = self.cfg.get("trigger_word", "").lower().strip()
        delay_seconds = max(1, min(self.delay_spin.value(), 60))  # Batasi 1-60 detik

        # Mode Trigger
        if current_mode == "Trigger":
            self._process_trigger_mode(author, message, trigger_word)
            
        # Mode Delay Latest    
        elif current_mode == "Delay Latest":
            self._process_delay_mode(author, message, delay_seconds)
            
        # Mode Sequential (default)
        else:  
            print("[DEBUG] Processing in sequential mode")
            self._enqueue_actual(author, message)

    def _process_trigger_mode(self, author, message, trigger_word):
        """Proses komentar dalam mode Trigger."""
        if trigger_word and trigger_word in message.lower():
            print(f"[DEBUG] Trigger word '{trigger_word}' matched")
            self._enqueue_actual(author, message)
        else:
            print(f"[DEBUG] No trigger word match - message ignored")

    def _process_delay_mode(self, author, message, delay):
        """Proses komentar dalam mode Delay Latest."""
        print(f"[DEBUG] Setting up delay timer for {delay} seconds")
        
        # Hentikan timer sebelumnya jika ada
        self._cleanup_existing_timer()
        
        # Buat QTimer baru dengan parent yang jelas
        self.delay_timer = QTimer(self)
        self.delay_timer.setSingleShot(True)
        
        # Gunakan functools.partial untuk menghindari masalah scope lambda
        from functools import partial
        self.delay_timer.timeout.connect(
            partial(self._enqueue_actual, author, message))
            
        self.delay_timer.start(delay * 1000)
        
        # Update UI
        self.log_view.append(f"⏱️ Reply scheduled in {delay} seconds")
        print(f"[DEBUG] Delay timer started | Duration: {delay}s | Author: {author}")

    def _cleanup_existing_timer(self):
        """Bersihkan timer yang sudah ada."""
        if hasattr(self, "delay_timer") and self.delay_timer:
            try:
                if isinstance(self.delay_timer, threading.Timer):
                    self.delay_timer.cancel()
                elif isinstance(self.delay_timer, QTimer):
                    self.delay_timer.stop()
                print("[DEBUG] Previous timer stopped")
            except Exception as e:
                print(f"[ERROR] Timer cleanup failed: {str(e)}")

    def _enqueue_actual(self, author, message):
        """
        Tambahkan komentar ke antrian dan mulai pemrosesan jika belum.
        
        Args:
            author: Nama pengirim komentar
            message: Isi komentar
        """
        self.log_view.append(f"👤 {author}: {message}")
        self.reply_queue.append((author, message))
        print(f"[DEBUG] Enqueued message | Queue size: {len(self.reply_queue)}")
        
        if not self.reply_busy:
            print("[DEBUG] Starting queue processing")
            self._dequeue()
        else:
            print("[DEBUG] Processing busy - item queued")

    def _dequeue(self):
        """Proses komentar berikutnya dari antrian."""
        if not self.reply_queue:
            print("[DEBUG] Queue empty - resetting busy flag")
            self.reply_busy = False
            return
        
        print(f"[DEBUG] Processing next item | Queue size: {len(self.reply_queue)}")
        self.reply_busy = True
        
        author, msg = self.reply_queue.pop(0)
        print(f"[DEBUG] Generating reply for: {author}: {msg[:50]}...")
        
        # Prepare thread parameters
        voice_model = self.cfg.get("cohost_voice_model", None)
        rt = ReplyThread(
            author=author,
            message=msg,
            cohost_name=self.cfg.get("cohost_name", "CoHost"),
            streamer_name=self.cfg.get("streamer_name", "Streamer"),
            personality=self.person_cb.currentText(),
            lang_out=self.out_lang.currentText(),
            extra_prompt=self.cfg.get("custom_context", ""),
            voice_model=voice_model
        )
        
        # Setup thread signals
        rt.finished.connect(self._on_reply)
        rt.finished.connect(
            lambda *_: self.threads.remove(rt) if rt in self.threads else None)
        
        # Start processing
        self.threads.append(rt)
        rt.start()
        print("[DEBUG] ReplyThread started")

    # Perbaikan untuk CohostTab pada cohost_tab_pro.py

    # PERBAIKAN 1: Perbaiki metode _on_reply pada CohostTab (cohost_tab_pro.py)

    def _on_reply(self, author, message, reply):
        """
        Handler untuk balasan yang sudah digenerate.
    
        Memperbarui UI, menyimpan log, dan memulai proses TTS.
        """
        if not reply:
            self.log_view.append("[WARN] Gagal mendapatkan balasan.")
            self.reply_busy = False
            QTimer.singleShot(100, self._dequeue)
            return
        self.current_tts_text = reply
    
        try:
            # Update UI (overlay dan log)
            mw = self.window()
            if hasattr(mw, "overlay_tab"):
                mw.overlay_tab.update_overlay(author, reply)
    
            self.log_view.append(f"🤖 {reply}")
    
            # Log ke file
            COHOST_LOG.parent.mkdir(exist_ok=True)
            with open(str(COHOST_LOG), "a", encoding="utf-8") as f:
                f.write(f"{author}\t{message}\t{reply}\n")
            self.replyGenerated.emit(author, message, reply)
    
            # Mulai TTS dengan urutan:
            # 1. Emit signal ttsAboutToStart (F1)
            # 2. Setup timer untuk deteksi selesai
            # 3. Lakukan TTS
    
            print("[DEBUG] Starting TTS process")
    
            # Emit signal dan panggil F1
            self.ttsAboutToStart.emit()
            print("[DEBUG] ttsAboutToStart signal emitted")
            self.ttsAboutToStart.emit()
    
            # Setup timer berdasarkan panjang teks
            self._setup_tts_timers(reply)
    
            # Lakukan TTS
            code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
            voice_model = self.cfg.get("cohost_voice_model", None)
    
            print(f"[DEBUG] Executing TTS with voice={voice_model}, lang={code}")
            print(f"[DEBUG] Text preview: '{reply[:50]}{'...' if len(reply) > 50 else ''}'")
    
            speak(reply, code, voice_model)
    
        except Exception as e:
            print(f"[ERROR] Error in _on_reply: {e}")
            import traceback
            traceback.print_exc()
    
            # Pastikan cleanup meskipun ada error
            if hasattr(self, 'tts_active') and self.tts_active:
                self.ttsFinished.emit()
                print("[DEBUG] ttsFinished signal emitted (error recovery)")
                self.tts_active = False
    
            self.reply_busy = False
            QTimer.singleShot(100, self._dequeue)

    def _manual_tts_finished(self):
        """Timer-based fallback untuk TTS selesai."""
        print("[DEBUG] Manual TTS finished timer triggered")
    
        # Hentikan timeout timer jika masih aktif
        if hasattr(self, 'safety_timer') and self.safety_timer.isActive():
            self.safety_timer.stop()
    
        # Emit signal TTS selesai
        self.ttsFinished.emit()
        print("[DEBUG] ttsFinished signal emitted via timer")
    
        # Reset state
        self.reply_busy = False
    
        # Process antrian berikutnya
        QTimer.singleShot(100, self._dequeue)

    def _on_tts_finished(self):
        """
        Handler terpadu untuk penyelesaian TTS normal.
        Dipanggil ketika timer utama berakhir.
        """
        if not self.tts_active:
            print("[DEBUG] Ignoring TTS finished event - not active")
            return
    
        print("[DEBUG] TTS finished normally")
    
        # Tandai TTS selesai
        self.tts_active = False
    
        # Hentikan timer yang masih berjalan
        self._cleanup_timers()
    
        # Emit signal untuk F2
        self.ttsFinished.emit()
        print("[DEBUG] ttsFinished signal emitted (normal)")
    
        # Reset state dan siapkan untuk antrian berikutnya
        self._prepare_next_message()

    def _tts_safety_timeout(self):
        """
        Handler timeout untuk TTS yang berjalan terlalu lama.
        Dipanggil ketika safety timer berakhir.
        """
        if not self.tts_active:
            print("[DEBUG] Ignoring safety timeout - TTS not active")
            return
    
        print("[WARN] TTS safety timeout triggered - force completing TTS")
    
        # Tandai TTS selesai
        self.tts_active = False
    
        # Hentikan timer yang masih berjalan
        self._cleanup_timers()
    
        # Emit signal untuk F2
        self.ttsFinished.emit()
        print("[DEBUG] ttsFinished signal emitted (safety)")
    
        # Reset state dan siapkan untuk antrian berikutnya
        self._prepare_next_message()

    def _prepare_next_message(self):
        """Persiapkan untuk pemrosesan pesan berikutnya."""
        self.reply_busy = False
        QTimer.singleShot(100, self._dequeue)

    def _handle_tts_failure(self):
        """Central handler untuk kegagalan TTS."""
        # Pastikan signal ttsFinished dipancarkan
        try:
            self.ttsFinished.emit()
            print("[DEBUG] ttsFinished signal emitted via failure handler")
        except:
            pass
    
        # Reset state
        self.reply_busy = False
    
        # Lanjutkan ke antrian berikutnya
        QTimer.singleShot(100, self._dequeue)

    def _cleanup_timers(self):
        """
        Bersihkan semua timer aktif.
        Mencegah timer berjalan ganda atau konflik.
        """
        for timer_name in ['tts_timer', 'safety_timer']:
            if hasattr(self, timer_name):
                timer = getattr(self, timer_name)
                if isinstance(timer, QTimer) and timer.isActive():
                    timer.stop()
                    print(f"[DEBUG] Stopped {timer_name}")

    def _finish_tts(self):
        """Tandai TTS selesai dan siapkan untuk antrian berikutnya."""
        # Cek jika TTS aktif, panggil F2
        if self.tts_active:
            print("[DEBUG] TTS finishing - calling F2")
            # Emit signal animasi berhenti
            self.ttsFinished.emit()
            print("[DEBUG] ttsFinished signal emitted")
        
        # Reset flag
        self.tts_active = False
        self.reply_busy = False
        
        # Proses pesan berikutnya jika ada
        QTimer.singleShot(100, self._dequeue)
    
    # Tambahkan metode ini untuk dipanggil dari MonitorThread
    def resume_processing(self):
        """Dipanggil ketika PyTChat mulai dibaca lagi."""
        # Jika sedang dalam TTS, tandai selesai
        if self.tts_active:
            print("[DEBUG] PyTChat resumed - finishing TTS")
            self._finish_tts()

    def _explicit_end_tts(self):
        """Metode eksplisit untuk mengakhiri TTS setelah durasi tertentu."""
        print("[DEBUG] Executing explicit TTS end procedure")
        
        try:
            # Pastikan timer dihentikan
            if hasattr(self, 'tts_timer') and self.tts_timer.isActive():
                self.tts_timer.stop()
                print("[DEBUG] Stopped active TTS timer")
            
            # Emit sinyal penyelesaian
            self.ttsFinished.emit()
            print("[DEBUG] Emitted ttsFinished signal")
            
            # Reset state
            self.reply_busy = False
            
            # Lanjutkan ke item berikutnya dengan delay kecil
            QTimer.singleShot(100, self._dequeue)
            
        except Exception as e:
            print(f"[ERROR] Error in _explicit_end_tts: {str(e)}")
            self._cleanup_tts_state()

    def _cleanup_tts_state(self):
        """Bersihkan state TTS dan pastikan tidak ada deadlock."""
        self.ttsFinished.emit()
        self.reply_busy = False
        if hasattr(self, 'tts_timer') and self.tts_timer.isActive():
            self.tts_timer.stop()

    def _calculate_tts_duration(self, text):
        """
        Estimasi durasi TTS berdasarkan panjang teks.
    
        Menggunakan rumus sederhana:
        - Bahasa Indonesia: sekitar 12 karakter/detik
        - Bahasa Inggris: sekitar 14 karakter/detik
        - Tambah buffer 1.5 detik untuk proses awal dan akhir
        """
        # Tentukan kecepatan berdasarkan bahasa output
        chars_per_second = 14 if self.out_lang.currentText() == "English" else 12
    
        # Bersihkan teks dari karakter non-printable
        cleaned_text = re.sub(r'[^\w\s\?\,\.\!]', '', text)
    
        # Hitung durasi berdasarkan jumlah kata
        words = cleaned_text.split()
        word_count = len(words)
        char_count = len(cleaned_text)
    
        # Durasi berbasis karakter dengan minimal 2 detik
        duration = max(2.0, (char_count / chars_per_second) + 1.5)
    
        print(f"[DEBUG] TTS Duration estimate: {duration:.2f}s for {word_count} words ({char_count} chars)")
        return duration
    
    def _setup_tts_timers(self, text):
        """
        Setup timer untuk mendeteksi selesainya TTS.
    
        Menggunakan 2 timer:
        1. Timer normal: perkiraan durasi TTS berdasarkan panjang teks
        2. Safety timer: 2x durasi normal untuk menghindari deadlock
        """
        # Bersihkan timer yang mungkin masih aktif
        self._cleanup_timers()
    
        # Set flag TTS aktif
        self.tts_active = True
    
        # Hitung durasi berdasarkan panjang teks
        duration = self._calculate_tts_duration(text)
    
        # Timer utama - perkiraan selesainya TTS
        self.tts_timer = QTimer(self)
        self.tts_timer.setSingleShot(True)
        self.tts_timer.timeout.connect(self._on_tts_finished)
        self.tts_timer.start(int(duration * 1000))
    
        # Safety timer - jika TTS tidak selesai dalam 2x waktu
        self.safety_timer = QTimer(self)
        self.safety_timer.setSingleShot(True)
        self.safety_timer.timeout.connect(self._tts_safety_timeout)
        self.safety_timer.start(int(duration * 2000))
    
        print(f"[DEBUG] TTS timers set: normal={duration:.1f}s, safety={duration*2:.1f}s")



    def closeEvent(self, event):
        # stop the usage timer and all listeners when the window closes
        self.usage_timer.stop()
        self.stop()
        super().closeEvent(event)