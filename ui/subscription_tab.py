import os
import json
import requests
import sys
import time
import logging
import webbrowser
from pathlib import Path
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QMessageBox, 
    QHBoxLayout, QProgressBar, QFrame, QGroupBox, QGridLayout,
    QSpacerItem, QScrollArea, QSizePolicy, QTextEdit, QComboBox,
    QSpinBox, QInputDialog, QLineEdit
)
from PyQt6.QtGui import QFont, QDesktopServices, QColor, QPixmap
from PyQt6.QtCore import QUrl, Qt, QTimer, pyqtSignal
from modules_client.config_manager import ConfigManager
from modules_server.daily_limit_manager import get_daily_usage_stats

logger = logging.getLogger('StreamMate')

# Setup path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Import ConfigManager - UI harus pakai client config manager
# try:
#     from modules_client.config_manager import ConfigManager
# except ImportError:
#     from modules_client.config_manager import ConfigManager

class SubscriptionTab(QWidget):
    # Signal untuk update main window
    package_activated = pyqtSignal(str)
    demo_expired_signal = pyqtSignal()  # Sinyal baru untuk demo berakhir
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.cfg = ConfigManager()  # Client ConfigManager default sudah config/settings.json
        
        # Demo timer system
        self.demo_timer = None
        self.demo_start_time = None
        self.demo_duration_minutes = 30
        self.demo_active = False
        
        # Server URL dengan fallback
        self.server_url = self._get_server_url()
        
        # TAMBAHKAN background setup seperti login_tab
        self.setup_background()
        
        # Setup UI
        self.setup_ui()
        self.setup_timer()
        
        # Start background monitoring untuk demo
        self.setup_demo_monitoring()
        
        # ✅ TAMBAHAN: Debug parent connection
        print(f"[DEBUG] SubscriptionTab initialized with parent: {type(parent).__name__ if parent else 'None'}")
        if parent and hasattr(parent, 'pilih_paket'):
            print(f"[DEBUG] Parent has pilih_paket method - direct call available")
        else:
            print(f"[DEBUG] Parent missing pilih_paket method - will use signal")
        
        # Setup timer untuk update kredit dan status - OPTIMASI: Interval lebih lambat
        self.credit_timer = QTimer(self)
        self.credit_timer.timeout.connect(self.refresh_credits)
        self.credit_timer.start(120000)  # ✅ OPTIMASI: Ubah dari 30 detik ke 2 menit
        
        # Initial refresh
        self.refresh_credits()
        
    def _get_server_url(self):
        """Dapatkan URL server yang aktif dengan fallback yang baik"""
        primary_url = "http://69.62.79.238:8000"
        fallback_url = "http://localhost"
        
        # Test koneksi ke production server dengan timeout lebih pendek
        try:
            response = requests.get(f"{primary_url}/api/health", timeout=10)
            if response.status_code == 200:
                print(f"[DEBUG] Using production server: {primary_url}")
                return primary_url
        except Exception as e:
            print(f"[DEBUG] Production server failed: {e}")
            
        # Test koneksi ke localhost dengan timeout minimal
        try:
            response = requests.get(f"{fallback_url}/api/health", timeout=1)
            if response.status_code == 200:
                print(f"[DEBUG] Using localhost server: {fallback_url}")
                return fallback_url
        except Exception as e:
            print(f"[DEBUG] Localhost server failed: {e}")
            
        # Fallback ke production meskipun tidak dapat ditest
        print(f"[DEBUG] No server responding, defaulting to production: {primary_url}")
        return primary_url
    
    def setup_background(self):
        """Setup background gradient yang modern seperti login_tab."""
        self.setStyleSheet("""
            SubscriptionTab {
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
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
    def setup_ui(self):
        """Setup subscription tab UI yang lengkap dan profesional"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # Create scroll area untuk responsivitas
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(20)
        
        # ========== HEADER SECTION ==========
        header_widget = self.create_header_section()
        content_layout.addWidget(header_widget)
        
        # ========== STATUS SECTION ==========
        status_widget = self.create_status_section()
        content_layout.addWidget(status_widget)
        
        # ========== QUICK ACTIONS ==========
        quick_actions = self.create_quick_actions()
        content_layout.addWidget(quick_actions)
        
        # ========== PACKAGE CARDS ==========
        packages_widget = self.create_packages_section()
        content_layout.addWidget(packages_widget)
        
        # ========== INFO SECTION ==========
        info_widget = self.create_info_section()
        content_layout.addWidget(info_widget)
        
        # Add stretch
        content_layout.addStretch()
        
        # Set content to scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
    def create_header_section(self):
        """Create header dengan branding"""
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setSpacing(10)
        
        # Title
        title = QLabel("💰 StreamMate AI Subscription")
        title.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: bold;
                color: #1877F2;
            }
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Manage your streaming subscription and credits")
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #65676B;
            }
        """)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(subtitle)
        
        return header
        
    def create_status_section(self):
        """Create status section dengan informasi lengkap"""
        status_frame = QFrame()
        status_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E0E0E0;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        
        layout = QGridLayout(status_frame)
        layout.setSpacing(15)
        
        # Row 1: Status Langganan
        layout.addWidget(self.create_status_label("Status:"), 0, 0)
        self.status_value = QLabel("Checking...")
        self.status_value.setStyleSheet(self.get_value_style())
        layout.addWidget(self.status_value, 0, 1)
        
        # Row 2: Paket Aktif
        layout.addWidget(self.create_status_label("Package:"), 1, 0)
        self.package_value = QLabel("None")
        self.package_value.setStyleSheet(self.get_value_style())
        layout.addWidget(self.package_value, 1, 1)
        
        # Row 3: Kredit Tersisa
        layout.addWidget(self.create_status_label("Credits:"), 2, 0)
        self.credit_value = QLabel("0 credits")
        self.credit_value.setStyleSheet(self.get_value_style("#1877F2"))
        layout.addWidget(self.credit_value, 2, 1)
        
        # Row 4: Total Penggunaan
        layout.addWidget(self.create_status_label("Usage:"), 3, 0)
        self.usage_value = QLabel("0 credits")
        self.usage_value.setStyleSheet(self.get_value_style())
        layout.addWidget(self.usage_value, 3, 1)
        
        # Row 5: Expire Date (jika ada)
        self.expire_label = self.create_status_label("Expires:")
        self.expire_value = QLabel("-")
        self.expire_value.setStyleSheet(self.get_value_style())
        layout.addWidget(self.expire_label, 4, 0)
        layout.addWidget(self.expire_value, 4, 1)
        self.expire_label.setVisible(False)
        self.expire_value.setVisible(False)
        
        # Column stretch
        layout.setColumnStretch(1, 1)
        
        return status_frame
        
    def create_status_label(self, text):
        """Create consistent status label"""
        label = QLabel(text)
        label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #666;
                min-width: 100px;
            }
        """)
        return label
        
    def get_value_style(self, color="#333"):
        """Get style for value labels"""
        return f"""
            QLabel {{
                font-size: 14px;
                font-weight: bold;
                color: {color};
            }}
        """
        
    def create_quick_actions(self):
        """Create quick action buttons"""
        from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
        
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(15)
        
        # Demo button
        self.demo_btn = QPushButton("🎮 Try Demo 30 Minutes")
        self.demo_btn.setStyleSheet("""
            QPushButton {
                background-color: #42B883;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #37A372;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
            }
        """)
        self.demo_btn.clicked.connect(self.start_demo)
        layout.addWidget(self.demo_btn)
        
        # TAMBAHAN BARU: Basic Mode Button
        self.basic_mode_btn = QPushButton("🚀 Enter Basic Mode")
        self.basic_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #1877F2;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #166FE5;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        self.basic_mode_btn.clicked.connect(self.enter_basic_mode)
        self.basic_mode_btn.setEnabled(False)  # Default disabled
        layout.addWidget(self.basic_mode_btn)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Status")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #F0F2F5;
                color: #1877F2;
                border: 1px solid #1877F2;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E8F0FE;
            }
        """)
        refresh_btn.clicked.connect(lambda: self.refresh_credits(force_vps_sync=True))
        layout.addWidget(refresh_btn)
        
        # Logout button
        logout_btn = QPushButton("🚪 Logout")
        logout_btn.setStyleSheet("""
            QPushButton {
                background-color: #FA383E;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E8282D;
            }
        """)
        logout_btn.clicked.connect(self.logout)
        layout.addWidget(logout_btn)
        
        layout.addStretch()
        
        return widget
        
    def create_packages_section(self):
        """Create package cards dengan tombol beli kredit"""
        packages_frame = QFrame()
        packages_frame.setStyleSheet("""
            QFrame {
                background-color: #F8F9FA;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        
        main_layout = QVBoxLayout(packages_frame)
        
        # Section title
        title = QLabel("📦 Choose Subscription Package")
        title.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #333;
                margin-bottom: 20px;
            }
        """)
        main_layout.addWidget(title)
        
        # Cards container
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(20)
        
        # BASIC PACKAGE CARD
        basic_card = self.create_package_card(
            title="BASIC",
            price="Rp 100.000| $6,14",
            credits="100.000 credits",
            features=[
                "✅ Auto-Reply AI (Trigger Mode)",
                "⏳ Voice Translation (Coming Soon)",
                "✅ YouTube & TikTok Support",
                "✅ Basic TTS Voices",
                "✅ Chat Overlay",
                "✅ 24/7 Support"
            ],
            color="#4CAF50",
            package_id="basic",
            is_available=True,
            is_popular=True
        )
        cards_layout.addWidget(basic_card)
        
        # PRO PACKAGE CARD (LOCKED)
        pro_card = self.create_package_card(
            title="PRO",
            price="Rp 250.000",
            credits="100.000 credits",
            features=[
                "✅ All Basic features",
                "✅ Sequential & Delay Mode",
                "✅ Premium TTS Voices",
                "✅ Virtual Microphone",
                "✅ OCR Screen Translator",
                "✅ RAG Knowledge System",
                "✅ Priority Support"
            ],
            color="#FF9800",
            package_id="pro",
            is_available=False,
            is_coming_soon=True
        )
        cards_layout.addWidget(pro_card)
        
        main_layout.addLayout(cards_layout)
        
        return packages_frame
        
    def create_package_card(self, title, price, credits, features, color, 
                            package_id, is_available=True, is_popular=False, 
                            is_coming_soon=False):
        """Create attractive package card"""
        card = QFrame()
        card.setMinimumWidth(280)
        card.setMaximumWidth(350)
        
        # Card styling
        if is_available:
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: white;
                    border: 2px solid {color};
                    border-radius: 12px;
                    padding: 0;
                }}
                QFrame:hover {{
                    border: 3px solid {color};
                    transform: translateY(-2px);
                }}
            """)
        else:
            card.setStyleSheet("""
                QFrame {
                    background-color: #F5F5F5;
                    border: 2px solid #E0E0E0;
                    border-radius: 12px;
                    padding: 0;
                }
            """)
            
        layout = QVBoxLayout(card)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header dengan badge
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 20, 20, 10)
        
        # Badge
        if is_popular:
            badge = QLabel("🔥 MOST POPULAR")
            badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {color};
                    color: white;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: bold;
                }}
            """)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_layout.addWidget(badge)
        elif is_coming_soon:
            badge = QLabel("🚀 COMING SOON")
            badge.setStyleSheet("""
                QLabel {
                    background-color: #666;
                    color: white;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: bold;
                }
            """)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_layout.addWidget(badge)
            
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 24px;
                font-weight: bold;
                color: {color if is_available else '#999'};
                margin: 10px 0;
            }}
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title_label)
        
        # Price
        price_label = QLabel(price)
        price_label.setStyleSheet(f"""
            QLabel {{
                font-size: 28px;
                font-weight: bold;
                color: {color if is_available else '#999'};
            }}
        """)
        price_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(price_label)
        
        # Credits
        credits_label = QLabel(credits)
        credits_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #666;
                margin-bottom: 15px;
            }
        """)
        credits_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(credits_label)
        
        layout.addWidget(header)
        
        # Features
        features_widget = QWidget()
        features_widget.setStyleSheet("background-color: #FAFAFA;")
        features_layout = QVBoxLayout(features_widget)
        features_layout.setContentsMargins(20, 15, 20, 15)
        
        for feature in features:
            feat_label = QLabel(feature)
            feat_label.setStyleSheet(f"""
                QLabel {{
                    font-size: 13px;
                    color: {'#333' if is_available else '#999'};
                    padding: 3px 0;
                }}
            """)
            features_layout.addWidget(feat_label)
            
        layout.addWidget(features_widget)
        
        # Buy button
        button_widget = QWidget()
        button_layout = QVBoxLayout(button_widget)
        button_layout.setContentsMargins(20, 15, 20, 20)
        
        if is_available:
            # Buy package button
            buy_btn = QPushButton(f"🛒 Buy {title}")
            buy_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    border: none;
                    padding: 12px;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {self.darken_color(color)};
                }}
            """)
            buy_btn.clicked.connect(lambda: self.buy_package(package_id))
            button_layout.addWidget(buy_btn)
        else:
            # Coming soon button
            soon_btn = QPushButton("🔒 Coming Soon")
            soon_btn.setStyleSheet("""
                QPushButton {
                    background-color: #E0E0E0;
                    color: #999;
                    border: none;
                    padding: 12px;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: bold;
                }
            """)
            soon_btn.setEnabled(False)
            button_layout.addWidget(soon_btn)
            
        layout.addWidget(button_widget)
        
        return card

    def get_demo_status_display(self):
        """Dapatkan status demo untuk ditampilkan dengan warna hitam."""
        try:
            # ✅ PERBAIKAN: Cek demo reset harian sebelum display status
            self._check_demo_daily_reset()
            
            subscription_file = Path("config/subscription_status.json")
            if not subscription_file.exists():
                return {
                    "text": "✅ Demo available - Click to start 30 minutes free",
                    "color": "#000000"  # HITAM
                }
                
            with open(subscription_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            status = data.get("status", "")
            
            # KASUS 1: Demo sedang aktif
            if status == "demo":
                expire_date_str = data.get("expire_date", "")
                if expire_date_str:
                    try:
                        from datetime import datetime, timezone
                        if '+' in expire_date_str or 'Z' in expire_date_str:
                            expire_date = datetime.fromisoformat(expire_date_str.replace('Z', '+00:00'))
                            now_time = datetime.now(timezone.utc)
                        else:
                            expire_date = datetime.fromisoformat(expire_date_str)
                            now_time = datetime.now()
                        
                        if now_time < expire_date:
                            remaining = expire_date - now_time
                            mins_left = int(remaining.total_seconds() / 60)
                            
                            # Batasi maksimal 30 menit untuk display
                            if mins_left > 30:
                                mins_left = 30
                            
                            return {
                                "text": f"⏱️ Demo active - Remaining: {mins_left} minutes",
                                "color": "#000000"  # HITAM
                            }
                        else:
                            # Demo expired, tapi TIDAK mengubah file lokal
                            # Status akan diubah oleh stop_demo_auto() saja
                            return {
                                "text": "⏰ Demo expired - Reset tomorrow at 00:00 WIB",
                                "color": "#000000"  # HITAM
                            }
                    except Exception as e:
                        print(f"[DEBUG] Error parsing demo time: {e}")
                        return {
                            "text": "⚠️ Demo error - Reset tomorrow at 00:00 WIB", 
                            "color": "#000000"
                        }
                else:
                    return {
                        "text": "⚠️ Demo data error - Reset tomorrow at 00:00 WIB",
                        "color": "#000000"
                    }
                
            # KASUS 2: Demo sudah expired atau digunakan hari ini
            elif status == "expired" or data.get("demo_used", False):
                return {
                    "text": "⏰ Demo already used - Reset tomorrow at 00:00 WIB",
                    "color": "#000000"  # HITAM
                }
            
            # KASUS 3: Demo tersedia (belum digunakan)
            else:
                return {
                    "text": "✅ Demo available - 30 minutes free",
                    "color": "#000000"  # HITAM
                }
            
        except Exception as e:
            print(f"[DEBUG] Error in get_demo_status_display: {e}")
            return {
                "text": "⚠️ Demo status not readable",
                "color": "#000000"  # HITAM
            }

    def _check_demo_daily_reset(self):
        """Cek dan reset demo jika sudah lewat jam 00:00 WIB"""
        try:
            print("[DEMO-RESET] Checking if demo needs resetting...")
            
            subscription_file = Path("config/subscription_status.json")
            if not subscription_file.exists():
                print("[DEMO-RESET] No subscription file found, nothing to reset")
                return False
                
            with open(subscription_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            status = data.get("status", "")
            demo_used = data.get("demo_used", False)
            
            # Hanya cek reset jika status expired atau demo_used = True
            if status != "expired" and not demo_used:
                print("[DEMO-RESET] Demo not used yet, no need to reset")
                return False
            
            print(f"[DEMO-RESET] Current status: {status}, demo_used: {demo_used}")
            
            # Cek apakah sudah melewati jam 00:00 WIB dari tanggal demo terakhir digunakan
            import pytz
            from datetime import datetime, date
            
            wib = pytz.timezone('Asia/Jakarta')
            now_wib = datetime.now(wib)
            today_wib = now_wib.date()
            
            print(f"[DEMO-RESET] Current WIB time: {now_wib.isoformat()}")
            
            # Cek tanggal terakhir demo digunakan
            demo_expired_at = data.get("demo_expired_at", "")
            activated_at = data.get("activated_at", "")
            
            last_demo_date = None
            
            if demo_expired_at:
                try:
                    last_demo_datetime = datetime.fromisoformat(demo_expired_at.replace('Z', ''))
                    # Convert ke WIB jika perlu
                    if last_demo_datetime.tzinfo is None:
                        last_demo_datetime = wib.localize(last_demo_datetime)
                    else:
                        last_demo_datetime = last_demo_datetime.astimezone(wib)
                    last_demo_date = last_demo_datetime.date()
                    print(f"[DEMO-RESET] Last demo expired at: {last_demo_datetime.isoformat()}, date: {last_demo_date}")
                except Exception as e:
                    print(f"[DEMO-RESET] Error parsing demo_expired_at: {e}")
                    pass
            
            if not last_demo_date and activated_at:
                try:
                    activated_datetime = datetime.fromisoformat(activated_at.replace('Z', ''))
                    if activated_datetime.tzinfo is None:
                        activated_datetime = wib.localize(activated_datetime)
                    else:
                        activated_datetime = activated_datetime.astimezone(wib)
                    last_demo_date = activated_datetime.date()
                    print(f"[DEMO-RESET] Last demo activated at: {activated_datetime.isoformat()}, date: {last_demo_date}")
                except Exception as e:
                    print(f"[DEMO-RESET] Error parsing activated_at: {e}")
                    pass
            
            # Jika sudah berbeda hari (lewat jam 00:00 WIB), reset demo
            if last_demo_date and today_wib > last_demo_date:
                print(f"[DEMO-RESET] RESETTING DEMO - Last used: {last_demo_date}, Today: {today_wib}")
                
                # Reset status demo
                data["status"] = "inactive"
                data["demo_used"] = False
                if "demo_expired_at" in data:
                    del data["demo_expired_at"]
                if "expire_date" in data:
                    del data["expire_date"]
                    
                # Simpan file yang sudah direset
                with open(subscription_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                print(f"[DEMO-RESET] Demo successfully reset for new day")
                
                # Refresh UI button
                self.update_demo_button()
                
                return True  # Return True if reset occurred
            else:
                if last_demo_date:
                    print(f"[DEMO-RESET] No reset needed. Last used: {last_demo_date}, Today: {today_wib}")
                else:
                    print("[DEMO-RESET] No reset needed. Could not determine last usage date.")
                return False
                
        except Exception as e:
            print(f"[DEMO-RESET] Error checking demo reset: {e}")
            import traceback
            print(traceback.format_exc())
            return False

    def update_demo_button(self):
        """Update tombol demo berdasarkan status."""
        status_info = self.get_demo_status_display()
        button_text = status_info["text"].lower()
        
        # KASUS 1: Demo sedang aktif
        if "active" in button_text:
            self.demo_btn.setText("⏱️ Demo Currently Active")
            self.demo_btn.setEnabled(False)
            self.demo_btn.setStyleSheet("""
                QPushButton {
                    font-size: 16px;
                    font-weight: bold;
                    padding: 15px 30px;
                    background-color: #6c757d;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    margin: 10px 0;
                }
            """)
            
        # KASUS 2: Demo sudah digunakan/expired (menampilkan notifikasi reset)
        elif "already used" in button_text or "expired" in button_text or "reset" in button_text:
            self.demo_btn.setText("⏰ Demo Reset Tomorrow")
            self.demo_btn.setEnabled(True)  # Enable untuk show notifikasi
            self.demo_btn.setStyleSheet("""
                QPushButton {
                    font-size: 16px;
                    font-weight: bold;
                    padding: 15px 30px;
                    background-color: #dc3545;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    margin: 10px 0;
                }
                QPushButton:hover {
                    background-color: #c82333;
                }
            """)
            # Connect ke method yang hanya menampilkan popup info
            try:
                self.demo_btn.clicked.disconnect()
            except:
                pass
            self.demo_btn.clicked.connect(lambda: QMessageBox.information(
                self,
                "Demo Unavailable",
                "You can try the demo again after 00:00 WIB (midnight) tomorrow.",
                QMessageBox.StandardButton.Ok
            ))
            
        # KASUS 3: Demo tersedia
        else:
            self.demo_btn.setText("🚀 Try Demo 30 Minutes")
            self.demo_btn.setEnabled(True)
            self.demo_btn.setStyleSheet("""
                QPushButton {
                    font-size: 16px;
                    font-weight: bold;
                    padding: 15px 30px;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 #28a745, stop:1 #1e7e34);
                    color: white;
                    border: none;
                    border-radius: 10px;
                    margin: 10px 0;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 #218838, stop:1 #1c7430);
                }
            """)
            # Connect ke method normal untuk start demo
            try:
                self.demo_btn.clicked.disconnect()
            except:
                pass
            self.demo_btn.clicked.connect(self.start_demo)
        
    def create_info_section(self):
        """Create info section"""
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #E8F4F8;
                border: 1px solid #B8E0F0;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(info_frame)
        
        info_text = """
        <style>
            body { font-family: Arial, sans-serif; }
            h3 { color: #1877F2; margin-top: 10px; }
            ul { margin: 5px 0; padding-left: 20px; }
            li { margin: 3px 0; }
        </style>
        
        <h3>ℹ️ Important Information</h3>
        <ul>
            <li><b>Demo Mode:</b> 30 minutes free to try Basic features (one-time use)</li>
            <li><b>Payment:</b> Via iPaymu - Bank Transfer, E-Wallet, QRIS</li>
            <li><b>Activation:</b> Automatic after successful payment</li>
            <li><b>Credits:</b> Valid for 30 days from purchase</li>
        </ul>
        
        <h3>📞 Need Help?</h3>
        <p>Email: support@streammateai.com<br>
        WhatsApp: +62 812-3456-7890</p>
        """
        
        info_widget = QTextEdit()
        info_widget.setHtml(info_text)
        info_widget.setReadOnly(True)
        info_widget.setMaximumHeight(200)
        info_widget.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                border: none;
                font-size: 12px;
            }
        """)
        
        layout.addWidget(info_widget)
        
        return info_frame
        
    def setup_timer(self):
        """Setup auto refresh timer - DEPRECATED, gunakan credit_timer"""
        pass

    def refresh_credits(self, force_vps_sync=False):
        """Refresh status dan kredit"""
        try:
            # Check for daily demo reset first
            reset_occurred = self._check_demo_daily_reset()
            if reset_occurred:
                print("[REFRESH] Demo was reset during refresh_credits call")
                
            # 🎯 PERBAIKAN: Selalu ambil data dari VPS server terlebih dahulu
            email = self.cfg.get("user_data", {}).get("email", "")
            vps_data = None
            
            if email:
                try:
                    import requests
                    print("[REFRESH] Fetching latest data from VPS server...")
                    vps_url = "http://69.62.79.238:8000"
                    response = requests.post(f"{vps_url}/api/license/validate", 
                                           json={"email": email}, timeout=10)
                    
                    if response.status_code == 200:
                        vps_result = response.json().get("data", {})
                        # --- Perbaikan: Gunakan credit_balance/credit_used jika ada ---
                        credit_balance = float(vps_result.get("credit_balance", vps_result.get("hours_credit", 0)))
                        credit_used = float(vps_result.get("credit_used", vps_result.get("hours_used", 0)))
                        vps_data = {
                            "status": "paid" if vps_result.get("is_active") else "inactive",
                            "package": vps_result.get("tier", "basic"),
                            "credit_balance": credit_balance,
                            "credit_used": credit_used,
                            "hours_credit": credit_balance,  # for legacy fallback
                            "hours_used": credit_used,      # for legacy fallback
                            "email": email
                        }
                        print(f"[REFRESH] VPS data: {vps_data['credit_balance']:.6f} credits, {vps_data['credit_used']:.6f} used")
                    else:
                        print(f"[REFRESH] VPS error: {response.status_code}")
                except Exception as e:
                    print(f"[REFRESH] VPS connection error: {e}")
            
            # Fallback ke subscription file jika VPS gagal
            if not vps_data:
                subscription_file = Path("config/subscription_status.json")
                
                if not subscription_file.exists():
                    self.update_status_display({
                        "status": "inactive",
                        "package": "none", 
                        "credit_balance": 0,
                        "credit_used": 0,
                        "hours_credit": 0,
                        "hours_used": 0
                    })
                    return
                    
                with open(subscription_file, "r", encoding="utf-8") as f:
                    vps_data = json.load(f)
                print("[REFRESH] Using local subscription file")
                # --- Perbaikan: Pastikan field credit_balance/credit_used ada ---
                if "credit_balance" not in vps_data:
                    vps_data["credit_balance"] = float(vps_data.get("hours_credit", 0))
                if "credit_used" not in vps_data:
                    vps_data["credit_used"] = float(vps_data.get("hours_used", 0))
            
            # Cek status demo lokal sebelum overwrite dengan data server
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists():
                with open(subscription_file, "r", encoding="utf-8") as f:
                    local_data = json.load(f)
                local_status = local_data.get("status", "")
                expire_date_str = local_data.get("expire_date", "")
                from datetime import datetime, timezone
                demo_still_active = False
                if local_status == "demo" and expire_date_str:
                    try:
                        if '+' in expire_date_str or 'Z' in expire_date_str:
                            expire_date = datetime.fromisoformat(expire_date_str.replace('Z', '+00:00'))
                            now_time = datetime.now(timezone.utc)
                        else:
                            expire_date = datetime.fromisoformat(expire_date_str)
                            now_time = datetime.now()
                        if now_time < expire_date:
                            demo_still_active = True
                    except Exception as e:
                        print(f"[REFRESH] Error parsing local demo expire_date: {e}")
                if demo_still_active:
                    print("[REFRESH] Local demo still active, ignoring server data overwrite.")
                    self.update_status_display(local_data)
                    self.update_demo_button()
                    return

            self.update_status_display(vps_data)
            
            # ✅ PERBAIKAN: Log data untuk debugging
            credit_balance = float(vps_data.get("credit_balance", vps_data.get("hours_credit", 0)))
            credit_used = float(vps_data.get("credit_used", vps_data.get("hours_used", 0)))
            print(f"[REFRESH] Current data: {credit_balance:.1f} credits, {credit_used:.4f} used")
            
            # Update credit display jika ada
            if hasattr(self, 'credit_status_label'):
                if credit_balance < 1.0:
                    self.credit_status_label.setText(f"❌ Credits: {credit_balance:.1f} (Insufficient)")
                    self.credit_status_label.setStyleSheet("color: red; font-weight: bold;")
                elif credit_balance < 5.0:
                    self.credit_status_label.setText(f"⚠️ Credits: {credit_balance:.1f} (Low)")
                    self.credit_status_label.setStyleSheet("color: orange; font-weight: bold;")
                else:
                    self.credit_status_label.setText(f"✅ Credits: {credit_balance:.1f}")
                    self.credit_status_label.setStyleSheet("color: green;")
            
            # Update demo button to reflect current status
            self.update_demo_button()
            
        except Exception as e:
            logger.error(f"Error refreshing credits: {e}")
            self.status_value.setText("Error")

    def update_status_display(self, data):
        """Update UI dengan data subscription"""
        status = data.get("status", "inactive")
        package = data.get("package", "none")
        credit_balance = float(data.get("credit_balance", data.get("hours_credit", 0)))
        hours_used = float(data.get("hours_used", 0))
        
        # Update status
        if status == "paid":
            self.status_value.setText("✅ Active")
            self.status_value.setStyleSheet(self.get_value_style("#4CAF50"))
            self.demo_btn.setEnabled(False)
            self.demo_btn.setText("Demo Not Available")
        elif status == "demo":
            self.status_value.setText("🎮 Demo Mode")
            self.status_value.setStyleSheet(self.get_value_style("#FF9800"))
            self.demo_btn.setEnabled(False)
            self.demo_btn.setText("Demo Currently Active")
            
            # Show expire time for demo
            expire_date = data.get("expire_date")
            if expire_date:
                self.expire_label.setVisible(True)
                self.expire_value.setVisible(True)
                try:
                    from datetime import datetime
                    expire_dt = datetime.fromisoformat(expire_date.replace('Z', '+00:00'))
                    remaining = expire_dt - datetime.now(expire_dt.tzinfo or None)
                    if remaining.total_seconds() > 0:
                        mins = int(remaining.total_seconds() / 60)
                        self.expire_value.setText(f"{mins} minutes")
                    else:
                        self.expire_value.setText("Expired")
                except Exception as e:
                    self.expire_value.setText(expire_date)
        else:
            self.status_value.setText("❌ Inactive")
            self.status_value.setStyleSheet(self.get_value_style("#D32F2F"))
            
            # Check if demo was used
            if data.get("demo_used", False):
                self.demo_btn.setEnabled(False)
                self.demo_btn.setText("Demo Already Used")
            else:
                self.demo_btn.setEnabled(True)
                self.demo_btn.setText("🎮 Try Demo 30 Minutes")
        
        # UPDATE BASIC MODE BUTTON - BERDASARKAN KREDIT SAJA (TIDAK PEDULI STATUS)
        if hasattr(self, 'basic_mode_btn'):
            if status == "demo":
                # Khusus untuk demo, disable tombol
                self.basic_mode_btn.setEnabled(False)
                self.basic_mode_btn.setText("Basic Mode (Demo Active)")
                self.basic_mode_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #CCCCCC;
                        color: #666666;
                        border: none;
                        padding: 12px 24px;
                        border-radius: 8px;
                        font-size: 14px;
                        font-weight: bold;
                    }
                """)
            elif credit_balance >= 50:
                # Enable jika kredit cukup, tidak peduli status
                self.basic_mode_btn.setEnabled(True)
                self.basic_mode_btn.setText(f"🚀 Enter Basic Mode ({credit_balance:.1f} credits)")
                self.basic_mode_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1877F2;
                        color: white;
                        border: none;
                        padding: 12px 24px;
                        border-radius: 8px;
                        font-size: 14px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #166FE5;
                    }
                """)
            else:
                # Disable jika kredit tidak cukup
                self.basic_mode_btn.setEnabled(False)
                self.basic_mode_btn.setText(f"⚠️ Insufficient Credits ({credit_balance:.1f}/50)")
                self.basic_mode_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #CCCCCC;
                        color: #666666;
                        border: none;
                        padding: 12px 24px;
                        border-radius: 8px;
                        font-size: 14px;
                        font-weight: bold;
                    }
                """)
                
        # Update package
        self.package_value.setText(package.capitalize() if package != "none" else "None")
        
        # Update credits
        self.credit_value.setText(f"{credit_balance:.1f} credits")
        if credit_balance < 1:
            self.credit_value.setStyleSheet(self.get_value_style("#D32F2F"))
        elif credit_balance < 5:
            self.credit_value.setStyleSheet(self.get_value_style("#FF9800"))
        else:
            self.credit_value.setStyleSheet(self.get_value_style("#4CAF50"))
        
        # 🎯 SISTEM BARU: Tampilan terpisah untuk kredit dan waktu akses
        # Kredit = berdasarkan pemakaian fitur
        # Waktu = akses harian maksimal 10 jam
        try:
            daily_stats = get_daily_usage_stats()
            time_used = daily_stats.get("total_hours_used", 0.0)
            time_remaining = daily_stats.get("remaining_hours", 10.0)
            
            usage_text = f"Daily access: {time_used:.1f}h / 10h"
            if time_remaining <= 2.0:  # Warning jika sisa waktu kurang dari 2 jam
                usage_text += f" ⚠️ ({time_remaining:.1f}h remaining)"
                
        except Exception as e:
            # Fallback jika daily limit manager error
            usage_text = "Daily access: 0h / 10h (safe mode)"
        
        self.usage_value.setText(usage_text)
        
        # Color coding untuk usage
        if hours_used <= 0:
            self.usage_value.setStyleSheet(self.get_value_style("#4CAF50"))  # Green - no usage
        elif hours_used < 1:
            self.usage_value.setStyleSheet(self.get_value_style("#FF9800"))  # Orange - low usage
        else:
            self.usage_value.setStyleSheet(self.get_value_style("#D32F2F"))  # Red - high usage

    def buy_package(self, package_name):
        """Proses pembelian paket dengan server yang benar."""
        print("\n=== DEBUG PAYMENT START ===")
        print(f"DEBUG: Package name: {package_name}")
        
        email = self.cfg.get("user_data", {}).get("email", "")
        print(f"DEBUG: User email: {email}")
        
        if not email:
            print("DEBUG: No email found in config")
            QMessageBox.warning(self, "Login Required", "Please login first")
            return
            
        try:
            payment_url = "http://69.62.79.238:8000/api/payment/create"  # Fixed: Use production server with correct port
            print(f"DEBUG: Sending request to: {payment_url}")
            print(f"DEBUG: Request payload: {{'email': {email}, 'package': {package_name}}}")
            
            response = requests.post(
                payment_url,
                json={"email": email, "package": package_name},
                timeout=30
            )
            print(f"DEBUG: Response status code: {response.status_code}")
            print(f"DEBUG: Response headers: {response.headers}")
            print(f"DEBUG: Response text: {response.text}")

            if response.status_code == 200:
                data = response.json()
                print(f"DEBUG: Parsed response data: {data}")
                payment_url = data.get("data", {}).get("redirect_url")
                print(f"DEBUG: Payment URL from response: {payment_url}")

                if payment_url:
                    print("DEBUG: Opening payment URL in browser")
                    import webbrowser
                    webbrowser.open(payment_url)
                    
                    QMessageBox.information(
                        self, "Payment Started",
                        f"Payment browser has been opened.\n\n"
                        f"Package: {package_name.capitalize()}\n"
                        f"Complete payment in the browser."
                    )
                else:
                    print("DEBUG: No payment URL in response")
                    QMessageBox.warning(self, "Error", "Payment URL not received")
            else:
                try:
                    error_msg = response.json().get("detail", "Payment failed")
                except Exception as e:
                    error_msg = f"Payment failed (parse error): {str(e)}"
                print(f"DEBUG: Payment error: {error_msg}")
                QMessageBox.warning(self, "Payment Error", error_msg)
                
        except requests.exceptions.ConnectionError as e:
            print(f"DEBUG: Connection error: {str(e)}")
            QMessageBox.critical(
                self, "Connection Error",
                "Cannot connect to payment server.\n\n"
                "Please ensure:\n"
                "• Internet connection is active\n"  
                "• StreamMate server is running\n"
                "• Port 8000 is accessible"
            )
        except Exception as e:
            print(f"DEBUG: Unexpected error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Payment error: {str(e)}")
            
        print("=== DEBUG PAYMENT END ===\n")

    def process_payment(self, email, package_id):
        """Process payment untuk paket yang dipilih."""
        try:
            self.show_loading("Creating payment transaction...")
            
            # Simulasi request ke server payment
            import time
            time.sleep(1)  # Simulate network request
            
            # Buat URL payment simulasi (ganti dengan real payment gateway)
            payment_url = f"https://payment.streammateai.com?email={email}&package={package_id}"
            
            # Buka browser untuk payment
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            
            QDesktopServices.openUrl(QUrl(payment_url))
            
            self.hide_loading()
            
            # Show info message
            QMessageBox.information(
                self,
                "Payment Created",
                f"Payment page has been opened in browser.\n\n"
                f"After successful payment, credits will be automatically added to your account.\n\n"
                f"Close this message and refresh status to see updates."
            )
            
        except Exception as e:
            self.hide_loading()
            QMessageBox.critical(
                self,
                "Payment Error",
                f"Failed to create payment transaction:\n{str(e)}"
            )

    def show_loading(self, message="Processing..."):
        """Show loading state."""
        # Disable buttons during loading
        for btn in self.findChildren(QPushButton):
            btn.setEnabled(False)
            
    def hide_loading(self):
        """Hide loading state."""
        # Re-enable buttons
        for btn in self.findChildren(QPushButton):
            btn.setEnabled(True)
            
    def logout(self):
        """Logout dari aplikasi"""
        if self.parent and hasattr(self.parent, 'logout'):
            self.parent.logout()
        else:
            QMessageBox.information(self, "Logout", "Logout feature not available")
        self.log_queue.put(("INFO", "User logged out successfully"))
        
    def start_demo(self):
        """Start demo mode with 30 minutes limit."""
        try:
            # ❌ DEPRECATED: Pengecekan file lokal di sini menyebabkan bug untuk user baru.
            # Logika ini salah karena membaca status user sebelumnya.
            # Pengecekan kredit sekarang dilakukan di dalam alur setelah email teridentifikasi.
            # subscription_file = Path("config/subscription_status.json")
            # if subscription_file.exists():
            #     with open(subscription_file, "r", encoding="utf-8") as f:
            #         data = json.load(f)
            #     if data.get('hours_credit', 0) > 50:
            #         QMessageBox.warning(
            #             self,
            #             "Cannot Start Demo",
            #             "You already have more than 50 credits.\nDemo mode is only available for users with 50 or fewer credits."
            #         )
            #         return

            self.show_loading("Activating Demo Mode...")
            
            # DEBUG: Tambahkan debugging yang komprehensif
            print("\n=== DEMO ACTIVATION DEBUG START ===")
            print("1. Checking for user login status...")
            
            # Import QMessageBox to fix the "cannot access local variable" error
            from PyQt6.QtWidgets import QMessageBox
            
            self.show_loading("Checking Demo & Credit Status...")
            
            try:
                # Periksa file subscription secara langsung untuk debugging
                subscription_file = Path("config/subscription_status.json")
                if subscription_file.exists():
                    print(f"2. Subscription file exists: {subscription_file}")
                    try:
                        with open(subscription_file, 'r', encoding='utf-8') as f:
                            raw_content = f.read()
                            print(f"3. Raw file content (first 100 chars): {raw_content[:100]}...")
                            if raw_content.strip():
                                subscription_data = json.loads(raw_content)
                                print(f"4. Parsed JSON email: {subscription_data.get('email', 'NOT FOUND')}")
                            else:
                                print("3. File exists but is EMPTY!")
                    except Exception as e:
                        print(f"3. ERROR reading file: {str(e)}")
                else:
                    print("2. Subscription file DOES NOT EXIST")
                
                # Juga cek settings.json
                settings_file = Path("config/settings.json")
                if settings_file.exists():
                    print(f"5. Settings file exists: {settings_file}")
                    try:
                        with open(settings_file, 'r', encoding='utf-8') as f:
                            settings_data = json.load(f)
                            user_data = settings_data.get("user_data", {})
                            print(f"6. Settings user_data: {user_data}")
                            settings_email = user_data.get("email")
                            print(f"7. Settings email: {settings_email}")
                    except Exception as e:
                        print(f"6. ERROR reading settings: {str(e)}")
                        
                # Periksa juga email yang mungkin disimpan di instance
                instance_email = getattr(self, 'email', None)
                print(f"8. Instance email attribute: {instance_email}")

                # Panggil get_current_credit_info yang sudah diperbaiki
                credit_info = self.get_current_credit_info()
                print(f"9. Credit info from function: {credit_info}")
                
                # Logika utama untuk mendapatkan email yang digunakan
                logged_in_email = credit_info.get("email")
                if not logged_in_email and hasattr(self, 'email'):
                    logged_in_email = self.email
                    print(f"10. No email in credit_info, using instance email: {logged_in_email}")
                
                # PERBAIKAN: Jika masih tidak ada email, coba ambil dari settings.json
                if not logged_in_email and settings_file.exists():
                    try:
                        with open(settings_file, 'r', encoding='utf-8') as f:
                            settings_data = json.load(f)
                        settings_email = settings_data.get("user_data", {}).get("email")
                        if settings_email:
                            logged_in_email = settings_email
                            print(f"11. Using email from settings.json: {logged_in_email}")
                    except Exception as e:
                        print(f"11. ERROR reading settings for email fallback: {str(e)}")

                print(f"12. Final logged_in_email: {logged_in_email}")
                current_credits = float(credit_info.get("hours_credit", 0.0))
                print(f"13. Current credits: {current_credits}")
                
                # PERBAIKAN: Jika email masih NULL, tanya pengguna apakah ingin login
                if not logged_in_email:
                    self.hide_loading()
                    print("14. NO EMAIL FOUND ANYWHERE. Showing login option...")
                    
                    response = QMessageBox.question(
                        self,
                        "Login Recommended",
                        "It seems you're not logged in. Would you like to login first for a better demo experience?\n\n"
                        "• YES: Go to login page\n"
                        "• NO: Continue with manual email input",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    
                    if response == QMessageBox.StandardButton.Yes:
                        print("15. User chose to login first.")
                        # Redirect to login page/tab if available
                        if self.parent and hasattr(self.parent, 'show_login_tab'):
                            self.parent.show_login_tab()
                        return
                    else:
                        print("15. User chose to continue with manual email.")
                        self.prompt_for_demo_email()
                        return

                # 1. Jika pengguna login, periksa kredit mereka terlebih dahulu
                if logged_in_email:
                    print(f"14. Logged in as {logged_in_email}, credits: {current_credits}")
                    
                    # ATURAN BARU: Jika kredit > 50, jangan izinkan demo
                    if current_credits > 50:
                        self.hide_loading()
                        print("15. Credits > 50, demo not allowed.")
                        QMessageBox.information(self, "Demo Not Available",
                            f"Hi {logged_in_email},<br><br>"
                            f"Your current credit balance (<b>{current_credits:.1f}</b>) is sufficient. The free demo is intended for new users or those with low credit.<br><br>"
                            "Please use your existing credits to enjoy all features. Thank you! 🙏")
                        return

                    # 2. Jika kredit <= 50, lanjutkan untuk memeriksa status demo harian
                    print(f"15. Credit is low ({current_credits}). Checking daily demo status...")
                    status_response = requests.get(f"{self.server_url}/api/demo/status/{logged_in_email}", timeout=10)
                    
                    self.hide_loading()
                    print(f"16. Demo status response: HTTP {status_response.status_code}")
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json().get("data", {})
                        can_demo = status_data.get("can_demo", False)
                        print(f"17. Can demo: {can_demo}")
                        
                        if can_demo:
                            # Demo tersedia, tanyakan konfirmasi sebelum aktivasi
                            reply = QMessageBox.question(self, "Activate Demo?",
                                f"Demo is available for <b>{logged_in_email}</b>. ✨<br><br>"
                                "Would you like to activate your 30-minute free demo now?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
                            if reply == QMessageBox.StandardButton.Yes:
                                print("18. User confirmed demo activation.")
                                self.activate_demo_for_email(logged_in_email)
                            else:
                                print("18. User cancelled demo activation.")
                        else:
                            # Demo sudah digunakan hari ini
                            next_reset = status_data.get('next_reset_wib', 'tomorrow at 00:00 WIB')
                            print(f"18. Demo already used. Next reset: {next_reset}")
                            QMessageBox.information(
                                self,
                                "Demo Unavailable",
                                "You can try the demo again after 00:00 WIB (midnight) tomorrow.",
                                QMessageBox.StandardButton.Ok
                            )
                            return
                    else:
                        print(f"17. Failed to check demo status: HTTP {status_response.status_code}")
                        QMessageBox.warning(self, "Error", 
                                           f"Failed to check demo status (HTTP {status_response.status_code}). Please try again.")

                # 3. Jika tidak ada pengguna yang login, langsung minta email
                else:
                    self.hide_loading()
                    print("14. No logged-in user. Prompting for email.")
                    self.prompt_for_demo_email()

            except requests.exceptions.RequestException as e:
                print(f"ERROR: Connection error - {str(e)}")
                self.hide_loading()
                QMessageBox.critical(self, "Connection Error", f"Could not connect to the server: {e}")
            except Exception as e:
                print(f"ERROR: Unexpected error - {str(e)}")
                import traceback
                print(f"TRACEBACK: {traceback.format_exc()}")
                self.hide_loading()
                QMessageBox.critical(self, "An Error Occurred", f"An unexpected error occurred: {e}")
                
            print("=== DEMO ACTIVATION DEBUG END ===\n")

        except Exception as e:
            print(f"ERROR: Unexpected error - {str(e)}")
            import traceback
            print(f"TRACEBACK: {traceback.format_exc()}")
            self.hide_loading()
            QMessageBox.critical(self, "An Error Occurred", f"An unexpected error occurred: {e}")

    def prompt_for_demo_email(self):
        """Shows a dialog to input an email for the demo."""
        from PyQt6.QtWidgets import QInputDialog, QLineEdit, QMessageBox
        
        email, ok = QInputDialog.getText(
            self, 
            "Activate 30-Minute Demo 🚀", 
            "Enter your email to start the free demo:", 
            QLineEdit.EchoMode.Normal
        )

        if ok and email:
            if "@" in email and "." in email and len(email) >= 5:
                # Save temporary email for session
                self.email = email
                print(f"[DEMO] Email validated and saved: {email}")
                
                # Directly activate basic mode without credit check
                self.enter_basic_mode(bypass_credit_check=True)
            else:
                QMessageBox.warning(self, "Invalid Email", "Please enter a valid email address.")
        else:
            print("[DEMO] Demo activation cancelled by user.")
            
    def activate_demo_for_email(self, email):
        """Registers and activates the demo for a given email."""
        print(f"[DEMO] Activating demo for email: {email}")
        self.show_loading(f"Activating for {email}...")

        try:
            register_response = requests.post(
                f"{self.server_url}/api/demo/register",
                json={"email": email},
                timeout=15
            )
            
            self.hide_loading()

            if register_response.status_code == 200:
                register_result = register_response.json()
                if register_result.get("status") == "success":
                    # Successfully registered, now save status and activate
                    self.save_and_activate_demo_data(register_result["data"], email)
                else:
                    error_message = register_result.get('message', 'Unknown error from server')
                    QMessageBox.warning(self, "Demo Activation Failed", f"Could not activate demo: {error_message}")
            else:
                try:
                    error_data = register_response.json()
                    message = error_data.get("message", "Unknown server error")
                except json.JSONDecodeError:
                    message = register_response.text
                QMessageBox.warning(
                    self, "Server Error",
                    f"Failed to activate demo. Server responded with status {register_response.status_code}.<br><br>"
                    f"Details: {message}"
                )
        except requests.exceptions.RequestException as e:
            self.hide_loading()
            QMessageBox.critical(self, "Connection Error", f"Could not connect to the server: {e}")
        except Exception as e:
            self.hide_loading()
            QMessageBox.critical(self, "An Error Occurred", f"A system error occurred: {e}")
            
    def save_and_activate_demo_data(self, demo_info, email):
        """Saves the demo data to subscription_status.json and activates the UI."""
        from datetime import datetime, timedelta
        import pytz
        
        now_utc = datetime.now(pytz.UTC)
        now_wib = now_utc.astimezone(pytz.timezone('Asia/Jakarta'))
        expire_wib = now_wib + timedelta(minutes=30)
        
        subscription_data = {
            "email": email,
            "status": "demo",
            "package": "basic",
            "expire_date": expire_wib.isoformat(),
            "expire_date_wib": expire_wib.strftime("%Y-%m-%d %H:%M:%S WIB"),
            "demo_duration_minutes": demo_info.get("remaining_minutes", 30),
            "activated_at": now_wib.isoformat(),
            "updated_at": datetime.now().isoformat(),
            "hours_credit": 0,
            "hours_used": 0,
            "demo_used": True,
            "timezone": "Asia/Jakarta"
        }
        
        subscription_file = Path("config/subscription_status.json")
        with open(subscription_file, "w", encoding="utf-8") as f:
            json.dump(subscription_data, f, indent=2, ensure_ascii=False)

        if self.parent and hasattr(self.parent, 'pilih_paket'):
            self.parent.pilih_paket("basic")
        self.package_activated.emit("basic")
        
        self.demo_active = True
        self.demo_start_time = datetime.now()
        
        expire_display = expire_wib.strftime("%H:%M WIB")
        QMessageBox.information(
            self, "Demo Activated! 🚀",
            f"30-minute demo for <b>{email}</b> is now active! ✨<br><br>"
            f"⏰ Duration: 30 minutes<br>"
            f"🕐 Ends at: <b>{expire_display}</b><br><br>"
            f"The Basic mode is now active. Go to the CoHost tab to start!"
        )
        
        self.refresh_credits()

    def darken_color(self, color):
        """Membuat warna lebih gelap untuk hover effect"""
        color_map = {
            "#4CAF50": "#388E3C",
            "#FF9800": "#F57C00",
            "#1877F2": "#0C63D4",
            "#42B883": "#33A06F"
        }
        return color_map.get(color, color)
        
    def closeEvent(self, event):
        """Handle close event - OPTIMASI: Stop semua timer"""
        # Stop timer
        if hasattr(self, 'credit_timer'):
            self.credit_timer.stop()
        if hasattr(self, 'demo_monitor_timer'):
            self.demo_monitor_timer.stop()
        event.accept()
        
    def setVisible(self, visible):
        """OPTIMASI: Start/stop timer berdasarkan visibility dan refresh saat visible"""
        super().setVisible(visible)
        if hasattr(self, 'credit_timer'):
            if visible:
                self.credit_timer.start()
                # ✅ PERBAIKAN: Refresh credits saat tab visible untuk cek demo reset
                QTimer.singleShot(100, self.refresh_credits)
                
                # Also immediately check demo status if needed
                QTimer.singleShot(200, self.check_demo_status)
            else:
                self.credit_timer.stop()

    def get_current_credit_info(self):
        """
        Safely reads the current subscription status from the JSON file.
        Returns a dictionary with credit info or defaults if not found.
        """
        try:
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists() and subscription_file.stat().st_size > 0:
                with open(subscription_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Pastikan data yang dikembalikan adalah dictionary
                    return data if isinstance(data, dict) else {}
            # Jika file tidak ada atau kosong, kembalikan dictionary kosong
            return {}
        except (json.JSONDecodeError, IOError) as e:
            print(f"[ERROR] Failed to read or parse subscription status file: {e}")
            # Jika ada error, kembalikan dictionary kosong untuk mencegah crash
            return {}

    def enter_basic_mode(self, bypass_credit_check=False):
        """Masuk ke mode basic dengan validasi dan UI update."""
        from PyQt6.QtWidgets import QMessageBox
        import logging
        logger = logging.getLogger(__name__)
        try:
            # Check credit availability (skip if bypass flag is set)
            if not bypass_credit_check:
                credit_info = self.get_current_credit_info()
                credit_balance = float(credit_info.get("credit_balance", credit_info.get("hours_credit", 0)))
                MIN_CREDIT_REQUIRED = 50.0
                if credit_balance < MIN_CREDIT_REQUIRED:
                    QMessageBox.warning(
                        self, "Credits Insufficient",
                        f"Credits are insufficient for Basic Mode.\n\n"
                        f"Current credits: {credit_balance:.1f}\n"
                        f"Minimum required: {MIN_CREDIT_REQUIRED} credits\n\n"
                        f"Please purchase credits first."
                    )
                    return
                # Konfirmasi masuk mode Basic
                reply = QMessageBox.question(
                    self, "Enter Basic Mode",
                    f"Enter Basic Mode?\n\n"
                    f"Credits available: {credit_balance:.1f}\n"
                    f"Estimated: ~{int(credit_balance / 0.45)} auto-reply\n\n"
                    f"Basic Mode will be active and start using credits.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            # ✅ PERBAIKAN UTAMA: Langsung panggil parent method
            if self.parent and hasattr(self.parent, 'pilih_paket'):
                print(f"[DEBUG] Calling parent.pilih_paket('basic') directly")
                self.parent.pilih_paket("basic")
                if not bypass_credit_check:
                    QMessageBox.information(
                        self, "Basic Mode Active",
                        f"Basic Mode successfully activated!\n\n"
                        f"Credits available: {credit_balance:.1f}\n"
                        f"The app will switch to Basic mode."
                    )
            else:
                print(f"[DEBUG] Parent not available, using signal emit")
                self.package_activated.emit("basic")
                if not bypass_credit_check:
                    QMessageBox.information(
                        self, "Basic Mode Active",
                        f"Basic Mode successfully activated!\n\n"
                        f"Credits available: {credit_balance:.1f}\n"
                        f"Basic Mode activated."
                    )
        except Exception as e:
            logger.error(f"Error entering basic mode: {e}")
            QMessageBox.critical(
                self, "Error",
                f"Failed to enter Basic Mode: {str(e)}"
            )

    def activate_demo(self):
        """Aktifkan demo dengan validasi daily limit dan notifikasi yang tepat"""
        try:
            # ✅ PERBAIKAN: Cek status demo lokal terlebih dahulu
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists():
                try:
                    with open(subscription_file, "r", encoding="utf-8") as f:
                        local_data = json.load(f)
                    
                    local_status = local_data.get("status", "")
                    
                    # Jika demo masih aktif
                    if local_status == "demo":
                        QMessageBox.information(
                            self,
                            "Demo Currently Active 🎮",
                            "Demo mode is currently running! ⏰\n\n"
                            "Use the available Basic features.\n"
                            "Check the Cohost tab to start streaming!"
                        )
                        return
                    
                    # Jika demo expired atau sudah digunakan
                    elif local_status == "expired" or local_data.get("demo_used", False) or local_data.get("demo_active", False) == False:
                        # Hitung waktu reset (jam 00:00 besok)
                        from datetime import datetime, timedelta
                        import pytz
                        
                        wib = pytz.timezone('Asia/Jakarta')
                        now_wib = datetime.now(wib)
                        tomorrow_midnight = (now_wib + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                        time_until_reset = tomorrow_midnight - now_wib
                        
                        hours_left = int(time_until_reset.total_seconds() / 3600)
                        mins_left = int((time_until_reset.total_seconds() % 3600) / 60)
                        
                        QMessageBox.information(
                            self,
                            "Demo Already Used Today 📅",
                            f"30-minute demo has already been used today! ✨\n\n"
                            f"🕐 Demo will reset at: {tomorrow_midnight.strftime('%d/%m/%Y at 00:00 WIB')}\n"
                            f"⏳ Time remaining: {hours_left} hours {mins_left} minutes\n\n"
                            f"💡 Temporary solutions:\n"
                            f"• Purchase credit packages to continue\n"
                            f"• Or wait for demo reset tomorrow morning\n\n"
                            f"Thank you for using StreamMate AI! 🚀"
                        )
                        return
                        
                except Exception as e:
                    print(f"[DEBUG] Error checking local demo status: {e}")
            
            # Lanjutkan ke server check jika lokal OK
            self.start_demo()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "An Error Occurred",
                f"Sorry, an error occurred while activating demo:\n\n{str(e)}\n\n"
                f"Please try again or contact support if the problem persists."
            )

    def setup_demo_monitoring(self):
        """Setup demo monitoring system."""
        # Demo monitoring timer - cek setiap 10 detik (increased frequency for more reliable detection)
        self.demo_monitor_timer = QTimer()
        self.demo_monitor_timer.timeout.connect(self.check_demo_status)
        self.demo_monitor_timer.start(10000)  # Check every 10 seconds
        
        print("[DEMO-MONITOR] Demo monitoring system initialized")
        # Check demo status on startup
        self.check_demo_status()

    def check_demo_status(self):
        """Check demo status dan handle auto-stop."""
        try:
            subscription_file = Path("config/subscription_status.json")
            if not subscription_file.exists():
                return
                
            with open(subscription_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            status = data.get("status", "")
            
            # Debug output for monitoring
            if status == "demo":
                print("[DEMO-MONITOR] Found active demo status")
            
            if status != "demo":
                if self.demo_active:
                    print("[DEMO-MONITOR] Demo status changed from active to inactive")
                self.demo_active = False
                return
                
            # Demo sedang aktif, cek apakah sudah expired
            expire_date_str = data.get("expire_date", "")
            if not expire_date_str:
                print("[DEMO-MONITOR] WARNING: Demo status is active but no expiration date found")
                return
                
            from datetime import datetime
            import pytz
            
            # Parse expire time
            try:
                if '+' in expire_date_str:
                    expire_date = datetime.fromisoformat(expire_date_str)
                else:
                    expire_date = datetime.fromisoformat(expire_date_str)
                    if expire_date.tzinfo is None:
                        wib = pytz.timezone('Asia/Jakarta')
                        expire_date = wib.localize(expire_date)
                
                now = datetime.now(pytz.timezone('Asia/Jakarta'))
                
                # Jika demo sudah expired
                if now >= expire_date:
                    print(f"[DEMO-MONITOR] Demo expired! Current time: {now.isoformat()}, Expire time: {expire_date.isoformat()}")
                    self.stop_demo_auto()
                else:
                    # Demo masih aktif, update countdown
                    remaining = expire_date - now
                    remaining_minutes = int(remaining.total_seconds() / 60)
                    remaining_seconds = int(remaining.total_seconds() % 60)
                    print(f"[DEMO-MONITOR] Demo active - {remaining_minutes} minutes {remaining_seconds} seconds remaining")
                    self.demo_active = True
                    
            except Exception as e:
                print(f"[DEMO-MONITOR] Error parsing expire date: {e}")
                import traceback
                print(traceback.format_exc())
                
        except Exception as e:
            print(f"[DEMO-MONITOR] Error checking demo status: {e}")
            import traceback
            print(traceback.format_exc())

    def stop_demo_auto(self):
        """Stop demo otomatis setelah 30 menit."""
        try:
            print("[DEMO] Auto-stopping demo after timeout...")
            
            # 1. Update status ke expired di file JSON
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists():
                with open(subscription_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Hanya lanjutkan jika status masih 'demo' untuk menghindari konflik
                if data.get("status") == "demo":
                    data["status"] = "expired"
                    data["demo_active"] = False
                    data["demo_used"] = True
                    
                    with open(subscription_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print("[DEMO-TIMEOUT] Subscription file updated: status=expired, demo_used=True")
                else:
                    print("[DEMO-TIMEOUT] Demo already stopped by another process. Aborting auto-stop.")
                    return

            # 2. Hentikan auto-reply cohost secara paksa
            self.package_activated.emit("inactive") # Ini akan mematikan cohost
            
            # 3. Emit sinyal bahwa demo sudah berakhir untuk pindah tab
            print("[DEMO-TIMEOUT] Emitting demo_expired_signal to switch tab")
            self.demo_expired_signal.emit()

            # 4. Refresh UI di tab ini
            self.refresh_credits()
            
            # 5. Tampilkan notifikasi
            QMessageBox.information(
                self,
                "Demo Selesai ⏰",
                "Demo 30 menit telah selesai!\n\n"
                "Anda akan diarahkan kembali ke halaman subscription."
            )
            
            print("[DEMO-TIMEOUT] Demo auto-stop completed successfully.")
            
        except Exception as e:
            print(f"[DEMO-TIMEOUT] Error during auto-stop: {e}")

    def refresh_vps_data(self):
        """Refresh data dari VPS server"""
        try:
            # Get user email
            email = self.get_user_email()
            if not email:
                return
                
            # Call VPS API
            vps_url = "http://69.62.79.238:8000"
            response = requests.post(
                f"{vps_url}/api/license/validate",
                json={"email": email},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                vps_data = data.get("data", {})
                
                # PERBAIKAN: Gunakan field baru 'credit_balance' bukan 'hours_credit'
                hours_credit = float(vps_data.get("credit_balance", 0))
                hours_used = float(vps_data.get("credit_used", 0))
                
                # Update UI
                self.vps_credit_label.setText(f"{hours_credit:.2f} jam")
                self.vps_used_label.setText(f"{hours_used:.2f} jam")
                
                # Update local file
                self.update_local_subscription_file(hours_credit, hours_used)
                
            else:
                print(f"VPS API error: {response.status_code}")
                
        except Exception as e:
            print(f"Error refreshing VPS data: {e}")

    def update_local_subscription_file(self, hours_credit, hours_used):
        """Update local subscription file dengan data dari VPS"""
        try:
            subscription_file = Path("config/subscription_status.json")
            
            if subscription_file.exists():
                with open(subscription_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {}
            
            # PERBAIKAN: Gunakan field baru 'credit_balance' bukan 'hours_credit'
            data["credit_balance"] = hours_credit
            data["credit_used"] = hours_used
            data["updated_at"] = datetime.now().isoformat()
            
            with open(subscription_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"Error updating subscription file: {e}")