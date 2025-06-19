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
import multiprocessing

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
    from modules_server.config_manager import ConfigManager
except ImportError:
    from modules_server.config_manager import ConfigManager

# Import modules lainnya
from modules_client.cache_manager import CacheManager
from modules_client.spam_detector import SpamDetector
from modules_server.real_credit_tracker import credit_tracker, track_usage_with_forced_deduction, force_credit_deduction
from modules_client.viewer_memory import ViewerMemory

# Import subscription checker
try:
    from modules_server.subscription_checker import (
        get_today_usage, add_usage, time_until_next_day,
        HourlySubscriptionChecker, start_usage_tracking,
        stop_usage_tracking, register_activity
    )
    SUBSCRIPTION_CHECKER_AVAILABLE = False  # DISABLED - menggunakan VPS license validation
except ImportError:
    SUBSCRIPTION_CHECKER_AVAILABLE = False
    # Fallback functions
    def get_today_usage(*args, **kwargs):
        return "basic", 0, 24
    def add_usage(*args, **kwargs):
        pass
    def time_until_next_day(*args, **kwargs):
        return 24
    def start_usage_tracking(*args, **kwargs):
        pass
    def stop_usage_tracking(feature="general"):
        pass
    def register_activity(*args, **kwargs):
        pass
    HourlySubscriptionChecker = None

# Import API functions dengan fallback
try:
    from modules_client.api import generate_reply  
except ImportError:
    from modules_server.deepseek_ai import generate_reply

# Import TTS dari server
from modules_server.tts_engine import speak

# Import the new EXE-compatible handler
from modules_client.pytchat_exe_fixed import PyTchatEXEFix, PyTchatListenerEXE

# ✅ FIX: Impor fungsi path helper
from utils.path_util import get_app_data_path

# ====================================================================
#  ReplyThread for AI Reply Generation
# ====================================================================
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
        try:
            # Load configuration
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

            # Analyze message for relevant response
            message_lower = self.message.lower()
            
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

            # 🔥 ENHANCED: Get viewer context for natural responses
            viewer_context = ""
            viewer_status = "new"
            
            if self.viewer_memory:
                try:
                    viewer_info = self.viewer_memory.get_viewer_info(self.author)
                    if viewer_info:
                        viewer_status = viewer_info.get("status", "new")
                        viewer_context = self.viewer_memory.get_recent_context(self.author, limit=2)
                except Exception:
                    pass  # Fallback gracefully
            
            # Build AI prompt
            normalized_author = self.author.replace('.', '').replace('_', '').lower()
            display_author = self.author

            # Deteksi platform dari format nama
            is_tiktok = (
                self.author.islower() or
                ('.' not in self.author and '_' not in self.author and len(self.author) <= 15)
            )
            platform_context = "TikTok Live" if is_tiktok else "YouTube Live"

            # 🔥 ENHANCED: Build prompt with viewer context
            prompt = (
                f"Kamu adalah AI Co-Host yang sedang live streaming {platform_context}. "
                f"Informasi tentang streamer dan karaktermu: {extra}. "
                f"Penonton {display_author} (status: {viewer_status}) bertanya: '{self.message}'. "
            )
            
            # Add viewer context if available
            if viewer_context:
                prompt += f"Konteks percakapan sebelumnya: {viewer_context}. "

            # 🔥 ENHANCED: Add context-aware instructions
            if question_type == "greeting":
                if viewer_status == "vip":
                    prompt += f"Sapa {self.author} dengan antusias sebagai viewer setia. Ceritakan update terbaru tentang streaming. "
                elif viewer_status == "regular":  
                    prompt += f"Sapa {self.author} dengan ramah dan familiar. Tanyakan kabar atau aktivitas terbaru. "
                else:
                    prompt += f"Sambut {self.author} dengan hangat sebagai viewer baru. Ceritakan sedikit tentang stream ini. "
            elif question_type == "eating":
                prompt += f"Jawab tentang makan dengan santai. Bisa share pengalaman makanan atau rekomendasi. "
            elif question_type == "gaming_build":
                prompt += f"Berikan saran build/item yang practical. Jelaskan singkat kenapa bagus untuk gameplay. "
            elif question_type == "gaming_play":
                prompt += f"Ceritakan tentang game saat ini - hero, strategy, atau situasi match yang menarik. "
            else:
                if viewer_status in ["vip", "regular"]:
                    prompt += f"Jawab dengan personal touch, mengingat {self.author} adalah penonton aktif. "
                else:
                    prompt += f"Jawab informatif dan welcoming untuk menarik engagement viewer baru. "

            # Add response format instructions
            prompt += (
                f"Awali dengan menyebut nama {self.author} sekali saja di awal kalimat. "
                f"Jawab dalam {lang_label} dengan maksimal 2 kalimat pendek. "
                f"Gaya bicara santai seperti streamer pada umumnya. "
                f"Jangan gunakan emoji, huruf tebal atau tanda baca berlebihan. "
                f"Pastikan jawaban singkat dan relevan dengan pertanyaan. "
            )

            # Generate AI reply
            try:
                reply = generate_reply(prompt)
                
                if not reply:
                    reply = f"Hai {self.author} sorry koneksi lagi bermasalah"
                else:
                    # 🎯 ENHANCED: Clean reply with comprehensive TTS-friendly cleaning
                    reply = clean_text_for_tts(reply.strip())
                    
                    # Ensure starts with author name
                    if not reply.lower().startswith(self.author.lower()):
                        reply = f"{self.author} {reply}"
                
                    # Limit length - increased for better responses
                    if len(reply) > 300:
                        # Find natural break point instead of hard cut
                        last_sentence = reply.rfind('.', 0, 297)
                        last_comma = reply.rfind(',', 0, 297)
                        
                        if last_sentence > 250:  # Good sentence break
                            reply = reply[:last_sentence + 1]
                        elif last_comma > 250:  # Good comma break
                            reply = reply[:last_comma + 1]
                        else:  # Hard cut as fallback
                            reply = reply[:297] + "..."
                        
            except Exception as e:
                reply = f"Hai {self.author} sorry ada error: {str(e)[:50]}..."

            self.finished.emit(self.author, self.message, reply)
            
        except Exception as e:
            error_reply = f"Hai {self.author} maaf ada error teknis"
            self.finished.emit(self.author, self.message, error_reply)

# ====================================================================
#  DEFINITIVE SOLUTION: In-Process Threaded Pytchat Listener
# ====================================================================
class PytchatListenerThread(QThread):
    """
    ENHANCED: Uses new PyTchatEXEFix for better EXE compatibility
    """
    newComment = pyqtSignal(str, str)
    logMessage = pyqtSignal(str, str)
    
    def __init__(self, video_id: str):
        super().__init__()
        self.video_id = video_id
        self._is_running = True
        self.listener = None
        
        # ✅ PERBAIKAN UTAMA: Track pesan untuk menghindari duplikasi
        self.seen_messages = set()
        self.start_time = time.time()
        self.last_message_time = 0
        self.stream_active_check_interval = 30  # Check setiap 30 detik
        
        # 🔥 PERBAIKAN UTAMA: Waktu aktivasi auto-reply untuk filter komentar lama (YouTube)
        self.autoreply_start_time = None
        self.skip_old_comments = True  # Flag untuk skip komentar lama
        self.old_comments_skip_duration = 3.0  # Skip komentar dalam 3 detik pertama (YouTube lebih cepat)
        self.connection_established = False

    def run(self):
        # Check if pytchat is available
        if not PyTchatEXEFix.is_available():
            self.logMessage.emit("ERROR", "Pytchat library is not available. Cannot start listener.")
            return

        self.logMessage.emit("INFO", f"Enhanced threaded listener starting for video ID: {self.video_id}")
        
        # ✅ PERBAIKAN: Validasi apakah video/stream masih aktif
        if not self._validate_stream_active():
            self.logMessage.emit("ERROR", f"Stream tidak aktif atau tidak dapat diakses: {self.video_id}")
            return
        
        try:
            # Create enhanced listener
            self.listener = PyTchatListenerEXE(video_id=self.video_id)
            
            # Setup callbacks
            def on_message(msg):
                current_time = time.time()
                
                # 🔥 PERBAIKAN UTAMA: Skip komentar lama saat pertama kali connect (YouTube)
                if self.skip_old_comments and self.autoreply_start_time:
                    time_since_start = current_time - self.autoreply_start_time
                    if time_since_start < self.old_comments_skip_duration:
                        # Skip komentar dalam durasi awal (kemungkinan komentar lama)
                        self.logMessage.emit("DEBUG", f"⏭️ Skipping old comment from {msg.author} (startup period)")
                        return
                    else:
                        # Setelah durasi skip, matikan flag dan mulai proses normal
                        if self.skip_old_comments:
                            self.skip_old_comments = False
                            self.logMessage.emit("INFO", f"✅ Auto-reply sekarang aktif untuk komentar baru (YouTube)!")
                
                # ✅ PERBAIKAN UTAMA: Filter pesan berdasarkan timestamp dan duplikasi
                if self._is_valid_new_message(msg):
                    # Track message frequency untuk deteksi cache dump
                    current_second = int(current_time)
                    if not hasattr(self, 'recent_messages_per_second'):
                        self.recent_messages_per_second = {}
                    
                    self.recent_messages_per_second[current_second] = self.recent_messages_per_second.get(current_second, 0) + 1
                    
                    # Cleanup old tracking data (keep only last 60 seconds)
                    cutoff_time = current_second - 60
                    self.recent_messages_per_second = {
                        k: v for k, v in self.recent_messages_per_second.items() 
                        if k > cutoff_time
                    }
                    
                    # 🔥 Log komentar yang akan diproses (YouTube)
                    self.logMessage.emit("INFO", f"📨 Processing new comment from {msg.author}: {msg.message}")
                    
                    self.newComment.emit(msg.author, msg.message)
                    self.last_message_time = current_time
            
            def on_connect():
                self.connection_established = True
                # 🔥 Set autoreply start time saat koneksi berhasil (YouTube)
                self.autoreply_start_time = time.time()
                self.logMessage.emit("SUCCESS", f"Successfully connected to YouTube Live: {self.video_id}")
                self.logMessage.emit("INFO", f"🔄 Auto-reply akan aktif untuk komentar baru setelah {self.old_comments_skip_duration} detik")
            
            def on_error(error):
                self.logMessage.emit("ERROR", f"Chat error: {error}")
                # ✅ PERBAIKAN: Jika error stream, stop listener
                if "unavailable" in str(error).lower() or "offline" in str(error).lower():
                    self._is_running = False
            
            self.listener.on_message = on_message
            self.listener.on_connect = on_connect
            self.listener.on_error = on_error
            
            # Start listener
            if self.listener.start():
                self.logMessage.emit("SUCCESS", "Enhanced listener started successfully")
                
                # Keep thread alive while listener is running
                last_stream_check = time.time()
                suspicious_message_count = 0
                total_message_count = 0
                
                while self._is_running and self.listener.is_running():
                    time.sleep(0.5)
                    
                    current_time = time.time()
                    
                    # ✅ PERBAIKAN: Lebih ketat - check stream setiap 15 detik
                    if current_time - last_stream_check > 15:
                        if not self._validate_stream_active():
                            self.logMessage.emit("ERROR", "Stream tidak lagi aktif, menghentikan listener")
                            break
                        last_stream_check = current_time
                        
                    # ✅ PERBAIKAN: Deteksi pola pesan cache - jika terlalu banyak pesan berturut-turut
                    if hasattr(self, 'last_message_time') and self.last_message_time > 0:
                        time_since_last_msg = current_time - self.last_message_time
                        
                        # Jika tidak ada pesan baru dalam 2 menit, cek ulang
                        if time_since_last_msg > 120:
                            if not self._validate_stream_active():
                                self.logMessage.emit("ERROR", "Tidak ada pesan baru dalam 2 menit + stream offline, stopping")
                                break
                        
                        # Hapus kode timeout 5 menit di sini - biarkan streamer menghentikan secara manual
                    
                    # ✅ PERBAIKAN BARU: Deteksi flood messages dari cache
                    if hasattr(self, 'recent_messages_per_second'):
                        msgs_this_second = self.recent_messages_per_second.get(int(current_time), 0)
                        if msgs_this_second > 20:  # Lebih dari 20 pesan per detik = kemungkinan cache dump
                            suspicious_message_count += 1
                            if suspicious_message_count > 5:  # 5 detik berturut-turut flood
                                self.logMessage.emit("ERROR", "Detected cache dump (too many messages), stopping listener")
                                break
                        else:
                            suspicious_message_count = max(0, suspicious_message_count - 1)
            else:
                self.logMessage.emit("ERROR", "Failed to start enhanced listener")
                
        except Exception as e:
            self.logMessage.emit("ERROR", f"Enhanced listener error: {e}")
        
        finally:
            if self.listener:
                self.listener.stop()
            self.logMessage.emit("INFO", "Enhanced pytchat listener thread has stopped.")

    def _validate_stream_active(self):
        """Validasi apakah stream masih aktif dengan multiple methods"""
        try:
            import requests
            import json
            import re
            
            # Method 1: Check YouTube page content
            url = f"https://www.youtube.com/watch?v={self.video_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                self.logMessage.emit("ERROR", f"Cannot access video page: HTTP {response.status_code}")
                return False
                
            content = response.text.lower()
            
            # ✅ PERBAIKAN 1: Check for explicit live indicators
            live_indicators = [
                '"islivebroadcast":true',
                '"islive":true',
                '"live now"',
                'islivecontent":true'
            ]
            
            ended_indicators = [
                '"islivebroadcast":false',
                'live stream has ended',
                'this live stream has ended',
                'premiada terminó',
                '"islive":false',
                'islivecontent":false'
            ]
            
            # Check for ended stream first (more reliable)
            for indicator in ended_indicators:
                if indicator in content:
                    self.logMessage.emit("ERROR", f"Stream has ended - found indicator: {indicator}")
                    return False
            
            # Check for live indicators
            is_live = any(indicator in content for indicator in live_indicators)
            
            # ✅ PERBAIKAN 2: Additional validation using oembed API
            try:
                oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={self.video_id}&format=json"
                oembed_response = requests.get(oembed_url, timeout=10)
                
                if oembed_response.status_code == 200:
                    oembed_data = oembed_response.json()
                    title = oembed_data.get('title', '').lower()
                    
                    # Check if title indicates it's not live
                    if 'ended' in title or 'finished' in title or 'replay' in title:
                        self.logMessage.emit("ERROR", f"Stream not live based on title: {title}")
                        return False
                        
                elif oembed_response.status_code == 404:
                    self.logMessage.emit("ERROR", "Video not found or unavailable")
                    return False
                    
            except Exception as oembed_error:
                self.logMessage.emit("WARNING", f"OEmbed validation failed: {oembed_error}")
            
            # ✅ PERBAIKAN 3: Final decision - must have explicit live indicators
            if not is_live:
                self.logMessage.emit("ERROR", "No live indicators found - stream appears to be offline")
                return False
            
            self.logMessage.emit("INFO", "Stream validation passed - appears to be live")
            return True
            
        except Exception as e:
            self.logMessage.emit("ERROR", f"Error validating stream: {e}")
            # ✅ PERBAIKAN: Jika ada error validasi, anggap stream TIDAK aktif (lebih aman)
            return False
    
    def _is_valid_new_message(self, msg):
        """Check apakah pesan ini valid dan baru (bukan dari cache lama)"""
        try:
            # ✅ PERBAIKAN 1: Skip pesan yang terlalu lama (dari cache)
            msg_time = getattr(msg, 'timestamp', time.time())
            if isinstance(msg_time, (int, float)):
                # Jika pesan lebih dari 5 menit sebelum listener start, skip
                if msg_time < self.start_time - 300:
                    return False
            
            # ✅ PERBAIKAN 2: Skip duplikasi berdasarkan author + message + aprox time
            message_key = (msg.author, msg.message, int(time.time() / 60))  # Per-minute grouping
            if message_key in self.seen_messages:
                return False
            
            # ✅ PERBAIKAN 3: Limit seen_messages size untuk memory efficiency
            if len(self.seen_messages) > 1000:
                # Keep only recent messages (clear old ones)
                current_minute = int(time.time() / 60)
                self.seen_messages = {key for key in self.seen_messages if key[2] >= current_minute - 10}
            
            self.seen_messages.add(message_key)
            
            # ✅ PERBAIKAN 4: Skip pesan yang terlalu pendek atau mencurigakan (spam dari cache)
            if len(msg.message.strip()) < 2:
                return False
                
            return True
            
        except Exception as e:
            # Jika ada error dalam validasi, tetap proses pesan
            return True

    def stop(self):
        self.logMessage.emit("INFO", "Stopping enhanced Pytchat listener thread...")
        self._is_running = False
        if self.listener:
            self.listener.stop()
    
    def reset_for_new_session(self):
        """Reset listener untuk session baru - hanya proses komentar baru"""
        self.autoreply_start_time = time.time()
        self.skip_old_comments = True
        self.connection_established = False
        self.seen_messages.clear()
        if hasattr(self, 'recent_messages_per_second'):
            self.recent_messages_per_second.clear()
        self.logMessage.emit("INFO", "🔄 YouTube listener reset - akan skip komentar lama")

# ====================================================================

# ✅ FIX: Gunakan fungsi helper untuk path log yang aman untuk EXE
COHOST_LOG = get_app_data_path("cohost_log.txt")
VOICES_PATH = ROOT / "config" / "voices.json"
CHAT_BUFFER = ROOT / "temp" / "chat_buffer.txt"

# Pastikan direktori temp ada
Path(ROOT / "temp").mkdir(exist_ok=True)


# ====================================================================
#  STTThread for Speech-to-Text Processing
# ====================================================================

# Import SUPER DIRECT Google STT (zero overhead)
try:
    from modules_client.super_direct_stt import SuperDirectSTTThread
    from google.cloud import speech
    SUPER_DIRECT_STT_AVAILABLE = True
    print("[INFO] ⚡ Super Direct Google STT available - ZERO overhead mode!")
except ImportError:
    SUPER_DIRECT_STT_AVAILABLE = False
    print("[INFO] Super Direct Google STT not available, using speech_recognition")

