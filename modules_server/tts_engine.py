# modules_server/tts_engine.py
import os
import tempfile
import threading
import time
import io
import uuid
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
import requests
import json
import logging
import sys

# ✅ PERBAIKAN: Conditional import pyttsx3 to fix Pylance error
try:
    import pyttsx3
    _pyttsx3_available = True
except ImportError:
    _pyttsx3_available = False
    pyttsx3 = None

logger = logging.getLogger('StreamMate')

# Load environment variables
load_dotenv()

DEFAULT_LANG = os.getenv("VOICE_LANG", "en")
DEFAULT_VOICE = os.getenv("VOICE_NAME", "id-ID-Standard-A")

# Setup logging
logging_path = Path("logs/tts.log")
logging_path.parent.mkdir(exist_ok=True)

logging.basicConfig(
    filename=str(logging_path),
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# ✅ PERBAIKAN: Setup ffmpeg dari thirdparty
def _setup_ffmpeg():
    """Setup ffmpeg path dari folder thirdparty"""
    try:
        # Get proper base path depending on frozen state
        if getattr(sys, 'frozen', False):
            # Frozen/EXE mode - use sys.executable directory
            base_path = Path(sys.executable).parent
            print(f"[TTS] Running in frozen mode, base path: {base_path}")
        else:
            # Regular Python script mode - use current file directory's parent
            base_path = Path(__file__).resolve().parent.parent
            print(f"[TTS] Running in development mode, base path: {base_path}")
        
        # Path ke ffmpeg di thirdparty
        ffmpeg_bin = base_path / "thirdparty" / "ffmpeg" / "bin"
        
        print(f"[TTS] Looking for ffmpeg in: {ffmpeg_bin}")
        
        if ffmpeg_bin.exists():
            ffmpeg_exe = ffmpeg_bin / "ffmpeg.exe"
            ffprobe_exe = ffmpeg_bin / "ffprobe.exe"
            
            if ffmpeg_exe.exists() and ffprobe_exe.exists():
                # Set environment variables untuk pydub
                os.environ["FFMPEG_PATH"] = str(ffmpeg_exe.resolve())
                os.environ["FFPROBE_PATH"] = str(ffprobe_exe.resolve())
                
                # Tambahkan ke PATH untuk system detection
                current_path = os.environ.get("PATH", "")
                ffmpeg_dir = str(ffmpeg_bin.resolve())
                
                if ffmpeg_dir not in current_path:
                    os.environ["PATH"] = f"{ffmpeg_dir};{current_path}"
                
                print(f"[TTS] ffmpeg setup successful: {ffmpeg_exe}")
                return True
            else:
                print(f"[TTS] ffmpeg executables not found in {ffmpeg_bin}")
                print(f"[TTS] ffmpeg.exe exists: {ffmpeg_exe.exists()}")
                print(f"[TTS] ffprobe.exe exists: {ffprobe_exe.exists()}")
        else:
            print(f"[TTS] ffmpeg bin directory not found: {ffmpeg_bin}")
            
    except Exception as e:
        print(f"[TTS] ffmpeg setup failed: {e}")
    
    return False

# Setup ffmpeg saat startup
_ffmpeg_available = _setup_ffmpeg()

# Setup pydub dengan ffmpeg dari thirdparty
try:
    from pydub import AudioSegment
    # PERBAIKAN: Jangan import play untuk menghindari CMD window
    # from pydub.playback import play
    
    # Override pydub paths jika ffmpeg tersedia
    if _ffmpeg_available:
        # Get proper base path depending on frozen state
        if getattr(sys, 'frozen', False):
            # Frozen/EXE mode
            base_path = Path(sys.executable).parent
        else:
            # Regular Python script mode
            base_path = Path(__file__).resolve().parent.parent
            
        ffmpeg_exe = base_path / "thirdparty" / "ffmpeg" / "bin" / "ffmpeg.exe"
        ffprobe_exe = base_path / "thirdparty" / "ffmpeg" / "bin" / "ffprobe.exe"
        
        if ffmpeg_exe.exists() and ffprobe_exe.exists():
            AudioSegment.converter = str(ffmpeg_exe)
            AudioSegment.ffmpeg = str(ffmpeg_exe)
            AudioSegment.ffprobe = str(ffprobe_exe)
            
            print(f"[TTS] pydub configured with thirdparty ffmpeg: {ffmpeg_exe}")
        else:
            print(f"[TTS] WARNING: ffmpeg not found for pydub configuration")
    
    _pydub_available = True
except ImportError as e:
    print(f"[TTS] pydub not available: {e}")
    _pydub_available = False

# OPTIMAL: Gunakan pydub.playback yang sudah terbukti stabil
def _safe_audio_play(audio_segment):
    """Play AudioSegment dengan multiple fallback methods"""
    print(f"[AUDIO] Attempting to play audio with multiple methods...")
    
    # Method 1: Gunakan pydub playback (jika tersedia)
    try:
        # Import pydub playback
        from pydub.playback import play
        
        # Play langsung dengan pydub
        print(f"[AUDIO] Method 1: Using pydub.playback.play")
        play(audio_segment)
        print(f"[AUDIO] ✅ Method 1 successful: pydub.playback.play")
        return True
        
    except Exception as e:
        print(f"[AUDIO] ❌ Method 1 failed (pydub.playback): {e}")
    
    # Method 2: Export to WAV and play with sounddevice
    try:
        print(f"[AUDIO] Method 2: Using sounddevice")
        import sounddevice as sd
        import numpy as np
        import tempfile
        import wave
        
        # Create temp file for WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        # Export to WAV
        audio_segment.export(str(temp_path), format="wav")
        
        # Read with wave
        with wave.open(str(temp_path), 'rb') as wf:
            sample_width = wf.getsampwidth()
            channels = wf.getnchannels()
            rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
        
        # Convert to numpy array
        dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
        if sample_width in dtype_map:
            dtype = dtype_map[sample_width]
        else:
            dtype = np.int16
        
        # Process audio data
        samples = np.frombuffer(frames, dtype=dtype)
        if sample_width == 2:
            samples = samples.astype(np.float32) / 32768.0
        elif sample_width == 1:
            samples = samples.astype(np.float32) / 128.0
        elif sample_width == 4:
            samples = samples.astype(np.float32) / 2147483648.0
        
        # Reshape for stereo
        if channels == 2:
            samples = samples.reshape((-1, 2))
        
        # Play with sounddevice
        sd.play(samples, rate, blocking=True)
        
        # Clean up
        try:
            temp_path.unlink()
        except:
            pass
            
        print(f"[AUDIO] ✅ Method 2 successful: sounddevice")
        return True
        
    except Exception as e:
        print(f"[AUDIO] ❌ Method 2 failed (sounddevice): {e}")
    
    # Method 3: Play with simpleaudio if available
    try:
        print(f"[AUDIO] Method 3: Using simpleaudio")
        try:
            import simpleaudio as sa
            simpleaudio_available = True
        except ImportError:
            print(f"[AUDIO] simpleaudio not available, skipping Method 3")
            simpleaudio_available = False
            raise ImportError("simpleaudio not available")
        
        # Only continue if simpleaudio successfully imported
        if simpleaudio_available:
            # Export to WAV with specific parameters
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = Path(temp_file.name)
            
            # Export with optimal settings for simpleaudio
            audio_segment = audio_segment.set_channels(1)  # Convert to mono
            audio_segment = audio_segment.set_sample_width(2)  # 16-bit
            audio_segment = audio_segment.set_frame_rate(44100)  # Common rate
            audio_segment.export(str(temp_path), format="wav")
            
            # Play
            wave_obj = sa.WaveObject.from_wave_file(str(temp_path))
            play_obj = wave_obj.play()
            play_obj.wait_done()  # Wait for playback to finish
            
            # Clean up
            try:
                temp_path.unlink()
            except:
                pass
                
            print(f"[AUDIO] ✅ Method 3 successful: simpleaudio")
            return True
        
    except Exception as e:
        print(f"[AUDIO] ❌ Method 3 failed (simpleaudio): {e}")
    
    # Method 4: Last resort - try to play with system command
    try:
        print(f"[AUDIO] Method 4: Using system command")
        import subprocess
        
        # Export to WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        audio_segment.export(str(temp_path), format="wav")
        
        # Use appropriate command for different platforms
        if sys.platform == 'win32':
            # On Windows, use PowerShell to play audio silently
            cmd = ["powershell", "-c", f"(New-Object Media.SoundPlayer '{temp_path}').PlaySync()"]
            subprocess.call(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            # On other platforms, use appropriate command
            cmd = ["play", str(temp_path)]
            subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Clean up
        try:
            temp_path.unlink()
        except:
            pass
            
        print(f"[AUDIO] ✅ Method 4 successful: system command")
        return True
        
    except Exception as e:
        print(f"[AUDIO] ❌ Method 4 failed (system command): {e}")
    
    print(f"[AUDIO] ❌ All playback methods failed")
    return False

# ✅ PERBAIKAN: Fungsi untuk membaca config voices
def _load_voice_config():
    """Load voice configuration dari config/voices.json"""
    try:
        voices_path = Path("config/voices.json")
        if voices_path.exists():
            with open(voices_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"[TTS] Error loading voice config: {e}")
    return None

def _is_google_cloud_voice(voice_name):
    """Cek apakah voice_name adalah Google Cloud voice dari config"""
    if not voice_name:
        return False
    
    voice_config = _load_voice_config()
    if not voice_config:
        return False
    
    # Cek di gtts_standard dan chirp3
    for category in ["gtts_standard", "chirp3"]:
        if category in voice_config:
            for lang_code, voices in voice_config[category].items():
                for voice in voices:
                    if voice.get("model") == voice_name:
                        return True
    return False

def _get_voice_lang_from_config(voice_name):
    """Dapatkan language code dari voice yang dipilih di config"""
    if not voice_name:
        return None
    
    voice_config = _load_voice_config()
    if not voice_config:
        return None
    
    # Cek di gtts_standard dan chirp3
    for category in ["gtts_standard", "chirp3"]:
        if category in voice_config:
            for lang_code, voices in voice_config[category].items():
                for voice in voices:
                    if voice.get("model") == voice_name:
                        return lang_code
    return None

def _get_voice_gender_from_config(voice_name):
    """Dapatkan gender dari voice yang dipilih di config"""
    if not voice_name:
        return None
    
    voice_config = _load_voice_config()
    if not voice_config:
        return None
    
    # Cek di gtts_standard dan chirp3
    for category in ["gtts_standard", "chirp3"]:
        if category in voice_config:
            for lang_code, voices in voice_config[category].items():
                for voice in voices:
                    if voice.get("model") == voice_name:
                        return voice.get("gender", "UNKNOWN")
    return None

# Queue untuk mencegah overlapping audio
_audio_queue = []
_queue_lock = threading.Lock()
_queue_thread = None
_is_queue_running = False

# API URL untuk Animaze WebSocket Server
ANIMAZE_API_URL = "http://animaze.streammateai.com/api/hotkey"

def send_animaze_hotkey(key):
    """Kirim hotkey ke Animaze WebSocket API."""
    try:
        logging.info(f"[Animaze] Sending hotkey: {key}")
        response = requests.post(
            ANIMAZE_API_URL, 
            json={"key": key}, 
            timeout=2
        )
        if response.status_code == 200:
            logging.info(f"[Animaze] Hotkey {key} sent successfully")
            return True
        else:
            logging.error(f"[Animaze] Failed to send hotkey {key}: {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"[Animaze] Error sending hotkey: {e}")
        return False

def _create_safe_temp_path(suffix=".mp3"):
    """Buat path temporary file yang aman."""
    try:
        # Prioritas 1: Gunakan folder temp aplikasi
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True, parents=True)
        
        # Buat nama file unik
        temp_filename = f"tts_{uuid.uuid4().hex[:8]}{suffix}"
        temp_path = temp_dir / temp_filename
        
        # Test write permission
        test_content = b"test"
        temp_path.write_bytes(test_content)
        temp_path.unlink()  # Hapus file test
        
        return temp_path
        
    except Exception as e:
        logging.warning(f"[TTS] App temp folder failed: {e}")
        
        try:
            # Prioritas 2: System temp dengan prefix
            return tempfile.NamedTemporaryFile(
                delete=False, 
                suffix=suffix, 
                prefix="streammate_tts_"
            ).name
        except Exception as e2:
            logging.error(f"[TTS] System temp also failed: {e2}")
            # Prioritas 3: Current directory
            return Path.cwd() / f"temp_tts_{uuid.uuid4().hex[:8]}{suffix}"

def _safe_cleanup_file(file_path, delay=2.0):
    """Cleanup file dengan delay dan error handling."""
    def cleanup():
        try:
            if isinstance(file_path, (str, Path)):
                path_obj = Path(file_path)
                if path_obj.exists():
                    path_obj.unlink()
                    logging.info(f"[TTS] Cleaned up: {file_path}")
        except Exception as e:
            logging.warning(f"[TTS] Cleanup failed for {file_path}: {e}")
    
    # Cleanup dengan delay untuk memastikan file tidak sedang digunakan
    cleanup_timer = threading.Timer(delay, cleanup)
    cleanup_timer.daemon = True
    cleanup_timer.start()

def _fallback_tts(text, language_code=None, voice_name=None, on_finished=None):
    """Fallback TTS dengan voice selection yang benar."""
    try:
        print(f"[DEBUG] pyttsx3 fallback - lang: {language_code}, voice: {voice_name}")
        
        # ✅ PERBAIKAN: Gunakan global import check
        if not _pyttsx3_available or pyttsx3 is None:
            print(f"[DEBUG] pyttsx3 not available")
            print(f"[TTS-TEXT-ONLY] {text}")
            if on_finished:
                on_finished()
            return False
        
        engine = pyttsx3.init()
        
        # Set rate dan volume
        engine.setProperty('rate', 160)  # Kecepatan lebih natural
        engine.setProperty('volume', 0.9)
        
        # PERBAIKAN: Pilih voice berdasarkan voice_name parameter dari CoHost
        voices = engine.getProperty('voices')
        selected_voice = None
        
        print(f"[DEBUG] Available pyttsx3 voices: {len(voices) if voices else 0}")
        print(f"[DEBUG] Requested voice_name: {voice_name}")
        
        if voices and len(voices) > 0:
            # Safe voice selection dengan bounds checking
            try:
                # PRIORITAS 1: Jika voice_name spesifik diminta (dari CoHost selection)
                if voice_name and voice_name != "default":
                    print(f"[DEBUG] Looking for specific voice: {voice_name}")
                    
                    # Cari voice yang sesuai dengan voice_name dari CoHost
                    for i, voice in enumerate(voices):
                        voice_id = getattr(voice, 'id', '').lower()
                        voice_name_attr = getattr(voice, 'name', '').lower()
                        
                        # Check if voice matches request (case insensitive)
                        if (voice_name.lower() in voice_id or 
                            voice_name.lower() in voice_name_attr or
                            voice_name.lower().replace('-', '').replace('_', '') in voice_id.replace('-', '').replace('_', '')):
                            selected_voice = voice.id
                            print(f"[DEBUG] Found matching voice: {voice_name_attr} -> {voice_id}")
                            break
                
                # PRIORITAS 2: Fallback berdasarkan language_code
                if not selected_voice and language_code:
                    for i, voice in enumerate(voices):
                        voice_id = getattr(voice, 'id', '').lower()
                        voice_name_attr = getattr(voice, 'name', '').lower()
                        
                        print(f"[DEBUG] Voice {i}: {voice_name_attr} | ID: {voice_id}")
                        
                        # Cari voice Indonesia atau yang sesuai
                        if language_code and (language_code.startswith('id-') or language_code == 'id'):
                            if 'indonesia' in voice_id or 'id-id' in voice_id:
                                selected_voice = voice.id
                                print(f"[DEBUG] Selected Indonesian voice: {voice_name_attr}")
                                break
                        
                        # Fallback ke female voice yang tersedia
                        if 'female' in voice_id or 'zira' in voice_id or 'hazel' in voice_id:
                            if selected_voice is None:  # Hanya set jika belum ada
                                selected_voice = voice.id
                                print(f"[DEBUG] Candidate female voice: {voice_name_attr}")
                
                # PRIORITAS 3: Jika tidak ada yang cocok, gunakan voice pertama
                if not selected_voice and voices:
                    selected_voice = voices[0].id
                    print(f"[DEBUG] Using first available voice: {getattr(voices[0], 'name', 'Unknown')}")
                    
            except (IndexError, AttributeError) as e:
                print(f"[DEBUG] Voice selection error: {e}, using default")
                if voices and len(voices) > 0:
                    selected_voice = voices[0].id
        
        # Set voice yang dipilih
        if selected_voice:
            try:
                engine.setProperty('voice', selected_voice)
                print(f"[DEBUG] Voice set successfully: {selected_voice}")
            except Exception as voice_error:
                print(f"[DEBUG] Failed to set voice: {voice_error}")
        
        # Speak text dengan error handling
        try:
            engine.say(text)
            engine.runAndWait()
            print(f"[DEBUG] pyttsx3 TTS completed successfully")
        except Exception as speak_error:
            print(f"[DEBUG] pyttsx3 speak error: {speak_error}")
            # Try alternative method
            try:
                engine.stop()
                engine = pyttsx3.init()  # Reinitialize
                engine.say(text)
                engine.runAndWait()
                print(f"[DEBUG] pyttsx3 TTS completed after reinit")
            except Exception as reinit_error:
                print(f"[DEBUG] pyttsx3 reinit also failed: {reinit_error}")
                raise
        
        if on_finished:
            on_finished()
        return True
        
    except Exception as e:
        print(f"[DEBUG] pyttsx3 fallback failed: {e}")
        
        # Ultimate fallback: Text-only mode
        print(f"[TTS-TEXT-ONLY] {text}")
        if on_finished:
            on_finished()
        return False

def _play_audio_queue():
    """Background thread untuk memainkan audio dalam queue."""
    global _is_queue_running
    _is_queue_running = True
    
    while True:
        # Check if queue is empty
        with _queue_lock:
            if not _audio_queue:
                _is_queue_running = False
                break
            
            # Get next audio data
            audio_data = _audio_queue.pop(0)
        
        try:
            # Play audio
            from pydub.playback import play
            play(audio_data)
        except Exception as e:
            logging.error(f"Failed to play audio: {e}")
        
        # Small delay to prevent CPU overload
        time.sleep(0.1)

def speak(text: str, language_code: str = None, voice_name: str = None, output_device: int = None, on_finished=None):
    """
    General TTS wrapper dengan fallback handling yang robust.
    
    Args:
        text: Teks untuk diucapkan
        language_code: Kode bahasa
        voice_name: Model suara 
        output_device: Audio output device index
        on_finished: Callback saat audio selesai
    """
    if not text or text.strip() == "":
        if on_finished:
            on_finished()
        return
    
    # EMERGENCY BYPASS untuk development mode jika diperlukan
    if os.getenv("TTS_BYPASS", "").lower() == "true":
        print(f"[DEBUG] TTS BYPASS MODE - Text: {text[:50]}...")
        if on_finished:
            on_finished()
        return
    
    # Logging dan timing
    logger.info(f"TTS started: {text[:30]}... (voice={voice_name}, lang={language_code})")

    # Track TTS usage dengan sistem kredit baru
    try:
        from modules_server.real_credit_tracker import credit_tracker
        
        # Tentukan tipe TTS
        tts_type = "google" if voice_name and voice_name.startswith(("id-ID-", "en-US-")) else "gtts"
        
        # Track penggunaan
        credits_used = credit_tracker.track_tts_usage(text, tts_type)
        logger.info(f"TTS Credit tracked: {len(text)} chars = {credits_used:.4f} credits")
        
    except ImportError:
        logger.debug("Credit tracker not available for TTS tracking")
    except Exception as e:
        logger.error(f"Error tracking TTS usage: {e}")

    start_time = time.time()
    
    print(f"[DEBUG] speak() called with: text='{text[:30]}...', language={language_code}, voice={voice_name}")
    
    callback_executed = False
    
    def safe_callback():
        """Callback yang aman dan hanya dijalankan sekali."""
        nonlocal callback_executed
        if not callback_executed and on_finished:
            callback_executed = True
            try:
                on_finished()
                print(f"[DEBUG] Callback executed successfully")
            except Exception as e:
                print(f"[ERROR] Callback execution failed: {e}")
    
    # 1) Coba Google Cloud TTS dulu jika voice_name disediakan
    if voice_name:
        try:
            from pathlib import Path
            cred_path = Path("config/gcloud_tts_credentials.json")
            
            if cred_path.exists():
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path.resolve())
                
                try:
                    from modules_server.tts_google import speak_with_google_cloud
                    logging.info(f"[TTS] Using Google Cloud with voice: {voice_name}")
                    print(f"[DEBUG] Forwarding to Google Cloud TTS")
                    
                    speak_with_google_cloud(
                        text, voice_name, language_code, output_device, 
                        also_play_on_speaker=True, on_finished=safe_callback
                    )
                    
                    duration = time.time() - start_time
                    logger.info(f"TTS completed (Google Cloud) in {duration:.2f}s")
                    return
                    
                except Exception as e:
                    logging.error(f"[TTS] Google Cloud error: {e}")
                    print(f"[DEBUG] Google Cloud failed: {e}, falling back to gTTS")
            else:
                print(f"[DEBUG] Google Cloud credentials not found, using gTTS")
                
        except Exception as e:
            logging.error(f"[TTS] Google Cloud setup error: {e}")
            print(f"[DEBUG] Google Cloud setup failed: {e}")
    
    # 2) Fallback ke gTTS dengan voice config support
    lang = "en"  # Default
    
    # ✅ PERBAIKAN: Tentukan bahasa dari voice config
    if voice_name:
        config_lang = _get_voice_lang_from_config(voice_name)
        if config_lang:
            lang = config_lang.split("-")[0].lower()
            print(f"[DEBUG] Language from config voice: {lang} (from {config_lang})")
        elif voice_name.startswith("id-"):
            lang = "id"
            print(f"[DEBUG] Language from voice prefix: {lang}")
        elif voice_name.startswith("en-"):
            lang = "en"
            print(f"[DEBUG] Language from voice prefix: {lang}")
    
    if language_code and not config_lang:
        lang = language_code.split("-")[0].lower()
        print(f"[DEBUG] Language from parameter: {lang}")
    
    temp_path = None
    
    try:
        from gtts import gTTS
        
        # Pastikan pydub tersedia
        if not _pydub_available:
            print(f"[DEBUG] pydub not available, fallback to Windows TTS")
            raise ImportError("pydub not available")
        
        logging.info(f"[TTS] Using gTTS with language: {lang} (voice: {voice_name})")
        print(f"[DEBUG] Creating gTTS object with voice config...")
        
        # ✅ PERBAIKAN: Gunakan parameter yang sesuai voice dari config
        tts_params = {"text": text, "lang": lang, "slow": False}
        
        # Tambah parameter khusus berdasarkan voice dari config
        if voice_name:
            voice_gender = _get_voice_gender_from_config(voice_name)
            print(f"[DEBUG] Voice from config: {voice_name} ({voice_gender})")
            
            # Adjust gTTS parameters berdasarkan voice characteristics
            if "standard-a" in voice_name.lower() or voice_gender == "FEMALE":
                # Standard A: Female voice characteristics
                if lang == "en":
                    tts_params["tld"] = "com"  # US English untuk female
                    print(f"[DEBUG] Applied female characteristics: US English")
                elif lang == "id":
                    tts_params["slow"] = False  # Normal speed untuk female
                    print(f"[DEBUG] Applied female characteristics: Indonesian")
                    
            elif "standard-b" in voice_name.lower() or voice_gender == "MALE":
                # Standard B: Male voice characteristics
                if lang == "en":
                    tts_params["tld"] = "co.uk"  # UK English untuk male
                    print(f"[DEBUG] Applied male characteristics: UK English")
                elif lang == "id":
                    tts_params["slow"] = False  # Standard speed untuk male
                    print(f"[DEBUG] Applied male characteristics: Indonesian")
                    
            elif "standard-c" in voice_name.lower():
                # Standard C: Alternative characteristics
                if lang == "en":
                    tts_params["tld"] = "com.au"  # Australian English
                    print(f"[DEBUG] Applied Standard-C characteristics: AU English")
                elif lang == "id":
                    tts_params["slow"] = False
                    print(f"[DEBUG] Applied Standard-C characteristics: Indonesian")
                    
            elif "standard-d" in voice_name.lower():
                # Standard D: Alternative characteristics
                if lang == "en":
                    tts_params["tld"] = "ca"  # Canadian English
                    print(f"[DEBUG] Applied Standard-D characteristics: CA English")
                elif lang == "id":
                    tts_params["slow"] = False
                    print(f"[DEBUG] Applied Standard-D characteristics: Indonesian")
        
        print(f"[DEBUG] gTTS parameters: {tts_params}")
        
        # Buat TTS object dengan parameter yang sudah disesuaikan
        tts = gTTS(**tts_params)
        
        # Buat safe temp path dengan improved error handling
        print(f"[DEBUG] Creating safe temp path...")
        try:
            temp_path = _create_safe_temp_path(".mp3")
        except Exception as temp_error:
            print(f"[DEBUG] Safe temp path failed: {temp_error}")
            # Fallback ke sistem temp sederhana
            import tempfile
            temp_path = tempfile.mktemp(suffix=".mp3", prefix="streammate_")
        
        # Save TTS dengan retry mechanism
        print(f"[DEBUG] Saving TTS to: {temp_path}")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                tts.save(str(temp_path))
                break
            except Exception as save_error:
                print(f"[DEBUG] TTS save attempt {attempt + 1} failed: {save_error}")
                if attempt == max_retries - 1:
                    raise save_error
                time.sleep(0.5)  # Wait before retry
        
        # Verify file exists dan readable
        from pathlib import Path as PathlibPath
        temp_path_obj = PathlibPath(temp_path)
        if not temp_path_obj.exists():
            raise FileNotFoundError(f"TTS file not created: {temp_path}")
        
        if temp_path_obj.stat().st_size == 0:
            raise ValueError(f"TTS file is empty: {temp_path}")
        
        print(f"[DEBUG] TTS file created: {temp_path_obj.stat().st_size} bytes")
        
        # ✅ PERBAIKAN: Load audio TANPA FFmpeg subprocess (ROOT CAUSE FIX!)
        print(f"[DEBUG] Loading audio WITHOUT ffmpeg subprocess...")
        try:
            # METODE 1: Convert MP3 ke WAV dengan hidden FFmpeg, lalu load langsung
            import subprocess
            import wave
            
            temp_wav = temp_path.with_suffix('.wav')
            
            # FFmpeg conversion dengan HIDDEN window
            ffmpeg_cmd = [
                'ffmpeg', '-i', str(temp_path), 
                '-y', str(temp_wav)
            ]
            
            # CRITICAL: Hidden window setup untuk Windows
            startupinfo = None
            creation_flags = 0
            
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                creationflags=creation_flags
            )
            
            if result.returncode == 0:
                # Load WAV file dengan native Python wave library (NO FFmpeg!)
                with wave.open(str(temp_wav), 'rb') as wav_file:
                    frames = wav_file.readframes(wav_file.getnframes())
                    sample_rate = wav_file.getframerate()
                    channels = wav_file.getnchannels()
                    sample_width = wav_file.getsampwidth()
                
                # Create AudioSegment dari raw WAV data (NO FFmpeg subprocess!)  
                audio = AudioSegment(
                    data=frames,
                    sample_width=sample_width,
                    frame_rate=sample_rate,
                    channels=channels
                )
                print(f"[DEBUG] ✅ Audio loaded WITHOUT pydub.from_file: {len(audio)}ms, {audio.frame_rate}Hz")
                
                # Cleanup converted WAV
                try:
                    temp_wav.unlink()
                except:
                    pass
                    
            else:
                raise Exception(f"Hidden FFmpeg conversion failed: {result.stderr}")
                
        except Exception as load_error:
            print(f"[DEBUG] ❌ Hidden FFmpeg method failed: {load_error}")
            
            # FALLBACK: Try direct AudioSegment load dengan subprocess hiding 
            try:
                print(f"[DEBUG] Trying fallback AudioSegment.from_file...")
                
                # Patch pydub untuk menggunakan hidden subprocess
                import pydub.utils
                original_popen = subprocess.Popen
                
                def hidden_popen(*args, **kwargs):
                    if os.name == 'nt':
                        if 'startupinfo' not in kwargs:
                            si = subprocess.STARTUPINFO()
                            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            si.wShowWindow = subprocess.SW_HIDE
                            kwargs['startupinfo'] = si
                        if 'creationflags' not in kwargs:
                            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                    return original_popen(*args, **kwargs)
                
                # Temporarily patch subprocess
                subprocess.Popen = hidden_popen
                
                try:
                    audio = AudioSegment.from_file(str(temp_path), format="mp3")
                    print(f"[DEBUG] ✅ Fallback load successful: {len(audio)}ms")
                finally:
                    # Restore original Popen
                    subprocess.Popen = original_popen
                    
            except Exception as load_error2:
                print(f"[DEBUG] ❌ All loading methods failed: {load_error2}")
                # Create dummy audio untuk prevent crash
                audio = AudioSegment.silent(duration=1000)  # 1 second silence
                print(f"[DEBUG] Created fallback silence audio")
        
        # ✅ PERBAIKAN: Voice processing untuk memberikan variasi yang terdengar
        if voice_name:
            try:
                voice_gender = _get_voice_gender_from_config(voice_name)
                
                if "standard-a" in voice_name.lower() or voice_gender == "FEMALE":
                    # Standard A: Female voice processing
                    try:
                        # Increase pitch slightly untuk female characteristics
                        audio = audio.speedup(playback_speed=1.05)  # 5% faster (higher pitch)
                        audio = audio + 1  # Slight volume boost
                        print(f"[DEBUG] Applied female voice processing to {voice_name}")
                    except:
                        audio = audio + 1  # Volume only jika speedup gagal
                        print(f"[DEBUG] Applied female volume to {voice_name}")
                        
                elif "standard-b" in voice_name.lower() or voice_gender == "MALE":
                    # Standard B: Male voice processing
                    try:
                        # Decrease pitch slightly untuk male characteristics
                        audio = audio.speedup(playback_speed=0.96)  # 4% slower (lower pitch)
                        audio = audio + 0.5  # Different volume level
                        print(f"[DEBUG] Applied male voice processing to {voice_name}")
                    except:
                        audio = audio + 0.5  # Volume only jika speedup gagal
                        print(f"[DEBUG] Applied male volume to {voice_name}")
                        
                elif "standard-c" in voice_name.lower():
                    # Standard C: Alternative processing
                    try:
                        audio = audio.speedup(playback_speed=1.02)  # Slightly faster
                        audio = audio + 0.8  # Different volume
                        print(f"[DEBUG] Applied Standard-C processing to {voice_name}")
                    except:
                        audio = audio + 0.8
                        print(f"[DEBUG] Applied Standard-C volume to {voice_name}")
                        
                elif "standard-d" in voice_name.lower():
                    # Standard D: Alternative processing
                    try:
                        audio = audio.speedup(playback_speed=0.98)  # Slightly slower
                        audio = audio + 1.2  # Different volume
                        print(f"[DEBUG] Applied Standard-D processing to {voice_name}")
                    except:
                        audio = audio + 1.2
                        print(f"[DEBUG] Applied Standard-D volume to {voice_name}")
                        
                else:
                    print(f"[DEBUG] Using default processing for {voice_name}")
                    
            except Exception as processing_error:
                print(f"[DEBUG] Voice processing failed: {processing_error}, using original")
        
        # Load VM config
        use_dual_output = True
        boost_vm = False
        
        try:
            vm_config_path = Path("config/live_state.json")
            if vm_config_path.exists():
                vm_config = json.loads(vm_config_path.read_text(encoding="utf-8"))
                vm_active = vm_config.get("virtual_mic_active", False)
                dual_output = vm_config.get("dual_output", True)
                boost_vm = vm_config.get("boost_virtual_mic", False)
                
                if vm_active and output_device is None:
                    output_device = vm_config.get("virtual_mic_device_index")
                    print(f"[DEBUG] Using VM device from config: {output_device}")
                
                use_dual_output = dual_output if output_device is not None else False
        except Exception as e:
            print(f"[DEBUG] VM config error: {e}")
        
        # Audio output processing dengan improved fallback
        print(f"[DEBUG] Processing audio output...")
        
        if output_device is not None:
            try:
                import sounddevice as sd
                
                samples = audio.get_array_of_samples()
                arr = np.array(samples)
                
                # Boost untuk virtual mic jika diminta
                if boost_vm:
                    vm_arr = arr * 1.4
                    vm_arr = np.clip(vm_arr, np.iinfo(arr.dtype).min, np.iinfo(arr.dtype).max).astype(arr.dtype)
                else:
                    vm_arr = arr
                
                if use_dual_output:
                    # DUAL OUTPUT MODE
                    print(f"[DEBUG] Using dual output mode")
                    
                    vm_completed = threading.Event()
                    
                    def vm_thread_func():
                        try:
                            sd.play(vm_arr, audio.frame_rate, device=output_device)
                            sd.wait()
                            print(f"[DEBUG] VM playback completed")
                        except Exception as e:
                            print(f"[DEBUG] VM thread error: {e}")
                        finally:
                            vm_completed.set()
                    
                    # Start VM thread
                    vm_thread = threading.Thread(target=vm_thread_func, daemon=True)
                    vm_thread.start()
                    
                    # OPTIMAL: Standard audio playback
                    print(f"[DEBUG] Standard audio playback...")
                    success = _safe_audio_play(audio)
                    if not success:
                        print(f"[AUDIO] ⚠️ Audio playback failed, but continuing...")
                    
                    # Wait for VM thread
                    vm_completed.wait(timeout=15.0)
                    
                else:
                    # VM ONLY MODE  
                    print(f"[DEBUG] VM only mode (device {output_device})")
                    sd.play(vm_arr, audio.frame_rate, device=output_device)
                    sd.wait()
                
            except Exception as e:
                logging.error(f"[TTS] Sounddevice error: {e}")
                print(f"[DEBUG] Sounddevice failed: {e}, fallback to Windows-native")
                
                # Standard fallback audio playback
                success = _safe_audio_play(audio)
                if not success:
                    print(f"[AUDIO] ⚠️ Audio playback failed, but continuing...")
        else:
            # OPTIMAL: Standard playback - SIMPLE & RELIABLE
            print(f"[DEBUG] Standard audio playback")
            
            try:
                # Main playback method
                success = _safe_audio_play(audio)
                if success:
                    print(f"[DEBUG] ✅ Audio playback successful")
                else:
                    print(f"[DEBUG] ⚠️ Audio playback failed, but TTS completed")
                    
            except Exception as e:
                print(f"[DEBUG] Audio playback error: {e}, but TTS completed")
        
        print(f"[DEBUG] Audio processing completed")
        
        # Success callback
        safe_callback()
        
        # Success logging
        duration = time.time() - start_time
        logger.info(f"TTS completed (gTTS) in {duration:.2f}s")
        
    except Exception as e:
        # Error logging
        error_msg = f"gTTS failed: {str(e)}"
        logger.error(f"TTS error: {error_msg}")
        logging.error(f"[TTS] {error_msg}")
        print(f"[DEBUG] gTTS error: {e}")
        
        # Fallback TTS dengan parameter yang benar
        print(f"[DEBUG] Attempting fallback TTS...")
        fallback_success = _fallback_tts(
            text, 
            language_code=language_code, 
            voice_name=voice_name,
            on_finished=safe_callback if not callback_executed else None
        )
        
        if not fallback_success and not callback_executed:
            safe_callback()
    
    finally:
        # Cleanup temp file
        if temp_path:
            _safe_cleanup_file(temp_path, delay=1.0)

def check_audio_devices():
    """Cek ketersediaan perangkat audio dan log status."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        logging.info(f"Jumlah perangkat audio yang tersedia: {len(devices)}")
        
        for i, dev in enumerate(devices):
            # PERBAIKAN: Gunakan simbol yang aman untuk encoding Windows
            status = "[OK]" if dev["max_output_channels"] > 0 else "[NO]"
            logging.info(f"  [{i}] {status} {dev['name']} (Output: {dev['max_output_channels']})")
        
        return True
    except Exception as e:
        logging.error(f"Gagal memeriksa perangkat audio: {e}")
        return False

# Inisialisasi saat modul dimuat
try:
    check_audio_devices()
    
    # Buat direktori temp jika belum ada
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True, parents=True)
    
    logging.info("[TTS] Engine initialized successfully")
    
except Exception as init_error:
    logging.error(f"[TTS] Initialization error: {init_error}")