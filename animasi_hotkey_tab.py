# ui/animasi_hotkey_tab.py
import keyboard
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QCheckBox, 
    QGroupBox, QSpinBox, QHBoxLayout, QSlider
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    filename=str(log_dir / "hotkey.log"),
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

class AnimasiHotkeyTab(QWidget):
    """Tab untuk otomasi hotkey F1/F2 untuk animasi karakter"""
    
    # Signals
    startTTSHotkeyPressed = pyqtSignal()
    endTTSHotkeyPressed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.tts_timer = QTimer()
        self.tts_timer.setSingleShot(True)
        self.tts_timer.timeout.connect(self._auto_press_f2)
        
        self.init_ui()
        logging.info("Animasi Hotkey Tab initialized - Auto F1/F2")
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("🎭 Animasi Hotkey Controller")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            "Otomasi hotkey untuk sinkronisasi animasi dengan TTS:\n"
            "• F1 otomatis saat AI mulai bicara\n"
            "• F2 otomatis dengan timer setelah TTS selesai"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Enable/Disable
        self.enable_checkbox = QCheckBox("Aktifkan Otomasi Hotkey")
        self.enable_checkbox.setChecked(True)
        layout.addWidget(self.enable_checkbox)
        
        # Timer Settings
        timer_group = QGroupBox("⏱️ Pengaturan Timer F2")
        timer_layout = QVBoxLayout(timer_group)
        
        # Delay slider
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Delay F2 (detik):"))
        
        self.delay_slider = QSlider(Qt.Orientation.Horizontal)
        self.delay_slider.setRange(0, 20)  # 0-20 detik
        self.delay_slider.setValue(3)  # Default 3 detik
        self.delay_slider.valueChanged.connect(self._update_delay_label)
        delay_layout.addWidget(self.delay_slider)
        
        self.delay_label = QLabel("3.0s")
        self.delay_label.setMinimumWidth(40)
        delay_layout.addWidget(self.delay_label)
        
        timer_layout.addLayout(delay_layout)
        
        # Auto-calculate option
        self.auto_calc_checkbox = QCheckBox("Hitung otomatis berdasarkan panjang teks")
        self.auto_calc_checkbox.setChecked(True)
        timer_layout.addWidget(self.auto_calc_checkbox)
        
        # Multiplier for auto calculation
        mult_layout = QHBoxLayout()
        mult_layout.addWidget(QLabel("Multiplier:"))
        
        self.multiplier_spin = QSpinBox()
        self.multiplier_spin.setRange(50, 200)  # 50% - 200%
        self.multiplier_spin.setValue(120)  # Default 120%
        self.multiplier_spin.setSuffix("%")
        mult_layout.addWidget(self.multiplier_spin)
        
        timer_layout.addLayout(mult_layout)
        layout.addWidget(timer_group)
        
        # Test Buttons
        test_group = QGroupBox("🧪 Test Manual")
        test_layout = QVBoxLayout(test_group)
        
        test_f1_btn = QPushButton("Test F1 (Start Animation)")
        test_f1_btn.clicked.connect(self._test_f1)
        test_layout.addWidget(test_f1_btn)
        
        test_f2_btn = QPushButton("Test F2 (Stop Animation)")
        test_f2_btn.clicked.connect(self._test_f2)
        test_layout.addWidget(test_f2_btn)
        
        test_auto_btn = QPushButton("Test Sequence Otomatis")
        test_auto_btn.clicked.connect(self._test_auto_sequence)
        test_layout.addWidget(test_auto_btn)
        
        layout.addWidget(test_group)
        
        # Status
        self.status_label = QLabel("✓ Ready")
        self.status_label.setStyleSheet("color: green;")
        layout.addWidget(self.status_label)
        
        # Log viewer
        layout.addWidget(QLabel("📋 Activity Log:"))
        self.log_text = QLabel("Waiting for TTS events...")
        self.log_text.setWordWrap(True)
        self.log_text.setStyleSheet("background-color: #f0f0f0; padding: 5px;")
        layout.addWidget(self.log_text)
    
    def _update_delay_label(self, value):
        """Update label delay"""
        delay = value / 10.0  # Convert to seconds with decimal
        self.delay_label.setText(f"{delay:.1f}s")
    
    def start_tts_hotkey(self, text=""):
        """Otomatis tekan F1 saat TTS mulai"""
        if not self.enable_checkbox.isChecked():
            return
        
        try:
            # Press F1
            keyboard.press_and_release("F1")
            logging.info("F1 pressed automatically - TTS started")
            self.status_label.setText("🔴 F1 Sent - Animating")
            self.status_label.setStyleSheet("color: red;")
            
            self.log_text.setText(f"[{self._get_time()}] F1 ditekan - TTS dimulai")
            
            # Calculate timer for F2
            if self.auto_calc_checkbox.isChecked() and text:
                # Estimasi durasi berdasarkan panjang teks
                # Asumsi: ~150 karakter per detik untuk bahasa Indonesia
                char_count = len(text)
                base_duration = char_count / 150  # detik
                
                # Apply multiplier
                multiplier = self.multiplier_spin.value() / 100.0
                duration = base_duration * multiplier
                
                # Minimum 1 detik, maksimum 20 detik
                duration = max(1.0, min(20.0, duration))
                
                self.log_text.setText(
                    f"[{self._get_time()}] F1 ditekan\n"
                    f"Text: {len(text)} karakter\n"
                    f"Estimasi: {duration:.1f} detik"
                )
            else:
                # Use manual delay
                duration = self.delay_slider.value() / 10.0
            
            # Start timer for F2
            self.tts_timer.start(int(duration * 1000))  # Convert to milliseconds
            
        except Exception as e:
            logging.error(f"Error sending F1: {str(e)}")
            self.status_label.setText("❌ Error F1")
            self.status_label.setStyleSheet("color: red;")
    
    def end_tts_hotkey(self):
        """Manual trigger F2 (jika diperlukan)"""
        self._auto_press_f2()
    
    def _auto_press_f2(self):
        """Otomatis tekan F2 setelah timer"""
        if not self.enable_checkbox.isChecked():
            return
        
        try:
            # Press F2
            keyboard.press_and_release("F2")
            logging.info("F2 pressed automatically - TTS ended")
            self.status_label.setText("✓ F2 Sent - Idle")
            self.status_label.setStyleSheet("color: green;")
            
            self.log_text.setText(
                self.log_text.text() + 
                f"\n[{self._get_time()}] F2 ditekan - TTS selesai"
            )
            
        except Exception as e:
            logging.error(f"Error sending F2: {str(e)}")
            self.status_label.setText("❌ Error F2")
            self.status_label.setStyleSheet("color: red;")
    
    def _test_f1(self):
        """Test manual F1"""
        keyboard.press_and_release("F1")
        self.status_label.setText("Test F1 OK")
        self.log_text.setText(f"[{self._get_time()}] Test F1 ditekan manual")
    
    def _test_f2(self):
        """Test manual F2"""
        keyboard.press_and_release("F2")
        self.status_label.setText("Test F2 OK")
        self.log_text.setText(f"[{self._get_time()}] Test F2 ditekan manual")
    
    def _test_auto_sequence(self):
        """Test sequence otomatis F1 -> Timer -> F2"""
        self.log_text.setText(f"[{self._get_time()}] Testing auto sequence...")
        self.start_tts_hotkey("Ini adalah test sequence otomatis untuk animasi")
    
    def _get_time(self):
        """Get current time string"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")