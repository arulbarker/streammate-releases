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
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger('StreamMate')

# PERBAIKAN 1: Setup path yang benar
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Import PyQt6
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QScrollArea, QFrame, QTextEdit, QHBoxLayout, 
    QSpinBox, QSizePolicy, QMessageBox, QCheckBox, QGroupBox 
)
from PyQt6.QtGui import QCloseEvent, QTextOption
import keyboard

# Import ConfigManager dengan fallback
try:
    from modules_client.config_manager import ConfigManager
except ImportError:
    from modules_server.config_manager import ConfigManager

# Import modules lainnya
from modules_client.cache_manager import CacheManager
from modules_client.spam_detector import SpamDetector
from modules_client.viewer_memory import ViewerMemory
from modules_client.subscription_checker import (
    get_today_usage, add_usage, time_until_next_day, 
    HourlySubscriptionChecker, start_usage_tracking, 
    stop_usage_tracking, register_activity
)

# Import API functions dengan fallback
try:
    from modules_client.api import generate_reply  
except ImportError:
    from modules_server.deepseek_ai import generate_reply

# Import TTS dari server
from modules_server.tts_engine import speak

# PERBAIKAN 2: Paths yang benar
YT_SCRIPT = ROOT / "listeners" / "chat_listener.py"
CHAT_BUFFER = ROOT / "temp" / "chat_buffer.jsonl"
COHOST_LOG = ROOT / "temp" / "cohost_log.txt"
VOICES_PATH = ROOT / "config" / "voices.json"

# Pastikan direktori temp ada
Path(ROOT / "temp").mkdir(exist_ok=True)


# PERBAIKAN 3: FileMonitorThread yang berfungsi penuh
class FileMonitorThread(QThread):
    newComment = pyqtSignal(str, str)

    def __init__(self, buffer_file: Path):
        super().__init__()
        self.buffer_file = buffer_file
        self._seen = set()
        self._running = True
        # Pastikan file dan direktori ada
        self.buffer_file.parent.mkdir(exist_ok=True, parents=True)
        self.buffer_file.touch(exist_ok=True)

    def run(self):
        while self._running:
            try:
                if self.buffer_file.exists():
                    lines = self.buffer_file.read_text(encoding="utf-8").splitlines()
                else:
                    lines = []
            except Exception as e:
                print(f"[ERROR] FileMonitor read error: {e}")
                lines = []
                
            for line in lines:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    author = entry.get("author", "")
                    message = entry.get("message", "")
                    key = (author, message)
                    
                    if key not in self._seen and author and message:
                        self._seen.add(key)
                        self.newComment.emit(author, message)
                except Exception as parse_error:
                    print(f"[DEBUG] Parse error: {parse_error}")
                    continue
            time.sleep(0.5)

    def stop(self):
        self._running = False
        self.wait(2000)  # Tunggu maksimal 2 detik


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
    
        # Timer untuk cleanup tracking spam
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self._cleanup_spam_tracking)
        self.cleanup_timer.setInterval(300_000)  # 5 menit
        self.cleanup_timer.start()

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
            print("STT module not available")
            self.result.emit("")


# ReplyThread - untuk generate dan TTS balasan AI
class ReplyThread(QThread):
    finished = pyqtSignal(str, str, str)

    def __init__(self, author: str, message: str, personality: str, 
                 voice_model: str, language_code: str, lang_out: str, viewer_memory=None):
        super().__init__()
        self.author = author
        self.message = message
        self.personality = personality
        self.voice_model = voice_model
        self.language_code = language_code
        self.lang_out = lang_out
        self.viewer_memory = viewer_memory

    def run(self):
        print(f"[DEBUG] ========== ReplyThread START ==========")
        print(f"[DEBUG] Author: {self.author}")
        print(f"[DEBUG] Message: {self.message}")
        print(f"[DEBUG] Personality: {self.personality}")
        print(f"[DEBUG] Voice Model: {self.voice_model}")
        print(f"[DEBUG] Language Code: {self.language_code}")
        print(f"[DEBUG] Lang Out: {self.lang_out}")
        
        try:
            # Load configuration
            print(f"[DEBUG] Loading configuration...")
            cfg = ConfigManager("config/settings.json")
            extra = cfg.get("custom_context", "").strip()
            lang_label = "Bahasa Indonesia" if self.lang_out == "Indonesia" else "English"
            
            print(f"[DEBUG] Custom context loaded: '{extra}'")
            print(f"[DEBUG] Language label: {lang_label}")

            # Get viewer memory
            print(f"[DEBUG] Processing viewer memory...")
            viewer_status = "new"
            viewer_context = ""
            interaction_count = 0
            
            if self.viewer_memory:
                print(f"[DEBUG] Viewer memory available, getting info...")
                viewer_info = self.viewer_memory.get_viewer_info(self.author)
                if viewer_info:
                    viewer_status = viewer_info.get("status", "new")
                    viewer_context = self.viewer_memory.get_recent_context(self.author, limit=3)
                    print(f"[DEBUG] Viewer status: {viewer_status}")
                    print(f"[DEBUG] Viewer context: {viewer_context}")
                else:
                    print(f"[DEBUG] No viewer info found for {self.author}")
            else:
                print(f"[DEBUG] Viewer memory not available")

            # Analyze message for relevant response
            print(f"[DEBUG] Analyzing message category...")
            message_lower = self.message.lower()
            print(f"[DEBUG] Message lowercase: '{message_lower}'")
            
            # Detect question category
            question_type = "general"
            if any(word in message_lower for word in ["kabar", "apa kabar", "gimana"]):
                question_type = "greeting"
            elif any(word in message_lower for word in ["makan", "udah makan", "belum makan"]):
                question_type = "eating"
            elif any(word in message_lower for word in ["build", "item", "gear", "equipment"]):
                question_type = "gaming_build"
            elif any(word in message_lower for word in ["main", "game", "mabar", "rank", "push"]):
                question_type = "gaming_play"
            elif any(word in message_lower for word in ["halo", "hai", "hello", "assalamualaikum"]):
                question_type = "greeting"
            elif any(word in message_lower for word in ["khodam", "cek", "apa khodam", "khodamku"]):
                question_type = "khodam"
            
            print(f"[DEBUG] Question category detected: {question_type}")

            # Build base response
            print(f"[DEBUG] Building base response...")
            if question_type == "greeting":
                base_response = f"Hai {self.author}! Kabar baik nih, lagi seru streaming"
            elif question_type == "eating":
                base_response = f"Halo {self.author}! Udah makan kok, tadi sempet istirahat dulu"
            elif question_type == "gaming_build":
                base_response = f"Oh {self.author}, untuk build"
            elif question_type == "gaming_play":
                base_response = f"Iya {self.author}, lagi main nih"
            else:
                base_response = f"Hai {self.author}"
            
            print(f"[DEBUG] Base response: '{base_response}'")

            # Build AI prompt
            print(f"[DEBUG] Building AI prompt...")
            prompt = (
                f"Kamu adalah streamer yang sedang live streaming. "
                f"Nama kamu dan informasi penting: {extra}. "
                f"Penonton {self.author} bertanya: '{self.message}'. "
            )
            
            print(f"[DEBUG] Prompt base built")

            # Add specific instructions based on question type
            if question_type == "greeting":
                prompt += (
                    f"Sapa {self.author} dengan ramah. "
                    f"Ceritakan sedikit tentang aktivitas streaming kamu saat ini. "
                )
            elif question_type == "eating":
                prompt += (
                    f"Jawab pertanyaan tentang makan dengan santai. "
                    f"Bisa ceritakan makanan atau waktu makan. "
                )
            elif question_type == "gaming_build":
                prompt += (
                    f"Berikan saran build/item yang bagus. "
                    f"Jelaskan dengan singkat dan berguna untuk gameplay. "
                )
            elif question_type == "gaming_play":
                prompt += (
                    f"Ceritakan tentang game yang sedang dimainkan. "
                    f"Bisa tentang hero, strategy, atau kondisi match saat ini. "
                )
            elif question_type == "khodam":
                prompt += (
                    f"Jawab tentang khodam sesuai dengan informasi yang kamu miliki. "
                    f"Berikan respons yang sesuai dengan karakter kamu. "
                )
            else:
                prompt += (
                    f"Jawab pertanyaan dengan informatif dan relevan. "
                    f"Gunakan informasi tentang diri kamu untuk memberikan konteks. "
                )

            # Add response format instructions
            prompt += (
                f"Awali dengan menyebut nama {self.author}. "
                f"Jawab dalam {lang_label} dengan maksimal 2 kalimat pendek. "
                f"Gaya bicara santai seperti streamer Indonesia pada umumnya. "
                f"Jangan gunakan emoji atau tanda baca berlebihan. "
                f"Pastikan jawaban relevan dengan pertanyaan. "
            )

            # Add examples for guidance
            if question_type == "greeting":
                prompt += f"Contoh: '{self.author} hai juga! Lagi asik main Mobile Legends nih pake Gatot'"
            elif question_type == "eating":
                prompt += f"Contoh: '{self.author} udah makan tadi, sekarang lagi fokus push rank'"
            elif question_type == "khodam":
                prompt += f"Gunakan informasi khodam yang sudah kamu ketahui untuk menjawab"

            print(f"[DEBUG] Final prompt built:")
            print(f"[DEBUG] Prompt: '{prompt}'")
            print(f"[DEBUG] Prompt length: {len(prompt)} characters")

            # Generate AI reply
            print(f"[DEBUG] ========== CALLING AI API ==========")
            print(f"[DEBUG] Sending request to generate_reply()...")
            
            try:
                reply = generate_reply(prompt)
                print(f"[DEBUG] AI API call successful!")
                print(f"[DEBUG] Raw AI response: '{reply}'")
                print(f"[DEBUG] Response type: {type(reply)}")
                print(f"[DEBUG] Response length: {len(reply) if reply else 0}")
                
            except Exception as api_error:
                print(f"[DEBUG] AI API call failed!")
                print(f"[ERROR] API Error: {api_error}")
                import traceback
                traceback.print_exc()
                reply = None

            # Process reply
            print(f"[DEBUG] ========== PROCESSING REPLY ==========")
            
            if not reply:
                print(f"[DEBUG] Reply is empty, using fallback")
                reply = f"Hai {self.author} sorry koneksi lagi bermasalah"
            else:
                print(f"[DEBUG] Processing non-empty reply...")
                
                # Clean reply from weird formatting
                original_reply = reply
                reply = re.sub(r"[^\w\s\?]", "", reply)
                print(f"[DEBUG] After regex cleanup: '{reply}'")
                
                reply = re.sub(r"\s+", " ", reply).strip()
                print(f"[DEBUG] After space cleanup: '{reply}'")
                
                reply = reply.replace("\n", " ").replace("\r", " ")
                print(f"[DEBUG] After newline cleanup: '{reply}'")
                
                # Limit length
                words = reply.split()
                print(f"[DEBUG] Word count: {len(words)}")
                
                if len(words) > 25:
                    reply = " ".join(words[:25])
                    print(f"[DEBUG] Truncated to 25 words: '{reply}'")

                # Ensure author name is mentioned
                if self.author.lower() not in reply.lower():
                    reply = f"{self.author} {reply}"
                    print(f"[DEBUG] Added author name: '{reply}'")

            print(f"[DEBUG] ========== FINAL RESULT ==========")
            print(f"[DEBUG] Final reply: '{reply}'")
            print(f"[DEBUG] Final reply length: {len(reply)}")
            print(f"[DEBUG] Final word count: {len(reply.split())}")
            
            # Additional debugging info
            print(f"[DEBUG] Custom context used: '{extra}'")
            print(f"[DEBUG] Question type: {question_type}")
            print(f"[DEBUG] Viewer status: {viewer_status}")
            print(f"[DEBUG] Language: {lang_label}")
            
        except Exception as outer_error:
            print(f"[DEBUG] ========== OUTER EXCEPTION ==========")
            print(f"[ERROR] Outer exception in ReplyThread: {outer_error}")
            import traceback
            traceback.print_exc()
            reply = f"{self.author} hai sorry ada error teknis nih"

        # Emit result
        print(f"[DEBUG] ========== EMITTING RESULT ==========")
        print(f"[DEBUG] About to emit finished signal...")
        print(f"[DEBUG] Signal params: author='{self.author}', message='{self.message}', reply='{reply}'")
        
        try:
            self.finished.emit(self.author, self.message, reply)
            print(f"[DEBUG] Signal emitted successfully!")
        except Exception as emit_error:
            print(f"[ERROR] Failed to emit signal: {emit_error}")
            import traceback
            traceback.print_exc()
            
        print(f"[DEBUG] ========== ReplyThread END ==========")


