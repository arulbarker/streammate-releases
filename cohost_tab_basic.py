import json
import subprocess
import threading
import time
import textwrap
import re
import sys
import os
import signal
import sounddevice as sd
import soundfile as sf
import json
from pathlib import Path
from datetime import datetime
import logging
logger = logging.getLogger('StreamMate')

# Setup path HARUS DI AWAL!
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Import PyQt6
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QScrollArea, QFrame, QTextEdit, QHBoxLayout, QSpinBox, QSizePolicy, QMessageBox, QCheckBox, QGroupBox 
)
from PyQt6.QtGui import QCloseEvent
import keyboard
from PyQt6.QtGui import QTextOption

# Import ConfigManager dengan fallback
try:
    from modules_client.config_manager import ConfigManager
except ImportError:
    from modules_server.config_manager import ConfigManager

# Import modules_client lainnya
from modules_client.cache_manager import CacheManager
from modules_client.spam_detector import SpamDetector
from modules_client.viewer_memory import ViewerMemory
from modules_client.subscription_checker import get_today_usage, add_usage, time_until_next_day, HourlySubscriptionChecker
from modules_client.subscription_checker import start_usage_tracking, stop_usage_tracking, register_activity
# Import API functions dengan fallback
try:
    from modules_client.api import generate_reply  
except ImportError:
    from modules_server.deepseek_ai import generate_reply

# Import TTS dari server
from modules_server.tts_engine import speak

# Paths
YT_SCRIPT = ROOT / "listeners" / "chat_listener.py"
CHAT_BUFFER = ROOT / "temp" / "chat_buffer.jsonl"
COHOST_LOG = ROOT / "temp" / "cohost_log.txt"
VOICES_PATH = ROOT / "config" / "voices.json"

# Rest of the file continues...


# FileMonitorThread - untuk membaca buffer file dari YouTube listener
class FileMonitorThread(QThread):
    newComment = pyqtSignal(str, str)

    def __init__(self, buffer_file: Path):
        super().__init__()
        self.buffer_file = buffer_file
        self._seen = set()
        self._running = True
        buffer_file.parent.mkdir(exist_ok=True, parents=True)
        buffer_file.touch(exist_ok=True)

    def run(self):
        while self._running:
            try:
                lines = self.buffer_file.read_text(encoding="utf-8").splitlines()
            except Exception:
                lines = []
            for line in lines:
                try:
                    e = json.loads(line)
                    key = (e["author"], e["message"])
                    if key not in self._seen:
                        self._seen.add(key)
                        self.newComment.emit(e["author"], e["message"])
                except Exception:
                    continue
            time.sleep(0.5)

    def stop(self):
        self._running = False
        self.wait()


# TikTokListenerThread - untuk TikTokLive
class TikTokListenerThread(QThread):
    newComment = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self._ready = False 
        self.client = None

    def run(self):
        try:
            from TikTokLive import TikTokLiveClient
            from TikTokLive.events import ConnectEvent, CommentEvent
        except ImportError:
            print("[ERROR] TikTokLive not available")
            return

        # prepare buffer file
        buffer_file = ROOT / "temp" / "chat_buffer.jsonl"
        buffer_file.parent.mkdir(exist_ok=True, parents=True)
        buffer_file.touch(exist_ok=True)

        # load nickname  
        cfg = ConfigManager("config/settings.json")
        nickname = cfg.get("tiktok_nickname", "").strip()
        if not nickname.startswith("@"):
            nickname = "@" + nickname

        self.client = TikTokLiveClient(unique_id=nickname)

        @self.client.on(ConnectEvent)
        async def on_connect(evt):
            self._ready = False
            threading.Timer(3.0, lambda: setattr(self, "_ready", True)).start()

        @self.client.on(CommentEvent)
        async def on_comment(evt):
            if not self._ready:
                return
            author, msg = evt.user.nickname, evt.comment
            self.newComment.emit(author, msg)
            with open(buffer_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({"author":author, "message":msg}, ensure_ascii=False) + "\n")

        self.client.run()

    def stop(self):
        self._ready = False
        
        # Stop client jika ada
        if hasattr(self, 'client') and self.client:
            try:
                self.client.disconnect()
            except:
                pass
        
        # Force quit thread dengan timeout
        self.quit()
        self.wait(2000)  # Tunggu maksimal 2 detik


# STTThread - untuk hold-to-talk recording
class STTThread(QThread):
    result = pyqtSignal(str)

    def __init__(self, mic_index, src_lang, use_google=False):
        super().__init__()
        self.mic_index = mic_index
        self.src_lang = src_lang
        self.use_google = use_google
        self.running = True

    def run(self):
        """Rekam audio sampai running=False"""
        wav_path = Path("temp/cohost_record.wav")
        wav_path.parent.mkdir(exist_ok=True, parents=True)
        record_buffer = []
        
        try:
            # Record audio
            with sd.InputStream(
                samplerate=16000, channels=1, device=self.mic_index,
                callback=lambda indata, *_: record_buffer.extend(indata.copy())
            ):
                while self.running:
                    time.sleep(0.05)
            
            # Save audio file
            if record_buffer:
                sf.write(str(wav_path), record_buffer, 16000)
                
                # Tunggu sebentar untuk memastikan file tersimpan
                time.sleep(0.1)
        except Exception as e:
            print(f"Error in recording: {e}")
            self.result.emit("")
            return

        # Use Whisper untuk Basic mode
        try:
            from modules_client.translate_stt import transcribe
            txt = transcribe(str(wav_path), self.src_lang, self.use_google) or ""
            self.result.emit(txt.strip())
        except ImportError:
            # Fallback jika module tidak tersedia
            print("STT module not available")
            self.result.emit("")


# ReplyThread - untuk generate dan TTS balasan AI
class ReplyThread(QThread):
    finished = pyqtSignal(str, str, str)

    def __init__(
        self,
        author: str,
        message: str,
        personality: str,
        voice_model: str,
        language_code: str,
        lang_out: str,
        viewer_memory=None
    ):
        super().__init__()
        self.author = author
        self.message = message
        self.personality = personality
        self.voice_model = voice_model
        self.language_code = language_code
        self.lang_out = lang_out
        self.viewer_memory = viewer_memory

    def run(self):
        cfg = ConfigManager("config/settings.json")
        extra = cfg.get("custom_context", "").strip()
        lang_label = "Bahasa Indonesia" if self.lang_out == "Indonesia" else "English"

        # Get viewer memory
        viewer_status = "new"
        viewer_context = ""
        if self.viewer_memory:
            viewer_info = self.viewer_memory.get_viewer_info(self.author)
            if viewer_info:
                viewer_status = viewer_info.get("status", "new")
                viewer_context = self.viewer_memory.get_recent_context(self.author, limit=3)

        # Build prompt with memory
        prompt = (
            f"Kamu adalah AI Co-Host dengan kepribadian {self.personality}. "
            f"Penonton {self.author} berkata: '{self.message}'. "
            f"Balas dengan SINGKAT dan relevan dengan pertanyaan balas menggunakan {lang_label} tanpa tanda baca, huruf tebal emoji, atau format khusus. "
            f"Jawab langsung pertanyaan penonton dalam 1-2 kalimat pendek. "
         )

        # Add context if exists
        if viewer_context:
            prompt += f"Riwayat interaksi sebelumnya: {viewer_context}. "

        # Add instructions based on viewer status
        if viewer_status == "new":
            prompt += f"Ini penonton baru, sambut dengan ramah. "
        elif viewer_status == "regular":
            prompt += f"Ini penonton regular, bersikap akrab dan ingat interaksi sebelumnya. tapi jangan sebutkan regular nya "
        elif viewer_status == "vip":
            prompt += f"Ini penonton setia, berikan perhatian khusus dan ingat topik obrolan sebelumnya. "

        prompt += (
            f"Balas dalam {lang_label} tanpa tanda baca, tanpa emoji, tanpa huruf tebal. "
            f"Awali dengan sebut nama {self.author}."
        )

        # Tambahkan custom context jika ada
        if extra:
            prompt += f" Context: {extra}"

        try:
            reply = generate_reply(prompt) or ""
            reply = re.sub(r"[^\w\s\?]", "", reply)
            print(f"[DEBUG] Balasan AI: {reply}")
        except Exception as e:
            print(f"❌ Gagal generate balasan: {e}")
            reply = ""

        self.finished.emit(self.author, self.message, reply)


