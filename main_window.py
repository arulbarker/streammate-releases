# ui/main_window.py - VERSI FINAL TERBAIK
import sys
import os
import datetime
import json 
import logging
from pathlib import Path

# Setup logger
logger = logging.getLogger('StreamMate')

# Import PyQt6 components
from PyQt6.QtGui import QGuiApplication, QIcon
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QTabWidget, QMessageBox,
    QLabel, QStatusBar, QWidget, QVBoxLayout, QPushButton, QSizePolicy,
    QScrollArea, QLineEdit, QFormLayout, QTextEdit, QHBoxLayout, QCheckBox
)

# Tambahkan import ini setelah import lainnya
try:
    from modules_client.update_manager import UpdateManager
    from .update_dialog import UpdateDialog
    UPDATE_MANAGER_AVAILABLE = True
except ImportError:
    UPDATE_MANAGER_AVAILABLE = False

# Konstanta untuk mode testing
TESTING_MODE = os.getenv("STREAMMATE_DEV", "").lower() == "true"

# Setup project root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Skema warna Facebook Theme
FB_COLORS = {
    "primary": "#1877F2",
    "secondary": "#4267B2", 
    "light_bg": "#F0F2F5",
    "dark_bg": "#18191A",
    "text_primary": "#050505",
    "text_secondary": "#65676B",
    "button_primary": "#1877F2",
    "button_secondary": "#E4E6EB",
    "success": "#42B72A",
    "warning": "#F5B800",
    "error": "#FA383E",
}

# Style sheets
FB_BUTTON_PRIMARY = f"""
    QPushButton {{
        background-color: {FB_COLORS['button_primary']};
        color: white;
        border-radius: 6px;
        border: none;
        padding: 10px 15px;
        font-weight: bold;
    }}
    QPushButton:hover {{ background-color: #166FE5; }}
    QPushButton:pressed {{ background-color: #125FCA; }}
"""

FB_BUTTON_SECONDARY = f"""
    QPushButton {{
        background-color: {FB_COLORS['button_secondary']};
        color: {FB_COLORS['text_primary']};
        border-radius: 6px;
        border: none;
        padding: 10px 15px;
    }}
    QPushButton:hover {{ background-color: #D8DADF; }}
    QPushButton:pressed {{ background-color: #C9CCD1; }}
"""

# Import ConfigManager
try:
    from modules_client.config_manager import ConfigManager
except ImportError:
    from modules_server.config_manager import ConfigManager

# Import License validator dengan fallback
try:
    from modules_client.license_validator import LicenseValidator
    has_license_validator = True
except ImportError:
    has_license_validator = False
    class LicenseValidator:
        def __init__(self, testing_mode=False):
            self.testing_mode = testing_mode
            
        def validate(self, force_refresh=False):
            MAX_RETRIES = 3
            retry_count = 0
            result = {"is_valid": False, "tier": "basic"}

            while retry_count < MAX_RETRIES:
                try:
                    result = {"is_valid": True, "tier": "basic"}
                    return result
                except ConnectionError as e:
                    retry_count += 1
                    if retry_count >= MAX_RETRIES:
                        print(f"[WARNING] Server connection failed after {MAX_RETRIES} retries: {e}")
                        if hasattr(self, '_cached_result') and self._cached_result:
                            return self._cached_result
                        result = {
                            "is_valid": True,
                            "tier": "basic",
                            "expire_date": "2025-12-31",
                            "offline_mode": True
                        }
                        return result
                    import time
                    time.sleep(1)
            return result
        
    

# Import UI tabs
from .login_tab import LoginTab
from .subscription_tab import SubscriptionTab
from .translate_tab_basic import TranslateTab as TranslateTabBasic
from .cohost_tab_basic import CohostTabBasic as CohostTabBasic
from .virtual_mic_tab import VirtualMicTab
from .overlay_tab import OverlayTab
from .trakteer_tab import TrakteerTab
from .system_log_tab import SystemLogTab
from .reply_log_tab import ReplyLogTab
from .profile_tab import ProfileTab
from .tutorial_tab import TutorialTab
from .viewers_tab import ViewersTab
from datetime import datetime, timedelta

# Import subscription checker
from modules_client.subscription_checker import (
    set_idle_callbacks, start_usage_tracking, stop_usage_tracking
)

# Import Animasi Hotkey Tab dengan fallback
try:
    from .animasi_hotkey_tab import AnimasiHotkeyTab
    ANIMAZE_AVAILABLE = True
except ImportError as e:
    print(f"Animasi Hotkey Tab not available: {str(e)}")
    ANIMAZE_AVAILABLE = False
    
# Import RAG Tab dengan fallback
try:
    from .rag_tab import RAGTab
    RAG_AVAILABLE = True
except ImportError as e:
    print(f"RAG Tab not available: {str(e)}")
    RAG_AVAILABLE = False