class GoogleSTTThread(QThread):
    """Thread for Google Speech-to-Text processing - Enhanced for better language support"""
    result = pyqtSignal(str)
    
    def __init__(self, mic_index=0, language="id-ID"):
        super().__init__()
        self.mic_index = mic_index
        self.language = language
        self._is_running = True
        self.recording = False
        
        # Use SUPER DIRECT Google STT for ZERO overhead!
        self.use_super_direct = SUPER_DIRECT_STT_AVAILABLE
        
        if self.use_super_direct:
            print(f"[STT] ⚡ Using SUPER DIRECT Google STT (ZERO overhead) for {language}")
            self.super_direct_thread = SuperDirectSTTThread(mic_index, language)
            # 🎯 PASS PARENT REFERENCE: So Super Direct can emit to parent directly
            self.super_direct_thread.parent_thread = self
            print(f"[STT] ⚡ Super Direct connected to parent GoogleSTTThread")
        else:
            print(f"[STT] 🐌 Using speech_recognition library (with overhead) for {language}")
            # Balanced language mapping with proven thresholds
            self.language_models = {
                "id-ID": {
                    "language": "id-ID",
                    "show_all": False,
                    "noise_threshold": 0.015  # Balanced threshold
                },
                "en-US": {
                    "language": "en-US", 
                    "show_all": False,
                    "noise_threshold": 0.012  # Balanced for English
                }
            }
    
    def _forward_super_direct_result(self, text):
        """Forward Super Direct STT result to main result signal - ULTRA SIMPLE"""
        print(f"[STT] ⚡ Super Direct result: '{text}' - forwarding...")
        self.result.emit(text if text else "")
    
    def _handle_stt_timeout(self):
        """Handle STT timeout"""
        print(f"[STT] Direct Google STT timeout, forcing fallback...")
        self.use_direct_stt = False
        self.result.emit("")
    
    def run(self):
        """Run Google speech-to-text in background thread - Enhanced version"""
        
        # Use SUPER DIRECT Google STT (ZERO overhead!)
        if self.use_super_direct:
            print(f"[STT] ⚡ Starting SUPER DIRECT Google STT (ZERO overhead)...")
            
            if hasattr(self, 'super_direct_thread'):
                self.super_direct_thread.mic_index = self.mic_index
                self.super_direct_thread.language = self.language
                self.super_direct_thread.recording = self.recording
                self.super_direct_thread._is_running = self._is_running
                
                # Start the super direct thread and wait for completion
                if not self.super_direct_thread.isRunning():
                    self.super_direct_thread.start()
                    
                # Wait for super direct thread to finish processing
                while self._is_running and (self.super_direct_thread.isRunning() or self.recording):
                    self.msleep(50)  # Check every 50ms
                    
                print(f"[STT] ⚡ Super Direct thread completed")
            return
        
        # Fallback to speech_recognition library
        print(f"[STT] 🐌 Starting speech_recognition library (slower method)...")
        try:
            import sounddevice as sd
            import numpy as np
            import speech_recognition as sr
            import io
            import wave
            
            # Initialize recognizer with proven working settings
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 1000  # Moderate threshold
            recognizer.dynamic_energy_threshold = True  # Auto-adjustment for better adaptation
            recognizer.pause_threshold = 0.8  # Standard pause detection
            recognizer.non_speaking_duration = 0.5  # Standard non-speaking duration
            
            # Get language config
            lang_config = self.language_models.get(self.language, self.language_models["id-ID"])
            
            # Standard recording settings that work reliably
            sample_rate = 16000  # Standard rate for speech recognition
            chunk_duration = 0.1  # Standard 100ms chunks
            chunk_size = int(sample_rate * chunk_duration)
            
            # Collect audio chunks
            audio_chunks = []
            
            while self._is_running and self.recording:
                try:
                    # Record small chunk
                    chunk = sd.rec(chunk_size, 
                                 samplerate=sample_rate, 
                                 channels=1, 
                                 device=self.mic_index,
                                 dtype=np.int16)
                    sd.wait()
                    
                    if self._is_running and self.recording:
                        audio_chunks.append(chunk.flatten())
                    
                except Exception as e:
                    print(f"[ERROR] Recording chunk failed: {e}")
                    break
            
            if not audio_chunks:
                self.result.emit("")
                return
                
            # Combine all chunks
            audio_data = np.concatenate(audio_chunks)
            
            # Enhanced audio quality check and processing
            audio_rms = np.sqrt(np.mean(audio_data.astype(float) ** 2))
            volume_threshold = lang_config["noise_threshold"] * 32768
            
            print(f"[STT] Audio RMS: {audio_rms:.3f}, threshold: {volume_threshold:.1f}")
            
            if audio_rms < volume_threshold:
                print(f"[STT] Audio too quiet - increase microphone volume or speak louder")
                self.result.emit("")
                return
            
            # Simple but effective audio preprocessing
            audio_data = audio_data.astype(np.float32)
            
            # Remove DC offset
            audio_data = audio_data - np.mean(audio_data)
            
            # Simple normalization
            max_val = np.max(np.abs(audio_data))
            if max_val > 0:
                audio_data = audio_data / max_val * 0.95  # Light normalization
            
            # Convert back to int16
            audio_data = (audio_data * 32767).astype(np.int16)
            
            # Convert to WAV format for speech_recognition
            audio_bytes = io.BytesIO()
            with wave.open(audio_bytes, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data.tobytes())
            
            audio_bytes.seek(0)
            
            # Use Google Speech Recognition with standard settings
            try:
                with sr.AudioFile(audio_bytes) as source:
                    # Adjust for ambient noise for better accuracy
                    recognizer.adjust_for_ambient_noise(source, duration=0.2)
                    audio = recognizer.record(source)
                
                # Recognize speech using Google with enhanced settings
                print(f"[STT] Processing with language: {lang_config['language']}")
                print(f"[STT] Audio duration: {len(audio_data) / sample_rate:.2f}s")
                
                # Use simple, reliable recognition mode
                text = recognizer.recognize_google(
                    audio, 
                    language=lang_config['language'],
                    show_all=False  # Simple mode for better compatibility
                )
                
                if text and text.strip():
                    recognized_text = text.strip()
                    
                    # 🛡️ SAFETY: Only limit extremely long STT output (increased limit)
                    MAX_STT_OUTPUT = 1000  # Increased limit for longer speech
                    if len(recognized_text) > MAX_STT_OUTPUT:
                        print(f"[STT] Output extremely long ({len(recognized_text)} chars), truncating...")
                        # Find good break point
                        truncated = recognized_text[:MAX_STT_OUTPUT-20]
                        last_sentence = truncated.rfind('.')
                        last_space = truncated.rfind(' ')
                        
                        if last_sentence > MAX_STT_OUTPUT - 200:
                            recognized_text = recognized_text[:last_sentence + 1]
                        elif last_space > MAX_STT_OUTPUT - 100:
                            recognized_text = recognized_text[:last_space]
                        else:
                            recognized_text = truncated + "..."
                        
                        print(f"[STT] Truncated to: {len(recognized_text)} chars")
                    else:
                        print(f"[STT] Length OK: {len(recognized_text)} chars")
                    
                    print(f"[STT] Recognized ({self.language}): {recognized_text}")
                    self.result.emit(recognized_text)
                else:
                    print(f"[STT] Empty result for language: {self.language}")
                    self.result.emit("")
                    
            except sr.UnknownValueError:
                print(f"[STT] No speech detected for language: {self.language}")
                self.result.emit("")  # No speech detected
            except sr.RequestError as e:
                print(f"[STT] Google API error: {e}")
                self.result.emit(f"Google STT Error: {str(e)}")
                     
        except Exception as e:
            print(f"[STT] General error: {e}")
            self.result.emit(f"STT Error: {str(e)}")
    
    def start_recording(self):
        """Start recording audio"""
        self.recording = True
        if self.use_super_direct and hasattr(self, 'super_direct_thread'):
            self.super_direct_thread.recording = True
        if not self.isRunning():
            self.start()
    
    def stop_recording(self):
        """Stop recording audio"""
        self.recording = False
        if self.use_super_direct and hasattr(self, 'super_direct_thread'):
            self.super_direct_thread.recording = False
    
    def stop(self):
        """Stop auto-reply dan listener TANPA mengubah status demo."""
        if self.listener_thread and self.listener_thread.is_alive():
            self.stop_event.set()
            # Beri sedikit waktu untuk thread berhenti dengan sendirinya
            self.listener_thread.join(timeout=2.0)
            if self.listener_thread.is_alive():
                print("[CoHost] Warning: Listener thread did not terminate gracefully.")
        
        self.is_running = False
        self.stop_event.set()
        
        # Hapus referensi thread lama
        self.listener_thread = None
        
        # Update UI
        self.start_button.setText("▶️ Start Auto-Reply")
        self.start_button.setStyleSheet("background-color: #4CAF50;")
        self.status_label.setText("Status: Idle")
        self.status_label.setStyleSheet("color: #FFA726;")
        
        self.log_message("⏹️ Auto-reply stopped.")
        print("[CoHost] Auto-reply process stopped manually by user.")

# Keep old STTThread for backward compatibility but mark as deprecated
class STTThread(GoogleSTTThread):
    """DEPRECATED: Legacy STT thread - use GoogleSTTThread instead"""
    def __init__(self, mic_index=0, language="ind_Latn", use_google=False):
        # Convert old language format to new
        lang_map = {
            "ind_Latn": "id-ID",
            "eng_Latn": "en-US"
        }
        new_lang = lang_map.get(language, "id-ID")
        super().__init__(mic_index, new_lang)


class TikTokListenerThread(QThread):
    """
    TikTok Live listener thread using TikTokLive library
    """
    newComment = pyqtSignal(str, str)
    logMessage = pyqtSignal(str, str)
    
    def __init__(self, username: str):
        super().__init__()
        self.username = username.replace("@", "").strip()
        self._is_running = True
        self.client = None
        self.seen_messages = set()
        self.start_time = time.time()
        
        # 🔥 PERBAIKAN UTAMA: Waktu aktivasi auto-reply untuk filter komentar lama
        self.autoreply_start_time = None
        self.skip_old_comments = True  # Flag untuk skip komentar lama
        self.old_comments_skip_duration = 5.0  # Skip komentar dalam 5 detik pertama
        self.connection_established = False
        
    def run(self):
        """Run TikTok listener"""
        try:
            from TikTokLive import TikTokLiveClient
            from TikTokLive.events import ConnectEvent, CommentEvent, DisconnectEvent
            
            self.logMessage.emit("INFO", f"Starting TikTok listener for @{self.username}")
            
            # Create TikTok client
            self.client = TikTokLiveClient(unique_id=self.username)
            
            @self.client.on(ConnectEvent)
            async def on_connect(event):
                self.connection_established = True
                # 🔥 Set autoreply start time saat koneksi berhasil
                self.autoreply_start_time = time.time()
                self.logMessage.emit("SUCCESS", f"Connected to TikTok Live: @{self.username}")
                self.logMessage.emit("INFO", f"🔄 Auto-reply akan aktif untuk komentar baru setelah {self.old_comments_skip_duration} detik")
            
            @self.client.on(CommentEvent)
            async def on_comment(event):
                if not self._is_running:
                    return
                
                current_time = time.time()
                
                # 🔥 PERBAIKAN UTAMA: Skip komentar lama saat pertama kali connect
                if self.skip_old_comments and self.autoreply_start_time:
                    time_since_start = current_time - self.autoreply_start_time
                    if time_since_start < self.old_comments_skip_duration:
                        # Skip komentar dalam durasi awal (kemungkinan komentar lama)
                        self.logMessage.emit("DEBUG", f"⏭️ Skipping old comment from {event.user.nickname if hasattr(event.user, 'nickname') else event.user.unique_id} (startup period)")
                        return
                    else:
                        # Setelah durasi skip, matikan flag dan mulai proses normal
                        if self.skip_old_comments:
                            self.skip_old_comments = False
                            self.logMessage.emit("INFO", f"✅ Auto-reply sekarang aktif untuk komentar baru!")
                    
                author = event.user.nickname if hasattr(event.user, 'nickname') else str(event.user.unique_id)
                message = event.comment
                
                # Avoid duplicates dengan timestamp yang lebih akurat
                comment_signature = f"{author}:{message}:{int(current_time * 10)}"  # Lebih presisi
                if comment_signature in self.seen_messages:
                    self.logMessage.emit("DEBUG", f"⏭️ Skipping duplicate comment from {author}")
                    return
                    
                self.seen_messages.add(comment_signature)
                
                # Cleanup old messages (keep only last 1000)
                if len(self.seen_messages) > 1000:
                    oldest_messages = list(self.seen_messages)[:500]
                    for old_msg in oldest_messages:
                        self.seen_messages.discard(old_msg)
                
                # 🔥 Log komentar yang akan diproses
                self.logMessage.emit("INFO", f"📨 Processing new comment from {author}: {message}")
                
                # Emit new comment
                self.newComment.emit(author, message)
            
            @self.client.on(DisconnectEvent)
            async def on_disconnect(event):
                self.logMessage.emit("INFO", "Disconnected from TikTok Live")
                self._is_running = False
            
            # Start the client
            self.client.run()
            
        except ImportError as e:
            self.logMessage.emit("ERROR", "TikTokLive library not found. Install with: pip install TikTokLive")
        except Exception as e:
            self.logMessage.emit("ERROR", f"TikTok listener error: {str(e)}")
            import traceback
            self.logMessage.emit("ERROR", f"Traceback: {traceback.format_exc()}")
    
    def stop(self):
        """Stop TikTok listener"""
        self._is_running = False
        if self.client:
            try:
                # For TikTok client, we don't need to explicitly disconnect
                # The client will automatically disconnect when the thread stops
                # Setting _is_running = False will stop the event handlers
                self.client = None
            except Exception as e:
                print(f"Error stopping TikTok client: {e}")
    
    def reset_for_new_session(self):
        """Reset listener untuk session baru - hanya proses komentar baru"""
        self.autoreply_start_time = time.time()
        self.skip_old_comments = True
        self.connection_established = False
        self.seen_messages.clear()
        self.logMessage.emit("INFO", "🔄 TikTok listener reset - akan skip komentar lama")


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
        
        # Initialize auto cache manager
        try:
            from modules_client.auto_cache_manager import get_cache_manager
            self.auto_cache_manager = get_cache_manager()
            self.log_debug("Auto cache manager initialized")
        except Exception as e:
            self.log_debug(f"Failed to initialize auto cache manager: {e}")
            self.auto_cache_manager = None
        
        # Process management
        self.pytchat_listener_thread = None # DEFINITIVE: Replaces self.proc
        self.tiktok_thread = None
        self.threads = []
        
        # State management
        self.reply_queue = []
        self.reply_busy = False
        self.processing_batch = False
        self.batch_counter = 0
        self.tts_active = False
        self.recent_messages = []
        
        # Enhanced listener threads
        self.pytchat_listener_thread = None
        self.tiktok_listener_thread = None
        
        # Streamer communication
        self.stt_thread = None
        self.conversation_active = False
        self.hotkey_enabled = True
        self.tiktok_thread = None  # Legacy compatibility
        
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
        
        # 🔧 Topic cooldown settings
        self.topic_cooldown_minutes = self.cfg.get("topic_cooldown_minutes", 10) * 60  # Convert to seconds
        self.topic_blocking_enabled = self.cfg.get("enable_topic_blocking", True)

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
        
        # Process management - Updated for isolated process
        self.yt_listener_process = None
        self.message_queue = None
        self.log_queue = None
        self.queue_monitor_thread = None
        self.log_monitor_thread = None
        
        # Setup UI SETELAH semua komponen diinisialisasi
        self.init_ui()
        self._load_hotkey()
        self.load_voices()
        
        # Start hotkey listener for streamer communication
        self.hotkey_thread = threading.Thread(target=self._hotkey_listener, daemon=True)
        self.hotkey_thread.start()
        
        self.log_user("🎙️ Streamer communication ready! Hold hotkey to talk with AI CoHost.", "✅")

    def log_user(self, message, icon="ℹ️"):
        """Log pesan untuk user dengan format yang konsisten - PERBAIKAN UI DISPLAY"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {icon} {message}"
        
        # ✅ PERBAIKAN UTAMA: Tampilkan di UI log_view 
        if hasattr(self, 'log_view'):
            self.log_view.append(formatted_message)
            # Auto-scroll ke bawah jika ada log baru
            self.log_view.ensureCursorVisible()
        
        # Juga print ke terminal untuk debugging
        print(f"[{timestamp}] [CoHost] {message}")

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
            self.log_user(f"❌ Error: {message}", "❌")

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
            platform_group = QGroupBox("Platform & Source")
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
            self.btn_save_vid = QPushButton("💾 Save Video ID")
            self.btn_save_vid.clicked.connect(self.save_video_id)
            platform_layout.addWidget(self.btn_save_vid)

            # TikTok fields
            self.nick_label = QLabel("TikTok Nickname:")
            platform_layout.addWidget(self.nick_label)
            self.nick_input = QLineEdit(self.cfg.get("tiktok_nickname", ""))
            platform_layout.addWidget(self.nick_input)
            self.btn_save_nick = QPushButton("💾 Save Nickname")
            self.btn_save_nick.clicked.connect(self.save_nickname)
            platform_layout.addWidget(self.btn_save_nick)

            content_layout.addWidget(platform_group)

            # AI Settings Group
            ai_group = QGroupBox("🧠 AI Settings")
            ai_layout = QVBoxLayout(ai_group)

            # Language output
            ai_layout.addWidget(QLabel("Output Language:"))
            self.out_lang = QComboBox()
            self.out_lang.addItems(["Indonesia", "English"])
            self.out_lang.setCurrentText(self.cfg.get("reply_language", "Indonesia"))
            self.out_lang.currentTextChanged.connect(self.load_voices)
            ai_layout.addWidget(self.out_lang)

            # Personality
            ai_layout.addWidget(QLabel("AI Personality:"))
            self.person_cb = QComboBox()
            self.person_cb.addItems(["Cheerful"])
            ai_layout.addWidget(self.person_cb)

            # 🔥 ENHANCED: Prompt Templates System
            ai_layout.addWidget(QLabel("🎭 AI Character & Prompt:"))
            
            # Template selector
            template_row = QHBoxLayout()
            template_row.addWidget(QLabel("📋 Quick Templates:"))
            self.template_combo = QComboBox()
            self.template_combo.addItems([
                "📝 Custom Prompt",
                "🎮 Gaming - MOBA Expert", 
                "🎮 Gaming - FPS Pro",
                "💰 Sales - E-Commerce", 
                "💰 Sales - Digital Products"
            ])
            self.template_combo.currentTextChanged.connect(self.load_template)
            template_row.addWidget(self.template_combo, 2)
            
            btn_preview_template = QPushButton("👁️ Preview")
            btn_preview_template.clicked.connect(self.preview_template)
            template_row.addWidget(btn_preview_template, 1)
            
            ai_layout.addLayout(template_row)

            # Custom prompt text area
            ai_layout.addWidget(QLabel("✏️ Edit Prompt (customize as needed):"))
            self.custom_input = QTextEdit(self.cfg.get("custom_context", ""))
            self.custom_input.setPlaceholderText("Choose a template above or write your custom prompt...")
            self.custom_input.setMinimumHeight(100)
            self.custom_input.setMaximumHeight(150)
            ai_layout.addWidget(self.custom_input)

            # Action buttons
            button_row = QHBoxLayout()
            self.custom_btn = QPushButton("💾 Save Prompt")
            self.custom_btn.clicked.connect(self.save_custom)
            button_row.addWidget(self.custom_btn)
            
            btn_clear = QPushButton("🗑️ Clear")
            btn_clear.clicked.connect(lambda: self.custom_input.clear())
            button_row.addWidget(btn_clear)
            
            btn_reset_template = QPushButton("🔄 Reset Template")
            btn_reset_template.clicked.connect(lambda: self.load_template(self.template_combo.currentText()))
            button_row.addWidget(btn_reset_template)
            
            ai_layout.addLayout(button_row)

            content_layout.addWidget(ai_group)

            # Trigger Group
            trigger_group = QGroupBox("🎯 Trigger & Cooldown Settings")
            trigger_layout = QVBoxLayout(trigger_group)

            # Trigger input
            trigger_row = QHBoxLayout()
            trigger_row.addWidget(QLabel("Viewer Triggers:"))
            self.trigger_input = QLineEdit()
            existing_triggers = self.cfg.get("trigger_words", [])
            if isinstance(existing_triggers, list):
                self.trigger_input.setText(", ".join(existing_triggers))
            else:
                self.trigger_input.setText(self.cfg.get("trigger_word", ""))
            self.trigger_input.setPlaceholderText("example: bro, hey, ?, greet me (separate with comma)")
            trigger_row.addWidget(self.trigger_input)
            trigger_layout.addLayout(trigger_row)

            self.trigger_btn = QPushButton("💾 Save Trigger")
            self.trigger_btn.clicked.connect(self.save_trigger)
            trigger_layout.addWidget(self.trigger_btn)

            # Cooldown settings
            trigger_layout.addWidget(QLabel("⏱️ Cooldown Settings:"))
            cooldown_layout = QVBoxLayout()

            # Cooldown antar batch
            batch_cooldown_layout = QHBoxLayout()
            batch_cooldown_layout.addWidget(QLabel("Batch Cooldown (seconds):"))
            self.cooldown_spin = QSpinBox()
            self.cooldown_spin.setRange(0, 30)
            self.cooldown_spin.setValue(self.cooldown_duration)
            self.cooldown_spin.valueChanged.connect(self.update_cooldown)
            self.cooldown_spin.setToolTip("Delay between batch reply processing")
            batch_cooldown_layout.addWidget(self.cooldown_spin)
            cooldown_layout.addLayout(batch_cooldown_layout)

            # Cooldown per penonton
            viewer_cooldown_layout = QHBoxLayout()
            viewer_cooldown_layout.addWidget(QLabel("Viewer Cooldown (minutes):"))
            self.viewer_cooldown_spin = QSpinBox()
            self.viewer_cooldown_spin.setRange(1, 30)
            self.viewer_cooldown_spin.setValue(self.cfg.get("viewer_cooldown_minutes", 3))
            self.viewer_cooldown_spin.valueChanged.connect(self.update_viewer_cooldown)
            self.viewer_cooldown_spin.setToolTip("Minimum delay between questions from the same viewer")
            viewer_cooldown_layout.addWidget(self.viewer_cooldown_spin)
            cooldown_layout.addLayout(viewer_cooldown_layout)

            # Max queue dan daily limit
            queue_limit_layout = QHBoxLayout()
            queue_limit_layout.addWidget(QLabel("Max Queue:"))
            self.max_queue_spin = QSpinBox()
            self.max_queue_spin.setRange(1, 10)
            self.max_queue_spin.setValue(self.max_queue_size)
            self.max_queue_spin.valueChanged.connect(self.update_max_queue)
            self.max_queue_spin.setToolTip("Maximum comments in batch queue")
            queue_limit_layout.addWidget(self.max_queue_spin)

            queue_limit_layout.addWidget(QLabel("Daily Limit:"))
            self.daily_limit_spin = QSpinBox()
            self.daily_limit_spin.setRange(1, 10)
            self.daily_limit_spin.setValue(self.cfg.get("viewer_daily_limit", 5))
            self.daily_limit_spin.valueChanged.connect(self.update_daily_limit)
            self.daily_limit_spin.setToolTip("Maximum interactions per viewer per day")
            queue_limit_layout.addWidget(self.daily_limit_spin)
            cooldown_layout.addLayout(queue_limit_layout)

            # 🔧 TOPIC COOLDOWN CONTROLS
            topic_cooldown_layout = QHBoxLayout()
            topic_cooldown_layout.addWidget(QLabel("Topic Cooldown (minutes):"))
            self.topic_cooldown_spin = QSpinBox()
            self.topic_cooldown_spin.setRange(0, 60)
            self.topic_cooldown_spin.setValue(self.cfg.get("topic_cooldown_minutes", 10))
            self.topic_cooldown_spin.valueChanged.connect(self.update_topic_cooldown)
            self.topic_cooldown_spin.setToolTip("Minutes to wait before same topic can be discussed again (0 = disabled)")
            topic_cooldown_layout.addWidget(self.topic_cooldown_spin)
            
            # Toggle topic blocking
            self.topic_blocking_checkbox = QCheckBox("Enable Topic Blocking")
            self.topic_blocking_checkbox.setChecked(self.cfg.get("enable_topic_blocking", True))
            self.topic_blocking_checkbox.stateChanged.connect(self.toggle_topic_blocking)
            self.topic_blocking_checkbox.setToolTip("Block repeated topics for better conversation variety")
            topic_cooldown_layout.addWidget(self.topic_blocking_checkbox)
            
            cooldown_layout.addLayout(topic_cooldown_layout)

            trigger_layout.addLayout(cooldown_layout)
            content_layout.addWidget(trigger_group)

            # Voice & Controls Group
            voice_group = QGroupBox("🔊 Voice & Controls")
            voice_layout = QVBoxLayout(voice_group)

            voice_layout.addWidget(QLabel("CoHost Voice:"))
            voice_row = QHBoxLayout()
            self.voice_cb = QComboBox()
            voice_row.addWidget(self.voice_cb, 3)

            preview_btn = QPushButton("🔈 Preview")
            preview_btn.clicked.connect(self.preview_voice)
            voice_row.addWidget(preview_btn, 1)

            voice_layout.addLayout(voice_row)

            save_voice_btn = QPushButton("💾 Save Voice")
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

            # Streamer Communication Group - NEW FEATURE
            streamer_group = QGroupBox("🎙️ Streamer Communication (Talk to AI CoHost)")
            streamer_layout = QVBoxLayout(streamer_group)

            # Microphone Selection
            streamer_layout.addWidget(QLabel("🎤 Microphone:"))
            mic_row = QHBoxLayout()
            
            self.mic_combo = QComboBox()
            self._load_microphones()
            mic_row.addWidget(self.mic_combo, 3)
            
            btn_refresh_mic = QPushButton("🔄 Refresh")
            btn_refresh_mic.clicked.connect(self._load_microphones)
            mic_row.addWidget(btn_refresh_mic, 1)
            
            btn_test_mic = QPushButton("🎵 Test Mic")
            btn_test_mic.clicked.connect(self._test_microphone)
            mic_row.addWidget(btn_test_mic, 1)
            
            streamer_layout.addLayout(mic_row)

            # Save microphone setting
            btn_save_mic = QPushButton("💾 Save Microphone")
            btn_save_mic.clicked.connect(self._save_microphone)
            streamer_layout.addWidget(btn_save_mic)

            # Hotkey Settings
            streamer_layout.addWidget(QLabel("⌨️ Talk Hotkey:"))
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

            btn_save_hk = QPushButton("💾 Save")
            btn_save_hk.clicked.connect(self.save_hotkey)
            hotkey_row.addWidget(btn_save_hk)

            streamer_layout.addLayout(hotkey_row)

            # Communication Toggle
            self.toggle_btn = QPushButton("🔔 Streamer Chat: ON")
            self.toggle_btn.setCheckable(True)
            self.toggle_btn.setChecked(True)
            self.toggle_btn.clicked.connect(self.toggle_hotkey)
            streamer_layout.addWidget(self.toggle_btn)

            # Instructions & Cost Info
            instructions = QLabel(
                "💡 Hold hotkey and speak to talk with AI CoHost.\n"

            )
            instructions.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
            instructions.setWordWrap(True)
            streamer_layout.addWidget(instructions)

            content_layout.addWidget(streamer_group)

            # Log Group - PENTING: Ini adalah bagian yang menampilkan log
            log_group = QGroupBox("📋 Activity Log")
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
            self.log_user("CoHost Basic ready to use!", "✅")
            
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
            self.log_view.setPlainText("UI failed to load, using fallback mode.\nPlease restart application.")
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
        self.log_user("Additional prompt saved successfully", "💾")

    # 🔥 POWERFUL TEMPLATE SYSTEM METHODS
    def get_template_prompts(self):
        """Return dictionary of powerful templates for gaming and sales"""
        return {
            "📝 Custom Prompt": "",
            
            "🎮 Gaming - MOBA Expert": """Kamu adalah gaming coach dan streamer expert MOBA (Mobile Legends, AOV, LOL). Karaktermu:
