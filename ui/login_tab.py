# ui/login_tab.py - line 10-15
import json
import os
import time
import threading
import traceback
import requests  # TAMBAHKAN INI
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpacerItem, QSizePolicy, QMessageBox, QFrame, QGridLayout,
    QGraphicsDropShadowEffect, QScrollArea, QProgressBar
)
from PyQt6.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QRect, QEasingCurve
from PyQt6.QtGui import QFont, QIcon, QPixmap, QLinearGradient, QBrush, QPalette, QColor

# ─── fallback antara modules_client & modules_server ─────────────────
try:
    from modules_client.config_manager import ConfigManager
    from modules_client.google_oauth import login_google
    from modules_client.license_validator import LicenseValidator
except ModuleNotFoundError:
    from modules_server.config_manager import ConfigManager

    # stub kalau login_google tidak tersedia di server
    def login_google():
        raise NotImplementedError("Fitur Login Google hanya tersedia di modules_client")
    
    # stub license validator
    class LicenseValidator:
        def validate(self, force_refresh=False):
            return {"is_valid": False, "tier": "demo", "expire_date": None}

class AnimatedButton(QPushButton):
    """Custom button dengan animasi hover yang smooth."""
    
    def __init__(self, text, style_type="primary"):
        super().__init__(text)
        self.style_type = style_type
        self.setup_style()
        self.setup_animation()
    
    def setup_style(self):
        """Setup style berdasarkan tipe button."""
        if self.style_type == "primary":
            self.setStyleSheet("""
                QPushButton {
                    font-size: 16px;
                    font-weight: bold;
                    padding: 15px 30px;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #1877F2, stop:1 #166FE5);
                    color: white;
                    border: none;
                    border-radius: 12px;
                    min-width: 200px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #166FE5, stop:1 #125FCA);
                    
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #125FCA, stop:1 #0F4FA8);
                }
            """)
        elif self.style_type == "secondary":
            self.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    font-weight: 500;
                    padding: 12px 24px;
                    background-color: rgba(255, 255, 255, 0.1);
                    color: #1877F2;
                    border: 2px solid #1877F2;
                    border-radius: 10px;
                    min-width: 150px;
                }
                QPushButton:hover {
                    background-color: rgba(24, 119, 242, 0.1);
                    border-color: #166FE5;
                    color: #166FE5;
                }
                QPushButton:pressed {
                    background-color: rgba(24, 119, 242, 0.2);
                }
            """)
        elif self.style_type == "demo":
            self.setStyleSheet("""
                QPushButton {
                    font-size: 15px;
                    font-weight: bold;
                    padding: 12px 25px;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #42B883, stop:1 #369970);
                    color: white;
                    border: none;
                    border-radius: 10px;
                    min-width: 180px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #369970, stop:1 #2D7A5C);
                }
            """)
    
    def setup_animation(self):
        """Setup animasi untuk button."""
        # Shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

class FeatureCard(QFrame):
    """Card untuk menampilkan fitur aplikasi."""
    
    def __init__(self, icon, title, description):
        super().__init__()
        self.setup_ui(icon, title, description)
    
    def setup_ui(self, icon, title, description):
        """Setup UI untuk feature card."""
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                padding: 15px;
            }
            QLabel {
                color: white;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 32px; margin-bottom: 5px;")
        layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1877F2;")
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.8);")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

class LoginTab(QWidget):
    """Login tab dengan desain modern dan professional."""
    
    def __init__(self, parent):
        super().__init__()
        self.parent_window = parent
        self.cfg = ConfigManager("config/settings.json")
        self.validator = LicenseValidator()
        
        # Animation timer untuk loading effect
        self.loading_timer = QTimer()
        self.loading_timer.timeout.connect(self.update_loading)
        self.loading_dots = 0
        
        # Setup UI
        self.init_ui()
        self.setup_background()
        
    def setup_background(self):
        """Setup background gradient yang modern."""
        self.setStyleSheet("""
            LoginTab {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #0F1419, stop:0.3 #1a1f2e,
                            stop:0.7 #2c3e50, stop:1 #34495e);
            }
        """)
    
    def init_ui(self):
        """Inisiasi UI dengan desain modern dan professional."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area untuk responsivitas
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(30)
        content_layout.setContentsMargins(40, 40, 40, 40)
        
        # ========== HEADER SECTION ==========
        header_section = self.create_header_section()
        content_layout.addWidget(header_section)
        
        # ========== FEATURES SECTION ==========
        features_section = self.create_features_section()
        content_layout.addWidget(features_section)
        
        # ========== ACTION SECTION ==========
        action_section = self.create_action_section()
        content_layout.addWidget(action_section)
        
        # ========== FOOTER SECTION ==========
        footer_section = self.create_footer_section()
        content_layout.addWidget(footer_section)
        
        # Spacer untuk mendorong konten ke tengah
        content_layout.addStretch(1)
        
        # Set content ke scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
    
    def create_header_section(self):
        """Buat section header dengan logo dan branding."""
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setSpacing(20)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Logo container dengan efek
        logo_container = QFrame()
        logo_container.setFixedSize(140, 140)
        logo_container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #1877F2, stop:1 #42B883);
                border-radius: 70px;
                border: 3px solid rgba(255, 255, 255, 0.2);
            }
        """)
        
        logo_layout = QVBoxLayout(logo_container)
        logo_icon = QLabel("🎤")
        logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_icon.setStyleSheet("font-size: 64px; color: white;")
        logo_layout.addWidget(logo_icon)
        
        # Shadow untuk logo
        logo_shadow = QGraphicsDropShadowEffect()
        logo_shadow.setBlurRadius(30)
        logo_shadow.setColor(QColor(24, 119, 242, 100))
        logo_shadow.setOffset(0, 8)
        logo_container.setGraphicsEffect(logo_shadow)
        
        # Center logo
        logo_center_layout = QHBoxLayout()
        logo_center_layout.addStretch()
        logo_center_layout.addWidget(logo_container)
        logo_center_layout.addStretch()
        header_layout.addLayout(logo_center_layout)
        
        # Main title dengan gradient text effect
        title = QLabel("StreamMate AI")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 42px;
                font-weight: bold;
                color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #1877F2, stop:0.5 #42B883, stop:1 #1877F2);
                margin: 10px 0;
            }
        """)
        header_layout.addWidget(title)
        
        # Subtitle dengan animate
        subtitle = QLabel("AI Live Streaming Automation")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 500;
                color: rgba(255, 255, 255, 0.9);
                letter-spacing: 1px;
            }
        """)
        header_layout.addWidget(subtitle)
        
        # Creator branding
        creator_label = QLabel("Powered by ARL GROUP")
        creator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        creator_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: 600;
                color: #42B883;
                letter-spacing: 0.5px;
                margin-top: 5px;
            }
        """)
        header_layout.addWidget(creator_label)
        
        # Version badge
        version = self.cfg.get("app_version", "1.0.0")
        version_badge = QLabel(f"v{version}")
        version_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_badge.setStyleSheet("""
            QLabel {
                background-color: rgba(66, 184, 131, 0.2);
                color: #42B883;
                border: 1px solid #42B883;
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
                max-width: 60px;
            }
        """)
        header_layout.addWidget(version_badge)
        
        return header_widget
    
    def create_features_section(self):
        """Buat section yang menampilkan fitur utama."""
        features_widget = QWidget()
        features_layout = QVBoxLayout(features_widget)
        features_layout.setSpacing(25)
        
        # Section title
        section_title = QLabel("🚀 Fitur Unggulan")
        section_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        section_title.setStyleSheet("""
            QLabel {
                font-size: 22px;
                font-weight: bold;
                color: white;
                margin-bottom: 15px;
            }
        """)
        features_layout.addWidget(section_title)
        
        # Features grid
        features_grid = QGridLayout()
        features_grid.setSpacing(15)
        
        # Daftar fitur dengan icon dan deskripsi
        features_data = [
            ("🎙️", "Voice Translation", "Terjemahan suara real-time dengan AI"),
            ("🤖", "Smart Auto-Reply", "Balasan komentar otomatis cerdas"),
            ("🎮", "Multi-Platform", "YouTube, TikTok, dan platform lainnya"),
            ("🎭", "Avatar Integration", "Sinkronisasi dengan VTuber avatar"),
            ("🔊", "Natural Voice", "Suara TTS berkualitas tinggi"),
            ("⚡", "Real-Time", "Respon instan tanpa delay")
        ]
        
        # Buat cards dalam grid 3x2
        for i, (icon, title, desc) in enumerate(features_data):
            row = i // 3
            col = i % 3
            
            card = FeatureCard(icon, title, desc)
            card.setMinimumHeight(120)
            features_grid.addWidget(card, row, col)
        
        features_layout.addLayout(features_grid)
        
        # Compatible games section
        games_title = QLabel("🎮 Cocok untuk Semua Game")
        games_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        games_title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #42B883;
                margin: 20px 0 10px 0;
            }
        """)
        features_layout.addWidget(games_title)
        
        games_desc = QLabel(
            "Mobile Legends • PUBG Mobile • Free Fire • Minecraft\n"
            "Roblox • Valorant • Genshin Impact • dan banyak lagi!"
        )
        games_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        games_desc.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: rgba(255, 255, 255, 0.8);
                line-height: 1.5;
            }
        """)
        features_layout.addWidget(games_desc)
        
        return features_widget
    
    def create_action_section(self):
        """Buat section untuk tombol aksi utama."""
        action_widget = QWidget()
        action_layout = QVBoxLayout(action_widget)
        action_layout.setSpacing(20)
        action_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Call to action title
        cta_title = QLabel("Mulai Streaming dengan AI Sekarang!")
        cta_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cta_title.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: white;
                margin-bottom: 10px;
            }
        """)
        action_layout.addWidget(cta_title)
        
        # Login button (primary)
        self.btn_login = AnimatedButton("🔑 Login dengan Google", "primary")
        self.btn_login.clicked.connect(self.login_google)
        action_layout.addWidget(self.btn_login, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # OR separator
        or_label = QLabel("atau")
        or_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        or_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: rgba(255, 255, 255, 0.6);
                margin: 10px 0;
            }
        """)
        action_layout.addWidget(or_label)
        
        # Tutorial button (secondary)
        btn_tutorial = AnimatedButton("📺 Lihat Tutorial", "secondary")
        btn_tutorial.clicked.connect(self.open_tutorial)
        action_layout.addWidget(btn_tutorial, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Demo button (special)
        btn_demo = AnimatedButton("🚀 Coba Demo Gratis", "demo")
        btn_demo.clicked.connect(self.start_demo_mode)
        action_layout.addWidget(btn_demo, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Loading indicator (hidden by default)
        self.loading_widget = QWidget()
        loading_layout = QHBoxLayout(self.loading_widget)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)  # Indeterminate progress
        self.loading_bar.setFixedWidth(200)
        self.loading_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #1877F2;
                border-radius: 8px;
                background-color: rgba(255, 255, 255, 0.1);
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #1877F2;
                border-radius: 6px;
            }
        """)
        
        self.loading_label = QLabel("Menghubungkan...")
        self.loading_label.setStyleSheet("""
            QLabel {
                color: #1877F2;
                font-size: 14px;
                margin-left: 10px;
            }
        """)
        
        loading_layout.addWidget(self.loading_bar)
        loading_layout.addWidget(self.loading_label)
        
        self.loading_widget.setVisible(False)
        action_layout.addWidget(self.loading_widget)
        
        return action_widget
    
    def create_footer_section(self):
        """Buat section footer dengan informasi tambahan."""
        footer_widget = QWidget()
        footer_layout = QVBoxLayout(footer_widget)
        footer_layout.setSpacing(15)
        
        # Support info
        support_frame = QFrame()
        support_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 15px;
            }
        """)
        support_layout = QVBoxLayout(support_frame)
        
        support_title = QLabel("💬 Butuh Bantuan?")
        support_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        support_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        support_layout.addWidget(support_title)
        
        support_info = QLabel(
            "Tutorial: youtube.com/@StreamMateID\n"
            "Email: support@streammateai.com\n"
            "Website: streammateai.com"
        )
        support_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        support_info.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: rgba(255, 255, 255, 0.7);
                line-height: 1.4;
            }
        """)
        support_layout.addWidget(support_info)
        
        footer_layout.addWidget(support_frame)
        
        # Copyright
        copyright = QLabel("© 2025 StreamMate AI by ARL GROUP. All rights reserved.")
        copyright.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: rgba(255, 255, 255, 0.5);
                margin-top: 20px;
            }
        """)
        footer_layout.addWidget(copyright)
        
        return footer_widget
    
    def show_loading(self, message="Menghubungkan..."):
        """Tampilkan loading indicator."""
        self.loading_label.setText(message)
        self.loading_widget.setVisible(True)
        self.btn_login.setEnabled(False)
        self.loading_timer.start(500)  # Update setiap 500ms
    
    def hide_loading(self):
        """Sembunyikan loading indicator."""
        self.loading_widget.setVisible(False)
        self.btn_login.setEnabled(True)
        self.loading_timer.stop()
        self.loading_dots = 0
    
    def update_loading(self):
        """Update loading animation."""
        dots = "." * (self.loading_dots % 4)
        base_text = self.loading_label.text().split('.')[0]
        self.loading_label.setText(f"{base_text}{dots}")
        self.loading_dots += 1
    
    def login_google(self):
        """Proses login dengan Google dengan loading state."""
        try:
            self.show_loading("Membuka Google Login...")
            
            # Delay kecil untuk UI responsiveness
            QTimer.singleShot(500, self._perform_google_login)
            
        except Exception as e:
            self.hide_loading()
            QMessageBox.critical(self, "Error", f"Terjadi kesalahan:\n{e}")
    
    def _perform_google_login(self):
        """Perform actual Google login."""
        try:
            self.loading_label.setText("Menunggu otentikasi Google...")
            email = login_google()
        except NotImplementedError as e:
            self.hide_loading()
            QMessageBox.warning(self, "Fitur Tidak Tersedia", str(e))
            return
        except Exception as e:
            self.hide_loading()
            QMessageBox.critical(self, "Gagal Login", f"Gagal login:\n{e}")
            return

        if not email or not isinstance(email, str) or "@" not in email:
            self.hide_loading()
            QMessageBox.warning(self, "Login Gagal", "Email tidak ditemukan atau format tidak valid.")
            return

        self.loading_label.setText("Memvalidasi akun...")
        print(f"[INFO] Pengguna login: {email}")
        
        # Periksa apakah ini email yang sama dengan logout terakhir
        temp_file = Path("temp/last_logout_email.txt")
        is_returning_user = False
        
        if temp_file.exists():
            last_email = temp_file.read_text(encoding="utf-8").strip()
            if last_email == email:
                is_returning_user = True
        
        # Simpan info user
        user_data = self.cfg.get("user_data", {})
        user_data["email"] = email
        user_data["last_login"] = datetime.now().isoformat()
        self.cfg.set("user_data", user_data)

        # Track login ke server
        try:
            response = requests.post(
                "http://localhost:8000/api/email/track",
                json={"email": email, "action": "login"},
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"[DEBUG] Login tracked to server for {email}")
            else:
                print(f"[DEBUG] Failed to track login: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] Login tracking error: {e}")
            # Continue tanpa mengganggu login flow

        # Jika pengguna yang sama dengan sebelumnya, periksa subscription_status.json
        if is_returning_user:
            sub_file = Path("config/subscription_status.json")
            if sub_file.exists():
                try:
                    sub_data = json.loads(sub_file.read_text(encoding="utf-8"))
                    if sub_data.get("email") == email and sub_data.get("status") == "paid":
                        # Pastikan ini masih valid
                        if "expire_date" in sub_data:
                            expire_date = datetime.fromisoformat(sub_data["expire_date"])
                            if expire_date > datetime.now():
                                # Masih valid, langsung arahkan ke paket
                                package = sub_data.get("package", "basic")
                                self.cfg.set("paket", package)
                                
                                self.loading_label.setText("Login berhasil! Memuat aplikasi...")
                                QTimer.singleShot(1000, lambda: self._complete_login(package))
                                return
                except Exception as e:
                    print(f"Error reading subscription file: {e}")

        # Proses normal untuk kasus lain
        self.loading_label.setText("Memverifikasi langganan...")
        
        QTimer.singleShot(1000, lambda: self._process_user_type(email))
    
    def _process_user_type(self, email):
        """Process user type and redirect accordingly."""
        try:
            if self._is_dev(email):
                # Developer mendapat akses langsung
                self.cfg.set("debug_mode", True)
                self.loading_label.setText("Mode Developer aktif...")
                QTimer.singleShot(500, lambda: self._complete_login("dev"))
            elif self._is_beta_allowed(email):
                # Beta tester
                self.cfg.set("debug_mode", False)
                self.loading_label.setText("Akses Beta terkonfirmasi...")
                QTimer.singleShot(500, lambda: self._complete_login("beta"))
            else:
                # Validasi langganan
                subscription = self.validator.validate(force_refresh=True)
                if subscription.get("is_valid", False):
                    tier = subscription.get("tier", "basic")
                    self.cfg.set("paket", tier)
                    self.loading_label.setText("Langganan valid! Memuat aplikasi...")
                    QTimer.singleShot(500, lambda: self._complete_login(tier))
                else:
                    # Tidak ada langganan aktif, tampilkan tab subscription
                    self.loading_label.setText("Mengarahkan ke halaman langganan...")
                    QTimer.singleShot(500, lambda: self._complete_login("subscription"))
        except Exception as e:
            # Fallback ke subscription tab jika validasi gagal
            print(f"[DEBUG] Validasi gagal: {e}")
            self.loading_label.setText("Terjadi kesalahan, mengarahkan ke halaman langganan...")
            QTimer.singleShot(500, lambda: self._complete_login("subscription"))
    
    def _complete_login(self, result_type):
        """Complete login process."""
        self.hide_loading()
        
        if result_type in ["dev", "beta", "subscription"]:
            self.parent_window.login_berhasil()
        else:
            # result_type adalah tier/package
            self.parent_window.pilih_paket(result_type)
    
    def start_demo_mode(self):
        """Mulai mode demo dengan konfirmasi."""
        reply = QMessageBox.question(
            self, "Mode Demo",
            "Mode demo memberikan akses gratis selama 45 menit.\n\n"
            "Fitur demo:\n"
            "• Terjemahan suara basic\n"
            "• Auto-reply sederhana\n"
            "• Tanpa integrasi avatar\n\n"
            "Lanjutkan ke mode demo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.show_loading("Mempersiapkan mode demo...")
            QTimer.singleShot(1500, self._activate_demo_mode)
    
    def _activate_demo_mode(self):
        """Aktivasi mode demo."""
        try:
            # Set demo config
            self.cfg.set("user_data", {
                "email": "demo@streammate.ai",
                "name": "Demo User",
                "last_login": datetime.now().isoformat()
            })
            self.cfg.set("paket", "demo")
            self.cfg.set("debug_mode", False)
            
            self.hide_loading()
            
            # Navigasi ke aplikasi dengan mode demo
            QMessageBox.information(
                self, "Demo Aktif",
                "Mode demo berhasil diaktifkan!\n\n"
                "Anda memiliki akses 45 menit untuk mencoba fitur basic."
            )
            
            self.parent_window.pilih_paket("basic")
            
        except Exception as e:
            self.hide_loading()
            QMessageBox.critical(self, "Error", f"Gagal mengaktifkan mode demo:\n{e}")
    
    def _is_beta_allowed(self, email):
        """Cek apakah email termasuk dalam whitelist beta tester."""
        try:
            with open("config/beta_users.json", encoding="utf-8") as f:
                data = json.load(f)
            allowed = data.get("emails", [])
            exp_date = data.get("expired_at", "")
            if email in allowed:
                if not exp_date:
                    return True
                return datetime.now() <= datetime.fromisoformat(exp_date)
        except Exception as e:
            print(f"[DEBUG] Gagal baca beta_users.json: {e}")
        return False

    def _is_dev(self, email):
        """Cek apakah email termasuk dalam whitelist developer."""
        try:
            with open("config/dev_users.json", encoding="utf-8") as f:
                return email in json.load(f).get("emails", [])
        except Exception as e:
            print(f"[DEBUG] Gagal baca dev_users.json: {e}")
        return False

    def open_tutorial(self):
        """Buka tutorial di YouTube dengan animasi loading."""
        self.show_loading("Membuka tutorial...")

        def _open_browser():
            import webbrowser
            webbrowser.open("https://youtube.com/@StreamMateID")
            self.hide_loading()

        QTimer.singleShot(1000, _open_browser)

    def _check_last_logout_email(self, current_email):
        """Cek apakah ini email yang sama dengan logout terakhir dari server."""
        try:
            response = requests.get(
                "http://localhost:8000/api/email/last_logout",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                last_email = data.get("email")
                if last_email and last_email.lower() == current_email.lower():
                    return True
            else:
                print(f"[DEBUG] Failed to get last logout email: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] Last logout email check error: {e}")
        
        # Fallback ke sistem lama (temp file)
        temp_file = Path("temp/last_logout_email.txt")
        if temp_file.exists():
            try:
                last_email = temp_file.read_text(encoding="utf-8").strip()
                return last_email.lower() == current_email.lower()
            except:
                pass
        
        return False

    def enterEvent(self, event):
        """Event saat mouse masuk ke widget - untuk efek visual tambahan."""
        super().enterEvent(event)
        # Bisa tambahkan efek visual saat hover jika diperlukan

    def leaveEvent(self, event):
        """Event saat mouse keluar dari widget."""
        super().leaveEvent(event)
        # Bisa tambahkan efek visual saat tidak hover

    def resizeEvent(self, event):
        """Handle resize event untuk responsivitas."""
        super().resizeEvent(event)
        # Auto-adjust layout berdasarkan ukuran window
        if self.width() < 800:
            # Untuk layar kecil, ubah layout menjadi single column
            pass
        else:
            # Untuk layar besar, gunakan layout normal
            pass