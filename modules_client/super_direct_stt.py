#!/usr/bin/env python3
"""
SUPER DIRECT Google Cloud Speech-to-Text
Zero overhead, direct API calls only
"""

import numpy as np
import sounddevice as sd
from PyQt6.QtCore import QThread, pyqtSignal
from google.cloud import speech
import time

class SuperDirectSTTThread(QThread):
    """
    SUPER DIRECT STT - Zero overhead, direct Google API calls
    No speech_recognition library overhead AT ALL
    """
    result = pyqtSignal(str)
    
    def __init__(self, mic_index=0, language="id-ID"):
        super().__init__()
        self.mic_index = mic_index
        self.language = language
        self._is_running = True
        self.recording = False
        
        # Direct Google client (no wrapper)
        self.client = speech.SpeechClient()
        
        # Minimal config for maximum speed
        self.config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language,
            model="latest_short",  # Fastest model for short speech
            use_enhanced=True,  # Enable for better accuracy with fast processing
            enable_automatic_punctuation=False,  # Disable for speed
            profanity_filter=False,  # Disable for speed
            enable_spoken_punctuation=False,  # Disable for speed
            enable_spoken_emojis=False,  # Disable for speed
        )
        
        print(f"[Super Direct STT] Initialized for {language} - ZERO overhead mode")
    
    def run(self):
        """Ultra-fast direct Google API call"""
        try:
            print(f"[Super Direct STT] Starting audio capture...")
            
            # Direct audio capture - no chunking overhead
            sample_rate = 16000
            max_duration = 8  # Reduced from 10 to 8 seconds for faster processing
            
            print(f"[Super Direct STT] Recording...")
            
            # Record all audio at once (no chunking overhead)
            audio_data = sd.rec(
                int(sample_rate * max_duration), 
                samplerate=sample_rate,
                channels=1,
                device=self.mic_index,
                dtype=np.int16
            )
            
            # Wait for recording to complete
            while self.recording and self._is_running:
                sd.wait(100)  # Check every 100ms
            
            # Stop recording immediately when button released
            sd.stop()
            
            # Get actual recorded length
            silence_threshold = 500
            last_sound = len(audio_data) - 1
            
            # Find last non-silent sample (trim silence)
            for i in range(len(audio_data) - 1, -1, -1):
                if abs(audio_data[i][0]) > silence_threshold:
                    last_sound = i
                    break
            
            if last_sound < sample_rate * 0.5:  # Less than 0.5 seconds
                print(f"[Super Direct STT] Audio too short")
                self.result.emit("")
                return
            
            # Trim to actual speech
            audio_data = audio_data[:last_sound + int(sample_rate * 0.1)]  # Add small padding
            audio_duration = len(audio_data) / sample_rate
            
            print(f"[Super Direct STT] Captured {audio_duration:.2f}s audio")
            
            # Minimal preprocessing (only DC removal)
            audio_flat = audio_data.flatten().astype(np.float32)
            audio_flat = audio_flat - np.mean(audio_flat)  # Remove DC offset only
            
            # Normalize lightly
            max_val = np.max(np.abs(audio_flat))
            if max_val > 0:
                audio_flat = audio_flat / max_val * 0.9
            
            # Convert to bytes (direct)
            audio_bytes = (audio_flat * 32767).astype(np.int16).tobytes()
            
            # Create audio object (direct)
            audio_obj = speech.RecognitionAudio(content=audio_bytes)
            
            # DIRECT API CALL - NO WRAPPER!
            print(f"[Super Direct STT] Calling Google API directly...")
            start_time = time.time()
            
            response = self.client.recognize(config=self.config, audio=audio_obj)
            
            api_time = time.time() - start_time
            print(f"[Super Direct STT] API response in {api_time:.3f}s")
            
            # Process results (direct)
            if response.results and response.results[0].alternatives:
                transcript = response.results[0].alternatives[0].transcript.strip()
                
                if transcript:
                    print(f"[Super Direct STT] SUCCESS: '{transcript}'")
                    # 🎯 EMIT TO PARENT: Direct connection to GoogleSTTThread
                    if hasattr(self, 'parent_thread') and self.parent_thread:
                        print(f"[Super Direct STT] ⚡ Emitting to parent GoogleSTTThread...")
                        self.parent_thread.result.emit(transcript)
                    else:
                        print(f"[Super Direct STT] ⚡ No parent, using own signal...")
                        self.result.emit(transcript)
                else:
                    print(f"[Super Direct STT] Empty transcript")
                    if hasattr(self, 'parent_thread') and self.parent_thread:
                        self.parent_thread.result.emit("")
                    else:
                        self.result.emit("")
            else:
                print(f"[Super Direct STT] No speech detected")
                if hasattr(self, 'parent_thread') and self.parent_thread:
                    self.parent_thread.result.emit("")
                else:
                    self.result.emit("")
                
        except Exception as e:
            print(f"[Super Direct STT] Error: {e}")
            self.result.emit("")
    
    def start_recording(self):
        """Start recording"""
        self.recording = True
        if not self.isRunning():
            self.start()
    
    def stop_recording(self):
        """Stop recording"""
        self.recording = False
    
    def stop(self):
        """Stop thread"""
        self._is_running = False
        self.recording = False


if __name__ == "__main__":
    # Quick test
    print("Testing Super Direct STT...")
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    stt = SuperDirectSTTThread()
    stt.result.connect(lambda text: print(f"Result: '{text}'"))
    
    print("Press Enter to start recording, press Enter again to stop...")
    input()
    stt.start_recording()
    input() 
    stt.stop_recording()
    
    stt.wait()
    print("Done!") 