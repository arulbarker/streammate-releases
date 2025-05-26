# modules_server/tts_google.py
import os
import sys
from google.cloud import texttospeech
from dotenv import load_dotenv
import sounddevice as sd
import soundfile as sf
import tempfile
import time
import threading
import traceback

# Load environment variables
load_dotenv()

# modules_server/tts_google.py (perubahan pada fungsi utama)

def speak_with_google_cloud(
    text: str,
    voice_name: str = "id-ID-Standard-A",
    language_code: str = "id-ID",
    device_index: int = None,
    also_play_on_speaker: bool = True,
    on_finished: callable = None
):
    """
    Synthesizes speech from text using Google Cloud TTS with better error handling.
    """
    # Log untuk debugging
    print(f"[DEBUG-GOOGLE] speak_with_google_cloud called with: voice={voice_name}, callback={on_finished is not None}")
    
    # Ambil konfigurasi virtual mic jika tersedia
    try:
        from pathlib import Path
        import json
        
        # Load virtual mic config
        vm_config_path = Path("config/live_state.json")
        if vm_config_path.exists():
            vm_config = json.loads(vm_config_path.read_text(encoding="utf-8"))
            
            # Cek apakah dual output diaktifkan
            also_play_on_speaker = vm_config.get("dual_output", also_play_on_speaker)
            
            # Gunakan device index dari config jika tidak ditentukan
            if device_index is None and vm_config.get("virtual_mic_active", False):
                device_index = vm_config.get("virtual_mic_device_index")
                print(f"[DEBUG-GOOGLE] Using device index from config: {device_index}")
    except Exception as e:
        print(f"[DEBUG-GOOGLE] Error loading VM config: {e}")
    
    # Buat thread terpisah untuk menjalankan TTS agar UI tidak freeze
    tts_thread = threading.Thread(
        target=_tts_worker,
        args=(text, voice_name, language_code, device_index, also_play_on_speaker, on_finished),
        daemon=True
    )
    tts_thread.start()
    return True

def _tts_worker(text, voice_name, language_code, device_index, also_play_on_speaker, on_finished):
    """Worker function to run TTS in a separate thread."""
    temp_path = None
    
    try:
        print(f"[TTS] Memulai TTS: voice_name={voice_name}, lang={language_code}, text='{text[:40]}...'")
        print(f"[DEBUG-GOOGLE] TTS worker started, has callback: {on_finished is not None}")
        
        # Create Google Cloud TTS client
        client = texttospeech.TextToSpeechClient()
        
        # Set up input configuration
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        # Set up voice configuration
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name
        )
        
        # Set up audio configuration
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )

        # Generate speech
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as out:
            out.write(response.audio_content)
            temp_path = out.name

        # Load audio file
        data, fs = sf.read(temp_path, dtype='float32')
        
        # --- IMPLEMENTASI DUAL OUTPUT ---
        try:
            # Check booster settings
            boost_vm = False
            try:
                import json
                from pathlib import Path
                vm_config_path = Path("config/live_state.json")
                if vm_config_path.exists():
                    vm_config = json.loads(vm_config_path.read_text(encoding="utf-8"))
                    boost_vm = vm_config.get("boost_virtual_mic", False)
            except:
                pass
                
            # Create boosted version if needed
            if boost_vm and device_index is not None:
                import numpy as np
                # Boost +3dB (multiply by ~1.4)
                vm_data = data * 1.4
                # Clip to prevent distortion
                vm_data = np.clip(vm_data, -1.0, 1.0)
            else:
                vm_data = data
            
            if device_index is not None and also_play_on_speaker:
                # --- MODE DUAL OUTPUT ---
                print(f"[DEBUG-GOOGLE] Using dual output mode (VM + Speaker)")
                
                # Playback ke virtual mic dalam thread terpisah
                def vm_thread_func():
                    try:
                        sd.play(vm_data, fs, device=device_index)
                        sd.wait()  # Wait for playback to finish
                        print(f"[DEBUG-GOOGLE] VM playback completed")
                    except Exception as e:
                        print(f"[DEBUG-GOOGLE] Error in VM thread: {e}")
                
                # Start thread for virtual mic
                vm_thread = threading.Thread(target=vm_thread_func, daemon=True)
                vm_thread.start()
                
                # Play di speaker default dan tunggu
                sd.play(data, fs)
                sd.wait()
                
                # Tunggu virtual mic thread selesai
                vm_thread.join(timeout=10.0)
                
            elif device_index is not None:
                # --- MODE VM ONLY ---
                print(f"[DEBUG-GOOGLE] Playing only on virtual mic (device {device_index})")
                sd.play(vm_data, fs, device=device_index)
                sd.wait()
            else:
                # --- MODE SPEAKER ONLY ---
                print(f"[DEBUG-GOOGLE] Playing only on default speaker")
                sd.play(data, fs)
                sd.wait()
        
        except Exception as e:
            print(f"[TTS] Error in audio routing: {e}")
            # Fallback to simple playback
            sd.play(data, fs)
            sd.wait()

        print("[TTS] Google Cloud TTS berhasil")
        
        # PENTING: Panggil callback on_finished setelah playback selesai
        if on_finished:
            try:
                print(f"[DEBUG-GOOGLE] Calling on_finished callback")
                # Use QTimer if in Qt environment
                if 'PyQt6' in sys.modules:
                    from PyQt6.QtCore import QTimer, QCoreApplication
                    print(f"[DEBUG-GOOGLE] Using QTimer.singleShot for callback")
                    QTimer.singleShot(0, on_finished)
                else:
                    print(f"[DEBUG-GOOGLE] Calling callback directly")
                    on_finished()
                print(f"[DEBUG-GOOGLE] Callback initiated")
            except Exception as callback_error:
                print(f"[TTS] Error in on_finished callback: {callback_error}")
                print(f"{traceback.format_exc()}")
        else:
            print(f"[DEBUG-GOOGLE] No callback provided")
        
    except Exception as e:
        print(f"❌ Google Cloud TTS gagal: {e}")
        print(f"Stack trace: {traceback.format_exc()}")
        
        # Tetap panggil callback jika terjadi error
        if on_finished:
            try:
                print(f"[DEBUG-GOOGLE] Calling on_finished callback after error")
                if 'PyQt6' in sys.modules:
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(0, on_finished)
                else:
                    on_finished()
            except Exception as callback_error:
                print(f"[TTS] Error in on_finished callback after error: {callback_error}")
    
    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass

# Test function if run directly
if __name__ == "__main__":
    test_text = "Ini adalah test text to speech menggunakan Google Cloud."
    
    def test_callback():
        print("Callback called - audio playback is complete!")
    
    speak_with_google_cloud(
        test_text, 
        voice_name="id-ID-Standard-A",
        on_finished=test_callback
    )
    # Sleep to let the thread finish
    time.sleep(10)