# PERBAIKAN 4: CohostTabBasic - implementasi lengkap dan stabil
class CohostTabBasic(QWidget):
    """Tab CoHost untuk mode Basic - AI co-host dengan fitur trigger-based reply"""
    # Signals untuk integrasi
    ttsAboutToStart = pyqtSignal()
    ttsFinished = pyqtSignal()
    replyGenerated = pyqtSignal(str, str, str)  # author, message, reply
    
    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager("config/settings.json")
        
        # Pastikan direktori penting ada
        required_dirs = [
            ROOT / "temp",
            ROOT / "logs",  
            ROOT / "config",
            ROOT / "listeners"
        ]
        
        for dir_path in required_dirs:
            try:
                dir_path.mkdir(exist_ok=True, parents=True)
                print(f"[DEBUG] Directory ensured: {dir_path}")
            except Exception as e:
                print(f"[ERROR] Failed to create directory {dir_path}: {e}")

        # Initialize components SETELAH direktori dibuat
        self.viewer_memory = ViewerMemory()
        self.cache_manager = CacheManager()
        self.spam_detector = SpamDetector()
        
        # Process management
        self.proc = None
        self.monitor = None
        self.tiktok_thread = None
        self.threads = []
        
        # State management
        self.reply_queue = []
        self.reply_busy = False
        self.processing_batch = False
        self.batch_counter = 0
        self.recent_messages = []
        
        # Settings
        self.cooldown_duration = 10
        self.max_queue_size = 5
        self.is_in_cooldown = False
        self.reply_delay = 3000  # 3 detik
        self.batch_size = 3
        self.message_history_limit = 10
        self.daily_message_limit = self.cfg.get("daily_message_limit", 5)

        # TAMBAHAN: Cooldown settings dari config
        self.viewer_cooldown_minutes = self.cfg.get("viewer_cooldown_minutes", 3) * 60  # Convert ke detik
        self.viewer_daily_limit = self.cfg.get("viewer_daily_limit", 5)     

        # Hotkey settings
        self.hotkey_enabled = True
        self.conversation_active = False
        self.stt_thread = None
        
        # Filter statistics
        self.filter_stats = {
            "toxic": 0, "short": 0, "emoji": 0, "spam": 0, "numeric": 0
        }

        # TAMBAHAN: Daily interactions tracking per viewer
        self.viewer_daily_interactions = {}
        self.viewer_cooldowns = {}
        self.spam_threshold_hours = 24

        # Timers
        self.cooldown_timer = QTimer()
        self.cooldown_timer.setSingleShot(True)
        self.cooldown_timer.timeout.connect(self._end_cooldown)
        
        self.batch_timer = QTimer()
        self.batch_timer.setSingleShot(True)
        self.batch_timer.timeout.connect(self._process_next_in_batch)
        
        self.usage_timer = QTimer()
        self.usage_timer.setInterval(60_000)
        self.usage_timer.timeout.connect(self._track_usage)
        
        # Credit tracking
        self.hour_tracker = HourlySubscriptionChecker()
        self.credit_timer = QTimer()
        self.credit_timer.timeout.connect(self._check_credit)
        self.credit_timer.setInterval(60000)
        
        # Setup UI SETELAH semua komponen diinisialisasi
        self.init_ui()
        self._load_hotkey()
        self.load_voices()
        
        # Start hotkey listener
        threading.Thread(target=self._hotkey_listener, daemon=True).start()

    def log_user(self, message, icon="ℹ️"):
        """Log pesan ramah pengguna ke UI saja."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {icon} {message}"
        if hasattr(self, 'log_view'):
            self.log_view.append(formatted_message)

    def log_debug(self, message):
        """Log debug ke terminal saja (tidak tampil di UI)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [DEBUG] [CoHost] {message}")

    def log_system(self, message):
        """Log sistem penting ke terminal saja."""
        timestamp = datetime.now().strftime("%H:%M:%S")  
        print(f"[{timestamp}] [SYSTEM] [CoHost] {message}")

    def log_error(self, message, show_user=True):
        """Log error ke terminal dan opsional ke UI."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [ERROR] [CoHost] {message}")
        if show_user and hasattr(self, 'log_view'):
            self.log_user(f"Terjadi masalah: {message}", "❌")

        # Initialize components
        self.viewer_memory = ViewerMemory()
        self.cache_manager = CacheManager()
        self.spam_detector = SpamDetector()
        
        # Process management
        self.proc = None
        self.monitor = None
        self.tiktok_thread = None
        self.threads = []
        
        # State management
        self.reply_queue = []
        self.reply_busy = False
        self.processing_batch = False
        self.batch_counter = 0
        self.recent_messages = []
        
        # Settings
        self.cooldown_duration = 10
        self.max_queue_size = 5
        self.is_in_cooldown = False
        self.reply_delay = 3000  # 3 detik
        self.batch_size = 3
        self.message_history_limit = 10

        self.daily_message_limit = self.cfg.get("daily_message_limit", 5)
        
        # Hotkey settings
        self.hotkey_enabled = True
        self.conversation_active = False
        self.stt_thread = None
        
        # Filter statistics
        self.filter_stats = {
            "toxic": 0, "short": 0, "emoji": 0, "spam": 0, "numeric": 0
        }

        # TAMBAHAN: Daily interactions tracking per viewer
        self.viewer_daily_interactions = {}  # {author: {"date": "2025-01-01", "messages": [], "interaction_count": 0, "status": "new"}}
        
        # TAMBAHAN BARU: Memory per-penonton untuk anti-spam
        self.viewer_cooldowns = {}  # {author: {"last_message": "text", "timestamp": time, "blocked_until": time}}
        self.spam_threshold_hours = 24  # Block 24 jam jika spam

        # Timers
        self.cooldown_timer = QTimer()
        self.cooldown_timer.setSingleShot(True)
        self.cooldown_timer.timeout.connect(self._end_cooldown)
        
        self.batch_timer = QTimer()
        self.batch_timer.setSingleShot(True)
        self.batch_timer.timeout.connect(self._process_next_in_batch)
        
        self.usage_timer = QTimer()
        self.usage_timer.setInterval(60_000)
        self.usage_timer.timeout.connect(self._track_usage)
        
        # Credit tracking
        self.hour_tracker = HourlySubscriptionChecker()
        self.credit_timer = QTimer()
        self.credit_timer.timeout.connect(self._check_credit)
        self.credit_timer.setInterval(60000)
        
        # Setup UI
        self.init_ui()
        self._load_hotkey()
        self.load_voices()
        
        # Start hotkey listener
        threading.Thread(target=self._hotkey_listener, daemon=True).start()

    def init_ui(self):
        """Initialize UI dengan layout yang proper"""
        try:
            main_layout = QVBoxLayout(self)
            main_layout.setSpacing(15)
            main_layout.setContentsMargins(20, 20, 20, 20)

            # Set proper size policy
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            
            # Create scroll area
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            
            # Content widget
            content_widget = QWidget()
            content_layout = QVBoxLayout(content_widget)
            content_layout.setSpacing(15)

            # Header
            header = QLabel("🤖 Auto-Reply Basic (Trigger Only)")
            header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
            content_layout.addWidget(header)

            # Platform Group
            platform_group = QGroupBox("Platform & Sumber")
            platform_layout = QVBoxLayout(platform_group)

            platform_layout.addWidget(QLabel("Platform:"))
            self.platform_cb = QComboBox()
            self.platform_cb.addItems(["YouTube", "TikTok"])
            self.platform_cb.setCurrentText(self.cfg.get("platform", "YouTube"))
            self.platform_cb.currentTextChanged.connect(self._update_platform_ui)
            platform_layout.addWidget(self.platform_cb)

            # YouTube fields
            self.vid_label = QLabel("Video ID/URL:")
            platform_layout.addWidget(self.vid_label)
            self.vid_input = QLineEdit(self.cfg.get("video_id", ""))
            platform_layout.addWidget(self.vid_input)
            self.btn_save_vid = QPushButton("💾 Simpan Video ID")
            self.btn_save_vid.clicked.connect(self.save_video_id)
            platform_layout.addWidget(self.btn_save_vid)

            # TikTok fields
            self.nick_label = QLabel("TikTok Nickname:")
            platform_layout.addWidget(self.nick_label)
            self.nick_input = QLineEdit(self.cfg.get("tiktok_nickname", ""))
            platform_layout.addWidget(self.nick_input)
            self.btn_save_nick = QPushButton("💾 Simpan Nickname")
            self.btn_save_nick.clicked.connect(self.save_nickname)
            platform_layout.addWidget(self.btn_save_nick)

            content_layout.addWidget(platform_group)

            # AI Settings Group
            ai_group = QGroupBox("🧠 Pengaturan AI")
            ai_layout = QVBoxLayout(ai_group)

            # Language output
            ai_layout.addWidget(QLabel("Bahasa Output:"))
            self.out_lang = QComboBox()
            self.out_lang.addItems(["Indonesia", "English"])
            self.out_lang.setCurrentText(self.cfg.get("reply_language", "Indonesia"))
            self.out_lang.currentTextChanged.connect(self.load_voices)
            ai_layout.addWidget(self.out_lang)

            # Personality
            ai_layout.addWidget(QLabel("Kepribadian AI:"))
            self.person_cb = QComboBox()
            self.person_cb.addItems(["Ceria"])
            ai_layout.addWidget(self.person_cb)

            # Custom prompt
            ai_layout.addWidget(QLabel("Prompt Tambahan (opsional):"))
            self.custom_input = QTextEdit(self.cfg.get("custom_context", ""))
            self.custom_input.setPlaceholderText("Contoh: Namaku Dadang, sedang main Mobile Legends.")
            self.custom_input.setMinimumHeight(80)
            self.custom_input.setMaximumHeight(120)
            ai_layout.addWidget(self.custom_input)

            self.custom_btn = QPushButton("💾 Simpan Prompt")
            self.custom_btn.clicked.connect(self.save_custom)
            ai_layout.addWidget(self.custom_btn)

            content_layout.addWidget(ai_group)

            # Trigger Group
            trigger_group = QGroupBox("🎯 Pengaturan Trigger & Cooldown")
            trigger_layout = QVBoxLayout(trigger_group)

            # Trigger input
            trigger_row = QHBoxLayout()
            trigger_row.addWidget(QLabel("Trigger Penonton:"))
            self.trigger_input = QLineEdit()
            existing_triggers = self.cfg.get("trigger_words", [])
            if isinstance(existing_triggers, list):
                self.trigger_input.setText(", ".join(existing_triggers))
            else:
                self.trigger_input.setText(self.cfg.get("trigger_word", ""))
            self.trigger_input.setPlaceholderText("contoh: bro, bang, ?, sapa aku (pisah dengan koma)")
            trigger_row.addWidget(self.trigger_input)
            trigger_layout.addLayout(trigger_row)

            self.trigger_btn = QPushButton("💾 Simpan Trigger")
            self.trigger_btn.clicked.connect(self.save_trigger)
            trigger_layout.addWidget(self.trigger_btn)

            # Cooldown settings
            trigger_layout.addWidget(QLabel("⏱️ Pengaturan Cooldown:"))
            cooldown_layout = QVBoxLayout()

            # Cooldown antar batch
            batch_cooldown_layout = QHBoxLayout()
            batch_cooldown_layout.addWidget(QLabel("Cooldown Batch (detik):"))
            self.cooldown_spin = QSpinBox()
            self.cooldown_spin.setRange(0, 30)
            self.cooldown_spin.setValue(self.cooldown_duration)
            self.cooldown_spin.valueChanged.connect(self.update_cooldown)
            self.cooldown_spin.setToolTip("Jeda waktu antar pemrosesan batch balasan")
            batch_cooldown_layout.addWidget(self.cooldown_spin)
            cooldown_layout.addLayout(batch_cooldown_layout)

            # Cooldown per penonton
            viewer_cooldown_layout = QHBoxLayout()
            viewer_cooldown_layout.addWidget(QLabel("Cooldown Penonton (menit):"))
            self.viewer_cooldown_spin = QSpinBox()
            self.viewer_cooldown_spin.setRange(1, 30)
            self.viewer_cooldown_spin.setValue(self.cfg.get("viewer_cooldown_minutes", 3))
            self.viewer_cooldown_spin.valueChanged.connect(self.update_viewer_cooldown)
            self.viewer_cooldown_spin.setToolTip("Jeda minimal antar pertanyaan dari penonton yang sama")
            viewer_cooldown_layout.addWidget(self.viewer_cooldown_spin)
            cooldown_layout.addLayout(viewer_cooldown_layout)

            # Max queue dan daily limit
            queue_limit_layout = QHBoxLayout()
            queue_limit_layout.addWidget(QLabel("Max Antrian:"))
            self.max_queue_spin = QSpinBox()
            self.max_queue_spin.setRange(1, 10)
            self.max_queue_spin.setValue(self.max_queue_size)
            self.max_queue_spin.valueChanged.connect(self.update_max_queue)
            self.max_queue_spin.setToolTip("Maksimal komentar dalam antrian batch")
            queue_limit_layout.addWidget(self.max_queue_spin)

            queue_limit_layout.addWidget(QLabel("Limit Harian:"))
            self.daily_limit_spin = QSpinBox()
            self.daily_limit_spin.setRange(1, 10)
            self.daily_limit_spin.setValue(self.cfg.get("viewer_daily_limit", 5))
            self.daily_limit_spin.valueChanged.connect(self.update_daily_limit)
            self.daily_limit_spin.setToolTip("Maksimal interaksi per penonton per hari")
            queue_limit_layout.addWidget(self.daily_limit_spin)
            cooldown_layout.addLayout(queue_limit_layout)

            trigger_layout.addLayout(cooldown_layout)

            cooldown_layout.addWidget(QLabel("Max Antrian:"))
            self.max_queue_spin = QSpinBox()
            self.max_queue_spin.setRange(1, 10)
            self.max_queue_spin.setValue(self.max_queue_size)
            self.max_queue_spin.valueChanged.connect(self.update_max_queue)
            cooldown_layout.addWidget(self.max_queue_spin)

            cooldown_layout.addWidget(QLabel("Limit Harian:"))
            self.daily_limit_spin = QSpinBox()
            self.daily_limit_spin.setRange(1, 10)
            self.daily_limit_spin.setValue(self.daily_message_limit)
            self.daily_limit_spin.valueChanged.connect(self.update_daily_limit)
            cooldown_layout.addWidget(self.daily_limit_spin)

            trigger_layout.addLayout(cooldown_layout)
            content_layout.addWidget(trigger_group)

            # Voice & Controls Group
            voice_group = QGroupBox("🔊 Suara & Kontrol")
            voice_layout = QVBoxLayout(voice_group)

            voice_layout.addWidget(QLabel("Suara CoHost:"))
            voice_row = QHBoxLayout()
            self.voice_cb = QComboBox()
            voice_row.addWidget(self.voice_cb, 3)

            preview_btn = QPushButton("🔈 Preview")
            preview_btn.clicked.connect(self.preview_voice)
            voice_row.addWidget(preview_btn, 1)

            voice_layout.addLayout(voice_row)

            save_voice_btn = QPushButton("💾 Simpan Suara")
            save_voice_btn.clicked.connect(self.save_voice)
            voice_layout.addWidget(save_voice_btn)

            # Status and controls
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

            # Checkboxes
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

            # Log Group - PENTING: Ini adalah bagian yang menampilkan log
            log_group = QGroupBox("📋 Log Aktivitas")
            log_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            log_layout = QVBoxLayout(log_group)

            log_row = QHBoxLayout()

            # Text area untuk log
            self.log_view = QTextEdit()
            self.log_view.setReadOnly(True)
            self.log_view.setMinimumHeight(200)
            self.log_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.log_view.setStyleSheet("""
                QTextEdit { 
                    background-color: #f5f5f5; 
                    padding: 10px; 
                    color: black;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                }
            """)
            log_row.addWidget(self.log_view, 4)

            # Button panel
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
                QPushButton:hover { background-color: #e0e0e0; }
            """

            btn_stats = QPushButton("📊 Filter Stats")
            btn_stats.setStyleSheet(button_style)
            btn_stats.clicked.connect(self.show_filter_stats)
            button_panel.addWidget(btn_stats)

            btn_reset_stats = QPushButton("🔄 Reset Stats")
            btn_reset_stats.setStyleSheet(button_style)
            btn_reset_stats.clicked.connect(self.reset_filter_stats)
            button_panel.addWidget(btn_reset_stats)

            btn_statistics = QPushButton("📊 Cache & Spam\nStatistics")
            btn_statistics.setStyleSheet(button_style)
            btn_statistics.clicked.connect(self.show_statistics)
            button_panel.addWidget(btn_statistics)

            btn_reset_spam = QPushButton("🚫 Reset Spam\nBlocks")
            btn_reset_spam.setStyleSheet(button_style)
            btn_reset_spam.clicked.connect(self.reset_spam_blocks)
            button_panel.addWidget(btn_reset_spam)

            btn_reset_daily = QPushButton("📅 Reset Daily\nInteractions")
            btn_reset_daily.setStyleSheet(button_style)
            btn_reset_daily.clicked.connect(self.reset_daily_interactions)
            button_panel.addWidget(btn_reset_daily)

            # Set equal widths untuk semua button
            max_width = 180
            for btn in [btn_stats, btn_reset_stats, btn_statistics, btn_reset_spam, btn_reset_daily]:
                btn.setMaximumWidth(max_width)
                btn.setMinimumWidth(max_width)

            button_panel.addStretch()
            log_row.addLayout(button_panel, 1)

            log_layout.addLayout(log_row)
            content_layout.addWidget(log_group, 1)  # Berikan stretch factor

            # Set content to scroll area
            scroll_area.setWidget(content_widget)
            main_layout.addWidget(scroll_area)

            # Update platform UI
            self._update_platform_ui(self.platform_cb.currentText())

            # Log initial message
            self.log_user("CoHost Basic siap digunakan!", "✅")
            
            print("[DEBUG] UI initialization completed successfully")
            
        except Exception as e:
            print(f"[ERROR] UI initialization failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback UI sederhana jika terjadi error
            self._create_fallback_ui()

    def _create_fallback_ui(self):
        """Create fallback UI jika init_ui() gagal"""
        try:
            layout = QVBoxLayout(self)
            
            # Header
            header = QLabel("🤖 CoHost Basic (Fallback Mode)")
            header.setStyleSheet("font-size: 16px; font-weight: bold; color: red;")
            layout.addWidget(header)
            
            # Simple log view
            self.log_view = QTextEdit()
            self.log_view.setReadOnly(True)
            self.log_view.setPlainText("UI gagal dimuat, menggunakan mode fallback.\nSilakan restart aplikasi.")
            layout.addWidget(self.log_view)
            
            # Simple controls
            control_layout = QHBoxLayout()
            
            self.btn_start = QPushButton("▶️ Start")
            self.btn_start.clicked.connect(self.start)
            control_layout.addWidget(self.btn_start)
            
            self.btn_stop = QPushButton("⏹️ Stop")  
            self.btn_stop.clicked.connect(self.stop)
            control_layout.addWidget(self.btn_stop)
            
            layout.addLayout(control_layout)
            
            self.status = QLabel("Status: Fallback Mode")
            layout.addWidget(self.status)
            
            print("[DEBUG] Fallback UI created")
            
        except Exception as e:
            print(f"[ERROR] Even fallback UI failed: {e}")

    def _update_platform_ui(self, platform):
        """Update UI berdasarkan platform"""
        if platform == "YouTube":
            self.vid_label.setVisible(True)
            self.vid_input.setVisible(True)
            self.btn_save_vid.setVisible(True)
            self.nick_label.setVisible(False)
            self.nick_input.setVisible(False)
            self.btn_save_nick.setVisible(False)
        else:
            self.vid_label.setVisible(False)
            self.vid_input.setVisible(False)
            self.btn_save_vid.setVisible(False)
            self.nick_label.setVisible(True)
            self.nick_input.setVisible(True)
            self.btn_save_nick.setVisible(True)

    # PERBAIKAN 5: Method save yang lengkap
    def save_custom(self):
        """Simpan prompt tambahan"""
        custom = self.custom_input.toPlainText().strip()
        self.cfg.set("custom_context", custom)
        self.log_user("Prompt tambahan berhasil disimpan", "💾")

    def save_trigger(self):
        """Simpan trigger words dengan validasi"""
        triggers = self.trigger_input.text().strip()
        trigger_list = [t.strip() for t in triggers.split(",") if t.strip()]

        if len(trigger_list) > 3:
            QMessageBox.warning(
                self, "Terlalu Banyak Trigger",
                "Maksimal 3 trigger words!\nContoh: bro, bang, min"
            )
            trigger_list = trigger_list[:3]
            self.trigger_input.setText(", ".join(trigger_list))

        self.cfg.set("trigger_words", trigger_list)
        self.cfg.set("trigger_word", "")
        self.log_user(f"Trigger berhasil disimpan: {', '.join(trigger_list)}", "🎯")

    def save_video_id(self):
        """Simpan Video ID YouTube"""
        raw_video = self.vid_input.text().strip()
        if "youtu" in raw_video:
            from urllib.parse import urlparse, parse_qs
            p = urlparse(raw_video)
            vid = parse_qs(p.query).get("v", [])
            video_id = vid[0] if vid else p.path.rsplit("/", 1)[-1]
        else:
            video_id = raw_video
        
        self.cfg.set("video_id", video_id)
        self.vid_input.setText(video_id)
        self.log_user(f"Video ID disimpan: {video_id}", "📹")

    def save_nickname(self):
        """Simpan TikTok nickname"""
        nickname = self.nick_input.text().strip()
        if nickname and not nickname.startswith("@"):
            nickname = "@" + nickname
        self.cfg.set("tiktok_nickname", nickname)
        self.nick_input.setText(nickname)
        self.log_user(f"TikTok nickname disimpan: {nickname}", "📱")

    def save_voice(self):
        """Simpan pilihan suara"""
        voice = self.voice_cb.currentData()
        self.cfg.set("cohost_voice_model", voice)
        self.log_user("Suara CoHost berhasil disimpan", "🔊")

    def update_cooldown(self, value):
        """Update cooldown duration"""
        self.cooldown_duration = value
        self.cfg.set("cohost_cooldown", value)
        self.log_user(f"Cooldown diatur ke {value} detik", "⏱️")

    def update_max_queue(self, value):
        """Update max queue size"""
        self.max_queue_size = value
        self.cfg.set("cohost_max_queue", value)
        self.log_user(f"Maksimal antrian diatur ke {value}", "📋")

    def update_daily_limit(self, value):
        """Update limit pertanyaan sama per hari."""
        self.daily_message_limit = value
        self.cfg.set("daily_message_limit", value)
        self.log_view.append(f"[INFO] Limit harian diset ke {value}x per pertanyaan sama")

    def update_viewer_cooldown(self, value):
        """Update cooldown per penonton"""
        self.cfg.set("viewer_cooldown_minutes", value)
        self.viewer_cooldown_minutes = value * 60  # Convert ke detik
        self.log_user(f"Cooldown per penonton diatur ke {value} menit", "⏱️")

    def update_daily_limit(self, value):
        """Update limit harian per penonton - PERBAIKAN"""
        self.cfg.set("viewer_daily_limit", value)
        self.viewer_daily_limit = value
        self.log_user(f"Limit harian per penonton diatur ke {value} interaksi", "📊")

    def preview_voice(self):
        """Preview suara yang dipilih"""
        voice = self.voice_cb.currentData()
        code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
        self.log_user("Memutar preview suara...", "🔈")
        try:
            speak("Ini preview suara CoHost!", language_code=code, voice_name=voice)
        except Exception as e:
            self.log_error(f"Preview suara gagal: {e}")

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
        self.log_user(f"Hotkey berhasil disimpan: {hot}", "⌨️")

    def toggle_hotkey(self):
        """Toggle hotkey on/off"""
        on = self.toggle_btn.isChecked()
        self.toggle_btn.setText("🔔 Ngobrol: ON" if on else "🔕 Ngobrol: OFF")
        self.hotkey_enabled = on

    def load_voices(self):
        """Load suara yang tersedia untuk CoHost berdasarkan bahasa"""
        try:
            if not hasattr(self, 'voice_cb'):
                print("[WARNING] voice_cb not initialized yet")
                return
                
            self.voice_cb.clear()
            
            voices_data = json.loads(VOICES_PATH.read_text(encoding="utf-8"))
            lang = self.out_lang.currentText() if hasattr(self, 'out_lang') else "Indonesia"
            
            # Basic mode menggunakan gTTS standard voices
            if lang == "Indonesia":
                voices = voices_data.get("gtts_standard", {}).get("id-ID", [])
            else:  # English
                voices = voices_data.get("gtts_standard", {}).get("en-US", [])
            
            if not voices:
                # Fallback voices jika file tidak ada
                if lang == "Indonesia":
                    self.voice_cb.addItem("Standard Indonesian", "id-ID-Standard-A")
                else:
                    self.voice_cb.addItem("Standard English", "en-US-Standard-A")
                print(f"[WARNING] No voices found, using fallback for {lang}")
                return
            
            for voice in voices:
                model = voice.get("model", "unknown")
                gender = voice.get("gender", "Unknown")
                display = f"{gender} - {model}"
                self.voice_cb.addItem(display, model)
            
            # Restore saved selection
            stored = self.cfg.get("cohost_voice_model", "")
            if stored:
                idx = self.voice_cb.findData(stored)
                if idx >= 0:
                    self.voice_cb.setCurrentIndex(idx)
                    
            print(f"[DEBUG] Loaded {self.voice_cb.count()} voices for {lang}")
                    
        except Exception as e:
            print(f"[ERROR] Load voices failed: {e}")
            # Emergency fallback
            if hasattr(self, 'voice_cb'):
                self.voice_cb.clear()
                self.voice_cb.addItem("Default Voice", "default")

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
            self.log_debug(f"Filtered short message: '{message}'")
            return True

        # 2. Skip emoji-only
        import re
        text_only = re.sub(r'[^\w\s]', '', message)
        if len(text_only.strip()) == 0:
            self.filter_stats["emoji"] += 1  
            self.log_debug(f"Filtered emoji-only message: '{message}'")
            return True

        # 3. Skip kata toxic (selalu aktif)
        toxic_words = ["anjing", "tolol", "bangsat", "kontol", "memek", "goblok", "babi",
                        "kampret", "tai", "bajingan", "pepek", "jancok", "asu"]
        message_lower = message.lower()
        for toxic in toxic_words:
            if toxic in message_lower:
                self.filter_stats["toxic"] += 1  
                self.log_debug(f"Filtered toxic word '{toxic}' in message: '{message}'")
                return True

        # 4. Skip nomor seri spam (3 3 3 3, 7 7 7, dll)
        nomor_pattern = r'^(\d+\s*)+$'
        if re.match(nomor_pattern, message_clean):
            numbers = re.findall(r'\d+', message_clean)
            if len(numbers) > 2 and all(n == numbers[0] for n in numbers):
                self.filter_stats["numeric"] += 1  
                self.log_debug(f"Filtered number spam: '{message}'")
                return True

        # 5. PERBAIKAN UTAMA: Skip kombinasi author + message yang sudah pernah diproses
        current_key = (author.lower().strip(), self._normalize_message(message_lower))
        
        # Cek dalam recent_messages (yang sudah dibalas dalam sesi ini)
        for prev_author, prev_msg in self.recent_messages:
            prev_key = (prev_author.lower().strip(), self._normalize_message(prev_msg.lower()))
            
            if current_key == prev_key:
                self.filter_stats["spam"] += 1
                self.log_debug(f"Filtered duplicate/similar message: '{message}'")
                return True

        # 6. PERBAIKAN TAMBAHAN: Skip jika author yang sama dengan pertanyaan sangat mirip dalam 10 menit terakhir
        author_lower = author.lower().strip()
        similar_threshold = 0.85  # 85% kemiripan
        
        # Hitung berapa kali author ini sudah bertanya hal serupa
        similar_count = 0
        for prev_author, prev_msg in self.recent_messages[-20:]:  # Cek 20 pesan terakhir
            if prev_author.lower().strip() == author_lower:
                similarity = self._calculate_similarity(
                    self._normalize_message(message_lower),
                    self._normalize_message(prev_msg.lower())
                )
                if similarity > similar_threshold:
                    similar_count += 1
                    
        if similar_count > 0:
            self.filter_stats["spam"] += 1
            self.log_view.append(f"[FILTERED] {author} sudah bertanya hal serupa {similar_count}x: '{message[:30]}...'")
            return True

        # 7. PERBAIKAN EKSTRA: Batasi frekuensi per author (maksimal 1 pertanyaan per 2 menit)
        import time
        current_time = time.time()
        
        # Inisialisasi tracker jika belum ada
        if not hasattr(self, 'author_last_time'):
            self.author_last_time = {}
        
        last_time = self.author_last_time.get(author_lower, 0)
        time_diff = current_time - last_time
        
        if time_diff < 120:  # 2 menit = 120 detik
            remaining = int(120 - time_diff)
            self.filter_stats["spam"] += 1
            self.log_view.append(f"[FILTERED] {author} terlalu cepat bertanya lagi (sisa cooldown: {remaining}s)")
            return True
        
        # Update waktu terakhir author bertanya
        self.author_last_time[author_lower] = current_time

        return False

    def _normalize_message(self, message):
        """Normalize pesan untuk perbandingan yang lebih akurat."""
        import re
        
        # Hapus tanda baca dan karakter khusus
        message = re.sub(r'[^\w\s]', '', message)
        
        # Hapus extra spaces dan lowercase
        message = re.sub(r'\s+', ' ', message)
        message = message.strip().lower()
        
        # Normalisasi kata-kata serupa
        replacements = {
            'halooo': 'halo',
            'haloooo': 'halo', 
            'haloo': 'halo',
            'haalo': 'halo',
            'haaaalo': 'halo',
            'banggg': 'bang',
            'bangg': 'bang',
            'abangku': 'bang',
            'abang': 'bang',
            'bro': 'bang',  # Normalisasi bro jadi bang
            'brooo': 'bang',
            'khodam': 'khodam',
            'kodam': 'khodam',
            'kodham': 'khodam'
        }
        
        for old, new in replacements.items():
            message = message.replace(old, new)
        
        return message

    def _calculate_similarity(self, str1, str2):
        """Hitung kemiripan antara dua string (0-1)"""
        if not str1 or not str2:
            return 0.0

        shorter = min(len(str1), len(str2))
        longer = max(len(str1), len(str2))

        if longer == 0:
            return 1.0

        matches = sum(1 for i in range(shorter) if str1[i] == str2[i])

        words1 = set(str1.split())
        words2 = set(str2.split())
        common_words = words1 & words2
        if words1 or words2:
            word_similarity = len(common_words) / max(len(words1), len(words2))
        else:
            word_similarity = 0

        return (matches / longer + word_similarity) / 2
    
    def _is_viewer_daily_limit_reached(self, author, message):
        """Cek apakah penonton sudah bertanya hal yang sama atau serupa dalam 24 jam."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        normalized_message = self._normalize_message(message.lower())
        
        # Bersihkan data hari lama
        self._cleanup_old_daily_data()
        
        # Inisialisasi data penonton jika belum ada
        if author not in self.viewer_daily_interactions:
            self.viewer_daily_interactions[author] = {
                "date": today,
                "messages": [],
                "normalized_messages": [],
                "interaction_count": 0,
                "status": "new",
                "first_seen": today,
                "similar_topics": {}
            }
        
        viewer_data = self.viewer_daily_interactions[author]
        
        # Reset jika hari berbeda
        if viewer_data["date"] != today:
            old_count = viewer_data.get("interaction_count", 0)
            if old_count >= 10:
                new_status = "vip"
            elif old_count >= 3:
                new_status = "regular"
            else:
                new_status = "new"
            
            viewer_data.update({
                "date": today,
                "messages": [],
                "normalized_messages": [],
                "interaction_count": 0,
                "status": new_status,
                "similar_topics": {}
            })
            self.log_debug(f"Daily reset for {author} - Status: {new_status}")
        
        # FILTER 1: Cek pertanyaan exact sama
        exact_count = viewer_data["normalized_messages"].count(normalized_message)
        if exact_count >= 1:
            self.log_user(f"⚠️ {author} sudah bertanya hal yang sama hari ini", "🚫")
            self.log_debug(f"Exact duplicate: {author} - '{message[:30]}...' already asked today")
            self.filter_stats["spam"] += 1
            return True
        
        # FILTER 2: Cek kemiripan dengan pesan sebelumnya
        similarity_threshold = 0.75  # 75% kemiripan
        for prev_normalized in viewer_data["normalized_messages"]:
            similarity = self._calculate_similarity(normalized_message, prev_normalized)
            if similarity > similarity_threshold:
                self.log_user(f"⚠️ {author} sudah bertanya hal serupa ({similarity:.0%})", "🚫")
                self.log_debug(f"Similar duplicate: {author} - similarity {similarity:.0%}: '{message[:30]}...'")
                self.filter_stats["spam"] += 1
                return True
        
        # FILTER 3: Deteksi topik umum dan batasi per topik
        common_topics = {
            "greeting": ["halo", "hai", "hello", "selamat", "salam", "assalamualaikum"],
            "khodam": ["khodam", "cek", "apa khodam", "siapa khodam", "hewan apa"],
            "game": ["game", "main", "push", "rank", "hero", "mobile", "legend", "build"],
            "eating": ["makan", "udah makan", "belum makan", "lapar"],
            "question": ["tanya", "nanya", "mau tanya", "boleh tanya", "bisa tanya"]
        }
        
        import time
        current_time = time.time()
        
        # Cek apakah pesan mengandung topik umum
        for topic, keywords in common_topics.items():
            if any(keyword in normalized_message for keyword in keywords):
                # Cek kapan terakhir kali membahas topik ini
                last_topic_time = viewer_data["similar_topics"].get(topic, 0)
                time_diff = current_time - last_topic_time
                
                # Jika kurang dari 2 jam (7200 detik) untuk topik yang sama
                if time_diff < 7200:  # 2 jam
                    remaining_hours = (7200 - time_diff) / 3600
                    self.log_user(f"⏱️ {author} tunggu {remaining_hours:.1f} jam lagi untuk topik '{topic}'", "🚫")
                    self.log_debug(f"Topic cooldown: {author} - '{topic}' asked {remaining_hours:.1f}h ago")
                    self.filter_stats["spam"] += 1
                    return True
                
                # Update waktu topik terakhir
                viewer_data["similar_topics"][topic] = current_time
                self.log_debug(f"Topic tracking: {author} - '{topic}' timestamp updated")
                break
        
        # FILTER 4: Batasi frekuensi per author dengan cooldown custom
        if not hasattr(self, 'author_last_time'):
            self.author_last_time = {}

        author_lower = author.lower().strip()
        last_time = self.author_last_time.get(author_lower, 0)
        time_diff = current_time - last_time

        # Gunakan cooldown custom dari setting
        cooldown_seconds = getattr(self, 'viewer_cooldown_minutes', 180)  # Default 3 menit jika belum diset
        if time_diff < cooldown_seconds:
            remaining = int(cooldown_seconds - time_diff)
            minutes = remaining // 60
            seconds = remaining % 60
            if minutes > 0:
                time_str = f"{minutes}m {seconds}s"
            else:
                time_str = f"{seconds}s"
            
            self.log_user(f"⏱️ {author} tunggu {time_str} lagi", "🚫")
            self.log_debug(f"User cooldown: {author} - {remaining}s remaining")
            self.filter_stats["spam"] += 1
            return True
        
        # FILTER 5: Batasi maksimal interaksi per penonton per hari (custom)
        daily_limit = getattr(self, 'viewer_daily_limit', 5)
        if viewer_data["interaction_count"] >= daily_limit:
            self.log_user(f"⚠️ {author} sudah mencapai batas {daily_limit} pertanyaan hari ini", "🚫")
            self.log_debug(f"Daily limit: {author} - {viewer_data['interaction_count']}/{daily_limit} interactions today")
            self.filter_stats["spam"] += 1
            return True
        
        # Jika lolos semua filter, tambahkan ke history
        viewer_data["messages"].append(message)
        viewer_data["normalized_messages"].append(normalized_message)
        viewer_data["interaction_count"] += 1
        
        # Update waktu terakhir author bertanya
        self.author_last_time[author_lower] = current_time
        
        # Batasi history untuk menghemat memory (simpan 20 pesan terakhir)
        if len(viewer_data["messages"]) > 20:
            viewer_data["messages"] = viewer_data["messages"][-20:]
            viewer_data["normalized_messages"] = viewer_data["normalized_messages"][-20:]
        
        # Log interaksi yang valid - USER FRIENDLY
        status_emoji = {"new": "🆕", "regular": "👤", "vip": "⭐"}
        status_icon = status_emoji.get(viewer_data['status'], "👤")
        
        daily_limit = getattr(self, 'viewer_daily_limit', 5)
        self.log_user(f"{status_icon} {author} - Pertanyaan ke-{viewer_data['interaction_count']}/{daily_limit} hari ini", "✅")
        self.log_debug(f"Valid interaction: {author} ({viewer_data['status']}) - {viewer_data['interaction_count']}/{daily_limit} today")
        
        return False

    def _cleanup_old_daily_data(self):
        """Bersihkan data lebih dari 7 hari dan topic cooldown lama."""
        from datetime import datetime, timedelta
        import time
        
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        current_time = time.time()
        
        expired_viewers = []
        cleaned_topics = 0
        
        for author, data in self.viewer_daily_interactions.items():
            try:
                data_date = datetime.strptime(data["date"], "%Y-%m-%d")
                if data_date < week_ago:
                    expired_viewers.append(author)
                else:
                    # Cleanup topic cooldown yang sudah lebih dari 24 jam
                    if "similar_topics" in data:
                        expired_topics = []
                        for topic, timestamp in data["similar_topics"].items():
                            if current_time - timestamp > 86400:  # 24 jam
                                expired_topics.append(topic)
                        
                        for topic in expired_topics:
                            del data["similar_topics"][topic]
                            cleaned_topics += 1
                            
            except Exception as e:
                self.log_debug(f"Error parsing date for {author}: {e}")
                expired_viewers.append(author)
        
        # Hapus viewer yang expired
        for author in expired_viewers:
            del self.viewer_daily_interactions[author]
        
        # Log cleanup hanya jika ada yang dibersihkan
        if expired_viewers or cleaned_topics:
            self.log_debug(f"Cleanup: removed {len(expired_viewers)} old viewers, {cleaned_topics} expired topics")

    def _cleanup_old_viewer_data(self, current_time):
        """Bersihkan data penonton yang sudah lebih dari 24 jam."""
        expired_viewers = []
        for author, data in self.viewer_cooldowns.items():
            # Hapus jika sudah lebih dari 24 jam dan tidak sedang diblock
            if (current_time - data.get("timestamp", 0)) > (self.spam_threshold_hours * 3600) and \
               data.get("blocked_until", 0) <= current_time:
                expired_viewers.append(author)
        
        for author in expired_viewers:
            del self.viewer_cooldowns[author]
        
        if expired_viewers:
            self.log_view.append(f"[CLEANUP] Hapus data {len(expired_viewers)} penonton lama")

    def show_filter_stats(self):
        """Tampilkan statistik filter dan interaksi harian."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Statistik filter biasa
        total_filtered = sum(self.filter_stats.values())
        
        # Statistik penonton hari ini
        today_viewers = 0
        total_interactions_today = 0
        status_counts = {"new": 0, "regular": 0, "vip": 0}
        
        for author, data in self.viewer_daily_interactions.items():
            if data.get("date") == today:
                today_viewers += 1
                total_interactions_today += data.get("interaction_count", 0)
                status = data.get("status", "new")
                status_counts[status] += 1

        stats_msg = "\n[FILTER STATISTICS]\n"
        stats_msg += "=" * 40 + "\n"
        stats_msg += f"Kata toxic: {self.filter_stats.get('toxic', 0)}\n"
        stats_msg += f"Pesan pendek: {self.filter_stats.get('short', 0)}\n"
        stats_msg += f"Emoji only: {self.filter_stats.get('emoji', 0)}\n"
        stats_msg += f"Spam/limit harian: {self.filter_stats.get('spam', 0)}\n"
        stats_msg += f"Nomor spam: {self.filter_stats.get('numeric', 0)}\n"
        stats_msg += "=" * 40 + "\n"
        stats_msg += f"Total difilter: {total_filtered}\n\n"
        
        stats_msg += "[DAILY INTERACTIONS]\n"
        stats_msg += "=" * 40 + "\n"
        stats_msg += f"Penonton aktif hari ini: {today_viewers}\n"
        stats_msg += f"Total interaksi hari ini: {total_interactions_today}\n"
        stats_msg += f"Penonton baru: {status_counts['new']}\n"
        stats_msg += f"Penonton regular: {status_counts['regular']}\n"
        stats_msg += f"Penonton VIP: {status_counts['vip']}\n"
        stats_msg += f"Limit per pertanyaan sama: {self.daily_message_limit}x/hari"

        self.log_view.append(stats_msg)

    def show_statistics(self):
        """Show cache dan spam statistics"""
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
            "toxic": 0, "short": 0, "emoji": 0, "spam": 0, "numeric": 0
        }
        self.log_view.append("[INFO] Filter statistics telah direset")

    def reset_spam_blocks(self):
        """Reset semua block spam penonton."""
        import time

        # Hitung berapa yang sedang diblock
        blocked_count = 0
        if hasattr(self, 'viewer_daily_interactions'):
            current_time = time.time()
            for author, data in self.viewer_daily_interactions.items():
                if data.get("blocked_until", 0) > current_time:
                    blocked_count += 1
            # Reset semua data spam
            self.viewer_daily_interactions.clear()

        # Reset old system juga jika ada
        if hasattr(self, 'viewer_cooldowns'):
            blocked_count += sum(1 for data in self.viewer_cooldowns.values() if data.get("blocked_until", 0) > time.time())
            self.viewer_cooldowns.clear()
            self.log_view.append(f"[RESET] {blocked_count} spam block dihapus, semua penonton bisa bertanya lagi")
        self.log_view.append("[RESET] History interaksi harian direset")

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
                prev = True
                self.conversation_active = True
                self.log_view.append("🔴 Mulai merekam...")

                self.stt_thread = STTThread(
                    self.cfg.get("selected_mic_index", 0),
                    self.cfg.get("cohost_input_lang", "ind_Latn"),
                    False
                )
                self.stt_thread.result.connect(self._handle_speech)
                self.stt_thread.start()

            elif not pressed and prev:
                prev = False
                self.conversation_active = False
                self.log_view.append("⏳ Memproses...")
                
                if self.stt_thread:
                    self.stt_thread.running = False

    def _handle_speech(self, txt):
        """Handle speech result from STT"""
        self.conversation_active = False

        if not txt:
            self.log_view.append("[WARN] STT kosong.")
            return

        self.log_user(f"Kamu berkata: {txt}", "🎙️")

        prompt = (
            f"Kamu adalah AI Co-Host {self.cfg.get('cohost_name', 'CoHost')} "
            f"dengan kepribadian {self.person_cb.currentText()}. "
            f"User berkata: \"{txt}\". "
            f"Balas dalam bahasa {self.out_lang.currentText().lower()} tanpa emoji, tanpa tanda baca."
        )
        
        try:
            reply = generate_reply(prompt) or ""
            reply = re.sub(r"[^\w\s\?]", "", reply)
            
            self.ttsAboutToStart.emit()
            
            code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
            voice_model = self.voice_cb.currentData()
            speak(reply, language_code=code, voice_name=voice_model)
            
            self.ttsFinished.emit()
            
            self.log_user(f"Balasan: {reply}", "🤖")
        except Exception as e:
            self.log_view.append(f"[ERROR] {str(e)}")
            self.ttsFinished.emit()

    def start(self):
        """Start auto-reply untuk mode Basic dengan validasi lengkap"""
        if not self._check_credit_before_start():
            return

        # Skip usage tracking untuk test mode
        main_window = self.window()
        if hasattr(main_window, 'license_validator') and main_window.license_validator.testing_mode:
            print("[DEBUG] Test mode active - skipping usage tracking")
        else:
            start_usage_tracking("cohost_basic")
            self.credit_timer.start()

        self.hour_tracker.start_tracking()
        
        logger.info("Starting CoHost Basic mode")
        
        # 1. VALIDATE AND SET MODE
        self.cfg.set("reply_mode", "Trigger")
        self.cfg.set("paket", "basic")

        # Reset batch counter
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
            self.log_user("Trigger word belum diset. Silakan atur trigger terlebih dahulu.", "⚠️")
            
            return

        # 4. VALIDATE PLATFORM CONFIG
        plat = self.platform_cb.currentText()
        self.cfg.set("platform", plat)

        if plat == "YouTube":
            vid = self.cfg.get("video_id", "").strip()
            if not vid:
                self.log_user("Video ID YouTube belum diisi.", "⚠️")
                return
            if len(vid) != 11:
                self.log_view.append(f"[ERROR] Video ID harus 11 karakter (saat ini: {len(vid)})")
                return
        else:  # TikTok
            nick = self.cfg.get("tiktok_nickname", "").strip()
            if not nick:
                self.log_user("TikTok nickname belum diisi.", "⚠️")
                return
            if not nick.startswith("@"):
                nick = "@" + nick
                self.cfg.set("tiktok_nickname", nick)

        # 5. LOG CONFIGURATION
        self.log_user("=== StreamMate Basic Dimulai ===", "🚀")
        self.log_user(f"Platform: {plat}", "📺")
        self.log_user(f"Mode: Hanya Trigger", "🎯")
        self.log_user(f"Trigger: {', '.join(trigger_words)}", "🔔")
        self.log_debug(f"Batch size: 3, Delay: 3s, Cooldown: 10s")

        # TAMBAHAN: Reset spam tracking
        if hasattr(self, 'author_last_time'):
            self.author_last_time.clear()

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
                self.proc = subprocess.Popen(
                    ["python", "-u", str(YT_SCRIPT)],
                    cwd=str(ROOT),
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
                )

                self.monitor = FileMonitorThread(CHAT_BUFFER)
                self.monitor.newComment.connect(self._enqueue)
                self.monitor.start()

                self.log_user("Terhubung ke YouTube Live", "✅")
                self.log_debug(f"YouTube listener PID: {self.proc.pid}")
            else:
                logger.info(f"TikTok listener starting for: {nick}")
                self.tiktok_thread = TikTokListenerThread()
                self.tiktok_thread.newComment.connect(self._enqueue)
                self.tiktok_thread.start()

                self.log_user("Terhubung ke TikTok Live", "✅")

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
            self.log_debug("Developer mode: kuota tidak diberlakukan")
        else:
            tier, used, limit = get_today_usage()
            remaining = limit - used
            self.log_user(f"📊 Kuota hari ini: {used:.1f}/{limit} jam", "📊")

            if remaining <= 0:
                self.log_user("❌ Kuota habis! Silakan tunggu besok.", "⚠️")
                self.stop()
                return

            self._track_usage()
            self.usage_timer.start()

        # Final status
        self.log_user("🤖 Auto-Reply siap! Menunggu komentar dengan trigger...", "✅")
        self.status.setText("✅ Auto-Reply Active")
        self.log_system("Auto-Reply Basic ready!")

    def _clean_buffer(self):
        """Bersihkan buffer chat lebih efisien"""
        try:
            if CHAT_BUFFER.exists():
                lines = CHAT_BUFFER.read_text(encoding="utf-8").splitlines()
                unique_entries = []
                seen = set()

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

                CHAT_BUFFER.write_text("\n".join(reversed(unique_entries)), encoding="utf-8")

                if self.monitor:
                    self.monitor._seen.clear()

                self.log_view.append(f"[INFO] Buffer dibersihkan: {len(lines)} → {len(unique_entries)} baris")
        except Exception as e:
            self.log_view.append(f"[WARN] Gagal bersihkan buffer: {e}")

    def stop(self):
        """Stop auto-reply"""
        stop_usage_tracking()
        self.credit_timer.stop()

        # Stop all timers
        if hasattr(self, "buffer_timer") and self.buffer_timer.isActive():
            self.buffer_timer.stop()
        if hasattr(self, "usage_timer") and self.usage_timer.isActive():
            self.usage_timer.stop()
        if hasattr(self, "cooldown_timer") and self.cooldown_timer.isActive():
            self.cooldown_timer.stop()
        if hasattr(self, "batch_timer") and self.batch_timer.isActive():
            self.batch_timer.stop()

        # Clear flags
        self.is_in_cooldown = False
        self.reply_busy = False
        self.conversation_active = False
        self.batch_counter = 0
        self.processing_batch = False

        # Stop threads
        if self.monitor:
            self.monitor.stop()
            self.monitor.wait(2000)
            self.monitor = None

        if self.tiktok_thread:
            self.tiktok_thread.stop()
            self.tiktok_thread.wait(2000)
            self.tiktok_thread = None

        # Terminate process
        if self.proc and self.proc.poll() is None:
            try:
                if sys.platform == "win32":
                    self.proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    self.proc.terminate()

                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=1)
            except Exception as e:
                self.log_view.append(f"[WARN] Error stopping process: {e}")
            finally:
                self.proc = None

        # Clear state
        self.reply_queue.clear()
        self.recent_messages.clear()

        if CHAT_BUFFER.exists():
            try:
                CHAT_BUFFER.unlink()
            except:
                CHAT_BUFFER.write_text("")

        # Update UI
        self.status.setText("❌ Auto-Reply Stopped")
        self.log_user("Auto-Reply berhasil dihentikan", "⏹️")

    def _has_trigger(self, message):
        """Check if message contains any trigger word"""
        message_lower = message.lower().strip()
        trigger_words = self.cfg.get("trigger_words", [])

        if not trigger_words:
            trigger_word = self.cfg.get("trigger_word", "").lower().strip()
            if trigger_word and trigger_word in message_lower:
                return True
        else:
            for trigger in trigger_words:
                if trigger.lower() in message_lower:
                    return True
        return False

    def _save_interaction(self, author, message, reply):
        """Simpan interaksi ke log dan viewer memory"""
        try:
            COHOST_LOG.parent.mkdir(exist_ok=True)
            with open(str(COHOST_LOG), "a", encoding="utf-8") as f:
                f.write(f"{author}\t{message}\t{reply}\n")
        except Exception as e:
            self.log_view.append(f"[WARN] Gagal save log: {e}")

        if self.viewer_memory:
            self.viewer_memory.add_interaction(author, message, reply)

        self.recent_messages.append((author, message))
        if len(self.recent_messages) > self.message_history_limit:
            self.recent_messages.pop(0)
        self.replyGenerated.emit(author, message, reply)

    def _enqueue(self, author, message):
        """Process comment dengan limit harian per-penonton."""
        self.log_user(f"{author}: {message}", "👤")

        # Cek trigger terlebih dahulu
        if not self._has_trigger(message):
            return

        self.log_user("✅ Trigger terdeteksi! Memproses balasan...", "🔔")

        # Cek limit harian per-penonton
        if self._is_viewer_daily_limit_reached(author, message):
            return

        # Register activity saat ada komentar valid
        register_activity("cohost_basic")

        # PERBAIKAN: Debug ke terminal saja
        self.log_debug(f"Enqueueing comment from {author}: {message}")
        self.log_debug(f"Memproses komentar: {author}")

        # Proses batch
        if self.processing_batch:
            if len(self.reply_queue) < self.max_queue_size:
                self.reply_queue.append((author, message))
                self.log_user(f"📋 Ditambahkan ke antrian ({len(self.reply_queue)} item)", "⏳")
            else:
                self.log_user(f"⚠️ Antrian penuh, dilewati: {author}", "📋")
            return

        # Jika tidak ada batch, langsung proses
        self.reply_queue = [(author, message)]
        self.log_debug(f"Starting new batch with: {author}")
        self._start_batch()

    def _start_batch(self):
        """Start batch processing"""
        if not self.reply_queue:
            self.log_debug("No queue to process")
            return
            
        self.log_debug(f"Starting batch with {len(self.reply_queue)} items")
        self.log_user("🔄 Memproses balasan...", "🤖")
        self.processing_batch = True
        self.batch_counter = 0
        self._process_next_in_batch()

    def _process_next_in_batch(self):
        """Process next message in batch"""
        self.log_debug(f"_process_next_in_batch called, queue: {len(self.reply_queue)}, batch_counter: {self.batch_counter}")
        
        if not self.reply_queue or self.batch_counter >= self.batch_size:
            self.log_debug(f"Ending batch - queue empty: {not self.reply_queue}, batch full: {self.batch_counter >= self.batch_size}")
            self._end_batch()
            return
            
        author, msg = self.reply_queue.pop(0)
        self.batch_counter += 1
        
        self.log_debug(f"Processing message {self.batch_counter}/{self.batch_size}: {author} - {msg}")
        self._create_reply_thread(author, msg)

    def _create_reply_thread(self, author, message):
        """Create reply thread dengan konfigurasi yang tepat"""
        self.log_debug(f"Creating reply thread for: {author}")
        
        lang_code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
        voice = self.voice_cb.currentData()
        
        self.log_debug(f"Lang: {lang_code}, Voice: {voice}")

        rt = ReplyThread(
            author=author,
            message=message,
            personality=self.person_cb.currentText(),
            voice_model=voice,
            language_code=lang_code,
            lang_out=self.out_lang.currentText(),
            viewer_memory=self.viewer_memory
        )

        rt.finished.connect(lambda a, m, r: self._on_reply(a, m, r))
        self.threads.append(rt)
        
        self.log_debug(f"Starting reply thread...")
        rt.start()

    def _on_reply(self, author, message, reply):
        """Handle reply dengan batch management yang lebih baik"""
        self.log_debug(f"_on_reply called: {author} - {reply}")
        
        if not reply:
            self.log_user("⚠️ Gagal membuat balasan", "❌")
            QTimer.singleShot(self.reply_delay, self._process_next_in_batch)
            return

        try:
            self.log_debug(f"Processing reply...")
            
            if hasattr(self.window(), "overlay_tab"):
                self.window().overlay_tab.update_overlay(author, reply)

            self.log_user(f"💬 {reply}", "🤖")
            self._save_interaction(author, message, reply)

            self.log_debug(f"Starting TTS...")
            self.ttsAboutToStart.emit()
            self._do_tts_with_callback(reply, lambda: self._handle_tts_complete())
            
            register_activity("cohost_basic")

        except Exception as e:
            self.log_error(f"Error in _on_reply: {e}", show_user=False)
            import traceback
            traceback.print_exc()
            self._cleanup_tts_state()

    def _do_tts_with_callback(self, text, on_complete):
        """TTS dengan guaranteed callback"""
        code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
        voice_model = self.cfg.get("cohost_voice_model", None)

        safety_timeout = self._calculate_tts_duration(text) + 2.0

        self.tts_safety_timer = QTimer(self)
        self.tts_safety_timer.setSingleShot(True)
        self.tts_safety_timer.timeout.connect(lambda: on_complete())
        self.tts_safety_timer.start(int(safety_timeout * 1000))

        def wrapped_callback():
            try:
                if hasattr(self, 'tts_safety_timer') and self.tts_safety_timer.isActive():
                    self.tts_safety_timer.stop()
                print(f"[DEBUG] TTS completed callback triggered")
                on_complete()
            except Exception as e:
                print(f"[ERROR] Callback error: {e}")
                self._cleanup_tts_state()

        try:
            speak(text, code, voice_model, on_finished=wrapped_callback)
        except Exception as e:
            print(f"[ERROR] TTS error: {e}")

    def _handle_tts_complete(self):
        """Handle TTS complete with proper batch flow"""
        self.ttsFinished.emit()
        
        self.batch_timer.stop()
        self.batch_timer.start(self.reply_delay)

    def _calculate_tts_duration(self, text):
        """Estimasi durasi TTS"""
        char_count = len(text)
        chars_per_second = 12
        return max(2.0, (char_count / chars_per_second) + 1.0)

    def _end_batch(self):
        """End batch processing - tanpa cooldown global, langsung cek queue."""
        self.processing_batch = False
        self.batch_counter = 0
        
        self.log_debug("Batch processing ended")
        
        # Langsung cek apakah ada queue lagi
        if self.reply_queue:
            # Delay singkat untuk stabilitas (sesuai pengaturan UI)
            delay_ms = self.cooldown_duration * 1000 if self.cooldown_duration > 0 else 1000
            self.log_debug(f"Queue tersisa: {len(self.reply_queue)} item, delay {delay_ms}ms")
            self.log_user(f"⏳ Menunggu {self.cooldown_duration}s sebelum memproses antrian berikutnya...", "⏱️")
            QTimer.singleShot(delay_ms, self._start_batch)
        else:
            self.log_user("✅ Siap menerima komentar baru", "🤖")

    def _end_cooldown(self):
        """Fungsi ini tidak dipakai lagi karena tidak ada cooldown global."""
        # Method ini dikosongkan karena sistem cooldown global sudah dihapus
        # Delay antar batch sekarang dihandle di _end_batch()
        self.log_debug("_end_cooldown() called but not used (legacy method)")
        pass

    def _cleanup_tts_state(self):
        """Cleanup state saat error atau timeout"""
        self.ttsFinished.emit()
        self.reply_busy = False

        if hasattr(self, 'tts_safety_timer') and self.tts_safety_timer.isActive():
            self.tts_safety_timer.stop()

        QTimer.singleShot(1000, self._process_next_in_batch)

    def _cleanup_spam_tracking(self):
        """Bersihkan data tracking spam yang sudah lama"""
        if not hasattr(self, 'author_last_time'):
            return
            
        import time
        current_time = time.time()
        
        # Hapus data yang lebih dari 1 jam
        expired_authors = []
        for author, last_time in self.author_last_time.items():
            if current_time - last_time > 3600:  # 1 jam
                expired_authors.append(author)
        
        for author in expired_authors:
            del self.author_last_time[author]
        
        if expired_authors:
            self.log_view.append(f"[CLEANUP] Hapus tracking {len(expired_authors)} author lama")

    def _track_usage(self):
        """Track penggunaan untuk subscription checking"""
        if self.cfg.get("debug_mode", False):
            self.log_view.append("[DEBUG] Developer mode: kuota tidak diberlakukan")
            return
        
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
                remaining = datetime.fromisoformat(exp) - datetime.now()
                menit = remaining.seconds // 60
                self.log_view.append(f"[Demo] Sisa {menit} menit")
                return
        
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
        """Cek kredit sebelum start"""
        # Skip semua checking untuk test mode
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
        """Cek kredit setiap menit saat aktif"""
        if not self.reply_busy:
            return
        
        if not self.hour_tracker.check_credit():
            self.stop()
            
            QMessageBox.warning(
                self,
                "Kredit Habis",
                "Kredit jam Anda telah habis!\n\n"
                "Auto-reply telah dihentikan.\n"
                "Silakan beli kredit untuk melanjutkan."
            )
            
            self.status.setText("❌ Kredit Habis")
            self.log_view.append("[SYSTEM] Auto-reply dihentikan - kredit habis")

    def closeEvent(self, event: QCloseEvent):
        """Handle window close event properly"""
        self.usage_timer.stop()
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
    
    def reset_daily_interactions(self):
        """Reset semua interaksi harian dan topic cooldown."""
        if hasattr(self, 'viewer_daily_interactions'):
            interaction_count = len(self.viewer_daily_interactions)
            self.viewer_daily_interactions.clear()
            self.log_view.append(f"[RESET] {interaction_count} interaksi harian direset")
        
        self.log_view.append("[RESET] Semua penonton bisa bertanya lagi tentang topik apapun")