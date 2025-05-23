# ui/overlay_tab.py - VERSI PERBAIKAN

import re
import json
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QEasingCurve
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QCheckBox,
    QSlider,
    QPushButton,
    QColorDialog,
    QSizePolicy,
    QScrollArea,
    QFrame,
    QSpinBox,
    QHBoxLayout,
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QGroupBox,
    QFileDialog,
    QMessageBox
)
from PyQt6.QtGui import QFont, QColor, QPalette

# Config Manager untuk menyimpan pengaturan
try:
    from modules_client.config_manager import ConfigManager
except ImportError:
    from modules_server.config_manager import ConfigManager

class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        # Setup window properties
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint  # Tanpa border window
        )
        self.setWindowTitle("StreamMate AI Overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Default style
        self.bg_rgba = (0, 0, 0, 128)
        self.text_color = "#FFFFFF"
        self.font_size = 16
        self.position = "bottom-left"
        self.animation_type = "none"
        self.display_mode = "normal"  # normal, reply-only, author-only
        
        # Animation properties
        self.animation = None
        self.fade_animation = None

        # Setup content
        self._setup_ui()
        
        # Initialize position and size
        self.resize(400, 100)
        self._update_position()
        
        # State for preventing overlay flicker on update
        self.current_text = ""
        self.last_update_time = datetime.now()

    def _setup_ui(self):
        # PENTING: Pakai SATU layout untuk root
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Content container dengan background color
        self.container = QFrame(self)
        self.container.setObjectName("overlay_container")
        
        # Label untuk teks
        self.label = QLabel("", self.container)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        
        # Layout untuk container
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        container_layout.addWidget(self.label)
        
        # Tambahkan container ke main layout
        self.main_layout.addWidget(self.container)
        
        # Update styles
        self._update_style()

    def _update_style(self):
        """Update tampilan berdasarkan pengaturan style."""
        try:
            # Background color untuk container
            r, g, b, a = self.bg_rgba
            
            # Custom style untuk container
            self.container.setStyleSheet(f"""
                QFrame#overlay_container {{
                    background-color: rgba({r},{g},{b},{a});
                    border-radius: 10px;
                    border: 1px solid rgba(255,255,255,0.2);
                }}
            """)
            
            # Custom style untuk label
            self.label.setStyleSheet(f"""
                color: {self.text_color};
                font-size: {self.font_size}px;
                font-family: 'Arial', sans-serif;
                padding: 5px;
            """)
            
            # Font weight
            font = self.label.font()
            font.setPointSize(int(self.font_size * 0.75))  # Konversi px to point size
            font.setBold(True)
            self.label.setFont(font)
            
        except Exception as e:
            print(f"Error saat update style: {e}")

    def _update_position(self):
        """Update posisi overlay berdasarkan setting."""
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        
        # Margin dari tepi
        margin = 20
        
        if self.position == "top-left":
            self.move(margin, margin)
        elif self.position == "top-right":
            self.move(screen.width() - self.width() - margin, margin)
        elif self.position == "bottom-left":
            self.move(margin, screen.height() - self.height() - margin)
        elif self.position == "bottom-right":
            self.move(screen.width() - self.width() - margin, 
                     screen.height() - self.height() - margin)
        elif self.position == "center":
            self.move((screen.width() - self.width()) // 2,
                     (screen.height() - self.height()) // 2)

    def set_text(self, author: str, reply: str):
        """Set teks overlay dengan animasi yang dipilih."""
        try:
            # Sanitize input 
            if author:
                author = re.sub(r"[^\w\s]", "", author)
            if reply:
                reply = re.sub(r"[^\w\s\?\!\.\,]", "", reply)
            
            # Format sesuai mode
            if self.display_mode == "normal" and author and reply:
                text = f"{author}: {reply}"
            elif self.display_mode == "reply-only" and reply:
                text = reply
            elif self.display_mode == "author-only" and author:
                text = author
            else:
                text = ""
                
            # Skip jika teks sama dengan sebelumnya untuk menghindari flicker
            if text == self.current_text:
                return
                
            self.current_text = text
            
            # Terapkan animasi sesuai jenis
            if self.animation_type == "fade" and text:
                self._animate_fade(text)
            elif self.animation_type == "slide-left" and text:
                self._animate_slide(text, from_left=True)
            elif self.animation_type == "slide-right" and text:
                self._animate_slide(text, from_left=False)
            elif self.animation_type == "bounce" and text:
                self._animate_bounce(text)
            else:
                # Tanpa animasi
                self.label.setText(text)
                
            # Update ukuran widget secara dinamis berdasarkan konten
            self._dynamic_resize()
            
        except Exception as e:
            print(f"Error saat set text: {e}")
            # Fallback tanpa animasi
            self.label.setText(f"{author}: {reply}")
            
    def _dynamic_resize(self):
        """Resize window secara dinamis berdasarkan konten label."""
        content_width = self.label.sizeHint().width() + 40  # 20px padding kanan kiri
        content_height = self.label.sizeHint().height() + 40  # 20px padding atas bawah
        
        # Set minimum size
        min_width, min_height = 200, 60
        
        # Tentukan ukuran final
        final_width = max(min_width, min(content_width, 600))  # Max width 600px
        final_height = max(min_height, min(content_height, 300))  # Max height 300px
        
        # Resize window
        self.resize(final_width, final_height)
        
        # Update posisi untuk tetap dalam batas layar
        self._update_position()
    
    def _animate_fade(self, text):
        """Animasi fade in/out."""
        # Setup opacity animation
        self.label.setStyleSheet(f"""
            color: {self.text_color};
            font-size: {self.font_size}px;
            opacity: 0;
        """)
        
        # Set text first
        self.label.setText(text)
        
        # Simple timer-based fade in
        def fade_in():
            self.label.setStyleSheet(f"""
                color: {self.text_color};
                font-size: {self.font_size}px;
                opacity: 1;
                transition: opacity 0.5s;
            """)
        
        QTimer.singleShot(100, fade_in)
    
    def _animate_slide(self, text, from_left=True):
        """Animasi slide dari kiri/kanan."""
        # Set text first
        self.label.setText(text)
        
        # Calculate start position outside view
        start_x = -self.width() if from_left else self.width()
        end_x = 0
        
        # Setup animation
        if self.animation:
            self.animation.stop()
            
        # Create property animation
        self.animation = QPropertyAnimation(self.label, b"geometry")
        self.animation.setDuration(500)
        self.animation.setStartValue(QRect(start_x, 0, self.label.width(), self.label.height()))
        self.animation.setEndValue(QRect(end_x, 0, self.label.width(), self.label.height()))
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.start()
    
    def _animate_bounce(self, text):
        """Animasi bounce."""
        # Set text first
        self.label.setText(text)
        
        # Setup animation
        if self.animation:
            self.animation.stop()
            
        # Create property animation
        self.animation = QPropertyAnimation(self.label, b"geometry")
        self.animation.setDuration(800)
        
        # Start slightly above
        start_y = -20
        
        # Bounce sequence
        self.animation.setStartValue(QRect(0, start_y, self.label.width(), self.label.height()))
        self.animation.setEndValue(QRect(0, 0, self.label.width(), self.label.height()))
        self.animation.setEasingCurve(QEasingCurve.Type.OutBounce)
        self.animation.start()

class OverlayTab(QWidget):
    def __init__(self):
        super().__init__()
        
        # Config manager
        self.cfg = ConfigManager("config/settings.json")
        
        # Overlay window instance
        self.overlay = OverlayWindow()
        
        # Timer untuk auto-clear teks
        self.clear_timer = QTimer(self)
        self.clear_timer.setSingleShot(True)
        self.clear_timer.timeout.connect(lambda: self.overlay.set_text("", ""))
        
        # Setup UI
        self._setup_ui()
        
        # Load saved settings
        self._load_settings()

    def _setup_ui(self):
        """Setup UI dengan struktur yang lebih terorganisir."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        
        # Proper size policy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Scroll area untuk konten yang panjang
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        
        # Header
        header = QLabel("🪧 AI Response Overlay")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #1877F2;")
        content_layout.addWidget(header)
        
        # Description
        desc = QLabel("Tampilkan balasan AI di layar livestream untuk membantu penonton membaca respons")
        desc.setWordWrap(True)
        content_layout.addWidget(desc)

        # ========== 1. KONTROL UTAMA ==========
        control_group = QGroupBox("🎮 Kontrol Utama")
        control_layout = QVBoxLayout()
        
        # Toggle On/Off
        toggle_row = QHBoxLayout()
        self.chk_toggle = QCheckBox("Tampilkan Overlay")
        self.chk_toggle.stateChanged.connect(self._on_toggle)
        toggle_row.addWidget(self.chk_toggle)
        
        # Tombol preview untuk testing
        preview_btn = QPushButton("👁️ Preview")
        preview_btn.clicked.connect(self._test_preview)
        toggle_row.addWidget(preview_btn)
        
        # Tombol clear
        clear_btn = QPushButton("🗑️ Clear Overlay")
        clear_btn.clicked.connect(lambda: self.overlay.set_text("", ""))
        toggle_row.addWidget(clear_btn)
        
        control_layout.addLayout(toggle_row)
        
        # Stay on top checkbox
        self.chk_stay_on_top = QCheckBox("Selalu Tampil di Atas (Stay on Top)")
        self.chk_stay_on_top.setChecked(True)
        control_layout.addWidget(self.chk_stay_on_top)
        
        control_group.setLayout(control_layout)
        content_layout.addWidget(control_group)

        # ========== 2. DURASI & UKURAN ==========
        settings_group = QGroupBox("⚙️ Pengaturan Umum")
        settings_layout = QVBoxLayout()
        
        # Durasi teks
        settings_layout.addWidget(QLabel("Durasi Teks (detik):"))
        duration_row = QHBoxLayout()
        
        self.duration_slider = QSlider(Qt.Orientation.Horizontal)
        self.duration_slider.setRange(1, 60)
        self.duration_slider.setValue(5)
        self.duration_slider.valueChanged.connect(self._on_duration_change)
        duration_row.addWidget(self.duration_slider)
        
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 60)
        self.duration_spin.setValue(5)
        self.duration_spin.valueChanged.connect(self.duration_slider.setValue)
        self.duration_slider.valueChanged.connect(self.duration_spin.setValue)
        duration_row.addWidget(self.duration_spin)
        
        duration_row.addWidget(QLabel("detik"))
        settings_layout.addLayout(duration_row)
        
        # Ukuran overlay
        settings_layout.addWidget(QLabel("Ukuran Overlay:"))
        size_row = QHBoxLayout()
        
        size_row.addWidget(QLabel("Lebar:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(200, 800)
        self.width_spin.setValue(400)
        self.width_spin.setSuffix(" px")
        self.width_spin.valueChanged.connect(lambda v: self._resize_overlay(v, self.height_spin.value()))
        size_row.addWidget(self.width_spin)
        
        size_row.addWidget(QLabel("Tinggi:"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(60, 400)
        self.height_spin.setValue(100)
        self.height_spin.setSuffix(" px")
        self.height_spin.valueChanged.connect(lambda v: self._resize_overlay(self.width_spin.value(), v))
        size_row.addWidget(self.height_spin)
        
        # Auto-size checkbox
        self.chk_auto_size = QCheckBox("Ukuran Otomatis (Sesuai Konten)")
        self.chk_auto_size.setChecked(True)
        size_row.addWidget(self.chk_auto_size)
        
        settings_layout.addLayout(size_row)
        
        settings_group.setLayout(settings_layout)
        content_layout.addWidget(settings_group)

        # ========== 3. POSISI OVERLAY ==========
        position_group = QGroupBox("📍 Posisi Overlay")
        position_layout = QVBoxLayout()
        
        self.position_combo = QComboBox()
        self.position_combo.addItems([
            "Kiri Atas", "Kanan Atas", 
            "Kiri Bawah", "Kanan Bawah", 
            "Tengah"
        ])
        self.position_combo.setCurrentIndex(2)  # Default kiri bawah
        self.position_combo.currentTextChanged.connect(self._on_position_change)
        position_layout.addWidget(self.position_combo)
        
        position_group.setLayout(position_layout)
        content_layout.addWidget(position_group)

        # ========== 4. ANIMASI ==========
        animation_group = QGroupBox("✨ Efek Animasi")
        animation_layout = QVBoxLayout()
        
        self.animation_combo = QComboBox()
        self.animation_combo.addItems([
            "Tanpa Animasi",
            "Fade In/Out",
            "Slide dari Kiri",
            "Slide dari Kanan",
            "Bounce"
        ])
        self.animation_combo.currentTextChanged.connect(self._on_animation_change)
        animation_layout.addWidget(self.animation_combo)
        
        animation_group.setLayout(animation_layout)
        content_layout.addWidget(animation_group)

        # ========== 5. TAMPILAN ==========
        appearance_group = QGroupBox("🎨 Pengaturan Tampilan")
        appearance_layout = QVBoxLayout()
        
        # Font size slider 
        appearance_layout.addWidget(QLabel("Ukuran Teks:"))
        font_row = QHBoxLayout()
        
        self.font_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setRange(8, 72)
        self.font_slider.setValue(16)
        self.font_slider.valueChanged.connect(self._on_fontsize)
        font_row.addWidget(self.font_slider)
        
        self.font_label = QLabel("16 px")
        font_row.addWidget(self.font_label)
        appearance_layout.addLayout(font_row)
        
        # Background opacity slider
        appearance_layout.addWidget(QLabel("Transparansi Latar:"))
        opacity_row = QHBoxLayout()
        
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 255)
        self.opacity_slider.setValue(128)
        self.opacity_slider.valueChanged.connect(self._on_opacity)
        opacity_row.addWidget(self.opacity_slider)
        
        self.opacity_label = QLabel("50%")
        opacity_row.addWidget(self.opacity_label)
        appearance_layout.addLayout(opacity_row)

        # Background color picker
        bg_color_row = QHBoxLayout()
        self.btn_bg_color = QPushButton("🎨 Pilih Warna Latar")
        self.btn_bg_color.clicked.connect(self._pick_bg_color)
        bg_color_row.addWidget(self.btn_bg_color)
        
        self.bg_color_preview = QLabel("⬛")
        self.bg_color_preview.setStyleSheet("font-size: 20px;")
        bg_color_row.addWidget(self.bg_color_preview)
        appearance_layout.addLayout(bg_color_row)

        # Text color picker
        text_color_row = QHBoxLayout()
        self.btn_text_color = QPushButton("🎨 Pilih Warna Teks")
        self.btn_text_color.clicked.connect(self._pick_text_color)
        text_color_row.addWidget(self.btn_text_color)
        
        self.text_color_preview = QLabel("⬜")
        self.text_color_preview.setStyleSheet("font-size: 20px; color: white;")
        text_color_row.addWidget(self.text_color_preview)
        appearance_layout.addLayout(text_color_row)

        # Green screen toggle
        self.chk_greenscreen = QCheckBox("🟢 Green Screen Mode")
        self.chk_greenscreen.stateChanged.connect(self._on_greenscreen)
        appearance_layout.addWidget(self.chk_greenscreen)
        
        appearance_group.setLayout(appearance_layout)
        content_layout.addWidget(appearance_group)

        # ========== 6. MODE TAMPILAN ==========
        mode_group = QGroupBox("📺 Mode Tampilan")
        mode_layout = QVBoxLayout()
        
        self.mode_group = QButtonGroup()
        
        self.mode_normal = QRadioButton("Mode Normal (Author + Reply)")
        self.mode_normal.setChecked(True)
        self.mode_group.addButton(self.mode_normal, 0)
        mode_layout.addWidget(self.mode_normal)
        
        self.mode_reply = QRadioButton("Reply Only (Tanpa Nama)")
        self.mode_group.addButton(self.mode_reply, 1)
        mode_layout.addWidget(self.mode_reply)
        
        self.mode_author = QRadioButton("Author Only")
        self.mode_group.addButton(self.mode_author, 2)
        mode_layout.addWidget(self.mode_author)
        
        # Connect mode buttons
        self.mode_group.buttonClicked.connect(self._on_mode_changed)
        
        mode_group.setLayout(mode_layout)
        content_layout.addWidget(mode_group)

        # ========== 7. PRESET TEMPLATES ==========
        preset_group = QGroupBox("🔖 Template Preset")
        preset_layout = QVBoxLayout()
        
        preset_layout.addWidget(QLabel("Preset Style:"))
        preset_row = QHBoxLayout()
        
        self.btn_preset1 = QPushButton("🎮 Gaming")
        self.btn_preset1.clicked.connect(lambda: self._apply_preset("gaming"))
        preset_row.addWidget(self.btn_preset1)
        
        self.btn_preset2 = QPushButton("🔍 Minimal")
        self.btn_preset2.clicked.connect(lambda: self._apply_preset("minimal"))
        preset_row.addWidget(self.btn_preset2)
        
        self.btn_preset3 = QPushButton("🌈 Colorful")
        self.btn_preset3.clicked.connect(lambda: self._apply_preset("colorful"))
        preset_row.addWidget(self.btn_preset3)
        
        preset_layout.addLayout(preset_row)
        
        # Save/load preset
        preset_io_row = QHBoxLayout()
        
        self.btn_save_preset = QPushButton("💾 Save Current Setup")
        self.btn_save_preset.clicked.connect(self._save_current_preset)
        preset_io_row.addWidget(self.btn_save_preset)
        
        self.btn_load_preset = QPushButton("📂 Load Preset")
        self.btn_load_preset.clicked.connect(self._load_preset)
        preset_io_row.addWidget(self.btn_load_preset)
        
        preset_layout.addLayout(preset_io_row)
        
        preset_group.setLayout(preset_layout)
        content_layout.addWidget(preset_group)

        # Set the content widget to scroll area
        scroll_area.setWidget(content_widget)
        
        # Add scroll area to main layout
        main_layout.addWidget(scroll_area)

    def _load_settings(self):
        """Load saved settings from config."""
        try:
            # Load overlay settings from config
            overlay_settings = self.cfg.get("overlay_settings", {})
            
            if overlay_settings:
                # Background color
                bg_rgba = overlay_settings.get("bg_rgba", (0, 0, 0, 128))
                self.overlay.bg_rgba = bg_rgba
                self.opacity_slider.setValue(bg_rgba[3])
                
                # Text color
                text_color = overlay_settings.get("text_color", "#FFFFFF")
                self.overlay.text_color = text_color
                self.text_color_preview.setStyleSheet(f"color: {text_color}; font-size: 20px;")
                
                # Font size
                font_size = overlay_settings.get("font_size", 16)
                self.overlay.font_size = font_size
                self.font_slider.setValue(font_size)
                
                # Position
                position = overlay_settings.get("position", "bottom-left")
                self.overlay.position = position
                self._set_position_from_value(position)
                
                # Duration
                duration = overlay_settings.get("duration", 5)
                self.duration_slider.setValue(duration)
                self.duration_spin.setValue(duration)
                
                # Animation
                animation = overlay_settings.get("animation", "none")
                self.overlay.animation_type = animation
                self._set_animation_from_value(animation)
                
                # Display mode
                display_mode = overlay_settings.get("display_mode", "normal")
                self.overlay.display_mode = display_mode
                self._set_display_mode_from_value(display_mode)
                
                # Size
                width = overlay_settings.get("width", 400)
                height = overlay_settings.get("height", 100)
                self.width_spin.setValue(width)
                self.height_spin.setValue(height)
                
                # Auto size
                auto_size = overlay_settings.get("auto_size", True)
                self.chk_auto_size.setChecked(auto_size)
                
                # Update overlay
                self.overlay._update_style()
                self.overlay._update_position()
                
                # Toggle state
                show_overlay = overlay_settings.get("show_overlay", False)
                self.chk_toggle.setChecked(show_overlay)
                self._on_toggle(show_overlay)
                
        except Exception as e:
            print(f"Error loading overlay settings: {e}")

    def _save_settings(self):
        """Save current settings to config."""
        try:
            # Collect current settings
            settings = {
                "bg_rgba": self.overlay.bg_rgba,
                "text_color": self.overlay.text_color,
                "font_size": self.overlay.font_size,
                "position": self.overlay.position,
                "duration": self.duration_spin.value(),
                "animation": self.overlay.animation_type,
                "display_mode": self.overlay.display_mode,
                "width": self.width_spin.value(),
                "height": self.height_spin.value(),
                "auto_size": self.chk_auto_size.isChecked(),
                "show_overlay": self.chk_toggle.isChecked()
            }
            
            # Save to config
            self.cfg.set("overlay_settings", settings)
            
        except Exception as e:
            print(f"Error saving overlay settings: {e}")

    def _on_toggle(self, state):
        """Toggle overlay visibility."""
        if state:
            self.overlay.show()
        else:
            self.overlay.hide()
        
        # Save settings
        self._save_settings()

    def _on_duration_change(self, value):
        """Update durasi teks overlay."""
        self.duration_spin.setValue(value)
        
        # Save settings
        self._save_settings()

    def _on_position_change(self, text):
        """Update posisi overlay."""
        position_map = {
            "Kiri Atas": "top-left",
            "Kanan Atas": "top-right",
            "Kiri Bawah": "bottom-left",
            "Kanan Bawah": "bottom-right",
            "Tengah": "center"
        }
        self.overlay.position = position_map.get(text, "bottom-left")
        self.overlay._update_position()
        
        # Save settings
        self._save_settings()

    def _set_position_from_value(self, position_value):
        """Set combo box position dari nilai internal."""
        position_map = {
            "top-left": "Kiri Atas",
            "top-right": "Kanan Atas",
            "bottom-left": "Kiri Bawah",
            "bottom-right": "Kanan Bawah",
            "center": "Tengah"
        }
        position_text = position_map.get(position_value, "Kiri Bawah")
        self.position_combo.setCurrentText(position_text)

    def _on_animation_change(self, text):
        """Update jenis animasi."""
        animation_map = {
            "Tanpa Animasi": "none",
            "Fade In/Out": "fade",
            "Slide dari Kiri": "slide-left",
            "Slide dari Kanan": "slide-right",
            "Bounce": "bounce"
        }
        self.overlay.animation_type = animation_map.get(text, "none")
        
        # Save settings
        self._save_settings()

    def _set_animation_from_value(self, animation_value):
        """Set combo box animation dari nilai internal."""
        animation_map = {
            "none": "Tanpa Animasi",
            "fade": "Fade In/Out",
            "slide-left": "Slide dari Kiri",
            "slide-right": "Slide dari Kanan",
            "bounce": "Bounce"
        }
        animation_text = animation_map.get(animation_value, "Tanpa Animasi")
        self.animation_combo.setCurrentText(animation_text)

    def _on_opacity(self, value):
        """Update opacity latar belakang."""
        r, g, b, _ = self.overlay.bg_rgba
        self.overlay.bg_rgba = (r, g, b, value)
        self.overlay._update_style()
        
        # Update label
        opacity_percent = int((value / 255) * 100)
        self.opacity_label.setText(f"{opacity_percent}%")
        
        # Save settings
        self._save_settings()

    def _on_fontsize(self, value):
        """Update ukuran font."""
        self.overlay.font_size = value
        self.overlay._update_style()
        self.font_label.setText(f"{value} px")
        
        # Save settings
        self._save_settings()

    def _pick_bg_color(self):
        """Pilih warna latar belakang."""
        _, _, _, a = self.overlay.bg_rgba
        c = QColorDialog.getColor(parent=self)
        if c.isValid():
            self.overlay.bg_rgba = (c.red(), c.green(), c.blue(), a)
            self.overlay._update_style()
            self.bg_color_preview.setStyleSheet(f"background-color: {c.name()}; font-size: 20px;")
            self.bg_color_preview.setText("    ")
            
            # Save settings
            self._save_settings()

    def _pick_text_color(self):
        """Pilih warna teks."""
        c = QColorDialog.getColor(parent=self)
        if c.isValid():
            self.overlay.text_color = c.name()
            self.overlay._update_style()
            self.text_color_preview.setStyleSheet(f"color: {c.name()}; font-size: 20px;")
            self.text_color_preview.setText("⬛")
            
            # Save settings
            self._save_settings()

    def _on_greenscreen(self, state):
        """Toggle mode green screen."""
        r, g, b, a = self.overlay.bg_rgba
        if state:
            self.overlay.bg_rgba = (0, 255, 0, 255)  # Full opacity green
        else:
            self.overlay.bg_rgba = (r, g, b, a)  # Restore previous color
        self.overlay._update_style()
        
        # Save settings
        self._save_settings()

    def _on_mode_changed(self, button):
        """Handle perubahan mode tampilan."""
        if button == self.mode_normal:
            self.overlay.display_mode = "normal"
        elif button == self.mode_reply:
            self.overlay.display_mode = "reply-only"
        elif button == self.mode_author:
            self.overlay.display_mode = "author-only"
        
        # Save settings
        self._save_settings()

    def _set_display_mode_from_value(self, mode_value):
        """Set radio button dari nilai internal."""
        if mode_value == "normal":
            self.mode_normal.setChecked(True)
        elif mode_value == "reply-only":
            self.mode_reply.setChecked(True)
        elif mode_value == "author-only":
            self.mode_author.setChecked(True)

    def _resize_overlay(self, width, height):
        """Resize overlay window."""
        if not self.chk_auto_size.isChecked():
            self.overlay.resize(width, height)
            self.overlay._update_position()
        
        # Save settings
        self._save_settings()

    def _apply_preset(self, preset):
        """Apply preset style."""
        if preset == "gaming":
            self.overlay.bg_rgba = (15, 15, 15, 230)
            self.overlay.text_color = "#00FF00"
            self.overlay.font_size = 18
            self.overlay.position = "bottom-left"
            self.overlay.animation_type = "slide-left"
            self.position_combo.setCurrentText("Kiri Bawah")
            self.animation_combo.setCurrentText("Slide dari Kiri")
        elif preset == "minimal":
            self.overlay.bg_rgba = (255, 255, 255, 200)
            self.overlay.text_color = "#000000"
            self.overlay.font_size = 14
            self.overlay.position = "bottom-right"
            self.overlay.animation_type = "fade"
            self.position_combo.setCurrentText("Kanan Bawah")
            self.animation_combo.setCurrentText("Fade In/Out")
        elif preset == "colorful":
            self.overlay.bg_rgba = (75, 0, 130, 180)
            self.overlay.text_color = "#FFFF00"
            self.overlay.font_size = 20
            self.overlay.position = "top-left"
            self.overlay.animation_type = "bounce"
            self.position_combo.setCurrentText("Kiri Atas")
            self.animation_combo.setCurrentText("Bounce")
        
        # Update UI controls
        self._update_ui_from_overlay()
        
        # Save settings
        self._save_settings()

    def _update_ui_from_overlay(self):
        """Update UI controls berdasarkan state overlay."""
        # Update opacity slider
        self.opacity_slider.setValue(self.overlay.bg_rgba[3])
        opacity_percent = int((self.overlay.bg_rgba[3] / 255) * 100)
        self.opacity_label.setText(f"{opacity_percent}%")
        
        # Update font size
        self.font_slider.setValue(self.overlay.font_size)
        self.font_label.setText(f"{self.overlay.font_size} px")
        
        # Update color previews
        r, g, b, _ = self.overlay.bg_rgba
        bg_color = QColor(r, g, b)
        self.bg_color_preview.setStyleSheet(f"background-color: {bg_color.name()}; font-size: 20px;")
        self.bg_color_preview.setText("    ")
        
        self.text_color_preview.setStyleSheet(f"color: {self.overlay.text_color}; font-size: 20px;")
        self.text_color_preview.setText("⬛")
        
        # Apply to overlay
        self.overlay._update_style()

    def _save_current_preset(self):
        """Save current setup as a custom preset."""
        try:
            # Collect current settings
            preset = {
                "bg_rgba": self.overlay.bg_rgba,
                "text_color": self.overlay.text_color,
                "font_size": self.overlay.font_size,
                "position": self.overlay.position,
                "animation": self.overlay.animation_type,
                "display_mode": self.overlay.display_mode,
                "width": self.width_spin.value(),
                "height": self.height_spin.value(),
                "auto_size": self.chk_auto_size.isChecked()
            }
            
            # Save to file
            preset_file = Path("config/overlay_presets.json")
            presets = {}
            
            if preset_file.exists():
                try:
                    presets = json.loads(preset_file.read_text(encoding="utf-8"))
                except:
                    presets = {}
            
            # Ask for preset name
            from PyQt6.QtWidgets import QInputDialog
            name, ok = QInputDialog.getText(self, "Save Preset", "Enter preset name:")
            
            if ok and name:
                presets[name] = preset
                preset_file.parent.mkdir(exist_ok=True)
                preset_file.write_text(json.dumps(presets, indent=2), encoding="utf-8")
                QMessageBox.information(self, "Success", f"Preset '{name}' saved successfully!")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save preset: {str(e)}")

    def _load_preset(self):
        """Load a saved preset."""
        try:
            preset_file = Path("config/overlay_presets.json")
            if not preset_file.exists():
                QMessageBox.warning(self, "No Presets", "No saved presets found.")
                return
            
            presets = json.loads(preset_file.read_text(encoding="utf-8"))
            if not presets:
                QMessageBox.warning(self, "No Presets", "No saved presets found.")
                return
            
            # Ask which preset to load
            from PyQt6.QtWidgets import QInputDialog
            name, ok = QInputDialog.getItem(
                self, "Load Preset", "Select preset to load:", 
                list(presets.keys()), 0, False
            )
            
            if ok and name:
                preset = presets[name]
                
                # Apply preset
                self.overlay.bg_rgba = preset.get("bg_rgba", (0, 0, 0, 128))
                self.overlay.text_color = preset.get("text_color", "#FFFFFF")
                self.overlay.font_size = preset.get("font_size", 16)
                self.overlay.position = preset.get("position", "bottom-left")
                self.overlay.animation_type = preset.get("animation", "none")
                self.overlay.display_mode = preset.get("display_mode", "normal")
                
                # Update UI
                self.width_spin.setValue(preset.get("width", 400))
                self.height_spin.setValue(preset.get("height", 100))
                self.chk_auto_size.setChecked(preset.get("auto_size", True))
                
                self._set_position_from_value(self.overlay.position)
                self._set_animation_from_value(self.overlay.animation_type)
                self._set_display_mode_from_value(self.overlay.display_mode)
                
                # Update UI controls
                self._update_ui_from_overlay()
                
                # Apply settings
                self.overlay._update_style()
                self.overlay._update_position()
                
                # Save settings
                self._save_settings()
                
                QMessageBox.information(self, "Success", f"Preset '{name}' loaded successfully!")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load preset: {str(e)}")

    def _test_preview(self):
        """Test preview function with sample text."""
        self.overlay.set_text("StreamMate", "Ini adalah teks contoh untuk overlay AI. Tampilan ini akan muncul saat AI membalas pesan penonton.")
        
        # Auto-clear after duration
        duration = self.duration_spin.value() * 1000
        self.clear_timer.stop()
        self.clear_timer.start(duration)
        
        # Make sure overlay is visible
        if not self.overlay.isVisible():
            self.overlay.show()
            self.chk_toggle.setChecked(True)

    def update_overlay(self, author, reply):
        """Update overlay dengan teks baru."""
        try:
            # Set text to overlay
            self.overlay.set_text(author, reply)
            
            # Auto-clear after duration
            duration = self.duration_spin.value() * 1000
            self.clear_timer.stop()
            self.clear_timer.start(duration)
            
            # Make sure overlay is visible if enabled
            if self.chk_toggle.isChecked() and not self.overlay.isVisible():
                self.overlay.show()
            
        except Exception as e:
            print(f"Error in update_overlay: {e}")