# Exception handler global
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    print("Uncaught Exception:", exc_type.__name__, exc_value)
    
    # Log error to file
    error_log = Path("logs/error_log.txt")
    error_log.parent.mkdir(exist_ok=True)
    with open(error_log, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {exc_type.__name__}: {exc_value}\n")

sys.excepthook = handle_exception

# High-DPI policy
QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)

class MainWindow(QMainWindow):
    """Main window aplikasi StreamMate AI dengan arsitektur yang robust."""
    
    def __init__(self):
        super().__init__()
        
        # Inisialisasi atribut penting
        self.animaze_tab = None
        self.validation_timer = None
        self.chat_listener_module = None
        self._credit_warning_shown = False
        self._no_credit_shown = False
        self._idle_warning_shown = False
        
        # Setup window properties
        self.setWindowTitle("StreamMate AI - Live Streaming Automation")
        self.resize(1000, 700)
        self.setMinimumSize(800, 600)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Main widgets
        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCentralWidget(self.stack)
        
        # Setup status bar
        self._setup_status_bar()
        
        # Setup icon jika tersedia
        self._setup_icon()
        
        # Load configuration
        self.cfg = ConfigManager("config/settings.json")
        version = "v1.0.0"
        self.cfg.set("app_version", version)
        
        # License validator
        self.license_validator = LicenseValidator(testing_mode=TESTING_MODE)
        
        # Timer untuk demo expiration check
        self.demo_timer = QTimer(self)
        self.demo_timer.timeout.connect(self.check_demo_expiration)
        self.demo_timer.start(60000)  # Cek tiap menit

        # Placeholder untuk tabs
        self.subscription_tab = None
        self.main_tabs = None
        self.overlay_tab = None
        self.rag_tab = None
        self._subscription_tab_created = False
        
        # Session status timer
        self.session_timer = QTimer(self)
        self.session_timer.setInterval(10000)  # 10 detik
        self.session_timer.timeout.connect(self.update_session_status)
        self.session_timer.start()
        
        # Setup idle callbacks untuk session management
        set_idle_callbacks(
            warning_callback=self.show_idle_warning,
            timeout_callback=self.handle_idle_timeout
        )
        
        # Start license check timer
        self.license_timer = QTimer(self)
        self.license_timer.timeout.connect(self.update_license_status)
        self.license_timer.start(60000)  # Check every minute
        
        # Initial setup
        self.update_license_status()
        self.check_audio_devices()
        self._preload_chat_listener()
        # Tambahkan setelah self._preload_chat_listener()
        if UPDATE_MANAGER_AVAILABLE:
            self._setup_update_manager()
        
        # Mode handling
        if TESTING_MODE:
            self.show_test_mode_ui()
            return
        
        # Normal startup flow
        self._handle_startup_flow()

    def _setup_status_bar(self):
        """Setup status bar dengan label yang diperlukan."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # License status label
        self.license_label = QLabel()
        self.status_bar.addPermanentWidget(self.license_label)
        
        # Version label
        version_label = QLabel("StreamMate v1.0.0")
        self.status_bar.addWidget(version_label)

    def _setup_icon(self):
        """Setup aplikasi icon jika tersedia."""
        icon_path = os.path.join(ROOT, "resources", "icons", "app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def _handle_startup_flow(self):
        """Handle alur startup normal berdasarkan kondisi login dan lisensi."""
        token_file = Path("config/google_token.json")
        
        if token_file.exists() and self.cfg.get("user_data", {}).get("email"):
            # User sudah login sebelumnya
            if self.cfg.get("debug_mode", False):
                # Debug mode - langsung masuk
                tier = self.cfg.get("paket", "basic")
                self.pilih_paket(tier)
                return

            # Validate license
            license_data = self.license_validator.validate()
            if license_data.get("is_valid", False):
                self.pilih_paket(license_data.get("tier", "basic"))
            else:
                # Invalid license - show subscription tab
                self._show_login_and_subscription()
        else:
            # No token - show login tab
            self._show_login_tab()

    def _show_login_tab(self):
        """Tampilkan login tab."""
        self.login_tab = LoginTab(self)
        self.stack.addWidget(self.login_tab)

    def _show_login_and_subscription(self):
        """Tampilkan login tab dan persiapkan subscription tab."""
        self.login_tab = LoginTab(self)
        self.stack.addWidget(self.login_tab)
        self.login_berhasil()  # Will show subscription tab

    def show_test_mode_ui(self):
        """Tampilkan UI khusus untuk mode testing."""
        test_widget = QWidget()
        layout = QVBoxLayout(test_widget)
        
        # Judul
        title = QLabel("StreamMate - Test Mode")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Deskripsi
        desc = QLabel("Pilih paket untuk pengujian. Mode ini hanya untuk development.")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Spacer
        layout.addSpacing(30)
        
        # Container untuk tombol
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        
        # Tombol paket Basic
        btn_basic = QPushButton("Paket Basic")
        btn_basic.setMinimumHeight(50)
        btn_basic.setStyleSheet("font-size: 16px; background-color: #4CAF50; color: white;")
        btn_basic.clicked.connect(lambda: self.pilih_paket("basic"))
        btn_layout.addWidget(btn_basic)
        
        # Tombol paket Pro
        btn_pro = QPushButton("Paket Pro")
        btn_pro.setMinimumHeight(50)
        btn_pro.setStyleSheet("font-size: 16px; background-color: #2196F3; color: white;")
        btn_pro.clicked.connect(lambda: self.pilih_paket("pro"))
        btn_layout.addWidget(btn_pro)
        
        layout.addWidget(btn_container)
        
        # Section untuk mode normal
        layout.addSpacing(30)
        
        normal_section = QWidget()
        normal_layout = QVBoxLayout(normal_section)
        
        normal_label = QLabel("Atau gunakan mode normal (production):")
        normal_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        normal_layout.addWidget(normal_label)
        
        btn_normal = QPushButton("Login Normal")
        btn_normal.setStyleSheet("font-size: 14px;")
        btn_normal.clicked.connect(self.switch_to_normal_mode)
        normal_layout.addWidget(btn_normal, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(normal_section)
        
        # Mode configuration section
        layout.addSpacing(20)
        
        mode_section = QWidget()
        mode_layout = QVBoxLayout(mode_section)
        
        mode_label = QLabel("Mode Configuration:")
        mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mode_layout.addWidget(mode_label)
        
        # Checkbox untuk debug mode
        self.debug_checkbox = QCheckBox("Enable Debug Mode")
        self.debug_checkbox.setChecked(self.cfg.get("debug_mode", False))
        self.debug_checkbox.toggled.connect(self.toggle_debug_mode)
        mode_layout.addWidget(self.debug_checkbox)
        
        # Status label
        status_text = self._get_mode_status()
        self.mode_status = QLabel(status_text)
        self.mode_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mode_layout.addWidget(self.mode_status)
        
        layout.addWidget(mode_section)

        # Testing mode warning
        warning = QLabel("⚠️ Anda dalam TEST MODE. Ubah TESTING_MODE = False di main_window.py untuk production.")
        warning.setStyleSheet("color: #FF5722; font-weight: bold;")
        warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(warning)
        
        # Spacer di bawah
        layout.addStretch()
        
        # Tambahkan widget ke stack
        self.stack.addWidget(test_widget)
        self.stack.setCurrentWidget(test_widget)
        
        # Update status bar
        self.status_bar.showMessage("Test Mode Active", 5000)

    def switch_to_normal_mode(self):
        """Beralih ke mode normal (login)."""
        self._show_login_tab()
        self.stack.setCurrentWidget(self.login_tab)

    def toggle_debug_mode(self, checked):
        """Toggle debug mode on/off."""
        self.cfg.set("debug_mode", checked)
        self.mode_status.setText(self._get_mode_status())
        QMessageBox.information(
            self, "Debug Mode", 
            f"Debug mode {'enabled' if checked else 'disabled'}.\nRestart aplikasi untuk menerapkan perubahan."
        )

    def _get_mode_status(self):
        """Get current mode status text."""
        status = []
        
        if TESTING_MODE:
            status.append("🧪 Test Mode")
        
        if self.cfg.get("debug_mode", False):
            status.append("🐛 Debug Mode")
        
        user_email = self.cfg.get("user_data", {}).get("email", "")
        if self._is_dev_user(user_email):
            status.append("👨‍💻 Developer")
        
        return " | ".join(status) if status else "🚀 Production Mode"

    def _is_dev_user(self, email):
        """Check if email is in dev users list."""
        try:
            dev_path = Path("config/dev_users.json")
            if dev_path.exists() and email:
                with open(dev_path, 'r') as f:
                    dev_data = json.load(f)
                    return email in dev_data.get("emails", [])
        except:
            pass
        return False

    def login_berhasil(self):
        """Show subscription tab after successful login."""
        # Validate license
        license_data = self.license_validator.validate(force_refresh=True)

        # Cek jika demo masih aktif
        demo_active = self.check_demo_status()

        if demo_active:
            # Demo masih aktif, langsung gunakan
            self.pilih_paket("basic")
        elif license_data.get("is_valid", False):
            # Cek dari subscription_status.json
            subscription_file = Path("config/subscription_status.json")
            package_from_config = None

            if subscription_file.exists():
                try:
                    subscription_data = json.loads(subscription_file.read_text(encoding="utf-8"))
                    if subscription_data.get("status") == "paid":
                        package_from_config = subscription_data.get("package", "basic")
                        self.cfg.set("paket", package_from_config)
                        logger.info(f"Paket {package_from_config} disimpan ke settings.json")
                except Exception as e:
                    print(f"Error reading subscription file: {e}")

            # Gunakan paket dari config jika ada
            package = package_from_config or license_data.get("tier", "basic")
            self.pilih_paket(package)
        else:
            # Show subscription tab
            self.subscription_tab = SubscriptionTab(self)
            self.stack.addWidget(self.subscription_tab)
            self.stack.setCurrentWidget(self.subscription_tab)

        # Update status bar
        self.update_license_status()

    def check_demo_status(self):
        """Cek apakah demo masih aktif."""
        subscription_file = Path("config/subscription_status.json")
        if subscription_file.exists():
            try:
                data = json.loads(subscription_file.read_text(encoding="utf-8"))
                if data.get("status") == "demo" and "expire_date" in data:
                    try:
                        expire_date = datetime.fromisoformat(data["expire_date"])
                        if datetime.now() < expire_date:
                            return True
                    except:
                        pass
            except:
                pass
        return False

    def pilih_paket(self, paket):
        """Initialize main UI based on selected package."""
        logger.info(f"Memanggil pilih_paket dengan paket: {paket}")
        
        # Simpan paket ke settings.json
        self.cfg.set("paket", paket)
        
        # Validasi kredit
        if not self._validate_credit_before_access(paket):
            return
        
        # Cek jika sudah ada main_tabs dengan paket yang sama
        if hasattr(self, 'main_tabs') and self.main_tabs:
            current_package = self.cfg.get("paket", "")
            if current_package == paket:
                logger.info(f"Paket {paket} sudah aktif, tidak perlu inisialisasi ulang UI")
                self.stack.setCurrentWidget(self.main_tabs)
                return

        # Inisialisasi UI berdasarkan paket
        tabs = QTabWidget()
        tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        if paket == "basic":
            self._setup_basic_tabs(tabs)
        else:  # "pro" or other enhanced packages
            self._setup_pro_tabs(tabs)

        # Setup dan tampilkan main tabs
        self.main_tabs = tabs
        self.stack.addWidget(self.main_tabs)
        self.stack.setCurrentWidget(self.main_tabs)

        # Update status
        self.status_bar.showMessage(f"StreamMate {paket.capitalize()} activated", 5000)

        # Start session tracking
        start_usage_tracking(f"init_{paket}")

        # Setup resize support dan size policies
        self._setup_resize_support()
        self._setup_size_policies()

        logger.info(f"Paket {paket} berhasil diaktifkan")

    def _validate_credit_before_access(self, paket):
        """Validasi kredit sebelum mengakses paket."""
        # Skip untuk test mode
        if hasattr(self, 'license_validator') and self.license_validator.testing_mode:
            return True
            
        # Skip untuk debug mode
        if self.cfg.get("debug_mode", False):
            return True

        # Validasi kredit dari subscription_status.json
        subscription_file = Path("config/subscription_status.json")
        if subscription_file.exists():
            try:
                with open(subscription_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                hours_credit = float(data.get("hours_credit", 0))
                status = data.get("status", "")
                
                if hours_credit <= 0 and status == "paid":
                    QMessageBox.warning(
                        self, "Kredit Habis",
                        "Kredit jam Anda telah habis.\nSilakan beli kredit untuk melanjutkan."
                    )
                    
                    # Arahkan ke subscription tab
                    if not hasattr(self, 'subscription_tab') or self.subscription_tab is None:
                        self.subscription_tab = SubscriptionTab(self)
                        self.stack.addWidget(self.subscription_tab)
                    self.stack.setCurrentWidget(self.subscription_tab)
                    return False
                    
            except Exception as e:
                print(f"Error validating credit: {e}")
        
        return True

    def _setup_basic_tabs(self, tabs):
        """Setup tab untuk mode Basic."""
        # Inisialisasi tab-tab untuk mode Basic
        t_tab = TranslateTabBasic()
        c_tab = CohostTabBasic()

        # Tab-tab tambahan yang dibutuhkan Basic
        self.reply_log_tab = ReplyLogTab()
        self.trakteer_tab = TrakteerTab()
        self.overlay_tab = OverlayTab()
        self.system_log_tab = SystemLogTab()
        self.tutorial_tab = TutorialTab()
        self.profile_tab = ProfileTab(self)

        # Basic mode tabs
        tabs.addTab(t_tab, "🎤 Translate Voice")
        tabs.addTab(c_tab, "🤖 Cohost Chat")
        tabs.addTab(self.overlay_tab, "💬 Chat Overlay")
        tabs.addTab(self.trakteer_tab, "🎁 Trakteer")
        tabs.addTab(self.reply_log_tab, "📝 Reply Log")
        tabs.addTab(self.system_log_tab, "🔍 System Log")
        tabs.addTab(self.tutorial_tab, "❓ Tutorial")
        tabs.addTab(self.profile_tab, "👤 Profile")

        # Connect signals untuk reply log dan overlay
        if hasattr(c_tab, 'replyGenerated'):
            c_tab.replyGenerated.connect(self._handle_new_reply)

            # Koneksi langsung ke overlay
            if hasattr(self, 'overlay_tab'):
                c_tab.replyGenerated.connect(
                    lambda author, msg, reply: self.overlay_tab.update_overlay(author, reply)
                )

        # Setup animasi hotkey jika tersedia
        if ANIMAZE_AVAILABLE:
            self._setup_animaze_integration(c_tab, t_tab)

    def _setup_pro_tabs(self, tabs):
        """Setup tab untuk mode Pro (implementasi masa depan)."""
        # Placeholder untuk mode Pro
        from .translate_tab_basic import TranslateTab as TranslateTabPro
        from .cohost_tab_basic import CohostTabBasic as CohostTabPro
        
        # Pro tabs (gunakan basic untuk sementara)
        self._setup_basic_tabs(tabs)

    def _setup_animaze_integration(self, c_tab, t_tab):
        """Setup integrasi dengan Animaze jika tersedia."""
        try:
            self.animaze_tab = AnimasiHotkeyTab()
            self.main_tabs.addTab(self.animaze_tab, "🎭 Animasi Hotkey")

            # Connect signals untuk CohostTab
            if hasattr(c_tab, 'ttsAboutToStart') and hasattr(self.animaze_tab, 'start_tts_hotkey'):
                c_tab.ttsAboutToStart.connect(self.animaze_tab.start_tts_hotkey)

            if hasattr(c_tab, 'ttsFinished') and hasattr(self.animaze_tab, 'end_tts_hotkey'):
                c_tab.ttsFinished.connect(self.animaze_tab.end_tts_hotkey)

            # Connect signals untuk TranslateTab
            if hasattr(t_tab, 'ttsAboutToStart') and hasattr(self.animaze_tab, 'start_tts_hotkey'):
                t_tab.ttsAboutToStart.connect(self.animaze_tab.start_tts_hotkey)

            if hasattr(t_tab, 'ttsFinished') and hasattr(self.animaze_tab, 'end_tts_hotkey'):
                t_tab.ttsFinished.connect(self.animaze_tab.end_tts_hotkey)

            self.animaze_tab.update_animaze_persona(self.cfg.get("personality", "Ceria"))
            logger.info("Animaze integration setup completed")

        except Exception as e:
            logger.error(f"Failed to setup Animaze integration: {e}")

    def _handle_new_reply(self, author, message, reply):
        """Handler untuk meneruskan balasan baru ke reply_log_tab."""
        if hasattr(self, 'reply_log_tab') and self.reply_log_tab:
            print(f"[DEBUG] Handling new reply from {author}: {message[:30]}...")

            if hasattr(self.reply_log_tab, 'add_interaction'):
                self.reply_log_tab.add_interaction(author, message, reply)

            if hasattr(self, 'overlay_tab') and self.overlay_tab:
                self.overlay_tab.update_overlay(author, reply)

    def update_license_status(self):
        """Update license status in status bar."""
        try:
            license_data = self.license_validator.validate()

            if license_data.get("is_valid", False):
                tier = license_data.get("tier", "basic").capitalize()
                expire_date = license_data.get("expire_date", "Unknown")

                # Cek kredit jam dari license_data
                daily_usage = license_data.get("daily_usage", {})
                today = datetime.now().date().isoformat()
                used_hours = daily_usage.get(today, 0)

                # Tentukan limit berdasarkan tier
                limit_hours = 12 if tier.lower() == "pro" else 5
                remaining_hours = max(0, limit_hours - used_hours)

                if expire_date and expire_date != "Unknown":
                    try:
                        expire_dt = datetime.fromisoformat(expire_date)
                        days_left = (expire_dt - datetime.now()).days

                        # Update label dengan info kredit jam
                        self.license_label.setText(
                            f"🔑 {tier} - {days_left} days | 💰 {remaining_hours:.1f}/{limit_hours}h"
                        )

                        # Alert berdasarkan hari atau jam tersisa
                        if days_left <= 5 or remaining_hours < 1:
                            self.license_label.setStyleSheet("color: red; font-weight: bold;")

                            if remaining_hours < 1 and remaining_hours > 0:
                                self.show_credit_warning(remaining_hours)
                            elif remaining_hours <= 0:
                                self.show_no_credit_dialog()
                        else:
                            self.license_label.setStyleSheet("")

                    except Exception as e:
                        print(f"Error parsing expire date: {e}")
                        self.license_label.setText(f"🔑 {tier} - Expires: {expire_date}")
                else:
                    # Untuk langganan tanpa expire date
                    self.license_label.setText(f"🔑 {tier} | 💰 {remaining_hours:.1f}/{limit_hours}h")

                    # Cek kredit jam
                    if remaining_hours < 1 and remaining_hours > 0:
                        self.show_credit_warning(remaining_hours)
                    elif remaining_hours <= 0:
                        self.show_no_credit_dialog()
            else:
                self.license_label.setText("❌ No valid license")
                self.license_label.setStyleSheet("color: red;")

        except Exception as e:
            print(f"Error updating license status: {e}")

    def show_credit_warning(self, hours_left):
        """Tampilkan warning saat kredit rendah."""
        if not hasattr(self, '_credit_warning_shown') or not self._credit_warning_shown:
            QMessageBox.warning(
                self, "Kredit Rendah",
                f"Sisa kredit: {hours_left:.1f} jam\n\nSegera isi ulang kredit Anda.",
                QMessageBox.StandardButton.Ok
            )
            self._credit_warning_shown = True
            QTimer.singleShot(30 * 60 * 1000, lambda: setattr(self, '_credit_warning_shown', False))

    def show_no_credit_dialog(self):
        """Dialog saat kredit habis."""
        if not hasattr(self, '_no_credit_shown') or not self._no_credit_shown:
            reply = QMessageBox.question(
                self, "Kredit Habis",
                "Kredit jam Anda telah habis.\n\nSilakan beli kredit untuk melanjutkan.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Switch ke tab subscription jika ada
                if hasattr(self, 'main_tabs'):
                    for i in range(self.main_tabs.count()):
                        if "Subscription" in self.main_tabs.tabText(i):
                            self.main_tabs.setCurrentIndex(i)
                            break
            self._no_credit_shown = True
            QTimer.singleShot(30 * 60 * 1000, lambda: setattr(self, '_no_credit_shown', False))
    def show_idle_warning(self, seconds_left):
        """Tampilkan peringatan idle."""
        mins_left = int(seconds_left / 60)
        if not hasattr(self, '_idle_warning_shown') or not self._idle_warning_shown:
            self.status_bar.showMessage(f"⚠️ Idle detected. Session will pause in {mins_left} minutes.", 10000)
            self._idle_warning_shown = True
    def handle_idle_timeout(self):
        """Handle saat idle timeout tercapai."""
        self.status_bar.showMessage("Session paused due to inactivity. Interact to resume.", 10000)
        self._idle_warning_shown = False
    def update_session_status(self):
        """Update status sesi di status bar."""
        if hasattr(self, 'license_label'):
            self.update_license_status()
    def check_demo_expiration(self):
        """Cek apakah demo sudah berakhir."""
        subscription_file = Path("config/subscription_status.json")
        result = False
        if subscription_file.exists():
            try:
                data = json.loads(subscription_file.read_text(encoding="utf-8"))
                if data.get("status") == "demo" and "expire_date" in data:
                    try:
                        expire_date_str = data["expire_date"]
                        if '+' in expire_date_str:
                            from datetime import timezone
                            expire_date = datetime.fromisoformat(expire_date_str)
                            now_time = datetime.now(timezone.utc)
                        else:
                            expire_date = datetime.fromisoformat(expire_date_str)
                            now_time = datetime.now()
                        if now_time >= expire_date:
                            # Demo berakhir
                            data["status"] = "expired"
                            subscription_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
                            print(f"[INFO] Demo expired, changing status to expired")
                            QMessageBox.information(
                                self, "Demo Berakhir",
                                "Waktu demo 30 menit telah berakhir.\n\n"
                                "Silakan beli kredit untuk melanjutkan penggunaan StreamMate AI."
                            )
                            # Navigasi ke subscription tab dengan lebih aman
                            if not hasattr(self, 'subscription_tab') or self.subscription_tab is None:
                                print("[INFO] Creating new subscription tab")
                                self.subscription_tab = SubscriptionTab(self)
                                self.stack.addWidget(self.subscription_tab)
                            try:
                                if self.stack.indexOf(self.subscription_tab) >= 0:
                                    print(f"[INFO] Setting subscription tab as current widget")
                                    self.stack.setCurrentWidget(self.subscription_tab)
                                else:
                                    print(f"[WARNING] Subscription tab not found in stack")
                                    self.stack.addWidget(self.subscription_tab)
                                    self.stack.setCurrentWidget(self.subscription_tab)
                            except Exception as e:
                                print(f"[ERROR] Failed to navigate to subscription tab: {e}")
                            # Nonaktifkan tab CoHost jika ada
                            if hasattr(self, 'main_tabs') and self.main_tabs:
                                for i in range(self.main_tabs.count()):
                                    if "Cohost" in self.main_tabs.tabText(i):
                                        print(f"[INFO] Disabling Cohost tab at index {i}")
                                        self.main_tabs.setTabEnabled(i, False)
                            result = True
                    except ValueError as e:
                        print(f"[DEBUG] Format expire_date invalid: {e}")
                        try:
                            if 'T' in expire_date_str:
                                date_part, time_part = expire_date_str.split('T')
                                time_part = time_part.split('.')[0]
                                expire_date_str = f"{date_part}T{time_part}"
                                expire_date = datetime.fromisoformat(expire_date_str)
                                now_time = datetime.now()
                                if now_time >= expire_date:
                                    data["status"] = "expired"
                                    subscription_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
                        except Exception as parse_error:
                            print(f"[DEBUG] Fallback parsing juga gagal: {parse_error}")
            except Exception as e:
                print(f"[ERROR] Error checking demo expiration: {e}")
                import traceback
                traceback.print_exc()
        print(f"[DEBUG] check_demo_expiration result: {result}")
        return result
    
    def logout(self):
        """Handle logout request dari ProfileTab."""
        reply = QMessageBox.question(
            self, 'Konfirmasi Logout',
            'Apakah Anda yakin ingin logout dari aplikasi?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Simpan email user untuk mempertahankan data saat login kembali
            email = self.cfg.get("user_data", {}).get("email", "")
            # Hapus token Google jika ada
            token_path = Path("config/google_token.json")
            if token_path.exists():
                try:
                    token_path.unlink()
                except Exception as e:
                    print(f"Error removing token: {e}")
            # Reset data user tapi jangan hapus subscription_status.json!
            self.cfg.set("user_data", {})
            
            # Track logout ke server
            if email:
                try:
                    import requests
                    response = requests.post(
                        "http://localhost:8000/api/email/track",
                        json={"email": email, "action": "logout"},
                        timeout=5
                    )
                    
                    if response.status_code == 200:
                        print(f"[DEBUG] Logout tracked to server for {email}")
                    else:
                        print(f"[DEBUG] Failed to track logout: {response.status_code}")
                        
                except Exception as e:
                    print(f"[DEBUG] Logout tracking error: {e}")
                
                # Fallback ke temp file untuk backward compatibility
                temp_file = Path("temp/last_logout_email.txt")
                temp_file.parent.mkdir(exist_ok=True)
                temp_file.write_text(email, encoding="utf-8")
            
            # Hentikan semua proses aktif
            if hasattr(self, 'main_tabs') and self.main_tabs:
                for i in range(self.main_tabs.count()):
                    tab = self.main_tabs.widget(i)
                    if hasattr(tab, 'stop'):
                        try:
                            tab.stop()
                        except:
                            pass
            
            # Buat tab login baru
            if not hasattr(self, 'login_tab') or not self.login_tab:
                self.login_tab = LoginTab(self)
                self.stack.addWidget(self.login_tab)
            
            # Tampilkan tab login
            self.stack.setCurrentWidget(self.login_tab)
            
            # Hapus tab yang sudah tidak perlu
            if hasattr(self, 'main_tabs') and self.main_tabs:
                self.stack.removeWidget(self.main_tabs)
                self.main_tabs = None
            if hasattr(self, 'subscription_tab') and self.subscription_tab:
                self.stack.removeWidget(self.subscription_tab)
                self.subscription_tab = None
            
            # Tampilkan konfirmasi
            self.status_bar.showMessage("Berhasil logout", 3000)
            
    def _setup_resize_support(self):
        """Pastikan semua tab mendukung resize dengan baik."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if hasattr(self, 'stack') and self.stack:
            self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            for i in range(self.stack.count()):
                widget = self.stack.widget(i)
                if widget:
                    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if hasattr(self, 'main_tabs') and self.main_tabs:
            self.main_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            for i in range(self.main_tabs.count()):
                tab = self.main_tabs.widget(i)
                if tab:
                    tab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                    for child in tab.findChildren(QTextEdit):
                        child.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                    for child in tab.findChildren(QLineEdit):
                        child.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                    from PyQt6.QtWidgets import QScrollArea
                    for child in tab.findChildren(QScrollArea):
                        child.setWidgetResizable(True)
                        child.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                    for layout in tab.findChildren(QFormLayout):
                        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.main_tabs.setMinimumWidth(750) if hasattr(self, 'main_tabs') else None
        print("[INFO] Resize support setup completed")
    def _setup_size_policies(self):
        """Setup kebijakan ukuran secara konsisten di seluruh aplikasi."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if hasattr(self, 'stack') and self.stack:
            self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if hasattr(self, 'main_tabs') and self.main_tabs:
            self.main_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            for i in range(self.main_tabs.count()):
                tab = self.main_tabs.widget(i)
                if tab:
                    tab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                    for child in tab.findChildren(QTextEdit):
                        child.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                    for child in tab.findChildren(QLineEdit):
                        child.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                    from PyQt6.QtWidgets import QScrollArea
                    for child in tab.findChildren(QScrollArea):
                        child.setWidgetResizable(True)
                        child.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                    for layout in tab.findChildren(QFormLayout):
                        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    def check_audio_devices(self):
        """Check audio devices and log status."""
        try:
            from modules_server.tts_engine import check_audio_devices
            return check_audio_devices()
        except Exception as e:
            print(f"Error checking audio devices: {e}")
            return False
    def _preload_chat_listener(self):
        """Pre-load chat_listener module for later use."""
        try:
            import importlib.util
            chat_listener_path = os.path.join(ROOT, "listeners", "chat_listener.py")
            if os.path.exists(chat_listener_path):
                spec = importlib.util.spec_from_file_location("chat_listener", chat_listener_path)
                self.chat_listener_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(self.chat_listener_module)
                print("[DEBUG] Chat listener module preloaded successfully")
        except Exception as e:
            print(f"[WARN] Failed to preload chat_listener module: {e}")
    def closeEvent(self, event):
        """Handle window close event."""
        # Stop license timer
        if hasattr(self, 'license_timer') and self.license_timer.isActive():
            self.license_timer.stop()
        # Stop validation timer
        if hasattr(self, 'validation_timer') and self.validation_timer and self.validation_timer.isActive():
            self.validation_timer.stop()
        # Stop session tracking
        stop_usage_tracking()
        # Ask for confirmation
        reply = QMessageBox.question(
            self, 'Confirm Exit',
            'Are you sure you want to exit the application?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Stop any active tabs before closing
            if hasattr(self, 'main_tabs') and self.main_tabs:
                current_tab = self.main_tabs.currentWidget()
                if hasattr(current_tab, 'stop'):
                    try:
                        current_tab.stop()
                    except:
                        pass
                for i in range(self.main_tabs.count()):
                    tab = self.main_tabs.widget(i)
                    if hasattr(tab, 'stop'):
                        try:
                            tab.stop()
                        except:
                            pass
            # Close any Animaze connections
            try:
                if hasattr(self, 'animaze_tab') and self.animaze_tab:
                    if hasattr(self.animaze_tab, 'disconnect_from_animaze'):
                        self.animaze_tab.disconnect_from_animaze()
            except Exception as e:
                print(f"Error disconnecting Animaze: {e}")
            # Accept event
            event.accept()
        else:
            event.ignore()
    def back_to_test_mode(self):
        """Kembali ke mode pengujian."""
        if TESTING_MODE:
            self.show_test_mode_ui() 

    def _setup_update_manager(self):
        """Setup update manager untuk auto-update."""
        try:
            self.update_manager = UpdateManager(self.cfg)
            
            # Connect signals
            self.update_manager.update_available.connect(self._handle_update_available)
            self.update_manager.update_error.connect(self._handle_update_error)
            
            logger.info("Update manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize update manager: {e}")

    def _handle_update_available(self, update_info):
        """Handle saat ada update tersedia."""
        try:
            # Cek apakah versi ini sudah di-skip
            skipped_version = self.cfg.get("skipped_update_version", "")
            if skipped_version == update_info["tag_name"]:
                logger.info(f"Update {update_info['tag_name']} was skipped by user")
                return

            # Cek reminder time
            reminder_time = self.cfg.get("update_reminder_time", 0)
            current_time = datetime.now().timestamp()
            if reminder_time > current_time:
                logger.info("Update reminder postponed")
                return

            # Tampilkan dialog update
            self._show_update_dialog(update_info)

        except Exception as e:
            logger.error(f"Error handling update available: {e}")

    def _show_update_dialog(self, update_info):
        """Tampilkan dialog update."""
        try:
            if not hasattr(self, 'update_manager'):
                return

            from .update_dialog import UpdateDialog
            dialog = UpdateDialog(self.update_manager, self)
            dialog.set_update_info(update_info)

            # Show dialog non-blocking
            dialog.show()

        except Exception as e:
            logger.error(f"Error showing update dialog: {e}")

    def _show_update_dialog(self, update_info):
        """Tampilkan dialog update."""
        try:
            if not hasattr(self, 'update_manager'):
                return
            
            dialog = UpdateDialog(self.update_manager, self)
            dialog.set_update_info(update_info)
            
            # Show dialog non-blocking
            dialog.show()
            
        except Exception as e:
            logger.error(f"Error showing update dialog: {e}")

    def _handle_update_error(self, error_message):
        """Handle error dari update manager."""
        logger.error(f"Update manager error: {error_message}")

    def check_for_updates_manual(self):
        """Manual check untuk update dari menu."""
        if hasattr(self, 'update_manager'):
            self.update_manager.check_for_updates(show_no_update=True)
        else:
            QMessageBox.information(
                self, "Update Check",
                "Update manager tidak tersedia.\nSilakan download versi terbaru dari website."
            )