- Sangat knowledgeable tentang meta, build, strategy
- Kasual tapi informatif, suka sharing tips praktis
- Pakai bahasa gaul gaming yang kekinian
- Sering kasih analisis singkat tapi berguna
- Bicarain hero favorit, build recommendation, gameplay tips
- Responsif terhadap pertanyaan gaming teknis

Contoh respon: "Wah main Fanny ya! Buat build sekarang meta nya damage penetration dulu bro, war axe -> hunter strike -> malefic roar. Combo cable nya jangan lupa timing nya, drag dulu baru hook!"

Current context: Gaming streamer yang lagi main MOBA""",
            
            "🎮 Gaming - Mobile Legends Pro": """Kamu adalah pro player Mobile Legends yang jadi streamer. Karaktermu:
- Master semua role: jungler, midlaner, gold laner, exp laner, roamer
- Sangat update dengan meta hero dan build terbaru
- Bisa kasih tips rotasi, objective control, dan war positioning
- Suka bahas counter pick dan draft strategy
- Gaya bicara santai tapi penuh insight
- Sering pakai istilah ML seperti: gank, rotate, turtle, lord, war, split push

Contoh respon: "Hayabusa mantap banget pick nya! Sekarang build meta nya War Axe dulu buat damage, terus Hunter Strike buat movement speed pas combo. Jangan lupa selalu ambil blue buff ya, terus split push aja kalau tim lagi war jauh dari objective."

Contoh respon lain: "Vale emang gila damage nya! Combo yang paling sakit itu skill 2-1-3, tapi kalau buat team fight mending 1-2-3 biar CC nya kerasa. Item build full magic power aja: Arcane Boots, Clock of Destiny, Lightning Truncheon, Holy Crystal."

Current context: Mobile Legends streamer yang lagi push rank""",
            
            "🎮 Gaming - Inzoi Expert": """Kamu adalah pro player game Inzoi yang jadi streamer. Karaktermu:
- Master semua aspek gameplay Inzoi dan mekanik permainan
- Sangat update dengan meta karakter dan strategi terbaru
- Bisa kasih tips farming, PVP, dan progression yang efisien
- Suka bahas build equipment dan skill tree terbaik
- Gaya bicara santai, kadang excited, dan penuh insight
- Suka pakai istilah khas Inzoi

Contoh respon: "Build Sword Master sekarang paling enak pakai equipment set Crimson Dragon buat damage, terus skill tree fokus ke critical rate sama attack speed! Jangan lupa daily dungeon tiap hari buat dapetin material upgrade yang langka."

Contoh respon lain: "Boss raid minggu ini lumayan susah, tapi kalau tim composition nya balance harusnya bisa clear. Tank harus jago taunt timing, DPS fokus ke weak point, healer jangan spam skill healing, harus efisien mana usage nya."

Current context: Inzoi streamer yang lagi main konten endgame""",
            
            "🎮 Gaming - FPS Pro": """Kamu adalah pro gamer FPS (PUBG, Free Fire, Valorant, CSGO) yang jadi streamer. Karaktermu:
- Master semua teknik FPS: aim, recoil control, positioning
- Analisa gameplay dengan detail tapi fun
- Jelasin strategy team dengan gampang
- Suka diskusi weapon meta, setting optimal
- Ngasih tips ranking up yang praktis
- Bahasa santai tapi profesional

Contoh respon: "Nice clutch bro! Crosshair placement lu udah bagus, cuma sensitivity nya mungkin masih kekecilan. Coba naik 10% lagi, terus training aim_botz 15 menit sehari pasti naik rank!"

Current context: Pro FPS gamer streamer""",
            
            "💰 Sales - E-Commerce": """Kamu adalah sales expert e-commerce yang jago closing. Karaktermu:
- Master persuasi tanpa keliatan pushy
- Paham buyer psychology dan pain points
- Jago storytelling produk yang engaging
- Kasih social proof dan urgency natural
- Responsive terhadap objection dengan solusi
- Ramah, trustworthy, tapi assertive

Contoh respon: "Bang ini produk best seller banget loh! Kemarin ada customer sampe beli 3 sekaligus karena hasilnya ampuh banget. Stock tinggal 5 lagi nih, banyak yang nanya-nanya terus. Mau secured dulu?"

Current context: E-commerce sales specialist""",
            
            "💰 Sales - TikTok Shop Keranjang": """Kamu adalah seller TikTok Shop yang jago jualan dengan sistem keranjang kuning. Karaktermu:
- Sangat mengenal semua produk di keranjang dengan detail
- Jago presentasi produk dengan cara yang menarik dan persuasif
- Responsif terhadap pertanyaan "spill" untuk menjelaskan produk di keranjang tertentu
- Paham harga, spesifikasi, dan keunggulan setiap produk
- Suka kasih diskon, promo, dan urgency yang bikin orang checkout
- Energik, ramah, dan jago closing

Contoh database produk:
- Keranjang 1: Sepatu Winketz anak sekolah hitam, ukuran 21-35, harga Rp125.000, gratis ongkir
- Keranjang 2: Tas ransel Hanke x Dannybear motif beruang, warna blue red/beige/white pearl, harga Rp498.000 (diskon 55%)
- Keranjang 3: Kemeja anak sekolah putih, ukuran 3-15 tahun, harga Rp89.000, bahan katun adem
- Keranjang 4: Celana sekolah hitam/abu, ukuran 3-15 tahun, harga Rp110.000, bahan tidak mudah kusut

Contoh respon saat ditanya "spill keranjang 2":
"Tas ransel Hanke x Dannybear ini kolaborasi premium banget! Motif beruang super cute, ada 3 warna: blue red, beige, sama white pearl. Material jacquard premium, ada kompartemen besar plus slot khusus untuk tablet. Tali bahu empuk bisa disesuaikan. Harga spesial cuma Rp498.000 dari harga normal Rp1.100.000, diskon gila 55%! Gratis ongkir ke seluruh Indonesia, stok terbatas!"

Contoh respon saat ditanya "spill sepatu keranjang 1":
"Sepatu Winketz anak sekolah ini best seller banget! Warna hitam klasik, ukuran lengkap dari 21-35. Material premium anti lecet, sol empuk nyaman dipakai seharian. Harga cuma Rp125.000 sudah termasuk gratis ongkir! Cocok untuk anak TK sampai SD, awet sampai 1 tahun pemakaian normal. Stok lagi banyak tapi cepat habis, mau checkout sekarang?"

Current context: TikTok Shop live seller dengan sistem keranjang""",
            
            "💰 Sales - Digital Products": """Kamu adalah digital marketing guru yang jual produk digital (course, ebook, tools). Karaktermu:
- Expert value-based selling dan benefit focused
- Jago edukasi customer tentang ROI dan transformation
- Pakai success stories dan case studies
- Master urgency dan scarcity yang authentic
- Follow up game yang kuat
- Bahasa convincing tapi educational

Contoh respon: "Course ini udah proven banget bang! Student kemarin dari income 2 juta jadi 15 juta dalam 3 bulan. Method nya step-by-step, ada live mentoring juga. Early bird price cuma sampai besok, normal price 2x lipat!"

