# modules_client/animaze_controller.py

import socket
import numpy as np
import time
import threading
import math
import random
from modules_client.animaze_profiles import AnimazeProfiles

class AnimazeController:
    """
    Controller untuk Animaze Programmable Tracker.
    Mengelola koneksi dan pengiriman data ke Animaze.
    """
    
    def __init__(self, host="127.0.0.1", port=9003):
        self.host = host
        self.port = port
        self.connected = False
        self.sock = None
        
        # State
        self.current_personality = "Ceria"
        self.is_speaking = False
        self.speech_intensity = 0.5
        self.running = False
        
        # Tracking waktu
        self.last_update = 0
        self.frame_time = 1/30  # 30fps
        
        # Connection state
        self.last_ping_time = 0
        self.ping_interval = 1.0  # Ping setiap 1 detik
    
    def connect(self):
        """Hubungkan ke Animaze Programmable Tracker."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.connected = True
            
            # Mulai thread untuk animasi dan update
            self.running = True
            self.animation_thread = threading.Thread(target=self._animation_loop)
            self.animation_thread.daemon = True
            self.animation_thread.start()
            
            return True
        except Exception as e:
            print(f"Error connecting to Animaze: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Putuskan koneksi dengan Animaze."""
        self.running = False
        if self.animation_thread:
            self.animation_thread.join(timeout=1.0)
        
        if self.sock:
            self.sock.close()
            self.sock = None
        
        self.connected = False
    
    def set_personality(self, personality):
        """Set kepribadian saat ini."""
        self.current_personality = personality
    
    def set_speaking(self, is_speaking, intensity=0.5):
        """Set status berbicara dan intensitasnya."""
        self.is_speaking = is_speaking
        self.speech_intensity = max(0.0, min(1.0, intensity))
    
    def trigger_expression(self, expression_name, intensity=1.0, duration=1.0):
        """
        Picu ekspresi tertentu untuk durasi singkat.
        
        Args:
            expression_name: Nama ekspresi ('smile', 'surprised', dll)
            intensity: Intensitas ekspresi (0.0-1.0)
            duration: Durasi dalam detik
        """
        # Implementasi trigger ekspresi khusus
        pass
    
    def _animation_loop(self):
        """Thread loop utama untuk animasi dan pengiriman data ke Animaze."""
        while self.running and self.connected:
            current_time = time.time()
            
            # Batasi frame rate
            if current_time - self.last_update < self.frame_time:
                time.sleep(0.005)  # Sleep kecil untuk mengurangi CPU usage
                continue
            
            # Ping Animaze secara berkala
            if current_time - self.last_ping_time > self.ping_interval:
                self._send_ping()
                self.last_ping_time = current_time
            
            # Dapatkan Action Units saat ini berdasarkan kepribadian dan status
            action_units = AnimazeProfiles.get_action_units(
                self.current_personality,
                self.is_speaking,
                self.speech_intensity
            )
            
            # Kirim ke Animaze
            self._send_action_units(action_units)
            
            # Update timestamp
            self.last_update = current_time
    
    def _send_action_units(self, action_units):
        """Kirim Action Units ke Animaze."""
        if not self.connected or not self.sock:
            return False
        
        try:
            self.sock.sendto(action_units.tobytes(), (self.host, self.port))
            return True
        except Exception as e:
            print(f"Error sending data to Animaze: {e}")
            self.connected = False
            return False
    
    def _send_ping(self):
        """Kirim ping ke Animaze untuk mempertahankan koneksi."""
        if not self.connected or not self.sock:
            return
        
        # Ping sederhana (array kosong)
        empty_data = np.zeros(1, dtype=np.float32)
        try:
            self.sock.sendto(empty_data.tobytes(), (self.host, self.port))
        except:
            self.connected = False