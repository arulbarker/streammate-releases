# modules_server/tts_engine.py
import os
import tempfile
import threading
import time
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
import requests
import json
import logging
logger = logging.getLogger('StreamMate')

# Load environment variables
load_dotenv()

DEFAULT_LANG = os.getenv("VOICE_LANG", "en")
DEFAULT_VOICE = os.getenv("VOICE_NAME", "id-ID-Standard-A")

# Setup logging
import logging
logging_path = Path("logs/tts.log")
logging_path.parent.mkdir(exist_ok=True)

logging.basicConfig(
    filename=str(logging_path),
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

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
    General TTS wrapper dengan fallback handling.
    
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
    
    # TAMBAHAN: Add logging
    logger.info(f"TTS started: {text[:30]}... (voice={voice_name}, lang={language_code})")
    start_time = time.time()
    
    # Debug logging
    print(f"[DEBUG] speak() called with: text='{text[:30]}...', language={language_code}, voice={voice_name}")
    if on_finished:
        print(f"[DEBUG] Callback provided: {on_finished}")
    
    # 1) Coba Google Cloud TTS dulu jika voice_name disediakan
    if voice_name:
        try:
            # Cek kredensial
            from pathlib import Path
            cred_path = Path("config/gcloud_tts_credentials.json")
            if cred_path.exists():
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path.resolve())
                
                try:
                    from modules_server.tts_google import speak_with_google_cloud
                    logging.info(f"[TTS] Menggunakan Google Cloud dengan suara: {voice_name}")
                    print(f"[DEBUG] Forwarding to speak_with_google_cloud with callback")
                    speak_with_google_cloud(text, voice_name, language_code, output_device, also_play_on_speaker=True, on_finished=on_finished)
                    
                    # TAMBAHAN: Success logging untuk Google Cloud
                    duration = time.time() - start_time
                    logger.info(f"TTS completed (Google Cloud) in {duration:.2f}s")
                    return
                    
                except Exception as e:
                    logging.error(f"[TTS] Error Google Cloud: {e}")
                    print(f"[DEBUG] Error calling Google TTS: {e}, falling back to gTTS")
            else:
                logging.warning("[TTS] Kredensial Google Cloud tidak ditemukan")
                print(f"[DEBUG] Google Cloud credentials not found, falling back to gTTS")
        except Exception as e:
            logging.error(f"[TTS] Error saat setup Google Cloud: {e}")
            print(f"[DEBUG] Error setting up Google Cloud: {e}, falling back to gTTS")
    
    # 2) Fallback ke gTTS
    lang = "en"
    if language_code:
        lang = language_code.split("-")[0].lower()
    
    try:
        from gtts import gTTS
        from pydub import AudioSegment
        from pydub.playback import play
        
        logging.info(f"[TTS] Menggunakan gTTS dengan bahasa: {lang}")
        print(f"[DEBUG] Using gTTS with language: {lang}")
        
        tts = gTTS(text=text, lang=lang)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            temp_path = tmp.name
            
        tts.save(temp_path)
        audio = AudioSegment.from_file(temp_path, format="mp3")
        
        # Load VM config
        try:
            from pathlib import Path
            vm_config_path = Path("config/live_state.json")
            if vm_config_path.exists():
                vm_config = json.loads(vm_config_path.read_text(encoding="utf-8"))
                vm_active = vm_config.get("virtual_mic_active", False)
                dual_output = vm_config.get("dual_output", True)
                boost_vm = vm_config.get("boost_virtual_mic", False)
                
                if vm_active and output_device is None:
                    output_device = vm_config.get("virtual_mic_device_index")
                    print(f"[DEBUG] Using virtual mic device from config: {output_device}")
                
                use_dual_output = dual_output if output_device is not None else False
            else:
                use_dual_output = True
                boost_vm = False
        except Exception as e:
            print(f"[DEBUG] Error loading VM config: {e}")
            use_dual_output = True
            boost_vm = False
        
        # Proses audio output
        if output_device is not None:
            try:
                import sounddevice as sd
                import soundfile as sf
                
                samples = audio.get_array_of_samples()
                arr = np.array(samples)
                
                # Boost jika diminta
                if boost_vm:
                    vm_arr = arr * 1.4
                    vm_arr = np.clip(vm_arr, np.iinfo(arr.dtype).min, np.iinfo(arr.dtype).max).astype(arr.dtype)
                else:
                    vm_arr = arr
                
                if use_dual_output:
                    # DUAL OUTPUT MODE
                    def vm_thread_func():
                        try:
                            sd.play(vm_arr, audio.frame_rate, device=output_device)
                            sd.wait()
                            print(f"[DEBUG] Virtual mic playback completed")
                        except Exception as e:
                            print(f"[DEBUG] Error in VM thread: {e}")
                    
                    vm_thread = threading.Thread(target=vm_thread_func, daemon=True)
                    vm_thread.start()
                    
                    print(f"[DEBUG] Playing audio on default speaker")
                    play(audio)
                    
                    print(f"[DEBUG] Default speaker playback done, waiting for VM thread")
                    vm_thread.join(timeout=10.0)
                    
                    if on_finished:
                        print(f"[DEBUG] Calling on_finished callback after dual output")
                        on_finished()
                else:
                    # SINGLE OUTPUT MODE  
                    print(f"[DEBUG] Playing only on virtual mic (device {output_device})")
                    sd.play(vm_arr, audio.frame_rate, device=output_device)
                    sd.wait()
                    
                    if on_finished:
                        print(f"[DEBUG] Calling on_finished callback after VM only")
                        on_finished()
                
            except Exception as e:
                logging.error(f"[TTS] Error playing with sounddevice: {e}")
                print(f"[DEBUG] Error playing with sounddevice: {e}, falling back to pydub")
                play(audio)
                if on_finished:
                    print(f"[DEBUG] Fallback playback complete, calling callback")
                    on_finished()
        else:
            # Standard play
            print(f"[DEBUG] Using standard pydub.playback.play")
            play(audio)
            print(f"[DEBUG] Standard playback complete, calling callback")
            if on_finished:
                on_finished()
        
        # Clean up
        try:
            os.remove(temp_path)
        except:
            pass
        
        # TAMBAHAN: Success logging untuk gTTS
        duration = time.time() - start_time
        logger.info(f"TTS completed (gTTS) in {duration:.2f}s")
            
    except Exception as e:
        # TAMBAHAN: Error logging
        logger.error(f"TTS failed: {str(e)}")
        logging.error(f"[TTS] Error gTTS: {e}")
        print(f"[DEBUG] Error in gTTS: {e}, still calling callback")
        if on_finished:
            on_finished()
            
def check_audio_devices():
    """Cek ketersediaan perangkat audio dan log status."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        logging.info(f"Available audio devices: {len(devices)}")
        for i, dev in enumerate(devices):
            status = "✅" if dev["max_output_channels"] > 0 else "❌"
            logging.info(f"  [{i}] {status} {dev['name']} (Out: {dev['max_output_channels']})")
        return True
    except Exception as e:
        logging.error(f"Failed to check audio devices: {e}")
        return False

# Panggil fungsi ini saat modul dimuat
try:
    check_audio_devices()
except:
    pass