Current context: Digital products sales expert"""
        }

    def load_template(self, template_name):
        """Load selected template into custom input"""
        templates = self.get_template_prompts()
        if template_name in templates:
            template_text = templates[template_name]
            self.custom_input.setPlainText(template_text)
            
            if template_name != "📝 Custom Prompt":
                self.log_user(f"Template loaded: {template_name}", "📋")
            else:
                self.log_user("Ready for custom prompt", "✏️")

    def preview_template(self):
        """Show template preview in a dialog"""
        current_template = self.template_combo.currentText()
        templates = self.get_template_prompts()
        
        if current_template in templates:
            template_content = templates[current_template]
            
            # Create preview dialog
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QLabel
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Template Preview: {current_template}")
            dialog.setModal(True)
            dialog.resize(600, 450)
            
            layout = QVBoxLayout(dialog)
            
            # Header
            header = QLabel(f"🔍 Preview: {current_template}")
            header.setStyleSheet("font-weight: bold; font-size: 14px; color: #2196F3; margin-bottom: 10px;")
            layout.addWidget(header)
            
            # Content
            content = QTextEdit()
            content.setPlainText(template_content if template_content else "Custom prompt - write your own!")
            content.setReadOnly(True)
            content.setStyleSheet("background: #f5f5f5; border: 1px solid #ddd; padding: 10px;")
            layout.addWidget(content)
            
            # Action buttons
            btn_layout = QVBoxLayout()
            
            btn_use = QPushButton("✅ Use This Template")
            btn_use.clicked.connect(lambda: [
                self.load_template(current_template),
                dialog.close(),
                self.log_user(f"Applied template: {current_template}", "🎯")
            ])
            btn_use.setStyleSheet("background: #4CAF50; color: white; font-weight: bold; padding: 8px;")
            btn_layout.addWidget(btn_use)
            
            btn_close = QPushButton("❌ Close Preview")
            btn_close.clicked.connect(dialog.close)
            btn_layout.addWidget(btn_close)
            
            layout.addLayout(btn_layout)
            
            dialog.exec_()

    def save_trigger(self):
        """Simpan trigger words dengan validasi"""
        triggers = self.trigger_input.text().strip()
        trigger_list = [t.strip() for t in triggers.split(",") if t.strip()]

        if len(trigger_list) > 3:
            QMessageBox.warning(
                self, "Too Many Triggers",
                "Maximum 3 trigger words!\nExample: bro, hey, hi"
            )
            trigger_list = trigger_list[:3]
            self.trigger_input.setText(", ".join(trigger_list))

        self.cfg.set("trigger_words", trigger_list)
        self.cfg.set("trigger_word", "")
        self.log_user(f"Triggers saved successfully: {', '.join(trigger_list)}", "🎯")

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
        self.log_user(f"Video ID saved: {video_id}", "📹")

    def save_nickname(self):
        """Simpan TikTok nickname"""
        nickname = self.nick_input.text().strip()
        if nickname and not nickname.startswith("@"):
            nickname = "@" + nickname
        self.cfg.set("tiktok_nickname", nickname)
        self.nick_input.setText(nickname)
        self.log_user(f"TikTok nickname saved: {nickname}", "📱")

    def save_voice(self):
        """Simpan pilihan suara"""
        voice = self.voice_cb.currentData()
        self.cfg.set("cohost_voice_model", voice)
        self.log_user("CoHost voice saved successfully", "🔊")

    def update_cooldown(self, value):
        """Update cooldown duration"""
        self.cooldown_duration = value
        self.cfg.set("cohost_cooldown", value)
        self.log_user(f"Cooldown set to {value} seconds", "⏱️")

    def update_max_queue(self, value):
        """Update max queue size"""
        self.max_queue_size = value
        self.cfg.set("cohost_max_queue", value)
        self.log_user(f"Maximum queue set to {value}", "📋")

    def update_daily_limit(self, value):
        """Update limit pertanyaan sama per hari."""
        self.daily_message_limit = value
        self.cfg.set("daily_message_limit", value)
        self.log_view.append(f"[INFO] Daily limit set to {value}x per same question")

    def update_viewer_cooldown(self, value):
        """Update cooldown per penonton"""
        self.cfg.set("viewer_cooldown_minutes", value)
        self.viewer_cooldown_minutes = value * 60  # Convert ke detik
        self.log_user(f"Viewer cooldown set to {value} minutes", "⏱️")

    def update_daily_limit(self, value):
        """Update limit harian per penonton - PERBAIKAN"""
        self.cfg.set("viewer_daily_limit", value)
        self.viewer_daily_limit = value
        self.log_user(f"Daily limit per viewer set to {value} interactions", "📊")

    # 🔧 TOPIC COOLDOWN CONTROL METHODS
    def update_topic_cooldown(self, value):
        """Update topic cooldown duration"""
        self.cfg.set("topic_cooldown_minutes", value)
        self.topic_cooldown_minutes = value * 60  # Convert to seconds
        if value == 0:
            self.log_user("Topic cooldown disabled", "🔓")
        else:
            self.log_user(f"Topic cooldown set to {value} minutes", "⏱️")

    def toggle_topic_blocking(self, state):
        """Toggle topic blocking on/off"""
        enabled = state == 2  # Checked state
        self.cfg.set("enable_topic_blocking", enabled)
        self.topic_blocking_enabled = enabled
        status = "enabled" if enabled else "disabled"
        self.log_user(f"Topic blocking {status}", "🔄")

    def preview_voice(self):
        """Preview suara yang dipilih dengan debugging yang lebih baik"""
        voice = self.voice_cb.currentData()
        code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
        voice_display = self.voice_cb.currentText()
        
        # Log untuk debugging
        self.log_user("Playing voice preview...", "🔈")
        self.log_debug(f"Preview voice: {voice_display} -> {voice}")
        self.log_debug(f"Language code: {code}")
        
        # Teks preview yang lebih informatif
        if voice and voice != "default":
            preview_text = f"This is {voice_display} voice preview. Hello, I am your AI CoHost!"
        else:
            preview_text = "This is default voice preview. Hello, I am your AI CoHost!"
        
        try:
            # Pastikan voice parameter dikirim dengan benar
            speak(
                text=preview_text, 
                language_code=code, 
                voice_name=voice,
                output_device=None,
                on_finished=lambda: self.log_user("Preview completed", "✅")
            )
        except Exception as e:
            self.log_error(f"Voice preview failed: {e}")
            # Fallback preview dengan info error
            try:
                fallback_text = f"Fallback preview for {voice_display}"
                speak(
                    text=fallback_text,
                    language_code=code,
                    voice_name=None,  # Force fallback
                    output_device=None,
                    on_finished=lambda: self.log_user("Fallback preview completed", "⚠️")
                )
            except Exception as e2:
                self.log_error(f"Fallback preview also failed: {e2}")

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
        self.log_user(f"Hotkey saved successfully: {hot}", "⌨️")

    def toggle_hotkey(self):
        """Toggle hotkey on/off"""
        on = self.toggle_btn.isChecked()
        self.toggle_btn.setText("🔔 Streamer Chat: ON" if on else "🔕 Streamer Chat: OFF")
        self.hotkey_enabled = on

    def _load_microphones(self):
        """Load available microphones"""
        try:
            import sounddevice as sd
            
            self.mic_combo.clear()
            devices = sd.query_devices()
            
            input_devices = []
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:  # Input device
                    name = device['name']
                    self.mic_combo.addItem(f"{i}: {name}", i)
                    input_devices.append((i, name))
            
            # Restore saved selection
            saved_mic = self.cfg.get("selected_mic_index", 0)
            for idx in range(self.mic_combo.count()):
                if self.mic_combo.itemData(idx) == saved_mic:
                    self.mic_combo.setCurrentIndex(idx)
                    break
            
            self.log_user(f"Found {len(input_devices)} microphone(s)", "🎤")
            
        except Exception as e:
            self.log_error(f"Failed to load microphones: {e}")
            self.mic_combo.addItem("Default Microphone", 0)

    def _test_microphone(self):
        """Test selected microphone"""
        try:
            import sounddevice as sd
            import numpy as np
            
            if self.mic_combo.count() == 0:
                self.log_error("No microphones available")
                return
            
            mic_index = self.mic_combo.currentData()
            device_name = self.mic_combo.currentText()
            
            self.log_user(f"Testing microphone: {device_name}", "🎵")
            
            # Record 2 seconds of audio
            duration = 2
            sample_rate = 16000
            
            audio_data = sd.rec(int(duration * sample_rate), 
                              samplerate=sample_rate, 
                              channels=1, 
                              device=mic_index,
                              dtype=np.float32)
            
            sd.wait()
            
            # Check audio levels
            max_level = np.max(np.abs(audio_data))
            avg_level = np.mean(np.abs(audio_data))
            
            if max_level > 0.01:  # Some audio detected
                self.log_user(f"✅ Microphone working! Level: {max_level:.3f}", "🎵")
            else:
                self.log_user("⚠️ Very low audio level. Check microphone connection.", "🎵")
                
        except Exception as e:
            self.log_error(f"Microphone test failed: {e}")

    def _save_microphone(self):
        """Save selected microphone"""
        try:
            if self.mic_combo.count() == 0:
                self.log_error("No microphones to save")
                return
            
            mic_index = self.mic_combo.currentData()
            device_name = self.mic_combo.currentText()
            
            self.cfg.set("selected_mic_index", mic_index)
            self.log_user(f"Microphone saved: {device_name}", "💾")
            
        except Exception as e:
            self.log_error(f"Failed to save microphone: {e}")

    def _check_stt_credit_before_use(self, required_credits):
        """Check if user has sufficient credits for STT usage"""
        try:
            # Skip credit check for test/demo mode
            main_window = self.window()
            if hasattr(main_window, 'license_validator') and main_window.license_validator.testing_mode:
                return True
            
            # Check current credit balance
            current_credits = credit_tracker.get_available_credits()
            
            if current_credits < required_credits:
                self.log_user(f"❌ Need {required_credits} credits, but only {current_credits:.2f} available", "💳")
                
                # Show credit insufficient message
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "Credits Insufficient",
                    f"You need {required_credits} credits for streamer communication.\n"
                    f"Current balance: {current_credits:.2f} credits\n\n"
                    "Please purchase more credits to continue using this feature."
                )
                return False
            
            return True
            
        except Exception as e:
            self.log_error(f"Credit check failed: {e}")
            # If credit check fails, allow usage (fail-safe)
            return True

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
            self.log_user(f"⚠️ {author} already asked the same thing today", "🚫")
            self.log_debug(f"Exact duplicate: {author} - '{message[:30]}...' already asked today")
            self.filter_stats["spam"] += 1
            return True
        
        # FILTER 2: Cek kemiripan dengan pesan sebelumnya
        similarity_threshold = 0.75  # 75% kemiripan
        for prev_normalized in viewer_data["normalized_messages"]:
            similarity = self._calculate_similarity(normalized_message, prev_normalized)
            if similarity > similarity_threshold:
                self.log_user(f"⚠️ {author} already asked similar question ({similarity:.0%})", "🚫")
                self.log_debug(f"Similar duplicate: {author} - similarity {similarity:.0%}: '{message[:30]}...'")
                self.filter_stats["spam"] += 1
                return True
        
        # 🔧 PERBAIKAN: Topic cooldown yang lebih natural (10 menit)
        common_topics = {
            "greeting": ["halo", "hai", "hello", "selamat", "salam", "assalamualaikum"],
            "khodam": ["khodam", "cek", "apa khodam", "siapa khodam", "hewan apa"],
            "eating": ["makan", "udah makan", "belum makan", "lapar"],
            "question": ["tanya", "nanya", "mau tanya", "boleh tanya", "bisa tanya"]
        }
        
        import time
        current_time = time.time()
        
        # 🔧 Topic blocking dengan setting yang bisa diatur user
        if self.topic_blocking_enabled and self.topic_cooldown_minutes > 0:
            for topic, keywords in common_topics.items():
                if any(keyword in normalized_message for keyword in keywords):
                    # Cek kapan terakhir kali membahas topik ini
                    last_topic_time = viewer_data["similar_topics"].get(topic, 0)
                    time_diff = current_time - last_topic_time
                    
                    # Gunakan setting user untuk topic cooldown
                    if time_diff < self.topic_cooldown_minutes:
                        remaining_minutes = (self.topic_cooldown_minutes - time_diff) / 60
                        self.log_user(f"⏱️ {author} wait {remaining_minutes:.1f} more minutes for topic '{topic}'", "🚫")
                        self.log_debug(f"Topic cooldown: {author} - '{topic}' asked {remaining_minutes:.1f}min ago")
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
            self.log_user(f"⚠️ {author} has reached the limit of {daily_limit} questions today", "🚫")
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
        self.log_user(f"{status_icon} {author} - Question {viewer_data['interaction_count']}/{daily_limit} today", "✅")
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
        
                        # Log cleanup only if anything was cleaned
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
            self.log_view.append(f"[CLEANUP] Removed data from {len(expired_viewers)} old viewers")

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
        stats_msg += f"Toxic words: {self.filter_stats.get('toxic', 0)}\n"
        stats_msg += f"Short messages: {self.filter_stats.get('short', 0)}\n"
        stats_msg += f"Emoji only: {self.filter_stats.get('emoji', 0)}\n"
        stats_msg += f"Spam/daily limit: {self.filter_stats.get('spam', 0)}\n"
        stats_msg += f"Numeric spam: {self.filter_stats.get('numeric', 0)}\n"
        stats_msg += "=" * 40 + "\n"
        stats_msg += f"Total filtered: {total_filtered}\n\n"
        
        stats_msg += "[DAILY INTERACTIONS]\n"
        stats_msg += "=" * 40 + "\n"
        stats_msg += f"Active viewers today: {today_viewers}\n"
        stats_msg += f"Total interactions today: {total_interactions_today}\n"
        stats_msg += f"New viewers: {status_counts['new']}\n"
        stats_msg += f"Regular viewers: {status_counts['regular']}\n"
        stats_msg += f"VIP viewers: {status_counts['vip']}\n"
        stats_msg += f"Limit per same question: {self.daily_message_limit}x/day"

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
        self.log_view.append("[INFO] Filter statistics have been reset")

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
            self.log_view.append(f"[RESET] {blocked_count} spam blocks removed, all viewers can ask questions again")
        self.log_view.append("[RESET] Daily interaction history has been reset")

    def _hotkey_listener(self):
        """Thread untuk mendengarkan hotkey hold-to-talk - Enhanced with Google STT"""
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
                self.log_user("🔴 Recording... (Hold to speak)", "🎙️")

                # Enhanced STT with language detection
                lang_code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
                
                # Log current language setting for debugging
                self.log_debug(f"STT Language: {lang_code} (Output: {self.out_lang.currentText()})")
                
                self.stt_thread = GoogleSTTThread(
                    self.cfg.get("selected_mic_index", 0),
                    lang_code
                )
                self.stt_thread.result.connect(self._handle_streamer_speech)
                self.stt_thread.start_recording()

            elif not pressed and prev:
                prev = False
                self.conversation_active = False
                self.log_user("⏳ Processing speech...", "🎙️")
                
                if self.stt_thread:
                    self.stt_thread.stop_recording()

    def _handle_streamer_speech(self, txt):
        """Handle streamer speech result from Google STT - Enhanced with safety limits"""
        print(f"[STT] 🎯 _handle_streamer_speech called with: '{txt}'")
        print(f"[STT] 🎯 Called from thread: {QThread.currentThread()}")
        print(f"[STT] 🎯 Text length: {len(txt) if txt else 0}")
        print(f"[STT] 🎯 Starting AI processing pipeline...")
        self.conversation_active = False
        
        # Set processing speed to fast mode
        self.reply_delay = 300  # Reduced delay for faster processing

        if not txt:
            # More user-friendly message for no speech detection
            current_lang = self.out_lang.currentText()
            self.log_user(f"No speech detected (Language: {current_lang})", "⚠️")
            self.log_debug("Try speaking louder or closer to microphone")
            return

        if txt.startswith("STT Error:") or txt.startswith("Google STT Error:"):
            self.log_error(txt)
            self.log_debug("STT API error - check internet connection and API credentials")
            return

        # 🛡️ SAFETY: Only protect against extremely long input (increased limit)
        original_length = len(txt)
        MAX_STT_LENGTH = 1200  # Increased limit to allow longer natural speech
        
        if original_length > MAX_STT_LENGTH:
            # Truncate at sentence boundary if possible
            truncated = txt[:MAX_STT_LENGTH]
            last_sentence = truncated.rfind('.')
            last_space = truncated.rfind(' ')
            
            if last_sentence > MAX_STT_LENGTH - 200:  # Good sentence break
                txt = txt[:last_sentence + 1]
            elif last_space > MAX_STT_LENGTH - 100:  # Good word break
                txt = txt[:last_space]
            else:  # Hard cut
                txt = txt[:MAX_STT_LENGTH-3] + "..."
            
            self.log_user(f"⚠️ Speech extremely long ({original_length} chars), truncated to {len(txt)} chars", "✂️")
            self.log_debug(f"Original: '{txt[:50]}...' | Truncated: '{txt}'")
        else:
            self.log_debug(f"Speech length OK: {original_length} chars")
        
        # 🛡️ SAFETY: Additional text cleaning to prevent issues
        try:
            # Remove excessive whitespace and clean characters
            txt = ' '.join(txt.split())  # Normalize whitespace
            txt = ''.join(char for char in txt if ord(char) < 65536)  # Remove problematic Unicode
            
            if not txt.strip():
                self.log_user("⚠️ Empty speech after cleaning", "🧹")
                return
                
        except Exception as clean_error:
            self.log_error(f"Error cleaning STT text: {clean_error}")
            self.log_user("⚠️ Could not process speech - text format issue", "❌")
            return

        # 💰 CREDIT TRACKING: Deduct credits for Google STT usage
        stt_cost = 0.02  # $0.006 Google STT + markup for sustainability
        
        try:
            # Check if user has sufficient credits before processing
            if not self._check_stt_credit_before_use(stt_cost):
                self.log_user("❌ Insufficient credits for streamer communication", "💳")
                return
            
            # Deduct credits for STT usage
            force_credit_deduction(stt_cost, "streamer_stt", "Streamer Communication (Google STT)")
            self.log_user(f"💳 STT Cost: {stt_cost} credits deducted", "📊")
            
        except Exception as e:
            self.log_error(f"Credit deduction failed: {e}")
            # Continue processing even if credit tracking fails
            pass

        self.log_user(f"🎙️ Streamer: {txt}", "💬")

        # Enhanced AI prompt with better context understanding
        lang_label = "Bahasa Indonesia" if self.out_lang.currentText() == "Indonesia" else "English"
        cohost_name = self.cfg.get('cohost_name', 'AI CoHost')
        personality = self.person_cb.currentText()
        custom_context = self.cfg.get("custom_context", "").strip()
        
        # Analyze the streamer's message to understand intent
        message_lower = txt.lower()
        intent = self._analyze_streamer_intent(message_lower)
        
        # Log intent for debugging
        self.log_debug(f"Detected intent: {intent} | Language: {lang_label}")
        
        # Build context-aware prompt based on intent
        try:
            if lang_label == "English":
                prompt = self._build_english_prompt(txt, cohost_name, personality, custom_context, intent)
            else:
                prompt = self._build_indonesian_prompt(txt, cohost_name, personality, custom_context, intent)
            
            # 🛡️ SAFETY: Check prompt length to prevent AI processing issues
            MAX_PROMPT_LENGTH = 2000  # Maximum safe prompt length
            if len(prompt) > MAX_PROMPT_LENGTH:
                self.log_debug(f"Prompt too long ({len(prompt)} chars), truncating...")
                prompt = prompt[:MAX_PROMPT_LENGTH-50] + "\n\nJawab singkat dan to the point."
                
        except Exception as prompt_error:
            self.log_error(f"Error building prompt: {prompt_error}")
            # Fallback to simple prompt
            prompt = f"Kamu adalah AI assistant. User berkata: '{txt}'. Jawab dengan singkat dan helpful."
        
        try:
            # 💰 CREDIT TRACKING: Deduct credits for AI processing
            ai_cost = 0.03  # Standard AI processing cost for streamer communication
            
            # Check credits for AI processing
            if not self._check_stt_credit_before_use(ai_cost):
                self.log_user("❌ Insufficient credits for AI processing", "💳")
                self.ttsFinished.emit()
                return
            
            # Enhanced AI reply generation with better error handling
            try:
                reply = generate_reply(prompt)
                if not reply or len(reply.strip()) == 0:
                    reply = "Maaf, saya tidak bisa memproses permintaan itu saat ini"
                
                # 🛡️ SAFETY: Only limit extremely long AI responses
                MAX_AI_RESPONSE = 1500  # Increased limit for more complete responses
                if len(reply) > MAX_AI_RESPONSE:
                    self.log_debug(f"AI response extremely long ({len(reply)} chars), truncating...")
                    # Find good break point
                    truncated = reply[:MAX_AI_RESPONSE-50]
                    last_sentence = truncated.rfind('.')
                    if last_sentence > MAX_AI_RESPONSE - 300:
                        reply = reply[:last_sentence + 1]
                    else:
                        reply = truncated + "..."
                else:
                    self.log_debug(f"AI response length OK: {len(reply)} chars")
                        
            except Exception as ai_error:
                self.log_error(f"AI generation failed: {ai_error}")
                reply = "Maaf, ada masalah dengan AI response"
            
            # Deduct credits for AI usage
            try:
                force_credit_deduction(ai_cost, "streamer_ai", "Streamer AI Response")
                self.log_user(f"💳 AI Cost: {ai_cost} credits deducted", "📊")
            except Exception as credit_error:
                self.log_error(f"AI credit deduction failed: {credit_error}")
            
            # 🔥 ENHANCED: Prepare text for TTS using new method
            tts_reply = self._prepare_text_for_tts(reply)
            
            self.log_user(f"🤖 AI CoHost: {reply}", "💭")
            
            # TTS the reply
            self.ttsAboutToStart.emit()
            
            try:
                # 💰 CREDIT TRACKING: Deduct credits for TTS
                tts_cost = 0.01  # TTS cost for streamer communication
                
                # Check credits for TTS
                if not self._check_stt_credit_before_use(tts_cost):
                    self.log_user("❌ Insufficient credits for TTS", "💳")
                    self.ttsFinished.emit()
                    return
                
                code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
                voice_model = self.voice_cb.currentData()
                
                # Enhanced TTS with better error handling
                try:
                    # 🛡️ SAFETY: Log TTS length for monitoring
                    self.log_debug(f"TTS processing: {len(tts_reply)} chars")
                    
                    speak(tts_reply, language_code=code, voice_name=voice_model)
                except Exception as tts_error:
                    self.log_error(f"TTS playback failed: {tts_error}")
                    # Try backup TTS with shorter text
                    try:
                        backup_reply = tts_reply[:400] if len(tts_reply) > 400 else tts_reply
                        self.log_debug(f"Trying backup TTS with shorter text: {len(backup_reply)} chars")
                        speak(backup_reply, language_code=code, voice_name=voice_model)
                    except Exception as backup_error:
                        self.log_error(f"Backup TTS also failed: {backup_error}")
                        # Continue without TTS rather than crashing
                
                # Deduct TTS credits after successful completion
                try:
                    force_credit_deduction(tts_cost, "streamer_tts", "Streamer TTS Response")
                    self.log_user(f"💳 TTS Cost: {tts_cost} credits deducted", "📊")
                except Exception as tts_credit_error:
                    self.log_error(f"TTS credit deduction failed: {tts_credit_error}")
                
                self.log_user("✅ AI response delivered", "🔊")
                
                # 📊 SUMMARY: Total cost breakdown
                total_cost = stt_cost + ai_cost + tts_cost
                self.log_user(f"💰 Total Session Cost: {total_cost} credits (STT: {stt_cost} + AI: {ai_cost} + TTS: {tts_cost})", "💳")
                
            except Exception as tts_error:
                self.log_error(f"TTS failed: {tts_error}")
            
            self.ttsFinished.emit()
            
        except Exception as e:
            self.log_error(f"AI response failed: {e}")
            # Log the full traceback for debugging
            import traceback
            self.log_error(f"Traceback: {traceback.format_exc()}")
            self.ttsFinished.emit()

    def _analyze_streamer_intent(self, message_lower):
        """Analyze streamer's message to understand intent and provide better responses"""
        
        # Commands to speak to viewers/audience (highest priority)
        if any(phrase in message_lower for phrase in [
            "salam ke penonton", "greet the viewers", "say hello to", "sapaan ke", 
            "bilang ke penonton", "tell the audience", "speak to viewers",
            "coba salam", "sapa penonton", "greeting viewers", "halo tes",
            "hai tes", "hello test", "salam tes", "greet test"
        ]):
            return "speak_to_viewers"
        
        # Content creation (check first to avoid conflicts)
        if any(word in message_lower for word in ["konten", "content", "thumbnail", "edit", "editing"]):
            return "content"
        
        # Technical questions (prioritize over general questions)
        if any(word in message_lower for word in ["setting", "audio", "video", "lag", "internet", "stream", "obs", "fps"]):
            return "technical"
        
        # Questions about what to do/play (specific suggestions)
        if any(phrase in message_lower for phrase in ["apa yang", "what should", "mau main", "want to play", "gimana", "how about", "ide konten"]):
            return "asking_suggestion"
        
        # Commands or requests (check before general questions)
        if any(word in message_lower for word in ["tolong", "please", "bisa", "can you", "help", "bantu"]):
            return "request"
        
        # Game-related (expand patterns)
        if any(word in message_lower for word in ["game", "main", "play", "rank", "skill", "hero", "character", "difficult", "susah", "strategi"]):
            return "gaming"
        
        # Questions about viewers/audience
        if any(word in message_lower for word in ["viewers", "penonton", "audience", "chat", "subscriber"]):
            return "about_viewers"
        
        # Personal/casual conversation
        if any(word in message_lower for word in ["capek", "tired", "makan", "eat", "istirahat", "break"]):
            return "personal"
        
        # Greeting patterns (more specific to avoid conflicts)
        if any(word in message_lower for word in ["halo", "hai", "hello", "hi", "assalamualaikum"]) and not any(word in message_lower for word in ["help", "bantu", "tolong"]):
            return "greeting"
        
        if message_lower.startswith("selamat") and not any(word in message_lower for word in ["bagaimana", "gimana"]):
            return "greeting"
        
        # Questions (general) - be more specific
        if any(word in message_lower for word in ["apa", "what", "kenapa", "why", "dimana", "where"]) and "?" in message_lower:
            return "question"
        
        if any(word in message_lower for word in ["bagaimana", "how"]) and not any(word in message_lower for word in ["gimana", "about"]):
            return "question"
        
        return "general"
    
    def _build_indonesian_prompt(self, original_text, cohost_name, personality, custom_context, intent):
        """Build contextual Indonesian prompt based on intent"""
        
        base_context = (
            f"Kamu adalah {cohost_name}, AI Co-Host profesional dengan kepribadian {personality}. "
            f"PENTING: Yang bicara adalah STREAMER (bos kamu), bukan penonton. "
            f"Streamer berkata: \"{original_text}\""
        )
        
        if custom_context:
            base_context += f"\n\nInformasi streamer: {custom_context}"
        
        # Intent-specific responses
        if intent == "speak_to_viewers":
            instruction = (
                "\n\nStreamer meminta kamu untuk berbicara langsung ke PENONTON/VIEWERS, bukan ke streamer. "
                "Respond seolah-olah kamu sedang menyapa atau berbicara langsung dengan audience yang sedang menonton. "
                "Gunakan kata ganti 'kalian', 'teman-teman', atau 'viewers' untuk menyapa penonton. "
                "Buat sambutan yang hangat dan mengundang interaksi dari chat."
            )
        
        elif intent == "greeting":
            instruction = (
                "\n\nRespond sebagai AI assistant yang ramah dan supportive. "
                "Balas sapaan dengan antusias dan tanyakan bagaimana kondisi stream hari ini. "
                "Berikan semangat untuk streaming session."
            )
        
        elif intent == "asking_suggestion":
            instruction = (
                "\n\nStreamer meminta saran. Berikan rekomendasi yang praktis dan berguna. "
                "Pertimbangkan audience, waktu streaming, dan trend saat ini. "
                "Berikan 1-2 saran konkret yang bisa langsung diterapkan."
            )
        
        elif intent == "about_viewers":
            instruction = (
                "\n\nStreamer bertanya tentang viewers/penonton. Berikan insight tentang engagement, "
                "cara berinteraksi dengan audience, atau saran untuk meningkatkan viewer experience. "
                "Fokus pada tips praktis untuk community building."
            )
        
        elif intent == "technical":
            instruction = (
                "\n\nStreamer ada masalah teknis. Berikan solusi praktis dan mudah dipahami. "
                "Prioritaskan solusi yang cepat dan tidak mengganggu stream. "
                "Gunakan bahasa yang simpel dan step-by-step jika perlu."
            )
        
        elif intent == "gaming":
            instruction = (
                "\n\nTopic tentang gaming. Berikan advice yang relevant tentang gameplay, "
                "strategi, atau entertainment value untuk viewers. "
                "Pertimbangkan apa yang menarik untuk ditonton audience."
            )
        
        elif intent == "content":
            instruction = (
                "\n\nStreamer membahas konten creation. Berikan saran kreatif dan praktis "
                "untuk membuat konten yang engaging. Fokus pada ide yang executable "
                "dan sesuai dengan platform streaming."
            )
        
        elif intent == "personal":
            instruction = (
                "\n\nStreamer sharing hal personal. Respond dengan empati dan care. "
                "Berikan saran yang supportive tentang work-life balance atau self-care. "
                "Tunjukkan bahwa kamu peduli dengan well-being streamer."
            )
        
        elif intent == "question":
            instruction = (
                "\n\nStreamer bertanya. Analisa pertanyaan dengan baik dan berikan jawaban "
                "yang informatif dan helpful. Jika tidak yakin, katakan akan cari info "
                "atau minta klarifikasi yang lebih spesifik."
            )
        
        elif intent == "request":
            instruction = (
                "\n\nStreamer meminta bantuan. Respond secara proaktif dan helpful. "
                "Berikan langkah-langkah konkret atau tawari assistance yang relevan. "
                "Tunjukkan ready to help attitude."
            )
        
        else:  # general
            instruction = (
                "\n\nRespond sebagai AI assistant yang supportive dan profesional. "
                "Pahami konteks dan berikan respon yang relevan dengan situation saat ini. "
                "Fokus pada membantu kelancaran streaming."
            )
        
        final_instruction = (
            "\n\nJawab dalam Bahasa Indonesia yang natural dan conversational. "
            "Maksimal 2 kalimat yang padat dan berguna. Hindari emoji berlebihan. "
            "Prioritaskan memberikan value dan insight yang membantu streamer."
        )
        
        return base_context + instruction + final_instruction
    
    def _build_english_prompt(self, original_text, cohost_name, personality, custom_context, intent):
        """Build contextual English prompt based on intent"""
        
        base_context = (
            f"You are {cohost_name}, a professional AI Co-Host with {personality} personality. "
            f"IMPORTANT: You're talking to the STREAMER (your boss), not viewers. "
            f"Streamer said: \"{original_text}\""
        )
        
        if custom_context:
            base_context += f"\n\nStreamer info: {custom_context}"
        
        # Intent-specific responses
        if intent == "speak_to_viewers":
            instruction = (
                "\n\nStreamer is asking you to speak directly to the VIEWERS/AUDIENCE, not to the streamer. "
                "Respond as if you're speaking directly to the audience who are watching. "
                "Use words like 'everyone', 'guys', 'viewers', or 'chat' to address the audience. "
                "Create a warm greeting that encourages chat interaction."
            )
        
        elif intent == "greeting":
            instruction = (
                "\n\nRespond as a supportive AI assistant. Reply to the greeting enthusiastically "
                "and ask about today's streaming session. Give encouragement for the stream."
            )
        
        elif intent == "asking_suggestion":
            instruction = (
                "\n\nStreamer is asking for suggestions. Provide practical and useful recommendations. "
                "Consider the audience, streaming time, and current trends. "
                "Give 1-2 concrete suggestions that can be implemented immediately."
            )
        
        elif intent == "about_viewers":
            instruction = (
                "\n\nStreamer is asking about viewers/audience. Provide insights about engagement, "
                "ways to interact with audience, or suggestions to improve viewer experience. "
                "Focus on practical tips for community building."
            )
        
        elif intent == "technical":
            instruction = (
                "\n\nStreamer has technical issues. Provide practical, easy-to-understand solutions. "
                "Prioritize quick fixes that won't disrupt the stream. "
                "Use simple language and step-by-step if needed."
            )
        
        elif intent == "gaming":
            instruction = (
                "\n\nTopic is about gaming. Give relevant advice about gameplay, "
                "strategy, or entertainment value for viewers. "
                "Consider what would be interesting for the audience to watch."
            )
        
        elif intent == "content":
            instruction = (
                "\n\nStreamer is discussing content creation. Provide creative and practical suggestions "
                "for creating engaging content. Focus on executable ideas "
                "that fit the streaming platform."
            )
        
        elif intent == "personal":
            instruction = (
                "\n\nStreamer is sharing something personal. Respond with empathy and care. "
                "Give supportive advice about work-life balance or self-care. "
                "Show that you care about the streamer's well-being."
            )
        
        elif intent == "question":
            instruction = (
                "\n\nStreamer is asking a question. Analyze the question carefully and provide "
                "informative and helpful answers. If unsure, say you'll look for info "
                "or ask for more specific clarification."
            )
        
        elif intent == "request":
            instruction = (
                "\n\nStreamer is asking for help. Respond proactively and helpfully. "
                "Provide concrete steps or offer relevant assistance. "
                "Show a ready-to-help attitude."
            )
        
        else:  # general
            instruction = (
                "\n\nRespond as a supportive and professional AI assistant. "
                "Understand the context and give relevant responses to the current situation. "
                "Focus on helping the stream run smoothly."
            )
        
        final_instruction = (
            "\n\nAnswer in natural and conversational English. "
            "Maximum 2 sentences that are concise and useful. Avoid excessive emojis. "
            "Prioritize providing value and insights that help the streamer."
        )
        
        return base_context + instruction + final_instruction

    def _handle_speech(self, txt):
        """LEGACY: Handle speech result from STT - kept for backward compatibility"""
        # Redirect to new method
        self._handle_streamer_speech(txt)

    def start(self):
        """Start auto-reply - DEFINITIVE PROCESS-BASED VERSION"""
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
        self.log_user("=== StreamMate Basic Started ===", "🚀")
        self.log_user(f"Platform: {plat}", "📺")
        self.log_user(f"Mode: Trigger Only", "🎯")
        self.log_user(f"Trigger: {', '.join(trigger_words)}", "🔔")
        self.log_debug(f"Batch size: 3, Delay: 3s, Cooldown: 10s")

        # TAMBAHAN: Reset spam tracking
        if hasattr(self, 'author_last_time'):
            self.author_last_time.clear()

        # 6. CLEANUP EXISTING STATE
        self.stop() # Use the main stop function for cleanup
        
        # ✅ PERBAIKAN BARU: Clear PyTchat cache dan reset tracking
        self._clear_pytchat_cache()
        
        # Reset message tracking untuk session baru
        if hasattr(self, 'recent_messages'):
            self.recent_messages.clear()
        if hasattr(self, 'viewer_daily_interactions'):
            self.viewer_daily_interactions.clear()

        # ✅ PERBAIKAN KRITIKAL: Set reply_busy = True SETELAH cleanup untuk aktivasi auto-reply
        self.reply_busy = True

        # 7. START NEW LISTENER - ENHANCED THREAD-BASED APPROACH
        try:
            if plat == "YouTube":
                vid = self.cfg.get("video_id", "").strip()
                if not vid or len(vid) != 11:
                    self.log_error("Invalid YouTube Video ID.")
                    return
                
                if not PyTchatEXEFix.is_available():
                    self.log_error("Cannot start: Pytchat library not found.")
                    return

                self.log_user("Starting enhanced YouTube listener...", "🚀")

                # Use the enhanced PytchatListenerThread
                self.pytchat_listener_thread = PytchatListenerThread(vid)
                
                # 🔥 PERBAIKAN UTAMA: Reset untuk session baru (YouTube)
                self.pytchat_listener_thread.reset_for_new_session()
                
                self.pytchat_listener_thread.newComment.connect(self._enqueue)
                self.pytchat_listener_thread.logMessage.connect(self.handle_thread_log)
                self.pytchat_listener_thread.start()

                self.log_user("✅ Enhanced PyTchat listener started successfully!", "🚀")
                self.log_user("⏳ Menunggu 3 detik untuk skip komentar lama...", "🔄")

            else:  # TikTok
                nick = self.cfg.get("tiktok_nickname", "").strip()
                if not nick:
                    self.log_error("TikTok username belum diisi.")
                    return
                
                self.log_user(f"Starting TikTok listener for @{nick}...", "🚀")
                
                # Use the TikTok listener thread
                self.tiktok_listener_thread = TikTokListenerThread(nick)
                
                # 🔥 PERBAIKAN UTAMA: Reset untuk session baru
                self.tiktok_listener_thread.reset_for_new_session()
                
                self.tiktok_listener_thread.newComment.connect(self._enqueue)
                self.tiktok_listener_thread.logMessage.connect(self.handle_thread_log)
                self.tiktok_listener_thread.start()
                
                self.log_user("✅ TikTok listener started successfully!", "🚀")
                self.log_user("⏳ Menunggu 5 detik untuk skip komentar lama...", "🔄")

        except Exception as e:
            self.log_user(f"Failed to start enhanced listener: {e}", "❌")
            self.log_error(f"Failed to start listener: {str(e)}")
            import traceback
            self.log_error(f"Traceback: {traceback.format_exc()}")
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
            self.log_user(f"📊 Today's quota: {used:.1f}/{limit} credits", "📊")

            if remaining <= 0:
                self.log_user("❌ Kuota habis! Silakan tunggu besok.", "⚠️")
                self.stop()
                return

            self._track_usage()
            self.usage_timer.start()

        # Final status
        self.log_user("🤖 Auto-Reply siap! (Process-Based Mode) Menunggu komentar dengan trigger...", "✅")
        self.status.setText("✅ Auto-Reply Active (Process-Based)")
        self.log_system("Auto-Reply Basic ready with isolated process.")

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

                if self.pytchat_listener_thread:
                    self.pytchat_listener_thread._seen.clear()

                self.log_view.append(f"[INFO] Buffer cleaned: {len(lines)} → {len(unique_entries)} lines")
        except Exception as e:
            self.log_view.append(f"[WARN] Gagal bersihkan buffer: {e}")

    def _clear_pytchat_cache(self):
        """Clear PyTchat cache dan temporary files untuk memastikan fresh start"""
        try:
            import shutil
            import tempfile
            
            # Clear common PyTchat cache locations
            cache_dirs = [
                Path.home() / ".cache" / "pytchat",
                Path(tempfile.gettempdir()) / "pytchat", 
                Path("temp") / "pytchat_cache",
                Path("cache") / "pytchat"
            ]
            
            for cache_dir in cache_dirs:
                if cache_dir.exists():
                    try:
                        shutil.rmtree(cache_dir)
                        self.log_debug(f"Cleared cache: {cache_dir}")
                    except Exception as e:
                        self.log_debug(f"Failed to clear cache {cache_dir}: {e}")
            
            # Clear local buffer files
            buffer_files = [
                CHAT_BUFFER,
                Path("temp") / "chat_history.json",
                Path("temp") / "message_buffer.txt"
            ]
            
            for buffer_file in buffer_files:
                if buffer_file.exists():
                    try:
                        buffer_file.unlink()
                        self.log_debug(f"Cleared buffer: {buffer_file}")
                    except Exception as e:
                        self.log_debug(f"Failed to clear buffer {buffer_file}: {e}")
                        
            self.log_user("🧹 PyTchat cache cleared for new session", "🗑️")
            
        except Exception as e:
            self.log_debug(f"Error clearing PyTchat cache: {e}")

    def stop(self):
        """Stop all running background processes and threads."""
        logger.info("Stopping CoHost Basic mode...")
        self.status.setText("⏹️ Stopped")
        
        # Stop credit timer
        if hasattr(self, 'credit_timer'):
            self.credit_timer.stop()

        # Stop enhanced pytchat listener thread
        if hasattr(self, 'pytchat_listener_thread') and self.pytchat_listener_thread:
            self.pytchat_listener_thread.stop()
            self.pytchat_listener_thread.quit()
            self.pytchat_listener_thread.wait(3000)
            self.pytchat_listener_thread = None
            self.log_user("Enhanced PyTchat listener stopped", "⏹️")

        # Stop queue monitoring threads (legacy)
        if hasattr(self, 'queue_monitor_thread') and self.queue_monitor_thread:
            self.queue_monitor_thread.stop()
            self.queue_monitor_thread.quit()
            self.queue_monitor_thread.wait(1000)
            self.queue_monitor_thread = None
        
        if hasattr(self, 'log_monitor_thread') and self.log_monitor_thread:
            self.log_monitor_thread.stop()
            self.log_monitor_thread.quit()
            self.log_monitor_thread.wait(1000)
            self.log_monitor_thread = None

        # Terminate the listener process
        if self.yt_listener_process and self.yt_listener_process.is_alive():
            self.log_debug("Terminating pytchat listener process...")
            self.yt_listener_process.terminate()
            self.yt_listener_process.join(timeout=2) # Wait for it to die
            self.yt_listener_process = None
            self.log_debug("Pytchat listener process terminated.")

        # Clean up queues
        if self.message_queue:
            self.message_queue.close()
            self.message_queue.join_thread()
        if self.log_queue:
            self.log_queue.close()
            self.log_queue.join_thread()
        
        # Stop TikTok listener thread
        if hasattr(self, 'tiktok_listener_thread') and self.tiktok_listener_thread:
            self.tiktok_listener_thread.stop()
            self.tiktok_listener_thread.quit()
            self.tiktok_listener_thread.wait(3000)
            self.tiktok_listener_thread = None
            self.log_user("TikTok listener stopped", "⏹️")
        
        # Stop legacy TikTok Thread (for compatibility)
        if self.tiktok_thread:
            self.tiktok_thread.stop()
            self.tiktok_thread = None

        # Stop usage tracking
        stop_usage_tracking("cohost_basic")

        self.reply_busy = False
        self.log_user("⏹️ Auto-reply stopped.", "🛑")

    def closeEvent(self, event: QCloseEvent):
        """Ensure threads are cleaned up on window close."""
        self.log_debug("CohostTab close event triggered. Stopping threads.")
        # 🔧 Clean up all reply threads first
        self._cleanup_all_threads()
        self.stop()
        super().closeEvent(event)

    def handle_thread_log(self, level, message):
        """Receives log messages from the listener thread."""
        if level == "ERROR":
            self.log_error(message)
        elif level == "SUCCESS":
            self.log_user(message, "✅")
        else:
            self.log_debug(f"[PytchatThread] {message}")

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

    def _prepare_text_for_tts(self, text):
        """🔥 NEW: Prepare text specifically for TTS - separate from saving full text"""
        
        # Clean text for TTS
        cleaned_text = clean_text_for_tts(text)
        
        # 🔥 ENHANCED: More generous TTS limit for complete responses
        TTS_MAX_LENGTH = 800  # Increased from 600 for longer natural responses
        if len(cleaned_text) > TTS_MAX_LENGTH:
            self.log_debug(f"TTS text too long ({len(cleaned_text)} chars), finding natural break...")
            
            # 🎯 IMPROVED: Better natural break point detection
            break_points = []
            
            # Priority 1: Sentence endings
            for i in range(min(len(cleaned_text), TTS_MAX_LENGTH - 50), 0, -1):
                if cleaned_text[i] in '.!?':
                    break_points.append(i + 1)
                    break  # Use the first (closest to limit) sentence end
            
            # Priority 2: Clause endings (commas) if no sentence break found
            if not break_points:
                for i in range(min(len(cleaned_text), TTS_MAX_LENGTH - 30), 0, -1):
                    if cleaned_text[i] == ',':
                        break_points.append(i + 1)
                        break
            
            # Priority 3: Word boundaries if no punctuation break found
            if not break_points:
                for i in range(min(len(cleaned_text), TTS_MAX_LENGTH - 10), 0, -1):
                    if cleaned_text[i] == ' ':
                        break_points.append(i)
                        break
            
            # Apply the best break point found
            if break_points:
                cut_point = break_points[0]
                final_text = cleaned_text[:cut_point].rstrip()
                self.log_debug(f"TTS text cut at natural break: {len(final_text)} chars")
            else:
                # Last resort: hard cut but without "..."
                final_text = cleaned_text[:TTS_MAX_LENGTH-10].rstrip()
                self.log_debug(f"TTS text hard cut: {len(final_text)} chars")
                
            return final_text
        else:
            self.log_debug(f"TTS length OK: {len(cleaned_text)} chars")
            return cleaned_text

    def _save_interaction(self, author, message, reply):
        """Simpan interaksi ke log dan viewer memory dengan logging yang lebih baik"""
        try:
            # PERBAIKAN: Pastikan folder log ada
            COHOST_LOG.parent.mkdir(exist_ok=True)
            
            # PERBAIKAN: Simpan dengan timestamp untuk tracking yang lebih baik
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(str(COHOST_LOG), "a", encoding="utf-8") as f:
                f.write(f"{timestamp}\t{author}\t{message}\t{reply}\n")
                
            # PERBAIKAN: Log ke UI dengan format yang jelas
            self.log_user(f"💾 Interaction saved: {author} → {reply[:50]}...", "📝")
            
        except Exception as e:
            self.log_view.append(f"[WARN] Gagal save log: {e}")

        # Update viewer memory
        if self.viewer_memory:
            self.viewer_memory.add_interaction(author, message, reply)

        # Update recent messages untuk spam prevention
        self.recent_messages.append((author, message))
        if len(self.recent_messages) > self.message_history_limit:
            self.recent_messages.pop(0)
            
        # PERBAIKAN: Emit signal untuk log tab dengan data lengkap
        try:
            self.replyGenerated.emit(author, message, reply)
            self.log_debug(f"Signal replyGenerated emitted: {author} - {reply[:30]}...")
        except Exception as e:
            self.log_error(f"Error emitting replyGenerated signal: {e}")

    def _on_reply(self, author, message, reply):
        """Handle reply dengan logging dan tracking yang lebih baik"""
        self.log_debug(f"_on_reply called: {author} - {reply}")

        if not reply:
            self.log_user("⚠️ Failed to generate reply", "❌")
            QTimer.singleShot(self.reply_delay, self._process_next_in_batch)
            return

        try:
            self.log_debug(f"Processing reply...")

            # Get AI reply from API server
            ai_reply = self._get_ai_reply(message)
            if ai_reply:
                reply = ai_reply

            # TAMBAHKAN TRACKING AI USAGE DI SINI:
            try:
                # Track AI usage dengan sistem kredit baru
                from modules_server.real_credit_tracker import credit_tracker
                estimated_tokens = len(reply.split()) * 1.3
                credits_used = credit_tracker.track_ai_usage(int(estimated_tokens))
                logger.info(f"AI Reply tracked: {len(reply)} chars, ~{estimated_tokens:.0f} tokens = {credits_used:.4f} credits")
            except Exception as tracking_error:
                logger.error(f"Error tracking AI usage: {tracking_error}")
                # Jangan gagalkan reply hanya karena tracking error

            # 🔥 PERBAIKAN: Save full text first, then truncate for TTS
            # Save complete interaction with full text
            self._save_interaction(author, message, reply)
            
            # Store the full reply for display
            full_reply = reply
            
            # Now truncate ONLY for TTS processing
            tts_reply = self._prepare_text_for_tts(reply)
            
            # PERBAIKAN: Tampilkan interaction detail dengan format yang jelas
            self.log_user(f"👤 {author}: {message}", "💬")
            self.log_user(f"🤖 AI Reply: {full_reply}", "🎯")
            
            # Update overlay with full text
            if hasattr(self.window(), "overlay_tab"):
                self.window().overlay_tab.update_overlay(author, full_reply)

            self.log_debug(f"Starting TTS...")
            self.ttsAboutToStart.emit()

            # PERBAIKAN KRITIKAL: Simpan karakter count untuk tracking
            self.current_reply_char_count = len(tts_reply)

            # TTS dengan text yang sudah di-truncate khusus untuk TTS
            self._do_async_tts(tts_reply)

            # PERBAIKAN: Track activity untuk license tracking
            register_activity("cohost_basic")

        except Exception as e:
            self.log_error(f"Error in _on_reply: {e}", show_user=False)
            import traceback
            traceback.print_exc()
            self._cleanup_tts_state()

    def _get_ai_reply(self, message):
        """Get AI reply from API server as fallback"""
        try:
            # Implementasi sederhana untuk fallback AI reply
            # Bisa dikembangkan lebih lanjut jika diperlukan
            return None  # Return None untuk menggunakan reply dari ReplyThread
        except Exception as e:
            self.log_debug(f"_get_ai_reply error: {e}")
            return None

    def _do_async_tts(self, text):
        """TTS asynchronous dengan queue control yang ketat"""
        import threading
        from PyQt6.QtCore import QTimer

        # 🎯 ENHANCED: Clean text for TTS before processing
        cleaned_text = clean_text_for_tts(text)
        if not cleaned_text:
            self.log_debug("Text became empty after cleaning, skipping TTS")
            self._handle_tts_complete()
            return

        def tts_worker():
            """Worker function untuk TTS di thread terpisah"""
            try:
                code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
                voice_model = self.voice_cb.currentData()

                self.log_debug(f"TTS worker started: {cleaned_text[:30]}...")
                self.log_debug(f"Using voice from UI: {voice_model}")

                # PERBAIKAN: Tandai sedang TTS untuk mencegah overlap
                self.tts_active = True

                # Import speak di dalam worker untuk menghindari conflict
                from modules_server.tts_engine import speak

                # TTS blocking call, tapi di thread terpisah
                # PERBAIKAN KRITIKAL: Panggil speak tanpa callback seperti di kode lama yang work
                # Callback akan ditangani di worker thread setelah speak selesai
                speak(cleaned_text, code, voice_model)
                
                self.log_debug(f"TTS worker completed")
                
                # PERBAIKAN KRITIKAL: Callback ke main thread menggunakan QTimer
                # Ini adalah kunci dari perbaikan yang bekerja di kode lama
                QTimer.singleShot(0, self._handle_tts_complete)
                
                self.log_debug(f"TTS worker completed (waiting for callback)")

            except Exception as e:
                self.log_error(f"TTS worker error: {e}")
                # Tetap callback untuk melanjutkan batch
                QTimer.singleShot(500, self._handle_tts_complete)
                # PERBAIKAN: Reset flag TTS aktif jika error
                self.tts_active = False

        # PERBAIKAN: Cek apakah sedang ada TTS yang berjalan
        if hasattr(self, 'tts_active') and self.tts_active:
            self.log_debug("TTS masih berjalan, menunda...")
            # PERBAIKAN: Tunggu lebih lama untuk memastikan TTS sebelumnya selesai
            QTimer.singleShot(1000, lambda: self._do_async_tts(text))
            return

        # Jalankan TTS di thread daemon terpisah
        tts_thread = threading.Thread(target=tts_worker, daemon=True)
        tts_thread.start()

        self.log_debug(f"TTS thread started for: {text[:30]}...")

    def _handle_tts_complete(self):
        """Handle TTS complete dengan kontrol queue yang lebih ketat"""
        self.log_debug("TTS completed, continuing batch...")
        self.ttsFinished.emit()

        # PERBAIKAN: Reset flag TTS aktif
        self.tts_active = False

        # PERBAIKAN KRITIKAL: Menggunakan batch_timer dengan delay yang sesuai
        # Ini adalah kunci dari perbaikan yang bekerja di kode lama
        self.batch_timer.stop()
        self.log_debug(f"Starting batch timer with delay: {self.reply_delay}ms")
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
        
        # ✅ PERBAIKAN KRITIKAL: Cek apakah auto-reply masih aktif sebelum lanjut queue
        if not self.reply_busy:
            self.log_debug("Auto-reply stopped, clearing remaining queue")
            self.reply_queue.clear()
            self.log_user("⏹️ Auto-reply stopped.", "🛑")
            return
        
        # Langsung cek apakah ada queue lagi
        if self.reply_queue:
            # Menggunakan delay sesuai dengan pengaturan cooldown dari UI
            # Ini sesuai dengan implementasi pada kode lama yang sudah work
            delay_ms = self.cooldown_duration * 1000 if self.cooldown_duration > 0 else 1000
            queue_size = len(self.reply_queue)
            self.log_debug(f"Queue tersisa: {queue_size} item, delay {delay_ms}ms")
            self.log_user(f"⏳ Waiting {self.cooldown_duration}s before processing next queue ({queue_size} items)...", "⏱️")
            
            # PERBAIKAN KRITIKAL: Pastikan batch_timer tidak aktif sebelum memulai timer baru
            if hasattr(self, 'batch_timer') and self.batch_timer.isActive():
                self.batch_timer.stop()
                
            # Gunakan QTimer.singleShot untuk memastikan timer berjalan dengan benar
            QTimer.singleShot(delay_ms, self._start_batch)
        else:
            self.log_user("✅ Ready to receive new comments", "🤖")

    def _end_cooldown(self):
        """Fungsi ini tidak dipakai lagi karena tidak ada cooldown global."""
        # Method ini dikosongkan karena sistem cooldown global sudah dihapus
        # Delay antar batch sekarang dihandle di _end_batch()
        self.log_debug("_end_cooldown() called but not used (legacy method)")
        pass

    def _cleanup_tts_state(self):
        """Cleanup state saat error atau timeout"""
        self.ttsFinished.emit()
        # PERBAIKAN: Reset flag TTS aktif untuk memastikan tidak ada TTS yang tertunda
        self.tts_active = False
        self.reply_busy = False

        if hasattr(self, 'tts_safety_timer') and self.tts_safety_timer.isActive():
            self.tts_safety_timer.stop()

        # PERBAIKAN: Tunggu lebih cepat sebelum memproses pesan berikutnya
        QTimer.singleShot(500, self._process_next_in_batch)

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
            self.log_view.append(f"[CLEANUP] Removed tracking for {len(expired_authors)} old authors")

    def _track_usage(self):
        """Track usage dengan FORCE credit deduction - pastikan kredit berkurang real-time"""
        try:
            # Cek apakah debug mode (skip tracking)
            if self.cfg.get("debug_mode", False):
                self.log_user("Developer Mode: credits not enforced", "🔧")
                return
            
            # 🔥 FORCE immediate credit deduction untuk AI dan TTS usage
            tts_chars = getattr(self, 'current_reply_char_count', 100)
            tts_credits = tts_chars * 1.0 / 100    # ✅ DINAIKKAN: 0.2 → 1.0 kredit per 100 karakter (5x lipat)
            ai_credits = 100 * 1.5 / 100          # ✅ DINAIKKAN: 0.3 → 1.5 kredit per 100 token (5x lipat)
            total_credits = tts_credits + ai_credits
            
            self.log_debug(f"💳 FORCING credit deduction: TTS={tts_credits:.4f}, AI={ai_credits:.4f}, Total={total_credits:.4f}")
            
            # Force TTS deduction
            if tts_credits > 0:
                tts_success = track_usage_with_forced_deduction(
                    "TTS", 
                    tts_credits, 
                    f"TTS processing {tts_chars} characters"
                )
                if not tts_success:
                    self.log_error("❌ TTS credit deduction FAILED!")
            
            # Force AI deduction
            if ai_credits > 0:
                ai_success = track_usage_with_forced_deduction(
                    "AI", 
                    ai_credits, 
                    "AI reply generation (100 tokens)"
                )
                if not ai_success:
                    self.log_error("❌ AI credit deduction FAILED!")
            
            # Update session stats
            if not hasattr(self, 'session_usage'):
                self.session_usage = {"tts_chars": 0, "ai_requests": 0, "total_credits_used": 0}
            
            self.session_usage["tts_chars"] += tts_chars
            self.session_usage["ai_requests"] += 1
            self.session_usage["total_credits_used"] += total_credits
            
            # Get updated usage from credit tracker
            usage = credit_tracker.get_daily_usage()
            used_hours = usage.get("total_hours", 0)
            limit_hours = usage.get("limit_hours", 10)
            remaining = limit_hours - used_hours
            
            # Log penggunaan saat ini dengan lebih detail
            components = usage.get("components", {})
            self.log_user(
                f"📊 Usage: {used_hours:.2f}/{limit_hours}h "
                f"(STT: {components.get('stt_seconds', 0):.0f}s, "
                f"TTS: {components.get('tts_characters', 0)} chars, "
                f"AI: {components.get('ai_requests', 0)} req)",
                "📈"
            )
            
            # Log session totals
            self.log_debug(f"💰 Session total: {self.session_usage.get('total_credits_used', 0):.4f} credits used")
            
            # Warning jika mendekati limit
            if remaining < 1:  # Kurang dari 1 jam
                self.log_user(f"⚠️ Remaining time: {remaining:.1f} hours", "⏰")
            
            # Force UI credit update
            self._force_credit_display_update()
            
        except Exception as e:
            logger.error(f"Error in FORCE usage tracking: {e}")
            self.log_user("Error in force usage tracking", "⚠️")

    def _force_credit_display_update(self):
        """Force update credit display in UI with latest balance"""
        try:
            from modules_server.real_credit_tracker import get_current_credit_balance
            
            # Get fresh balance from VPS or local
            current_balance = get_current_credit_balance()
            
            if current_balance > 0:
                self.log_user(f"💰 Current credits: {current_balance:.2f} credits", "💳")
            else:
                self.log_user("❌ Credits depleted! Please top up", "⚠️")
                
            # Update any credit display widgets if they exist
            if hasattr(self, 'credit_label'):
                self.credit_label.setText(f"Credits: {current_balance:.2f} credits")
                
            # Force update profile tab if exists
            main_window = self.window()
            if hasattr(main_window, 'profile_tab'):
                main_window.profile_tab.force_refresh()
                
        except Exception as e:
            self.log_debug(f"Error forcing credit display update: {e}")

    def show_memory_stats(self):
        """Tampilkan statistik viewer memory"""
        if not hasattr(self, 'viewer_memory'):
            self.log_view.append("[ERROR] Viewer memory not available")
            return
        
        total_viewers = len(self.viewer_memory.memory_data)
        new_viewers = sum(1 for v in self.viewer_memory.memory_data.values() if v['status'] == 'new')
        regular_viewers = sum(1 for v in self.viewer_memory.memory_data.values() if v['status'] == 'regular')
        vip_viewers = sum(1 for v in self.viewer_memory.memory_data.values() if v['status'] == 'vip')
        
        stats_msg = f"[VIEWER MEMORY STATS]\nTotal Viewers: {total_viewers}\n- New: {new_viewers}\n- Regular: {regular_viewers}\n- VIP: {vip_viewers}\nData will auto-cleanup after 30 days of inactivity"
        
        self.log_view.append(stats_msg)

    def _check_credit_before_start(self):
        """Cek kredit/demo status sebelum start dengan logika yang benar."""
        # Skip semua checking untuk mode development/testing
        if self.cfg.get("debug_mode", False) or self._is_dev_user():
            return True
        if hasattr(self.window(), 'license_validator') and self.window().license_validator.testing_mode:
            return True

        try:
            # Sumber kebenaran satu-satunya adalah file status yang disinkronkan dari server
            subscription_file = Path("config/subscription_status.json")
            if not subscription_file.exists():
                QMessageBox.warning(self, "Status Not Found", "Subscription status not found!\n\nPlease login again or try demo.")
                return False

            with open(subscription_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            status = data.get("status", "pending")
            
            # KASUS 1: Demo mode aktif
            if status == "demo":
                expire_date_str = data.get("expire_date")
                if not expire_date_str:
                    self.log_user("🎮 Demo Mode Active (no expiration date)", "✅")
                    return True
                
                # Cek jika demo sudah expired
                try:
                    # Handle timezone-aware and naive datetime objects
                    if '+' in expire_date_str or 'Z' in expire_date_str:
                        from datetime import timezone
                        expire_date = datetime.fromisoformat(expire_date_str.replace('Z', '+00:00'))
                        now_time = datetime.now(timezone.utc)
                    else:
                        expire_date = datetime.fromisoformat(expire_date_str)
                        now_time = datetime.now()

                    if now_time < expire_date:
                        remaining = (expire_date - now_time).total_seconds() / 60
                        self.log_user(f"🎮 Demo Mode Active - Remaining: {int(remaining)} minutes", "✅")
                        return True
                    else:
                        QMessageBox.warning(self, "Demo Expired", "Your demo session has ended.\nPlease purchase credits to continue.")
                        return False
                except Exception as e:
                    self.log_error(f"Error parsing demo expire date: {e}")
                    return False # Jangan izinkan jika tanggal demo error

            # KASUS 2: Status berbayar (paid atau active)
            elif status in ["paid", "active"]:
                credits = float(data.get("credit_balance", data.get("hours_credit", 0)))
                if credits >= 50:  # Minimal 50 kredit untuk Basic Mode
                    self.log_user(f"💰 Credits available: {credits:.1f} credits", "✅")
                    return True
                elif credits > 0:
                    QMessageBox.warning(self, "Insufficient Credits", f"You have {credits:.1f} credits, but need at least 50 credits to use Basic Mode.\nPlease purchase more credits to continue.")
                    return False
                else:
                    QMessageBox.warning(self, "Credits Depleted", "Your credits have been depleted.\nPlease purchase more to continue.")
                    return False
            
            # KASUS 3: Status lain (pending, expired, dll)
            else:
                QMessageBox.warning(self, "Subscription Required", f"Your account status is '{status}'.\nPlease activate a demo or purchase credits to use this feature.")
                return False

        except Exception as e:
            self.log_error(f"Critical error in _check_credit_before_start: {e}")
            QMessageBox.critical(self, "Error", f"A critical error occurred while checking your subscription: {e}")
            return False

    def _check_credit(self):
        """Cek kredit/demo status setiap menit saat aktif - PERBAIKAN UNTUK DEMO MODE"""
        if not self.reply_busy:
            return
        
        # ✅ PERBAIKAN: Cek status demo terlebih dahulu
        try:
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists():
                with open(subscription_file, "r", encoding="utf-8") as f:
                    subscription_data = json.load(f)
                
                status = subscription_data.get("status", "")
                
                # KASUS 1: Demo mode - cek apakah masih aktif
                if status == "demo":
                    expire_date_str = subscription_data.get("expire_date", "")
                    if expire_date_str:
                        try:
                            from datetime import datetime, timezone
                            if '+' in expire_date_str or 'Z' in expire_date_str:
                                expire_date = datetime.fromisoformat(expire_date_str.replace('Z', '+00:00'))
                                now_time = datetime.now(timezone.utc)
                            else:
                                expire_date = datetime.fromisoformat(expire_date_str)
                                now_time = datetime.now()
                            
                            if now_time < expire_date:
                                # Demo masih aktif, jangan hentikan
                                remaining_minutes = int((expire_date - now_time).total_seconds() / 60)
                                if remaining_minutes <= 5:  # Warning 5 menit terakhir
                                    self.log_user(f"⏰ Demo will end in {remaining_minutes} minutes", "⚠️")
                                return  # Demo masih aktif, lanjutkan
                            else:
                                # Demo session ended
                                self.stop()
                                QMessageBox.information(
                                    self,
                                    "Demo Ended",
                                    "Demo mode 30 minutes has ended!\n\n"
                                    "Auto-reply has been stopped.\n"
                                    "Please purchase credits to continue or try demo again tomorrow."
                                )
                                self.status.setText("⏰ Demo Ended")
                                self.log_user("⏰ Demo session ended - Auto-reply stopped", "🎮")
                                return
                        except Exception as e:
                            self.log_error(f"Error parsing demo expire date in periodic check: {e}")
                            # Jika error, tetap lanjutkan untuk safety
                            return
                    else:
                        # Demo tanpa expire date, tetap lanjutkan
                        return
                
                # KASUS 2: Status paid - cek kredit normal
                elif status == "paid":
                    hours_credit = float(subscription_data.get("hours_credit", 0))
                    if hours_credit <= 0:
                        self.stop()
                        QMessageBox.warning(
                            self,
                            "Credits Depleted",
                            "Your hour credits have been depleted!\n\n"
                            "Auto-reply has been stopped.\n"
                            "Please purchase credits to continue."
                        )
                        self.status.setText("❌ Credits Depleted")
                        self.log_user("💳 Credits depleted - Auto-reply stopped", "❌")
                        return
                    elif hours_credit < 1:  # Warning jika kredit rendah
                        self.log_user(f"⚠️ Sisa kredit: {hours_credit:.1f} kredit", "💳")
                
                # KASUS 3: Status lainnya - hentikan
                else:
                    self.stop()
                    QMessageBox.warning(
                        self,
                        "Invalid Status",
                        f"Invalid account status: {status}\n\n"
                        "Auto-reply has been stopped.\n"
                        "Please login again."
                    )
                    self.status.setText("❌ Invalid Status")
                    self.log_user(f"⚠️ Status {status} invalid - Auto-reply stopped", "❌")
                    return
            else:
                # File subscription tidak ada - hentikan
                self.stop()
                QMessageBox.warning(
                    self,
                    "Status Not Found",
                    "Subscription status file not found!\n\n"
                    "Auto-reply has been stopped.\n"
                    "Please login again."
                )
                self.status.setText("❌ Status Not Found")
                self.log_user("📄 Subscription status not found - Auto-reply stopped", "❌")
                return
                
        except Exception as e:
            self.log_error(f"Error in periodic credit check: {e}")
            # Fallback ke sistem lama jika error parsing
            if not self.hour_tracker.check_credit():
                self.stop()
                QMessageBox.warning(
                    self,
                    "Credits Depleted",
                    "Your hour credits have been depleted!\n\n"
                    "Auto-reply has been stopped.\n"
                    "Please purchase credits to continue."
                )
            self.status.setText("❌ Credits Depleted")
            self.log_view.append("[SYSTEM] Auto-reply stopped - credits depleted")

    def update_credit_display(self):
        """Update tampilan kredit di UI."""
        try:
            from modules_server.real_credit_tracker import credit_tracker
            
            # Ambil info kredit
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists():
                with open(subscription_file, 'r', encoding='utf-8') as f:
                    sub_data = json.load(f)
                    current_credit = float(sub_data.get("hours_credit", 0))
                    
                    # Update status label jika ada
                    if hasattr(self, 'credit_status_label'):
                        if current_credit < 1.0:
                            self.credit_status_label.setText(f"❌ Kredit: {current_credit:.1f} (Tidak cukup)")
                            self.credit_status_label.setStyleSheet("color: red; font-weight: bold;")
                        elif current_credit < 5.0:
                            self.credit_status_label.setText(f"⚠️ Kredit: {current_credit:.1f} (Rendah)")
                            self.credit_status_label.setStyleSheet("color: orange; font-weight: bold;")
                        else:
                            self.credit_status_label.setText(f"✅ Kredit: {current_credit:.1f}")
                            self.credit_status_label.setStyleSheet("color: green;")
            
        except Exception as e:
            logger.error(f"Error updating credit display: {e}")

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
            self.log_view.append(f"[RESET] {interaction_count} daily interactions reset")
        
        self.log_view.append("[RESET] All viewers can ask questions about any topic again")

    def check_daily_limit(self):
        """Cek batas penggunaan harian"""
        try:
            # Get current usage
            used_hours = float(self.license_data.get("today_usage", 0))
            limit_hours = 12 if self.license_data.get("package") == "pro" else 5
            
            if used_hours >= limit_hours:
                QMessageBox.warning(
                    self,
                    "Daily Limit Reached",
                    f"Daily usage limit of {limit_hours} credits/day has been reached.\n\n"
                    f"Total usage: {used_hours:.2f} credits\n"
                    f"Please wait until tomorrow or upgrade to Pro package."
                )
                return False
                
            # Check remaining time
            remaining = limit_hours - used_hours
            if remaining < 1:  # Kurang dari 1 kredit
                self.log_user(f"⚠️ Remaining credits: {remaining:.1f} credits", "⏰")
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking daily limit: {e}")
            return True

    def check_credit(self):
        """Cek kredit tersisa"""
        try:
            hours_left = float(self.license_data.get("hours_credit", 0))
            
            if hours_left <= 0:
                QMessageBox.warning(
                    self,
                    "Credits Depleted",
                    "Your credits are depleted!\n\n"
                    "Please purchase credits to continue."
                )
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking credit: {e}")
            return False

    def _enqueue(self, author, message):
        """Process comment dengan validasi status langganan yang benar."""

        # ✅ PERBAIKAN UTAMA: Validasi timestamp untuk mencegah pesan lama dari cache
        current_time = time.time()
        
        # Skip pesan duplikat yang sudah pernah diproses dalam session ini
        message_signature = f"{author}:{message}"
        if hasattr(self, 'processed_messages_session'):
            if message_signature in self.processed_messages_session:
                self.log_debug(f"Skipping duplicate message from session: {author}")
                return
        else:
            self.processed_messages_session = set()
            
        # Tambahkan ke tracking session
        self.processed_messages_session.add(message_signature)
        
        # Cleanup session tracking jika terlalu besar (>1000 entries)
        if len(self.processed_messages_session) > 1000:
            # Keep only recent 500 entries
            recent_entries = list(self.processed_messages_session)[-500:]
            self.processed_messages_session = set(recent_entries)

        # ✅ PERBAIKAN UTAMA: Log komentar yang masuk untuk user visibility
        self.log_user(f"📨 Incoming comment from {author}: {message}", "👁️")

        # ✅ BARU: Log SEMUA komentar ke cohost_log.txt untuk Reply Log Tab
        # Tidak peduli ada trigger atau tidak - semua komentar tercatat
        try:
            COHOST_LOG.parent.mkdir(exist_ok=True)
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Log dengan format: timestamp, author, message, status (trigger/no-trigger)
            with open(str(COHOST_LOG), "a", encoding="utf-8") as f:
                # Cek apakah ada trigger untuk menandai status
                has_trigger = self._has_trigger(message)
                status = "TRIGGER" if has_trigger else "NO-TRIGGER"
                f.write(f"{timestamp}\t{author}\t{message}\t[{status}] Komentar diterima\n")
                
            self.log_debug(f"💾 Logged comment to cohost_log.txt: {author}")
            
        except Exception as e:
            self.log_debug(f"Failed to log comment: {e}")

        # Skip if message or author is empty
        if not author or not message:
            self.log_debug(f"Skipping empty message/author")
            return

        # Skip if auto-reply not active
        if not self.reply_busy:
            self.log_debug(f"Auto-reply not active, skipping")
            return

        # Skip if conversation active (hold-to-talk)
        if self.conversation_active:
            self.log_debug(f"Hold-to-talk active, skipping auto-reply")
            return

        # Check trigger words - TETAP DIBUTUHKAN untuk memproses balasan
        if not self._has_trigger(message):
            self.log_debug(f"No trigger detected in: {message}")
            return

        self.log_user("✅ Trigger detected! Processing reply...", "🔔")

        # ✅ PERBAIKAN: Validasi langganan yang disederhanakan untuk mode demo
        try:
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists():
                with open(subscription_file, "r", encoding="utf-8") as f:
                    subscription_data = json.load(f)

                status = subscription_data.get("status", "")
                
                # KASUS 1: Mode demo - cek apakah masih aktif (lebih permisif)
                if status == "demo":
                    expire_date_str = subscription_data.get("expire_date", "")
                    if expire_date_str:
                        try:
                            # Handle timezone dengan benar
                            if '+' in expire_date_str or 'Z' in expire_date_str:
                                from datetime import timezone
                                expire_date = datetime.fromisoformat(expire_date_str.replace('Z', '+00:00'))
                                now_time = datetime.now(timezone.utc)
                            else:
                                expire_date = datetime.fromisoformat(expire_date_str)
                                now_time = datetime.now()

                            if expire_date > now_time:
                                remaining = expire_date - now_time
                                mins_left = int(remaining.total_seconds() / 60)
                                
                                # Batasi maksimal 30 menit untuk demo
                                if mins_left > 30:
                                    mins_left = 30
                                
                                self.log_debug(f"🎮 Demo aktif - sisa: {mins_left} menit")
                                # Lanjutkan pemrosesan untuk demo
                            else:
                                self.log_user("⏰ Demo has ended", "⏰")
                                return  # Hanya return, jangan stop
                        except ValueError as e:
                            self.log_debug(f"Error parsing demo date: {e}")
                            # Untuk demo, tetap lanjutkan meskipun ada error parsing
                            self.log_debug("Demo date error - tetap lanjutkan untuk development")
                    else:
                        self.log_debug("Demo tanpa expire date - lanjutkan untuk development")

                # KASUS 2: User berbayar dengan kredit
                elif status == "paid":
                    hours_credit = float(subscription_data.get("hours_credit", 0))
                    if hours_credit > 0:
                        self.log_debug(f"User berbayar - kredit: {hours_credit} jam")
                    else:
                        self.log_user("⚠️ Credits depleted", "💳")
                        return  # Hanya return, jangan stop
                
                # KASUS 3: Status lain - tetap coba proses untuk development
                else:
                    self.log_debug(f"Status: {status} - lanjutkan untuk development mode")

            else:
                # Tidak ada file subscription - untuk development mode, tetap lanjutkan
                self.log_debug("No subscription file - continue for development")

        except Exception as e:
            self.log_debug(f"Subscription validation error: {e} - continue anyway")
            # Untuk development, tetap lanjutkan meskipun ada error

        # Cek limit harian per-penonton (hanya jika validasi langganan lolos)
        if self._is_viewer_daily_limit_reached(author, message):
            return

        # Register activity saat ada komentar valid
        register_activity("cohost_basic")      
        self.log_debug(f"Processing comment from {author}: {message}")
        
        # Proses batch
        if self.processing_batch:
            if len(self.reply_queue) < self.max_queue_size:
                self.reply_queue.append((author, message))
                self.log_user(f"📋 Added to queue ({len(self.reply_queue)} items)", "⏳")
            else:
                self.log_user(f"⚠️ Queue full, skipped: {author}", "📋")
            return

        # Jika tidak ada batch, langsung proses
        self.reply_queue = [(author, message)]
        self.log_debug(f"Starting new batch with: {author}")
        self._start_batch()

    def _start_batch(self):
        """Start batch processing"""
        # ✅ PERBAIKAN: Cek apakah auto-reply masih aktif
        if not self.reply_busy:
            self.log_debug("Auto-reply stopped, not starting batch")
            self.reply_queue.clear()
            return
            
        if not self.reply_queue:
            self.log_debug("No queue to process")
            return
            
        self.log_debug(f"Starting batch with {len(self.reply_queue)} items")
        self.log_user("🔄 Processing reply...", "🤖")
        self.processing_batch = True
        self.batch_counter = 0
        self._process_next_in_batch()

    def _process_next_in_batch(self):
        """Process next message dengan kontrol TTS yang lebih ketat"""
        try:
            # PERBAIKAN: Tambahkan try-except untuk menangkap error
            self.log_debug(f"_process_next_in_batch called, queue: {len(self.reply_queue) if hasattr(self, 'reply_queue') else 0}, batch_counter: {self.batch_counter}")
            
            # ✅ PERBAIKAN KRITIKAL: Cek apakah auto-reply masih aktif
            if not self.reply_busy:
                self.log_debug("Auto-reply stopped, ending batch processing")
                self._end_batch()
                return
            
            # PERBAIKAN: Cek apakah TTS masih aktif
            if hasattr(self, 'tts_active') and self.tts_active:
                self.log_debug("TTS masih berjalan, menunda proses batch...")
                # PERBAIKAN: Tunggu lebih lama (1000ms) seperti di kode lama yang sudah work
                QTimer.singleShot(1000, self._process_next_in_batch)
                return
            
            # PERBAIKAN: Cek apakah reply_queue ada dan tidak kosong
            if not hasattr(self, 'reply_queue') or not self.reply_queue or self.batch_counter >= self.batch_size:
                self.log_debug(f"Ending batch - queue empty: {not hasattr(self, 'reply_queue') or not self.reply_queue}, batch full: {self.batch_counter >= self.batch_size}")
                self._end_batch()
                return
                
            # PERBAIKAN: Ambil pesan dari queue dengan error handling
            try:
                author, msg = self.reply_queue.pop(0)
                self.batch_counter += 1
                
                self.log_debug(f"Processing message {self.batch_counter}/{self.batch_size}: {author} - {msg}")
                self._create_reply_thread(author, msg)
            except IndexError:
                self.log_error("Queue empty when trying to process next message")
                self._end_batch()
            except Exception as e:
                self.log_error(f"Error processing message from queue: {e}")
                # Coba lanjutkan dengan pesan berikutnya jika masih ada
                if hasattr(self, 'reply_queue') and self.reply_queue:
                    QTimer.singleShot(500, self._process_next_in_batch)
                else:
                    self._end_batch()
        except Exception as e:
            self.log_error(f"Critical error in _process_next_in_batch: {e}")
            # Fallback - coba end batch
            self._end_batch()

    def _create_reply_thread(self, author, message):
        """🔥 FIXED: Create reply thread and connect signals properly"""
        try:
            # Fix personality combobox reference
            personality = self.person_cb.currentText()
            voice_model = self.voice_cb.currentData()
            language_code = "id-ID" if self.out_lang.currentText() == "Indonesia" else "en-US"
            lang_out = self.out_lang.currentText()
            
            # 🔥 Get viewer preferences for enhanced AI (graceful fallback)
            viewer_prefs = {}
            use_enhanced = False
            
            if self.viewer_memory:
                try:
                    viewer_prefs = self.viewer_memory.get_viewer_preferences(author)
                    # Only use enhanced if we have meaningful data
                    if viewer_prefs and len(viewer_prefs) > 2:  # More than just empty defaults
                        use_enhanced = True
                        self.log_debug(f"Enhanced AI for {author}: mood={viewer_prefs.get('current_mood', 'unknown')}")
                except Exception as e:
                    self.log_debug(f"Viewer preferences error: {e}, using standard AI")
                    viewer_prefs = {}
            
            # 🔥 SIMPLIFIED: Use standard thread with enhanced context if available
            if use_enhanced:
                self.log_debug(f"Creating enhanced reply for {author}")
                
            # ✅ Create thread and connect signals
            reply_thread = ReplyThread(
                author, message, personality, voice_model, 
                language_code, lang_out, self.viewer_memory
            )
            
            # ✅ CRITICAL FIX: Connect finished signal properly with lambda to handle the 3 parameters
            # Menggunakan lambda seperti di kode lama yang sudah work
            reply_thread.finished.connect(lambda a, m, r: self._on_reply(a, m, r))
            
            # ✅ Track thread for cleanup
            if not hasattr(self, 'threads'):
                self.threads = []
            self.threads.append(reply_thread)
            
            # ✅ Auto-cleanup tidak diperlukan karena thread ditangani di threads list
            
            # ✅ Start the thread
            reply_thread.start()
            
            self.log_debug(f"Reply thread started for {author}")
                
        except Exception as e:
            self.log_error(f"Error creating reply thread: {e}")
            # Emergency fallback - create simple reply
            try:
                fallback_reply = f"Halo {author}, maaf ada masalah teknis"
                self._on_reply(author, message, fallback_reply)
            except Exception as fallback_error:
                self.log_error(f"Fallback reply error: {fallback_error}")

    def _cleanup_reply_thread(self, thread):
        """🔧 Clean up finished reply thread"""
        try:
            if hasattr(self, 'active_reply_threads') and thread in self.active_reply_threads:
                self.active_reply_threads.remove(thread)
                self.log_debug(f"Reply thread cleaned up. Active threads: {len(self.active_reply_threads)}")
            
            # Ensure thread is properly finished
            if thread.isRunning():
                thread.quit()
                thread.wait(1000)  # Wait max 1 second
                
        except Exception as e:
            self.log_debug(f"Thread cleanup error: {e}")
    
    def _cleanup_all_threads(self):
        """🔧 Clean up all active threads on shutdown"""
        try:
            if hasattr(self, 'active_reply_threads'):
                self.log_debug(f"Cleaning up {len(self.active_reply_threads)} reply threads...")
                for thread in self.active_reply_threads[:]:  # Copy list to avoid modification during iteration
                    if thread.isRunning():
                        thread.quit()
                        thread.wait(1000)
                    self.active_reply_threads.remove(thread)
                self.log_debug("All reply threads cleaned up")
        except Exception as e:
            self.log_debug(f"Thread cleanup error: {e}")

# ====================================================================
#  Enhanced Reply Thread with Human-like Learning  
# ====================================================================

class EnhancedReplyThread(ReplyThread):
    """Enhanced reply thread with mood awareness and learning"""
    
    def __init__(self, author: str, message: str, personality: str, 
                 voice_model: str, language_code: str, lang_out: str, 
                 viewer_memory=None, viewer_prefs=None):
        # Call parent constructor
        super().__init__(author, message, personality, voice_model, 
                        language_code, lang_out, viewer_memory)
        self.viewer_prefs = viewer_prefs or {}

    def run(self):
        try:
            # Load configuration
            cfg = ConfigManager("config/settings.json")
            extra = cfg.get("custom_context", "").strip()
            lang_label = "Bahasa Indonesia" if self.lang_out == "Indonesia" else "English"

            # 🔥 ENHANCED: Get comprehensive viewer context
            viewer_status = "new"
            viewer_context = ""
            mood_context = ""
            learning_context = ""
            
            if self.viewer_memory:
                viewer_info = self.viewer_memory.get_viewer_info(self.author)
                if viewer_info:
                    viewer_status = viewer_info.get("status", "new")
                    viewer_context = self.viewer_memory.get_recent_context(self.author, limit=3)
                    
                    # Get mood and sentiment context
                    current_mood = self.viewer_prefs.get("current_mood", "stable_engagement")
                    sentiment_trend = self.viewer_prefs.get("sentiment_trend", "neutral")
                    
                    mood_context = f"Current viewer mood: {current_mood}, sentiment trend: {sentiment_trend}"
                    
                    # Get learning-based preferences
                    response_style = self.viewer_prefs.get("response_style", {})
                    preferred_topics = self.viewer_prefs.get("preferred_topics", [])
                    
                    if preferred_topics:
                        learning_context = f"Viewer prefers topics: {', '.join(preferred_topics)}. "
                    
                    if response_style.get("length") == "short":
                        learning_context += "Prefers concise responses. "
                    elif response_style.get("length") == "long":
                        learning_context += "Enjoys detailed explanations. "

            # Enhanced message analysis
            message_lower = self.message.lower()
            
            # 🔥 ENHANCED: Multi-dimensional analysis
            question_type = self._enhanced_intent_detection(message_lower, self.viewer_prefs)
            
            # Build AI prompt with human-like context awareness
            normalized_author = self.author.replace('.', '').replace('_', '').lower()
            display_author = self.author

            # Enhanced platform detection
            is_tiktok = (
                self.author.islower() or
                ('.' not in self.author and '_' not in self.author and len(self.author) <= 15)
            )
            platform_context = "TikTok Live" if is_tiktok else "YouTube Live"

            # 🔥 HUMAN-LIKE PROMPT BUILDING
            base_prompt = (
                f"Kamu adalah AI Co-Host yang sangat natural dan manusiawi dalam berkomunikasi. "
                f"Kamu sedang live streaming {platform_context}. "
                f"Informasi tentang streamer dan karaktermu: {extra}. "
                f"Penonton {display_author} (status: {viewer_status}) berkata: '{self.message}'. "
            )
            
            # Add contextual awareness
            if viewer_context:
                base_prompt += f"\n\nKonteks percakapan sebelumnya: {viewer_context}"
            
            if mood_context:
                base_prompt += f"\n\nSuasana hati viewer: {mood_context}"
            
            if learning_context:
                base_prompt += f"\n\nPeferensi yang dipelajari: {learning_context}"

            # Enhanced response instructions based on analysis
            response_instructions = self._build_human_like_instructions(
                question_type, viewer_status, self.viewer_prefs
            )
            
            base_prompt += response_instructions

            # Generate AI reply with enhanced context
            try:
                reply = generate_reply(base_prompt)
                
                if not reply:
                    reply = self._get_fallback_response(display_author, viewer_status)
                else:
                    # Enhanced reply processing
                    reply = self._process_reply_with_learning(reply, self.viewer_prefs)
                    
                    # Ensure natural name usage
                    if not reply.lower().startswith(self.author.lower()):
                        greeting = self._get_natural_greeting(display_author, viewer_status, self.viewer_prefs)
                        reply = f"{greeting} {reply}"
                
                    # Apply learned response style
                    reply = self._apply_learned_style(reply, self.viewer_prefs)
                        
            except Exception as e:
                reply = self._get_error_response(display_author, str(e))

            self.finished.emit(self.author, self.message, reply)
            
        except Exception as e:
            error_reply = f"Hai {self.author} maaf ada error teknis"
            self.finished.emit(self.author, self.message, error_reply)

    def _enhanced_intent_detection(self, message_lower, viewer_prefs):
        """🔥 Enhanced intent detection using viewer learning data"""
        
        # Get preferred topics for context
        preferred_topics = viewer_prefs.get("preferred_topics", [])
        current_mood = viewer_prefs.get("current_mood", "stable_engagement")
        
        # Basic intent detection
        if any(word in message_lower for word in ["kabar", "apa kabar", "gimana"]):
            intent = "greeting"
        elif any(word in message_lower for word in ["main", "game", "gaming", "rank", "hero"]):
            intent = "gaming"
        elif "?" in message_lower:
            intent = "question"
        elif any(word in message_lower for word in ["halo", "hai", "hello"]):
            intent = "greeting"
        else:
            intent = "general"
        
        # Enhance with mood context
        if current_mood == "potentially_disengaged" and intent == "general":
            intent = "re_engagement_needed"
        elif current_mood == "information_seeking" and intent != "question":
            intent = "curious_general"
        elif current_mood == "highly_engaged":
            intent = f"{intent}_enthusiastic"
            
        return intent

    def _build_human_like_instructions(self, intent, viewer_status, viewer_prefs):
        """Build human-like response instructions based on comprehensive context"""
        
        current_mood = viewer_prefs.get("current_mood", "stable_engagement")
        response_style = viewer_prefs.get("response_style", {})
        preferred_length = response_style.get("length", "short")  # CHANGED: Default to short
        
        base_instruction = "\n\nRESPOND SEPERTI MANUSIA ASLI dengan karakteristik berikut:\n"
        
        # Mood-based response style
        if current_mood == "highly_engaged":
            base_instruction += "- Tunjukkan antusiasme yang genuine dan energi tinggi\n"
        elif current_mood == "potentially_disengaged":
            base_instruction += "- Coba tarik perhatian dengan topik menarik\n"
        elif current_mood == "information_seeking":
            base_instruction += "- Berikan informasi yang helpful dan to-the-point\n"
        
        # Intent-specific instructions
        if "enthusiastic" in intent:
            base_instruction += "- Match energy level viewer yang tinggi\n"
        elif intent == "re_engagement_needed":
            base_instruction += "- Buat percakapan yang engaging dan personal\n"
        
        # 🔥 FIXED: Always force short responses (100 chars max)
        base_instruction += "- WAJIB: Jawab SINGKAT maksimal 100 karakter (1 kalimat pendek)\n"
        base_instruction += "- Hindari penjelasan panjang, fokus pada inti pesan\n"
        base_instruction += "- Gunakan bahasa casual dan natural\n"
        
        # Viewer status context
        if viewer_status == "new":
            base_instruction += "- Buat mereka merasa welcome dengan salam singkat\n"
        elif viewer_status == "vip":
            base_instruction += "- Tunjukkan appreciation singkat\n"
        
        base_instruction += (
            f"\nJawab dalam {self.lang_out} dengan style natural, conversational, dan SANGAT SINGKAT. "
            f"PRIORITAS: Jawaban harus under 100 karakter total."
        )
        
        return base_instruction

    def _get_natural_greeting(self, author, status, viewer_prefs):
        """Get natural greeting based on mood and learned preferences"""
        current_mood = viewer_prefs.get("current_mood", "stable_engagement")
        
        # Mood-aware greetings
        if current_mood == "highly_engaged":
            greetings = [f"Woi {author}!", f"Yoo {author}!", f"Halo {author} semangat banget!"]
        elif current_mood == "potentially_disengaged":
            greetings = [f"Hey {author}", f"Halo {author}, apa kabar?", f"Hi {author}!"]
        elif status == "vip":
            greetings = [f"Wah {author} datang!", f"Halo {author} viewer setia!", f"Yow {author}!"]
        else:
            greetings = [f"Halo {author}", f"Hi {author}", f"Hai {author}"]
        
        import random
        return random.choice(greetings)

    def _process_reply_with_learning(self, reply, viewer_prefs):
        """Process reply using learned patterns - FIXED double reply issue"""
        
        # Apply learned improvements
        response_style = viewer_prefs.get("response_style", {})
        
        # 🔥 ENHANCED CLEANING: Fix double reply issue
        reply = reply.strip()
        
        # Remove quotes and brackets
        reply = re.sub(r'^["\'\[\(]', '', reply)
        reply = re.sub(r'["\'\]\)]$', '', reply)
        
        # 🔥 CRITICAL FIX: Remove duplicate sentences with quotes
        # Pattern: "sentence1" "sentence2" -> sentence1 sentence2
        reply = re.sub(r'"([^"]*?)"\s*"([^"]*?)"', r'\1 \2', reply)
        
        # Remove line breaks
        reply = reply.replace('\\n', ' ').replace('\n', ' ')
        
        # 🔥 ENHANCED: Remove duplicate author names within reply
        author_lower = self.author.lower()
        
        # Pattern: ARL CRASHZONE ... ARL CRASHZONE -> ARL CRASHZONE ...
        words = reply.split()
        cleaned_words = []
        last_was_author = False
        
        for word in words:
            if word.lower() == author_lower:
                if not last_was_author:  # Only keep first occurrence
                    cleaned_words.append(word)
                    last_was_author = True
                # Skip subsequent author names
            else:
                cleaned_words.append(word)
                last_was_author = False
        
        reply = ' '.join(cleaned_words)
        
        # Remove excessive spaces
        reply = re.sub(r'\s+', ' ', reply).strip()
        
        return reply

    def _apply_learned_style(self, reply, viewer_prefs):
        """Apply learned response style preferences - FIXED to 100 chars max"""
        
        # 🔥 FIXED: Force maximum 100 characters for all responses
        MAX_LENGTH = 100
        
        if len(reply) > MAX_LENGTH:
            # Find natural break points within 100 chars
            break_points = []
            
            # Look for sentence endings first
            for i in range(min(len(reply), MAX_LENGTH - 10), 0, -1):
                if reply[i] in '.!?':
                    break_points.append(i + 1)
                    break
            
            # If no sentence ending, look for comma or space
            if not break_points:
                for i in range(min(len(reply), MAX_LENGTH - 5), 0, -1):
                    if reply[i] in ', ':
                        break_points.append(i)
                        break
            
            # Apply the cut
            if break_points:
                reply = reply[:break_points[0]].rstrip()
            else:
                # Hard cut at 95 chars to leave room
                reply = reply[:95].rstrip()
        
        return reply

    def _get_fallback_response(self, author, status):
        """Get fallback response based on viewer status"""
        if status == "vip":
            return f"Hai {author} sorry lagi ada gangguan teknis, gimana kabarnya?"
        elif status == "regular":
            return f"Hi {author} ada masalah koneksi nih, tunggu sebentar ya"
        else:
            return f"Halo {author} welcome! Lagi ada kendala teknis"
    
    def _get_error_response(self, author, error):
        """Get natural error response"""
        return f"Hai {author} sorry ada error: {error[:30]}..."

# ====================================================================
#  DEFINITIVE SOLUTION V2: Isolated Process with Queue Communication
# ====================================================================
class QueueMonitorThread(QThread):
    """
    Monitors a multiprocessing.Queue for new chat messages and emits a signal.
    This is a lightweight thread that runs in the main GUI process.
    """
    newComment = pyqtSignal(str, str)
    
    def __init__(self, message_queue: multiprocessing.Queue):
        super().__init__()
        self.message_queue = message_queue
        self._is_running = True

    def run(self):
        while self._is_running:
            try:
                # Get data from the queue, with a timeout to prevent blocking
                author, message = self.message_queue.get(timeout=1)
                self.newComment.emit(author, message)
            except multiprocessing.queues.Empty:
                # This is expected, just continue the loop
                continue
            except Exception as e:
                # Handle other potential errors, e.g., if the queue is closed
                print(f"[QueueMonitor] Error: {e}")
                time.sleep(1)
    
    def stop(self):
        self._is_running = False

class LogQueueMonitorThread(QThread):
    """Monitors the log queue from the subprocess and relays it to the UI."""
    logMessage = pyqtSignal(str, str)

    def __init__(self, log_queue: multiprocessing.Queue):
        super().__init__()
        self.log_queue = log_queue
        self._is_running = True

    def run(self):
        while self._is_running:
            try:
                level, message = self.log_queue.get(timeout=1)
                self.logMessage.emit(level, message)
            except multiprocessing.queues.Empty:
                continue
            except Exception:
                # If the queue is closed, the process likely ended.
                break
    
    def stop(self):
        self._is_running = False

# ====================================================================
#  Text Cleaning Function for TTS
# ====================================================================

def clean_text_for_tts(text):
    """
    🎯 ENHANCED: Membersihkan teks untuk TTS agar tidak mengucapkan emoji dan mengurangi jeda tidak natural
    """
    if not text:
        return ""
    
    import re
    
    # Remove emojis (comprehensive Unicode ranges)
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        u"\U00002500-\U00002BEF"  # chinese char
        u"\U00002702-\U000027B0"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001f926-\U0001f937"
        u"\U00010000-\U0010ffff"
        u"\u2640-\u2642" 
        u"\u2600-\u2B55"
        u"\u200d"
        u"\u23cf"
        u"\u23e9"
        u"\u231a"
        u"\ufe0f"  # dingbats
        u"\u3030"
        "]+", re.UNICODE)
    
    text = emoji_pattern.sub('', text)
    
    # Remove markdown/formatting
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # bold **text**
    text = re.sub(r'\*(.+?)\*', r'\1', text)      # italic *text*
    text = re.sub(r'_(.+?)_', r'\1', text)        # underline _text_
    text = re.sub(r'~~(.+?)~~', r'\1', text)      # strikethrough ~~text~~
    
    # 🔥 PERBAIKAN UTAMA: Reduce artificial breaks that cause chunking
    
    # Replace multiple spaces with single space (removes invisible break points)
    text = re.sub(r'\s+', ' ', text)
    
    # Remove line breaks that cause unnatural pauses
    text = text.replace('\\n', ' ').replace('\n', ' ')
    
    # Fix common word combinations that shouldn't be broken
    # Example: "mau cobain" -> ensure no break between them
    text = re.sub(r'\bmau\s+cobain\b', 'mau cobain', text, flags=re.IGNORECASE)
    text = re.sub(r'\bakan\s+main\b', 'akan main', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsedang\s+streaming\b', 'sedang streaming', text, flags=re.IGNORECASE)
    text = re.sub(r'\bgame\s+seru\b', 'game seru', text, flags=re.IGNORECASE)
    text = re.sub(r'\bmisi\s+baru\b', 'misi baru', text, flags=re.IGNORECASE)
    
    # Remove punctuation that causes unnatural breaks in casual speech
    text = re.sub(r'\s*-\s*', ' ', text)  # Remove dashes that break flow
    text = re.sub(r'\s*_\s*', ' ', text)  # Remove underscores
    
    # Fix excessive punctuation that causes chunking
    text = re.sub(r'[!]{2,}', '!', text)  # Multiple !!! -> !
    text = re.sub(r'[?]{2,}', '?', text)  # Multiple ??? -> ?
    text = re.sub(r'[.]{3,}', '.', text)  # Multiple .... -> . (remove ellipsis that cause breaks)
    
    # 🎯 CRUCIAL: Add natural flow words to prevent chunking
    # Replace abrupt transitions with smoother ones
    text = re.sub(r'\bnih\s+', 'nih, ', text, flags=re.IGNORECASE)  # Add comma after "nih"
    text = re.sub(r'\bbang\s+', 'bang, ', text, flags=re.IGNORECASE)  # Add comma after "bang"
    
    # Remove weird symbols that TTS can't pronounce well
    weird_symbols = ['⭐', '✨', '🎯', '💯', '🔥', '💪', '👍', '👎', '❤️', '💔', '😂', '😭', '🤣', '😍', '🥰', '😊', '🙂', '😅', '🤔', '😴', '😪', '🥱', '💤']
    for symbol in weird_symbols:
        text = text.replace(symbol, '')
    
    # Remove brackets, parentheses with content that might be stage directions
    text = re.sub(r'\[.*?\]', '', text)  # [action]
    text = re.sub(r'\(.*?\)', '', text)  # Remove parentheses content
    
    # Remove quotes at beginning/end
    text = re.sub(r'^["\'\[\(]', '', text)
    text = re.sub(r'["\'\]\)]$', '', text)
    
    # Final cleanup: multiple spaces and normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    # Ensure text doesn't start with punctuation
    text = re.sub(r'^[^\w]+', '', text)
    
    # 🔥 FINAL FIX: Ensure smooth flow by removing potential break points
    # Replace multiple consecutive commas/periods that cause chunking
    text = re.sub(r'[,]{2,}', ',', text)
    text = re.sub(r'[.]{2,}', '.', text)
    
    # Ensure single space after punctuation for natural flow
    text = re.sub(r'([,.!?])\s*', r'\1 ', text)
    text = re.sub(r'\s+', ' ', text)  # Final space normalization
    
    return text.strip()
