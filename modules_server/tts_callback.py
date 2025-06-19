# modules_server/tts_callback.py
import threading
from modules_server.tts_engine import speak as original_speak
from modules_server.tts_google import speak_with_google_cloud as original_speak_google

def speak_with_callback(text, language_code=None, voice_name=None, callback=None):
    """
    Wrapper untuk speak() dengan dukungan callback.
    
    Args:
        text: Teks yang akan diucapkan
        language_code: Kode bahasa
        voice_name: Nama suara
        callback: Fungsi yang dipanggil setelah TTS selesai
    """
    try:
        # Panggil TTS original dalam thread terpisah
        def tts_thread():
            try:
                original_speak(text, language_code, voice_name)
                # TTS selesai, panggil callback
                if callback:
                    callback()
            except Exception as e:
                print(f"Error in TTS thread: {e}")
                # Tetap panggil callback
                if callback:
                    callback()
        
        # Jalankan TTS dalam thread terpisah
        t = threading.Thread(target=tts_thread, daemon=True)
        t.start()
        
        return True
    except Exception as e:
        print(f"Error setting up speak_with_callback: {e}")
        # Tetap panggil callback
        if callback:
            callback()
        return False

def speak_with_google_cloud_callback(text, voice_name=None, language_code=None, callback=None):
    """
    Wrapper untuk speak_with_google_cloud() dengan dukungan callback.
    
    Args:
        text: Teks yang akan diucapkan
        voice_name: Nama suara
        language_code: Kode bahasa
        callback: Fungsi yang dipanggil setelah TTS selesai
    """
    try:
        # Panggil TTS Google dalam thread terpisah
        def tts_thread():
            try:
                original_speak_google(text, voice_name, language_code)
                # TTS selesai, panggil callback
                if callback:
                    callback()
            except Exception as e:
                print(f"Error in Google TTS thread: {e}")
                # Tetap panggil callback
                if callback:
                    callback()
        
        # Jalankan TTS dalam thread terpisah
        t = threading.Thread(target=tts_thread, daemon=True)
        t.start()
        
        return True
    except Exception as e:
        print(f"Error setting up speak_with_google_cloud_callback: {e}")
        # Tetap panggil callback
        if callback:
            callback()
        return False