# CohostTabBasic - implementasi final yang stable
class CohostTabBasic(QWidget):
    """Tab CoHost untuk mode Basic - AI co-host dengan fitur trigger-based reply"""
    # Signals untuk integrasi dengan AnimazeTab
    ttsAboutToStart = pyqtSignal()
    ttsFinished = pyqtSignal()
    replyGenerated = pyqtSignal(str, str, str)  # author, message, reply
    
    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager("config/settings.json")
        self.viewer_memory = ViewerMemory()
        self.proc = None
        self.monitor = None
        self.tiktok_thread = None
        self.cache_manager = CacheManager()
        self.spam_detector = SpamDetector()
        
        # State management yang benar
        self.reply_queue = []
        self.reply_busy = False
        self.processing_batch = False
        self.batch_counter = 0
        self.recent_messages = []
        self.threads = []
        
        # Cooldown settings
        self.cooldown_duration = 10
        self.max_queue_size = 5
        self.is_in_cooldown = False
        
        # Timing settings
        self.reply_delay = 3000  # 3 detik antar balasan
        self.batch_size = 3      # 3 balasan per batch
        self.batch_cooldown = 10000  # 10 detik cooldown
        self.message_history_limit = 10
        
        # Hotkey settings
        self.hotkey_enabled = True
        self.muted = False
        self.conversation_active = False
        self.stt_thread = None
        
        # Filter statistics
        self.filter_stats = {
            "toxic": 0,
            "short": 0,
            "emoji": 0,
            "spam": 0,
            "numeric": 0
        }
        
        # Timer untuk cooldown
        self.cooldown_timer = QTimer()
        self.cooldown_timer.setSingleShot(True)
        self.cooldown_timer.timeout.connect(self._end_cooldown)
        
        # Timer untuk batch processing
        self.batch_timer = QTimer()
        self.batch_timer.setSingleShot(True)
        self.batch_timer.timeout.connect(self._process_next_in_batch)
        
        # Timer untuk penggunaan
        self.usage_timer = QTimer()
        self.usage_timer.setInterval(60_000)  # 1 menit
        self.usage_timer.timeout.connect(self._track_usage)
        
        # Setup UI
        self.init_ui()
        
        # Load initial settings
        self._load_hotkey()
        self.load_voices()

        # Tambahan untuk tracking kredit
        self.hour_tracker = HourlySubscriptionChecker() 
        self.credit_timer = QTimer()
        self.credit_timer.timeout.connect(self._check_credit)
        self.credit_timer.setInterval(60000)  # Check every minute
        
        # Start hotkey listener thread
        threading.Thread(target=self._hotkey_listener, daemon=True).start()

    def init_ui(self):
        """Initialize UI elements"""
        # Gunakan SATU layout utama
        main_layout = QVBoxLayout(self)

        # Set proper size policy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Buat ScrollArea untuk mengakomodasi konten panjang
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Widget konten yang akan di-scroll
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Header
        header = QLabel("🤖 Auto-Reply Basic (Trigger Only)")
        header.setStyleSheet("font-size: 16px; font-weight: bold;")
        content_layout.addWidget(header)

        # Platform selector
        platform_group = QGroupBox("Platform & Sumber")
        platform_layout = QVBoxLayout(platform_group)

        platform_layout.addWidget(QLabel("Platform:"))
        self.platform_cb = QComboBox()
        self.platform_cb.addItems(["YouTube", "TikTok"])
        self.platform_cb.setCurrentText(self.cfg.get("platform", "YouTube"))
        self.platform_cb.currentTextChanged.connect(self._update_platform_ui)
        platform_layout.addWidget(self.platform_cb)

        # YouTube Video ID / URL
        self.vid_label = QLabel("Video ID/URL:")
        platform_layout.addWidget(self.vid_label)
        self.vid_input = QLineEdit(self.cfg.get("video_id", ""))
        self.vid_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        platform_layout.addWidget(self.vid_input)
        self.btn_save_vid = QPushButton("💾 Simpan Video ID")
        self.btn_save_vid.clicked.connect(self.save_video_id)
        platform_layout.addWidget(self.btn_save_vid)

        # TikTok Nickname
        self.nick_label = QLabel("TikTok Nickname:")
        platform_layout.addWidget(self.nick_label)
        self.nick_input = QLineEdit(self.cfg.get("tiktok_nickname", ""))
        self.nick_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        platform_layout.addWidget(self.nick_input)
        self.btn_save_nick = QPushButton("💾 Simpan Nickname")
        self.btn_save_nick.clicked.connect(self.save_nickname)
        platform_layout.addWidget(self.btn_save_nick)

        content_layout.addWidget(platform_group)

        # AI Settings Group
        ai_group = QGroupBox("🧠 Pengaturan AI")
        ai_layout = QVBoxLayout(ai_group)

        # Bahasa output
        ai_layout.addWidget(QLabel("Bahasa Output:"))
        self.out_lang = QComboBox()
        self.out_lang.addItems(["Indonesia", "English"])
        self.out_lang.setCurrentText(self.cfg.get("reply_language", "Indonesia"))
        self.out_lang.currentTextChanged.connect(self.load_voices)
        ai_layout.addWidget(self.out_lang)

        # Kepribadian AI
        ai_layout.addWidget(QLabel("Kepribadian AI:"))
        self.person_cb = QComboBox()
        self.person_cb.addItems(["Ceria"])
        ai_layout.addWidget(self.person_cb)

        # Ganti QLineEdit dengan QTextEdit untuk prompt tambahan
        ai_layout.addWidget(QLabel("Prompt Tambahan (opsional):"))
        self.custom_input = QTextEdit(self.cfg.get("custom_context", ""))
        self.custom_input.setPlaceholderText("Contoh: Namaku Dadang, sedang main Mobile Legends. Fokus bahas gameplay.")
        self.custom_input.setMinimumHeight(80)
        self.custom_input.setMaximumHeight(120)
        self.custom_input.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                padding: 10px;
                color: black;
            }
        """)
        self.custom_input.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.custom_input.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        ai_layout.addWidget(self.custom_input)

        # Buat layout baru untuk tombol simpan
        save_buttons_layout = QHBoxLayout()

        # Tambahkan tombol simpan prompt
        self.custom_btn = QPushButton("💾 Simpan Prompt")
        self.custom_btn.clicked.connect(self.save_custom)
        save_buttons_layout.addWidget(self.custom_btn)

        ai_layout.addLayout(save_buttons_layout)
        content_layout.addWidget(ai_group)

        # Trigger group
        trigger_group = QGroupBox("🎯 Pengaturan Trigger & Cooldown")
        trigger_layout = QVBoxLayout(trigger_group)

        # Trigger penonton
        trigger_row = QHBoxLayout()
        trigger_row.addWidget(QLabel("Trigger Penonton:"))
        self.trigger_input = QLineEdit()
        existing_triggers = self.cfg.get("trigger_words", [])
        if isinstance(existing_triggers, list):
            self.trigger_input.setText(", ".join(existing_triggers))
        else:
            old_trigger = self.cfg.get("trigger_word", "")
            self.trigger_input.setText(old_trigger)
        self.trigger_input.setPlaceholderText("contoh: bro, bang, ?, sapa aku (pisah dengan koma)")
        trigger_row.addWidget(self.trigger_input)
        trigger_layout.addLayout(trigger_row)

        # Tombol simpan trigger
        self.trigger_btn = QPushButton("💾 Simpan Trigger")
        self.trigger_btn.clicked.connect(self.save_trigger)
        trigger_layout.addWidget(self.trigger_btn)

        # Cooldown setting
        trigger_layout.addWidget(QLabel("⏱️ Pengaturan Cooldown:"))
        cooldown_layout = QHBoxLayout()
        cooldown_layout.addWidget(QLabel("Cooldown (detik):"))

        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(0, 30)
        self.cooldown_spin.setValue(self.cooldown_duration)
        self.cooldown_spin.valueChanged.connect(self.update_cooldown)
        cooldown_layout.addWidget(self.cooldown_spin)

        cooldown_layout.addWidget(QLabel("Max Antrian:"))

        self.max_queue_spin = QSpinBox()
        self.max_queue_spin.setRange(1, 10)
        self.max_queue_spin.setValue(self.max_queue_size)
        self.max_queue_spin.valueChanged.connect(self.update_max_queue)
        cooldown_layout.addWidget(self.max_queue_spin)

        trigger_layout.addLayout(cooldown_layout)
        content_layout.addWidget(trigger_group)

        # Voice & Controls
        voice_group = QGroupBox("🔊 Suara & Kontrol")
        voice_layout = QVBoxLayout(voice_group)

        # Suara CoHost
        voice_layout.addWidget(QLabel("Suara CoHost:"))
        voice_row = QHBoxLayout()
        self.voice_cb = QComboBox()
        voice_row.addWidget(self.voice_cb, 3)  # 75% dari lebar

        preview_btn = QPushButton("🔈 Preview")
        preview_btn.clicked.connect(self.preview_voice)
        voice_row.addWidget(preview_btn, 1)  # 25% dari lebar

        voice_layout.addLayout(voice_row)

        save_voice_btn = QPushButton("💾 Simpan Suara")
        save_voice_btn.clicked.connect(self.save_voice)
        voice_layout.addWidget(save_voice_btn)

        # Status and Control Buttons
        self.status = QLabel("Status: Ready")
        voice_layout.addWidget(self.status)

        control_row = QHBoxLayout()
        self.btn_start = QPushButton("▶️ Start Auto-Reply")
        self.btn_start.clicked.connect(self.start)
        control_row.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹️ Stop Auto-Reply")
        self.btn_stop.clicked.connect(self.stop)
        control_row.addWidget(self.btn_stop)

        btn_memory_stats = QPushButton("📊 Memory Stats")
        btn_memory_stats.clicked.connect(self.show_memory_stats)
        control_row.addWidget(btn_memory_stats)

        voice_layout.addLayout(control_row)
        content_layout.addWidget(voice_group)

        # Hotkey Group
        hotkey_group = QGroupBox("⌨️ Hold-to-Talk")
        hotkey_layout = QVBoxLayout(hotkey_group)

        hotkey_layout.addWidget(QLabel("Hotkey:"))
        hotkey_row = QHBoxLayout()

        # Checkboxes in horizontal layout
        check_layout = QHBoxLayout()
        self.chk_ctrl = QCheckBox("Ctrl")
        check_layout.addWidget(self.chk_ctrl)

        self.chk_alt = QCheckBox("Alt")
        check_layout.addWidget(self.chk_alt)

        self.chk_shift = QCheckBox("Shift")
        check_layout.addWidget(self.chk_shift)

        hotkey_row.addLayout(check_layout)

        # Key combo
        self.key_combo = QComboBox()
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
            self.key_combo.addItem(c)
        hotkey_row.addWidget(self.key_combo)

        # Display and save button
        self.hk_edit = QLineEdit(self.cfg.get("cohost_hotkey", "Ctrl+Alt+X"))
        self.hk_edit.setReadOnly(True)
        hotkey_row.addWidget(self.hk_edit)

        btn_save_hk = QPushButton("💾 Simpan")
        btn_save_hk.clicked.connect(self.save_hotkey)
        hotkey_row.addWidget(btn_save_hk)

        hotkey_layout.addLayout(hotkey_row)

        # Toggle button
        self.toggle_btn = QPushButton("🔔 Ngobrol: ON")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(True)
        self.toggle_btn.clicked.connect(self.toggle_hotkey)
        hotkey_layout.addWidget(self.toggle_btn)

        content_layout.addWidget(hotkey_group)

        # Log Group - Yang Paling Besar dan Expandable
        log_group = QGroupBox("📋 Log Aktivitas")
        log_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        log_layout = QVBoxLayout(log_group)

        # Log view and buttons in horizontal layout
        log_row = QHBoxLayout()

        # Text area yang expandable
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(200)
        self.log_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.log_view.setStyleSheet("QTextEdit { background-color: #f5f5f5; padding: 10px; color: black; }")
        log_row.addWidget(self.log_view, 4)  # 80% dari lebar

        # Buttons panel
        button_panel = QVBoxLayout()
        button_panel.addStretch()

        button_style = """
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 8px;
                margin: 5px;
                text-align: left;
                min-height: 40px;
                color: black;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """

        btn_stats = QPushButton("  📊 Lihat Filter Stats")
        btn_stats.setStyleSheet(button_style)
        btn_stats.clicked.connect(self.show_filter_stats)
        button_panel.addWidget(btn_stats)

        btn_reset_stats = QPushButton("  🔄 Reset Stats")
        btn_reset_stats.setStyleSheet(button_style)
        btn_reset_stats.clicked.connect(self.reset_filter_stats)
        button_panel.addWidget(btn_reset_stats)

        btn_statistics = QPushButton("  📊 Lihat Statistik\n    Cache & Spam")
        btn_statistics.setStyleSheet(button_style)
        btn_statistics.clicked.connect(self.show_statistics)
        button_panel.addWidget(btn_statistics)

        # Tetapkan lebar maksimum yang sama untuk semua tombol
        max_width = 180
        btn_stats.setMaximumWidth(max_width)
        btn_reset_stats.setMaximumWidth(max_width)
        btn_statistics.setMaximumWidth(max_width)

        button_panel.addStretch()
        log_row.addLayout(button_panel, 1)  # 20% dari lebar

        log_layout.addLayout(log_row)
        content_layout.addWidget(log_group, 1)  # Beri stretch factor 1 agar expandable

        # Atur widget konten ke scroll area
        scroll_area.setWidget(content_widget)
        
        # Tambahkan scroll area ke layout utama
        main_layout.addWidget(scroll_area)

        # Update platform UI sesuai pilihan saat ini
        self._update_platform_ui(self.platform_cb.currentText())

    def _update_platform_ui(self, platform):
        """Update UI berdasarkan platform yang dipilih"""
        if platform == "YouTube":
            # Show YouTube fields
            self.vid_label.setVisible(True)
            self.vid_input.setVisible(True)
            self.btn_save_vid.setVisible(True)
            
            # Hide TikTok fields
            self.nick_label.setVisible(False)
            self.nick_input.setVisible(False)
            self.btn_save_nick.setVisible(False)
        else:  # TikTok
            # Hide YouTube fields
            self.vid_label.setVisible(False)
            self.vid_input.setVisible(False)
            self.btn_save_vid.setVisible(False)
            
            # Show TikTok fields
            self.nick_label.setVisible(True)
            self.nick_input.setVisible(True)
            self.btn_save_nick.setVisible(True)

    def save_custom(self):
        """Simpan prompt tambahan"""
        custom = self.custom_input.toPlainText().strip()
        self.cfg.set("custom_context", custom)
        self.log_view.append("[INFO] Prompt tambahan disimpan")

        # Tambahan: Berikan feedback visual dengan highlight sementara
        original_style = self.custom_input.styleSheet()
        self.custom_input.setStyleSheet("""
            QTextEdit {
                background-color: #e6ffe6;
                padding: 10px;
                color: black;
                border: 1px solid #4CAF50;
            }
        """)

        # Kembalikan style asli setelah 2 detik
        QTimer.singleShot(2000, lambda: self.custom_input.setStyleSheet(original_style))

    def save_trigger(self):
        """Simpan multiple trigger words dengan maksimal 3."""
        triggers = self.trigger_input.text().strip()
        trigger_list = [t.strip() for t in triggers.split(",") if t.strip()]

        # Validasi maksimal 3 trigger
        if len(trigger_list) > 3:
            QMessageBox.warning(
                self, "Terlalu Banyak Trigger",
                "Maksimal 3 trigger words!\nContoh: bro, bang, min"
            )
            # Ambil 3 pertama saja
            trigger_list = trigger_list[:3]
            self.trigger_input.setText(", ".join(trigger_list))

        # Validasi trigger quality
        warnings = []
        for trigger in trigger_list:
            if len(trigger) < 2:
                warnings.append(f"'{trigger}' terlalu pendek (min 2 karakter)")
            if trigger in ["?", ".", "!", ","]:
                warnings.append(f"'{trigger}' adalah tanda baca, tidak recommended")

        if warnings:
            QMessageBox.warning(
                self, "Trigger Warning",
                "Perhatian:\n" + "\n".join(warnings) +
                "\n\nIni bisa menyebabkan terlalu banyak match!"
            )

        self.cfg.set("trigger_words", trigger_list)
        self.cfg.set("trigger_word", "")  # Clear old format
        self.log_view.append(f"[INFO] {len(trigger_list)} trigger disimpan: {', '.join(trigger_list)}")

    def save_video_id(self):
        """Simpan Video ID YouTube"""
        raw_video = self.vid_input.text().strip()
        # Jika ada "youtu" di string, parsing URL → ambil param v atau path akhir
        if "youtu" in raw_video:
            from urllib.parse import urlparse, parse_qs
            p = urlparse(raw_video)
            vid = parse_qs(p.query).get("v", [])
            if vid:
                video_id = vid[0]
            else:
                # fallback: ambil bagian path terakhir
                video_id = p.path.rsplit("/", 1)[-1]
        else:
            video_id = raw_video
        
        self.cfg.set("video_id", video_id)
        self.vid_input.setText(video_id)
        self.log_view.append(f"[INFO] Video ID disimpan: {video_id}")

    def save_nickname(self):
        """Simpan TikTok nickname"""
        nickname = self.nick_input.text().strip()
        if nickname and not nickname.startswith("@"):
            nickname = "@" + nickname
        self.cfg.set("tiktok_nickname", nickname)
        self.nick_input.setText(nickname)
        self.log_view.append(f"[INFO] TikTok nickname disimpan: {nickname}")

    def save_voice(self):
        """Simpan pilihan suara"""
        voice = self.voice_cb.currentData()
        self.cfg.set("cohost_voice_model", voice)
        self.log_view.append(f"[INFO] Suara CoHost disimpan: {voice}")

    def update_cooldown(self, value):
        """Update cooldown duration."""
        self.cooldown_duration = value
        self.cfg.set("cohost_cooldown", value)
        self.log_view.append(f"[INFO] Cooldown diset ke {value} detik")

    def update_max_queue(self, value):
        """Update max queue size."""
        self.max_queue_size = value
        self.cfg.set("cohost_max_queue", value)
        self.log_view.append(f"[INFO] Max antrian diset ke {value}")

    def preview_voice(self):
        """Preview suara yang dipilih"""
        voice = self.voice_cb.currentData()
        code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
        self.log_view.append(f"[Preview] {voice}")
        try:
            speak("Ini preview suara CoHost!", language_code=code, voice_name=voice)
        except Exception as e:
            self.log_view.append(f"[ERROR] Preview gagal: {e}")

    def save_hotkey(self):
        """Simpan hotkey hold-to-talk"""
        mods = [m for cb, m in [
            (self.chk_ctrl, "Ctrl"),
            (self.chk_alt, "Alt"),
            (self.chk_shift, "Shift")
        ] if cb.isChecked()]
        key = self.key_combo.currentText()
        hot = "+".join(mods + ([key] if key else []))
        self.cfg.set("cohost_hotkey", hot)
        self.hk_edit.setText(hot)
        self.log_view.append(f"[INFO] Hotkey disimpan: {hot}")

    def toggle_hotkey(self):
        """Toggle hotkey on/off"""
        on = self.toggle_btn.isChecked()
        self.toggle_btn.setText("🔔 Ngobrol: ON" if on else "🔕 Ngobrol: OFF")
        self.hotkey_enabled = on

    def load_voices(self):
        """Load suara yang tersedia untuk CoHost berdasarkan bahasa"""
        self.voice_cb.clear()
        try:
            voices_data = json.loads(VOICES_PATH.read_text(encoding="utf-8"))
            lang = self.out_lang.currentText()
            
            # Basic mode menggunakan gTTS standard voices
            if lang == "Indonesia":
                voices = voices_data.get("gtts_standard", {}).get("id-ID", [])
            else:  # English
                voices = voices_data.get("gtts_standard", {}).get("en-US", [])
            
            for voice in voices:
                model = voice.get("model")
                gender = voice.get("gender")
                display = f"{gender} - {model}"
                self.voice_cb.addItem(display, model)
            
            # Restore saved selection
            stored = self.cfg.get("cohost_voice_model", "")
            idx = self.voice_cb.findData(stored)
            if idx >= 0:
                self.voice_cb.setCurrentIndex(idx)
                
        except Exception as e:
            self.log_view.append(f"[ERROR] Load voices gagal: {e}")

    def _load_hotkey(self):
        """Load saved hotkey configuration"""
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

    def _parse(self, h):
        """Parse hotkey string ke list"""
        return [p.lower() for p in h.split("+") if p]
    
    def _is_pressed(self, h):
        """Cek apakah hotkey sedang ditekan"""
        return all(keyboard.is_pressed(p) for p in self._parse(h))
    
    def _should_skip_message(self, author, message):
        """Filter pesan yang tidak perlu dibalas dengan tracking yang lebih ketat"""
        message_clean = message.strip()

        # 1. Skip pesan terlalu pendek
        if len(message_clean) < 5:
            self.filter_stats["short"] += 1  
            self.log_view.append(f"[FILTERED] Pesan terlalu pendek: '{message}'")
            return True

        # 2. Skip emoji-only
        import re
        text_only = re.sub(r'[^\w\s]', '', message)
        if len(text_only.strip()) == 0:
            self.filter_stats["emoji"] += 1  
            self.log_view.append(f"[FILTERED] Emoji only: '{message}'")
            return True

        # 3. Skip kata toxic (selalu aktif)
        toxic_words = ["anjing", "tolol", "bangsat", "kontol", "memek", "goblok", "babi",
                        "kampret", "tai", "bajingan", "pepek", "jancok", "asu"]
        message_lower = message.lower()
        for toxic in toxic_words:
            if toxic in message_lower:
                self.filter_stats["toxic"] += 1  
                self.log_view.append(f"[FILTERED] Kata toxic terdeteksi: '{toxic}' dalam '{message}'")
                return True

        # 4. Skip nomor seri spam (3 3 3 3, 7 7 7, dll)
        nomor_pattern = r'^(\d+\s*)+$'
        if re.match(nomor_pattern, message_clean):
            numbers = re.findall(r'\d+', message_clean)
            if len(numbers) > 2 and all(n == numbers[0] for n in numbers):
                self.filter_stats["numeric"] += 1  
                self.log_view.append(f"[FILTERED] Nomor spam: '{message}'")
                return True

        # 5. Skip pesan berulang/spam (cek konteks yang sama)
        normalized_msg = self._normalize_message(message_lower)

        for prev_author, prev_msg in self.recent_messages[-5:]:
            prev_normalized = self._normalize_message(prev_msg.lower())

            if self._calculate_similarity(normalized_msg, prev_normalized) > 0.8:
                self.filter_stats["spam"] += 1  
                self.log_view.append(f"[FILTERED] Pesan berulang/serupa: '{message}'")
                return True

        return False

    def _normalize_message(self, message):
        """Normalize pesan untuk perbandingan"""
        import re
        # Hapus tanda baca, extra spaces, lowercase
        message = re.sub(r'[^\w\s]', '', message)
        message = re.sub(r'\s+', ' ', message)
        return message.strip()

    def _calculate_similarity(self, str1, str2):
        """Hitung kemiripan antara dua string (0-1)"""
        if not str1 or not str2:
            return 0.0
    
        # Simple character-based similarity
        shorter = min(len(str1), len(str2))
        longer = max(len(str1), len(str2))
    
        if longer == 0:
            return 1.0
    
        # Count matching characters
        matches = sum(1 for i in range(shorter) if str1[i] == str2[i])
    
        # Add word-based check
        words1 = set(str1.split())
        words2 = set(str2.split())
        common_words = words1 & words2
        if words1 or words2:
            word_similarity = len(common_words) / max(len(words1), len(words2))
        else:
            word_similarity = 0
    
        # Combine character and word similarity
        return (matches / longer + word_similarity) / 2

    def show_filter_stats(self):
        """Tampilkan statistik filter"""
        total_filtered = sum(self.filter_stats.values())
    
        stats_msg = "\n[FILTER STATISTICS]\n"
        stats_msg += "=" * 30 + "\n"
        stats_msg += f"Kata toxic: {self.filter_stats.get('toxic', 0)}\n"
        stats_msg += f"Pesan pendek: {self.filter_stats.get('short', 0)}\n"
        stats_msg += f"Emoji only: {self.filter_stats.get('emoji', 0)}\n"
        stats_msg += f"Spam/berulang: {self.filter_stats.get('spam', 0)}\n"
        stats_msg += f"Nomor spam: {self.filter_stats.get('numeric', 0)}\n"
        stats_msg += "=" * 30 + "\n"
        stats_msg += f"Total difilter: {total_filtered}"
    
        self.log_view.append(stats_msg)

    def show_statistics(self):
        """Show cache dan spam statistics."""
        cache_stats = self.cache_manager.get_stats()
        spam_stats = self.spam_detector.get_overall_stats()

        stats_msg = textwrap.dedent(f"""
            [CACHE STATISTICS]
            Total Entries: {cache_stats['total_entries']}
            Total Hits: {cache_stats['total_hits']}
            Hit Rate: {cache_stats['hit_rate']:.1f}%
            Cache Size: {cache_stats['cache_size_kb']:.1f} KB

            [SPAM DETECTION]
            Total Users: {spam_stats['total_users']}
            Blocked Users: {spam_stats['blocked_users']}
            Total Messages: {spam_stats['total_messages']}
            Active Blocks: {', '.join(spam_stats['active_blocks'])}
        """).strip()

        self.log_view.append(stats_msg)

    def reset_filter_stats(self):
        """Reset filter statistics"""
        self.filter_stats = {
            "toxic": 0,
            "short": 0,
            "emoji": 0,
            "spam": 0,
            "numeric": 0
        }
        self.log_view.append("[INFO] Filter statistics telah direset")

    def _hotkey_listener(self):
        """Thread untuk mendengarkan hotkey hold-to-talk"""
        prev = False
        while True:
            time.sleep(0.05)
            if not self.hotkey_enabled:
                prev = False
                continue

            hot = self.cfg.get("cohost_hotkey", "Ctrl+Alt+X")
            pressed = self._is_pressed(hot)

            if pressed and not prev:
                # Mulai merekam
                prev = True
                self.conversation_active = True  # pause auto-reply
                self.log_view.append("🔴 Mulai merekam...")

                # Start recording thread
                self.stt_thread = STTThread(
                    self.cfg.get("selected_mic_index", 0),
                    self.cfg.get("cohost_input_lang", "ind_Latn"),
                    False  # Basic mode uses Whisper, not Google
                )
                self.stt_thread.result.connect(self._handle_speech)
                self.stt_thread.start()

            elif not pressed and prev:
                # Berhenti merekam
                prev = False
                self.conversation_active = False  # resume auto-reply
                self.log_view.append("⏳ Memproses...")
                
                # Stop recording
                if self.stt_thread:
                    self.stt_thread.running = False

    def _handle_speech(self, txt):
        """Handle speech result from STT"""
        self.conversation_active = False

        if not txt:
            self.log_view.append("[WARN] STT kosong.")
            return

        self.log_view.append(f"🎙️ Kamu: {txt}")

        # Generate reply
        prompt = (
            f"Kamu adalah AI Co-Host {self.cfg.get('cohost_name', 'CoHost')} "
            f"dengan kepribadian {self.person_cb.currentText()}. "
            f"User berkata: \"{txt}\". "
            f"Balas dalam bahasa {self.out_lang.currentText().lower()} tanpa emoji, tanpa tanda baca."
        )
        
        try:
            reply = generate_reply(prompt) or ""
            reply = re.sub(r"[^\w\s\?]", "", reply)
            
            # Emit signal untuk animasi mulai TTS
            self.ttsAboutToStart.emit()
            
            # TTS
            code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
            voice_model = self.voice_cb.currentData()
            speak(reply, language_code=code, voice_name=voice_model)
            
            # Emit signal untuk animasi selesai TTS
            self.ttsFinished.emit()
            
            self.log_view.append(f"🤖 {reply}")
        except Exception as e:
            self.log_view.append(f"[ERROR] {str(e)}")
            self.ttsFinished.emit()  # Pastikan signal tetap dipancarkan

    def start(self):
        """Start auto-reply untuk mode Basic dengan validasi lengkap."""
        # Periksa status demo jika ada
        if not self._check_credit_before_start():
            return
        subscription_file = Path("config/subscription_status.json")
        is_demo = False
        if subscription_file.exists():
            try:
                data = json.loads(subscription_file.read_text(encoding="utf-8"))
                if data.get("status") == "demo":
                    is_demo = True
                    expire_date = datetime.fromisoformat(data.get("expire_date", "2000-01-01"))
                    if expire_date <= datetime.now():
                        # Demo sudah expired
                        QMessageBox.warning(
                            self,
                            "Demo Expired",
                            "Waktu demo 30 menit telah berakhir.\n"
                            "Silakan beli kredit untuk melanjutkan.",
                        )
                        return
                    # Demo masih valid, lanjutkan tanpa cek kredit lain
            except Exception as e:
                print(f"[DEBUG] Error reading demo status: {e}")
                is_demo = False
        # TAMBAHAN: Skip usage tracking untuk test mode
        main_window = self.window()
        if hasattr(main_window, 'license_validator') and main_window.license_validator.testing_mode:
            print("[DEBUG] Test mode active - skipping usage tracking")
            # Jangan start usage timer
        else:
            # Mulai tracking menggunakan sistem baru
            start_usage_tracking("cohost_basic")
            # Tetap pertahankan timer untuk backward compatibility
            self.credit_timer.start()

        self.hour_tracker.start_tracking()
        self.credit_timer.start()
        
        logger.info("Starting CoHost Basic mode")
        # 1. VALIDATE AND SET MODE
        self.cfg.set("reply_mode", "Trigger")
        self.cfg.set("paket", "basic")

        # Reset batch counter saat start
        self.batch_counter = 0
        self.is_in_cooldown = False
        self.processing_batch = False

        # 2. MIGRATE OLD TRIGGER FORMAT
        old_trigger = self.cfg.get("trigger_word", "")
        if old_trigger and not self.cfg.get("trigger_words"):
            self.cfg.set("trigger_words", [old_trigger])
            self.log_view.append(f"[INFO] Migrated trigger: {old_trigger}")

        # 3. VALIDATE TRIGGER WORDS
        trigger_words = self.cfg.get("trigger_words", [])
        if not trigger_words:
            self.log_view.append("[ERROR] Tidak ada trigger word yang diset!")
            self.log_view.append("[INFO] Silakan set trigger word terlebih dahulu")
            return

        # 4. VALIDATE PLATFORM CONFIG
        plat = self.platform_cb.currentText()
        self.cfg.set("platform", plat)  # Save selected platform

        if plat == "YouTube":
            vid = self.cfg.get("video_id", "").strip()
            if not vid:
                self.log_view.append("[ERROR] Video ID belum diisi!")
                return
            if len(vid) != 11:
                self.log_view.append(f"[ERROR] Video ID harus 11 karakter (saat ini: {len(vid)})")
                return
        else:  # TikTok
            nick = self.cfg.get("tiktok_nickname", "").strip()
            if not nick:
                self.log_view.append("[ERROR] TikTok nickname belum diisi!")
                return
            # Normalize nickname
            if not nick.startswith("@"):
                nick = "@" + nick
                self.cfg.set("tiktok_nickname", nick)

        # 5. LOG CONFIGURATION
        self.log_view.append("=" * 50)
        self.log_view.append(f"[INFO] Starting StreamMate Basic")
        self.log_view.append(f"[INFO] Mode: Trigger Only")
        self.log_view.append(f"[INFO] Platform: {plat}")
        self.log_view.append(f"[INFO] Trigger Words: {', '.join(trigger_words)}")
        self.log_view.append(f"[INFO] Batch Size: 3 balasan")
        self.log_view.append(f"[INFO] Delay: 3s antar balasan, 10s cooldown")
        self.log_view.append("=" * 50)

        # 6. CLEANUP EXISTING STATE
        CHAT_BUFFER.write_text("")
        self.reply_queue.clear()
        self.reply_busy = False
        self.recent_messages.clear()

        # Stop existing listeners
        if self.monitor:
            self.monitor.stop()
            self.monitor = None
        if self.tiktok_thread:
            self.tiktok_thread.stop()
            self.tiktok_thread = None
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc = None

        # 7. START NEW LISTENERS
        try:
            if plat == "YouTube":
                logger.info(f"YouTube listener starting for video: {vid}")
                # Execute YouTube listener
                self.proc = subprocess.Popen(
                    ["python", "-u", str(YT_SCRIPT)],
                    cwd=str(ROOT),
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
                )

                # Start file monitor
                self.monitor = FileMonitorThread(CHAT_BUFFER)
                self.monitor.newComment.connect(self._enqueue)
                self.monitor.start()

                self.log_view.append(f"[INFO] YouTube listener started (PID: {self.proc.pid})")
            else:
                # Start TikTok listener
                logger.info(f"TikTok listener starting for: {nick}")
                self.tiktok_thread = TikTokListenerThread()
                self.tiktok_thread.newComment.connect(self._enqueue)
                self.tiktok_thread.start()

                self.log_view.append("[INFO] TikTok listener started")

        except Exception as e:
            self.log_view.append(f"[ERROR] Failed to start listener: {str(e)}")
            return

        # 8. SETUP BUFFER CLEANING TIMER
        if hasattr(self, "buffer_timer"):
            self.buffer_timer.stop()

        self.buffer_timer = QTimer(self)
        self.buffer_timer.timeout.connect(self._clean_buffer)
        self.buffer_timer.start(300_000)  # 5 menit

        # 9. SETUP USAGE TRACKING
        if self.cfg.get("debug_mode", False):
            self.log_view.append("[DEBUG] Developer mode: kuota tidak diberlakukan")
        else:
            # Check current usage
            tier, used, limit = get_today_usage()
            remaining = limit - used
            self.log_view.append(f"[INFO] Kuota hari ini: {used:.1f}/{limit} jam")

            if remaining <= 0:
                self.log_view.append("[ERROR] Kuota habis! Silakan tunggu besok.")
                self.stop()
                return

            # Start usage tracking
            self._track_usage()
            self.usage_timer.start()

        # 10. FINAL STATUS
        self.log_view.append("[INFO] Auto-Reply Basic siap!")
        self.log_view.append(f"[INFO] Menunggu trigger: {', '.join(trigger_words)}")
        self.status.setText("✅ Auto-Reply Active")
        logger.info("Auto-Reply Basic ready!")

    def _clean_buffer(self):
        """Bersihkan buffer chat lebih efisien."""
        try:
            if CHAT_BUFFER.exists():
                # Baca dan filter entri unik saja
                lines = CHAT_BUFFER.read_text(encoding="utf-8").splitlines()
                unique_entries = []
                seen = set()

                # Ambil 50 entri terakhir yang unik
                for line in reversed(lines):
                    try:
                        entry = json.loads(line)
                        key = (entry["author"], entry["message"])
                        if key not in seen:
                            seen.add(key)
                            unique_entries.append(line)
                            if len(unique_entries) >= 50:
                                break
                    except:
                        continue

                # Tulis ulang dengan entri unik
                CHAT_BUFFER.write_text("\n".join(reversed(unique_entries)), encoding="utf-8")

                # Reset FileMonitorThread _seen untuk prevent memory leak
                if self.monitor:
                    self.monitor._seen.clear()

                self.log_view.append(f"[INFO] Buffer dibersihkan: {len(lines)} → {len(unique_entries)} baris")
        except Exception as e:
            self.log_view.append(f"[WARN] Gagal bersihkan buffer: {e}")

    def stop(self):
        """Stop auto-reply."""
        # Hentikan tracking kredit
        stop_usage_tracking()
        self.credit_timer.stop()

        # 1. Stop all timers first
        if hasattr(self, "buffer_timer") and self.buffer_timer.isActive():
            self.buffer_timer.stop()

        if hasattr(self, "usage_timer") and self.usage_timer.isActive():
            self.usage_timer.stop()

        if hasattr(self, "cooldown_timer") and self.cooldown_timer.isActive():
            self.cooldown_timer.stop()

        if hasattr(self, "batch_timer") and self.batch_timer.isActive():
            self.batch_timer.stop()

        # 2. Clear flags
        self.is_in_cooldown = False
        self.reply_busy = False
        self.conversation_active = False
        self.batch_counter = 0
        self.processing_batch = False

        # 3. Stop monitor thread
        if self.monitor:
            self.monitor.stop()
            self.monitor.wait(2000)
            self.monitor = None

        # 4. Stop TikTok thread
        if self.tiktok_thread:
            self.tiktok_thread.stop()
            self.tiktok_thread.wait(2000)
            self.tiktok_thread = None

        # 5. Terminate YouTube process
        if self.proc and self.proc.poll() is None:
            try:
                if sys.platform == "win32":
                    # Windows: use CTRL_BREAK_EVENT
                    self.proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    # Unix: use SIGTERM
                    self.proc.terminate()

                # Wait for graceful shutdown
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    # Force kill
                    self.proc.kill()
                    self.proc.wait(timeout=1)
            except Exception as e:
                self.log_view.append(f"[WARN] Error stopping process: {e}")
            finally:
                self.proc = None

        # 6. Clear queues and state
        self.reply_queue.clear()
        self.recent_messages.clear()

        # 7. Clear buffer file
        if CHAT_BUFFER.exists():
            try:
                CHAT_BUFFER.unlink()
            except:
                CHAT_BUFFER.write_text("")

        # 8. Update UI
        self.status.setText("❌ Auto-Reply Stopped")
        self.log_view.append("[INFO] Auto-Reply stopped successfully")

    def _has_trigger(self, message):
        """Check if message contains any trigger word."""
        message_lower = message.lower().strip()
        trigger_words = self.cfg.get("trigger_words", [])

        if not trigger_words:
            # Fallback to old single trigger
            trigger_word = self.cfg.get("trigger_word", "").lower().strip()
            if trigger_word and trigger_word in message_lower:
                return True
        else:
            # Check multiple triggers
            for trigger in trigger_words:
                if trigger.lower() in message_lower:
                    return True
        return False

    def _save_interaction(self, author, message, reply):
        """Simpan interaksi ke log dan viewer memory."""
        # Save to file log
        try:
            COHOST_LOG.parent.mkdir(exist_ok=True)
            with open(str(COHOST_LOG), "a", encoding="utf-8") as f:
                f.write(f"{author}\t{message}\t{reply}\n")
        except Exception as e:
            self.log_view.append(f"[WARN] Gagal save log: {e}")

        # Update viewer memory
        if self.viewer_memory:
            self.viewer_memory.add_interaction(author, message, reply)

        # Update recent messages
        self.recent_messages.append((author, message))
        if len(self.recent_messages) > self.message_history_limit:
            self.recent_messages.pop(0)
        self.replyGenerated.emit(author, message, reply)

    def _enqueue(self, author, message):
        """Process comment dengan cooldown & batch aware."""
        # Tampilkan komentar
        self.log_view.append(f"👤 {author}: {message}")

        # Skip jika tidak ada trigger
        if not self._has_trigger(message):
            return

        self.log_view.append(f"🔔 Trigger terdeteksi!")

        # Jika dalam cooldown, skip
        if self.is_in_cooldown:
            self.log_view.append("[COOLDOWN] Skip komentar saat cooldown")
            return

        # Jika sedang proses batch, tambah ke queue
        if self.processing_batch:
            if len(self.reply_queue) < self.max_queue_size:
                self.reply_queue.append((author, message))
                self.log_view.append(f"[INFO] Reply queue: {len(self.reply_queue)} items")
            return
        
        # Register activity saat ada komentar baru yang diproses
        register_activity("cohost_basic")

        # Jika idle, proses langsung
        self.reply_queue = [(author, message)]
        self._start_batch()

    def _start_batch(self):
        """Start batch processing"""
        if not self.reply_queue:
            return
            
        self.processing_batch = True
        self.batch_counter = 0
        self._process_next_in_batch()

    def _process_next_in_batch(self):
        """Process next message in batch"""
        if not self.reply_queue or self.batch_counter >= self.batch_size:
            self._end_batch()
            return
            
        # Ambil message dari queue
        author, msg = self.reply_queue.pop(0)
        self.batch_counter += 1
        
        # Create reply thread
        self._create_reply_thread(author, msg)

    def _create_reply_thread(self, author, message):
        """Create reply thread dengan konfigurasi yang tepat."""
        lang_code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
        voice = self.voice_cb.currentData()

        # Create thread
        rt = ReplyThread(
            author=author,
            message=message,
            personality=self.person_cb.currentText(),
            voice_model=voice,
            language_code=lang_code,
            lang_out=self.out_lang.currentText(),
            viewer_memory=self.viewer_memory
        )

        # Connect signals
        rt.finished.connect(lambda a, m, r: self._on_reply(a, m, r))
        self.threads.append(rt)
        rt.start()

    def _on_reply(self, author, message, reply):
        """Handle reply dengan batch management yang lebih baik."""
        if not reply:
            self.log_view.append("[WARN] Gagal mendapatkan balasan.")
            # Process next after delay
            QTimer.singleShot(self.reply_delay, self._process_next_in_batch)
            return

        try:
            # Update UI & log
            if hasattr(self.window(), "overlay_tab"):
                self.window().overlay_tab.update_overlay(author, reply)

            self.log_view.append(f"🤖 {reply}")

            # Save to log & memory
            self._save_interaction(author, message, reply)

            # Emit signal TTS mulai
            self.ttsAboutToStart.emit()

            # TTS dengan callback yang benar
            self._do_tts_with_callback(reply, lambda: self._handle_tts_complete())
            
            # Register activity saat AI merespon
            register_activity("cohost_basic")

        except Exception as e:
            self.log_view.append(f"[ERROR] Error in _on_reply: {e}")
            self._cleanup_tts_state()

    def _do_tts_with_callback(self, text, on_complete):
        """TTS dengan guaranteed callback."""
        code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
        voice_model = self.cfg.get("cohost_voice_model", None)

        # Setup safety timer terlebih dahulu
        safety_timeout = self._calculate_tts_duration(text) + 2.0  # +2 detik buffer

        self.tts_safety_timer = QTimer(self)
        self.tts_safety_timer.setSingleShot(True)
        self.tts_safety_timer.timeout.connect(lambda: on_complete())
        self.tts_safety_timer.start(int(safety_timeout * 1000))

        # Wrapper callback dengan error handling
        def wrapped_callback():
            try:
                # Cancel safety timer
                if hasattr(self, 'tts_safety_timer') and self.tts_safety_timer.isActive():
                    self.tts_safety_timer.stop()
                print(f"[DEBUG] TTS completed callback triggered")
                on_complete()
            except Exception as e:
                print(f"[ERROR] Callback error: {e}")
                # Pastikan cleanup
                self._cleanup_tts_state()

        try:
            speak(text, code, voice_model, on_finished=wrapped_callback)
        except Exception as e:
            print(f"[ERROR] TTS error: {e}")
            # Pastikan safety timer tetap jalan
            pass

    def _handle_tts_complete(self):
        """Handle TTS complete with proper batch flow"""
        # Emit signal selesai
        self.ttsFinished.emit()
        
        # Process next after delay
        self.batch_timer.stop()
        self.batch_timer.start(self.reply_delay)

    def _calculate_tts_duration(self, text):
        """Estimasi durasi TTS."""
        char_count = len(text)
        # Bahasa Indonesia ~12 karakter/detik
        chars_per_second = 12
        return max(2.0, (char_count / chars_per_second) + 1.0)

    def _end_batch(self):
        """End batch processing and start cooldown"""
        self.processing_batch = False
        self.batch_counter = 0
        
        # Start cooldown
        self.is_in_cooldown = True
        self.log_view.append(f"[COOLDOWN] Batch selesai, cooldown {self.cooldown_duration}s")
        
        # Start cooldown timer
        self.cooldown_timer.start(self.cooldown_duration * 1000)

    def _end_cooldown(self):
        """End cooldown period"""
        self.is_in_cooldown = False
        self.log_view.append("[COOLDOWN] Selesai")
        
        # Check if there are pending messages
        if self.reply_queue:
            self._start_batch()

    def _cleanup_tts_state(self):
        """Cleanup state saat error atau timeout."""
        self.ttsFinished.emit()
        self.reply_busy = False

        # Cancel timers
        if hasattr(self, 'tts_safety_timer') and self.tts_safety_timer.isActive():
            self.tts_safety_timer.stop()

        # Process next
        QTimer.singleShot(1000, self._process_next_in_batch)

    def _track_usage(self):
        """Track penggunaan untuk subscription checking"""
        # Jika developer/debug_mode, skip
        if self.cfg.get("debug_mode", False):
            self.log_view.append("[DEBUG] Developer mode: kuota tidak diberlakukan")
            return
        
        # Check demo expiry
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
                # Masih demo, lewati hitung kuota harian
                remaining = datetime.fromisoformat(exp) - datetime.now()
                menit = remaining.seconds // 60
                self.log_view.append(f"[Demo] Sisa {menit} menit")
                return
        
        # Check daily usage
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

    def show_memory_stats(self):
        """Tampilkan statistik viewer memory"""
        if not hasattr(self, 'viewer_memory'):
            self.log_view.append("[ERROR] Viewer memory tidak tersedia")
            return
        
        total_viewers = len(self.viewer_memory.memory_data)
        new_viewers = sum(1 for v in self.viewer_memory.memory_data.values() if v['status'] == 'new')
        regular_viewers = sum(1 for v in self.viewer_memory.memory_data.values() if v['status'] == 'regular')
        vip_viewers = sum(1 for v in self.viewer_memory.memory_data.values() if v['status'] == 'vip')
        
        stats_msg = f"[VIEWER MEMORY STATS]\nTotal Viewers: {total_viewers}\n- New: {new_viewers}\n- Regular: {regular_viewers}\n- VIP: {vip_viewers}\nData akan auto-cleanup setelah 30 hari tidak aktif"
        
        self.log_view.append(stats_msg)

    def _check_credit_before_start(self):
        """Cek kredit sebelum start."""
        # TAMBAHAN: Skip semua checking untuk test mode
        main_window = self.window()
        if hasattr(main_window, 'license_validator') and main_window.license_validator.testing_mode:
            return True
            
        # Skip untuk debug mode
        if self.cfg.get("debug_mode", False):
            return True
        
        # Skip untuk developer
        if self._is_dev_user():
            return True
        
        if not self.hour_tracker.check_credit():
            QMessageBox.warning(
                self,
                "Kredit Habis",
                "Kredit jam Anda habis!\n\n"
                "Silakan beli kredit untuk melanjutkan.\n"
                "Klik OK untuk membuka tab Subscription.",
                QMessageBox.StandardButton.Ok
            )
            return False
        return True
    
    def _check_credit(self):
        """Cek kredit setiap menit saat aktif."""
        if not self.reply_busy:  # Tidak aktif
            return
        
        if not self.hour_tracker.check_credit():
            # Auto stop jika kredit habis
            self.stop()
            
            QMessageBox.warning(
                self,
                "Kredit Habis",
                "Kredit jam Anda telah habis!\n\n"
                "Auto-reply telah dihentikan.\n"
                "Silakan beli kredit untuk melanjutkan."
            )
            
            # Update UI
            self.status.setText("❌ Kredit Habis")
            self.log_view.append("[SYSTEM] Auto-reply dihentikan - kredit habis")

    def closeEvent(self, event: QCloseEvent):
        """Handle window close event properly"""
        # pastikan timer berhenti saat window ditutup
        self.usage_timer.stop()
        # hentikan semua listener
        self.stop()
        super().closeEvent(event)

    def _is_dev_user(self):
        """Helper method untuk cek dev user"""
        try:
            email = self.cfg.get("user_data", {}).get("email", "")
            dev_path = Path("config/dev_users.json")
            if dev_path.exists() and email:
                with open(dev_path, 'r') as f:
                    dev_data = json.load(f)
                    return email in dev_data.get("emails", [])
        except:
            pass
        return False