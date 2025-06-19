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
from modules_server.config_manager import ConfigManager
from modules_client.google_oauth import login_google
from modules_server.license_validator import LicenseValidator

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
                    background-color: rgba(24, 119, 242, 0.2);
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
            QLabel {
                color: white;
            }
            QPushButton {
                color: white;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #1a1f2e;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #34495e;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3f536b;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
    
    def init_ui(self):
        """Inisialisasi UI dengan layout yang responsive."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Scroll area untuk konten
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(30)
        content_layout.setContentsMargins(40, 40, 40, 40)
        
        # Add sections
        content_layout.addWidget(self.create_header_section())
        content_layout.addWidget(self.create_features_section())
        content_layout.addWidget(self.create_action_section())
        content_layout.addWidget(self.create_footer_section())
        
        # Add stretch at the end
        content_layout.addStretch()
        
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
        section_title = QLabel("🚀 Key Features")
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
            ("🎙️", "Voice Translation", "Real-time AI voice translation"),
            ("🤖", "Smart Auto-Reply", "Intelligent automatic comment replies"),
            ("🎮", "Multi-Platform", "YouTube, TikTok, and other platforms"),
            ("🎭", "Avatar Integration", "Synchronize with VTuber avatars"),
            ("🔊", "Natural Voice", "High-quality TTS voices"),
            ("⚡", "Real-Time", "Instant response without delay")
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
        games_title = QLabel("🎮 Compatible with All Games")
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
            "Roblox • Valorant • Genshin Impact • and many more!"
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
        cta_title = QLabel("Start AI Streaming Now!")
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
        self.btn_login = AnimatedButton("🔑 Login with Google", "primary")
        self.btn_login.clicked.connect(self.login_google)
        action_layout.addWidget(self.btn_login, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # OR separator
        or_label = QLabel("or")
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
        btn_tutorial = AnimatedButton("📺 Watch Tutorial", "secondary")
        btn_tutorial.clicked.connect(self.open_tutorial)
        action_layout.addWidget(btn_tutorial, alignment=Qt.AlignmentFlag.AlignCenter)
        
        
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
        
        self.loading_label = QLabel("Connecting...")
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
            QLabel {
                color: white;
            }
        """)
        support_layout = QVBoxLayout(support_frame)
        
        support_title = QLabel("💬 Need Help?")
        support_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        support_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        support_layout.addWidget(support_title)
        
        support_info = QLabel(
            "Tutorial: https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn\n"
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
    
    def show_loading(self, message="Connecting..."):
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
            self.show_loading("Opening Google Login...")
            
            # Delay kecil untuk UI responsiveness
            QTimer.singleShot(500, self._perform_google_login)
            
        except Exception as e:
            self.hide_loading()
            QMessageBox.critical(self, "Error", f"An error occurred:\n{e}")
    
    def _perform_google_login(self):
        """Perform actual Google login dengan debugging yang lebih detail."""
        try:
            self.loading_label.setText("Waiting for Google authentication...")
            email = login_google()
        except NotImplementedError as e:
            self.hide_loading()
            QMessageBox.warning(self, "Feature Not Available", str(e))
            return
        except Exception as e:
            self.hide_loading()
            print(f"[ERROR] Login failed: {e}")
            QMessageBox.critical(self, "Login Failed", "Login failed. Please check your internet connection and try again.")
            return

        # Enhanced email validation with minimal logging
        if not email:
            self.hide_loading()
            QMessageBox.warning(self, "Login Failed", "Email not found. Please try again.")
            return
            
        if not isinstance(email, str):
            self.hide_loading()
            QMessageBox.warning(self, "Login Failed", "Invalid email format received.")
            return
            
        if "@" not in email:
            self.hide_loading()
            QMessageBox.warning(self, "Login Failed", "Invalid email format.")
            return
            
        print(f"[INFO] User logged in: {email}")

        self.loading_label.setText("Validating account...")
        print(f"[DEBUG] LOGIN: Pengguna login: {email}")
        
        # TAMBAHAN DEBUG: Simpan info user
        user_data = self.cfg.get("user_data", {})
        user_data["email"] = email
        user_data["last_login"] = datetime.now().isoformat()
        self.cfg.set("user_data", user_data)
        print(f"[DEBUG] LOGIN: User data saved: {user_data}")

        # Track login ke server dengan dynamic URL
        try:
            from modules_client.google_oauth import get_server_url
            server_url = get_server_url()
            print(f"[DEBUG] LOGIN: Tracking login to server: {server_url}")
            
            response = requests.post(
                f"{server_url}/api/email/track",
                json={"email": email, "action": "login"},
                timeout=5
            )
            print(f"[DEBUG] LOGIN: Server tracking response: {response.status_code}")
            if response.status_code != 200:
                print(f"[DEBUG] LOGIN: Server tracking error response: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] LOGIN: Server tracking connection error: {e}")
        except Exception as e:
            print(f"[DEBUG] LOGIN: Server tracking unexpected error: {e}")

        # PERBAIKAN: Langsung proses tanpa checking
        self.loading_label.setText("Verifying subscription...")
        print(f"[DEBUG] LOGIN: Starting subscription validation...")
        
        QTimer.singleShot(1000, lambda: self._process_user_type(email))
    
    def _process_user_type(self, email):
        """Process user type - PRODUCTION ONLY dengan proteksi kredit"""
        print(f"[DEBUG] PROCESS: Starting validation for {email}")
        
        try:
            # LANGKAH 1: BACKUP KREDIT EXISTING SEBELUM VALIDASI
            subscription_file = Path("config/subscription_status.json")
            existing_credit = 0
            existing_data = {}
            
            if subscription_file.exists():
                try:
                    with open(subscription_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        existing_credit = float(existing_data.get("hours_credit", 0))
                        existing_email = existing_data.get("email", "").strip().lower()
                        
                    # Jika user sama dan ada kredit existing, simpan untuk proteksi
                    if existing_email == email.strip().lower() and existing_credit > 0:
                        print(f"[DEBUG] PROCESS: Found existing credit: {existing_credit} hours for {email}")
                except Exception as e:
                    print(f"[DEBUG] PROCESS: Error reading existing data: {e}")
            
            # LANGKAH 2: VALIDASI KE SERVER (yang sudah diperbaiki dengan sync)
            print(f"[DEBUG] PROCESS: Calling license validator...")
            subscription = self.validator.validate(force_refresh=True)
            print(f"[DEBUG] PROCESS: License validation result: {subscription}")
            
            # LANGKAH 3: PASTIKAN KREDIT TIDAK HILANG SETELAH VALIDASI
            if existing_credit > 0 and subscription_file.exists():
                try:
                    with open(subscription_file, 'r', encoding='utf-8') as f:
                        post_validation_data = json.load(f)
                        post_validation_credit = float(post_validation_data.get("hours_credit", 0))
                    
                    # Jika kredit berkurang drastis setelah validasi, restore
                    if post_validation_credit < (existing_credit * 0.9):  # Turun >10%
                        print(f"[DEBUG] PROCESS: CREDIT LOSS DETECTED! Restoring from {post_validation_credit} to {existing_credit}")
                        
                        # Restore existing data dengan merge dari validation
                        restored_data = existing_data.copy()
                        restored_data.update({
                            "email": email,
                            "status": subscription.get("status", existing_data.get("status", "paid")),
                            "tier": subscription.get("tier", existing_data.get("tier", "basic")),
                            "updated_at": datetime.now().isoformat(),
                            "protection_info": {
                                "protected_by": "login_credit_protection",
                                "protection_timestamp": datetime.now().isoformat(),
                                "original_credit": existing_credit,
                                "validation_credit": post_validation_credit
                            }
                        })
                        
                        with open(subscription_file, 'w', encoding='utf-8') as f:
                            json.dump(restored_data, f, indent=2, ensure_ascii=False)
                        
                        print(f"[DEBUG] PROCESS: Credit restored successfully")
                        
                        # Update subscription result untuk UI
                        subscription["hours_credit"] = existing_credit
                        subscription["is_valid"] = True
                
                except Exception as e:
                    print(f"[DEBUG] PROCESS: Error in credit protection: {e}")
            
            # LANGKAH 4: PROSES NORMAL BERDASARKAN HASIL VALIDASI
            if subscription.get("is_valid", False):
                tier = subscription.get("tier", "basic")
                self.cfg.set("paket", tier)
                print(f"[DEBUG] PROCESS: Valid subscription found - tier: {tier}")
                self.loading_label.setText("Valid subscription! Loading application...")
                QTimer.singleShot(500, lambda: self._complete_login(tier))
            else:
                print(f"[DEBUG] PROCESS: No valid subscription, redirecting to subscription tab")
                self.loading_label.setText("Redirecting to subscription page...")
                QTimer.singleShot(500, lambda: self._complete_login("subscription"))
            
        except Exception as e:
            print(f"[DEBUG] PROCESS: Error during validation: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback ke subscription tab jika validasi gagal
            self.loading_label.setText("An error occurred, redirecting to subscription page...")
            QTimer.singleShot(500, lambda: self._complete_login("subscription"))
    
    def _complete_login(self, result_type):
        """Complete login process berdasarkan hasil validasi."""
        self.hide_loading()
        
        try:
            print(f"[DEBUG] COMPLETE: Processing result_type: {result_type}")
            
            if result_type == "basic":
                print(f"[DEBUG] COMPLETE: Navigating to basic package")
                self.parent_window.pilih_paket("basic")
            elif result_type == "premium":
                print(f"[DEBUG] COMPLETE: Navigating to premium package")
                self.parent_window.pilih_paket("premium")
            else:
                # Fallback
                print(f"[DEBUG] COMPLETE: Fallback - calling login_berhasil()")
                self.parent_window.login_berhasil()
        except Exception as e:
            print(f"[DEBUG] COMPLETE: Error in complete_login: {e}")
            import traceback
            traceback.print_exc()
            # Fallback
            self.parent_window.login_berhasil()
    
    def open_tutorial(self):
        """Buka tutorial di YouTube dengan animasi loading."""
        self.show_loading("Opening tutorial...")

        def _open_browser():
            import webbrowser
            webbrowser.open("https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn")
            self.hide_loading()

        QTimer.singleShot(1000, _open_browser)

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
