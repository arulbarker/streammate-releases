# ui/profile_tab.py - FIXED VERSION
import os
import json
import requests
import sys
import logging
logger = logging.getLogger('StreamMate')
from pathlib import Path
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QFileDialog, QMessageBox, 
    QGroupBox, QFormLayout, QProgressBar, QSpacerItem, QSizePolicy,
    QLineEdit, QDialog, QGridLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QScrollArea, QTabWidget, QCheckBox, QCalendarWidget
)
from PyQt6.QtGui import QPixmap, QIcon, QFont, QImage, QColor
from PyQt6.QtCore import Qt, QTimer, QDate, QSize

# Impor sistem konfigurasi
from modules_server.config_manager import ConfigManager

# Impor validator lisensi jika ada
try:
    from modules_server.license_validator import LicenseValidator
    has_license_validator = True
except ImportError:
    has_license_validator = False
    LicenseValidator = None

# PERBAIKAN 1: Import credit tracker dengan error handling yang benar
try:
    from modules_server.real_credit_tracker import credit_tracker
    has_credit_tracker = True
except ImportError:
    has_credit_tracker = False
    credit_tracker = None

# PERBAIKAN 2: Import subscription checker dengan fallback
try:
    from modules_server.subscription_checker import get_today_usage, get_usage_history
    has_subscription_checker = True
except ImportError:
    has_subscription_checker = False
    def get_today_usage(): return {"hours_used": 0, "hours_credit": 0}
    def get_usage_history(): return []

# UI Components - style_module tidak ada, comment dulu
# from ui.style_module import ModernStylesheet

# PERBAIKAN 3: Initialize semua QLabel yang diperlukan SEBELUM init_ui()
from modules_server.daily_limit_manager import get_daily_usage_stats

# Timer untuk auto refresh - OPTIMASI: Interval lebih lambat
from PyQt6.QtCore import QTimer

# ✅ FIX: Impor fungsi path helper
from utils.path_util import get_app_data_path

class ProfileTab(QWidget):
    """Tab profil pengguna yang disempurnakan dengan statistik detail."""
    
    def __init__(self, parent=None):
        super().__init__()
        self.cfg = ConfigManager("config/settings.json")
        self.parent_window = parent
        
        # Inisiasi validator lisensi
        self.license_validator = None
        if has_license_validator:
            self.license_validator = LicenseValidator()
        
        # Timer untuk auto refresh - OPTIMASI: Interval lebih lambat
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(120000)  # ✅ OPTIMASI: Ubah dari 15 detik ke 2 menit
        self.refresh_timer.timeout.connect(self.update_usage_display)
        
        # PERBAIKAN 3: Initialize semua QLabel yang diperlukan SEBELUM init_ui()
        self.hours_credit = QLabel("0 credits")
        self.hours_used = QLabel("0 credits")
        self.hours_remaining = QLabel("0 credits")
        self.today_usage = QLabel("0 credits")
        self.daily_limit = QLabel("5 credits/day")
        
        # Setup UI
        self.init_ui()
        
        # Muat data
        self.load_profile_data()
        
        # Mulai timer refresh
        self.refresh_timer.start()
    
    def force_refresh(self):
        """Force refresh credit data from latest sources - untuk sync real-time"""
        try:
            print("[PROFILE] Force refresh triggered - updating credit display...")
            
            # Force update from subscription file yang terbaru
            self.update_usage_display()
            
            # Force reload profile data
            self.load_profile_data()
            
            print("[PROFILE] Force refresh completed")
            
        except Exception as e:
            print(f"[PROFILE] Error in force refresh: {e}")
    
    def init_ui(self):
        """Inisiasi elemen UI yang disempurnakan dengan tab dan informasi detail."""
        # Main layout menggunakan scroll area untuk konten yang panjang
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        
        # Scroll area untuk konten yang panjang
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        
        # ========== Bagian Header dengan Avatar ==========
        header_layout = QHBoxLayout()
        
        # Avatar area
        self.avatar_frame = QLabel()
        self.avatar_frame.setFixedSize(120, 120)
        self.avatar_frame.setStyleSheet("border: 2px solid #1877F2; border-radius: 60px;")
        self.avatar_frame.setScaledContents(True)
        header_layout.addWidget(self.avatar_frame)
        
        # Info pengguna
        user_info = QVBoxLayout()
        
        self.name_label = QLabel("User Name")
        self.name_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #1877F2;")
        user_info.addWidget(self.name_label)
        
        self.email_label = QLabel("email@example.com")
        self.email_label.setStyleSheet("font-size: 16px; color: #666;")
        user_info.addWidget(self.email_label)
        
        self.status_label = QLabel("Status: Basic")
        self.status_label.setStyleSheet("font-size: 16px; color: #1a73e8; font-weight: bold;")
        user_info.addWidget(self.status_label)
        
        # Label untuk last login
        self.last_login_label = QLabel("Last login: -")
        self.last_login_label.setStyleSheet("font-size: 13px; color: #888;")
        user_info.addWidget(self.last_login_label)
        
        # Row untuk tombol avatar dan edit
        buttons_row = QHBoxLayout()
        
        # Tombol ubah avatar
        avatar_btn = QPushButton("🖼️ Change Avatar")
        avatar_btn.setStyleSheet("padding: 8px; background-color: #e4e6eb; color: #050505; border-radius: 6px; border: none;")
        avatar_btn.clicked.connect(self.change_avatar)
        buttons_row.addWidget(avatar_btn)
        
        # Tombol edit profil
        edit_btn = QPushButton("✏️ Edit Profile")
        edit_btn.setStyleSheet("padding: 8px; background-color: #e4e6eb; color: #050505; border-radius: 6px; border: none;")
        edit_btn.clicked.connect(self.edit_profile)
        buttons_row.addWidget(edit_btn)
        
        user_info.addLayout(buttons_row)
        user_info.addStretch()
        header_layout.addLayout(user_info, 1)
        
        # Tombol logout di header
        logout_btn = QPushButton("🚪 Logout")
        logout_btn.setStyleSheet(
            "font-size: 14px; padding: 10px; "
            "background-color: #f44336; color: white; "
            "border-radius: 8px; border: none; font-weight: bold;"
        )
        logout_btn.clicked.connect(self.logout)
        header_layout.addWidget(logout_btn, alignment=Qt.AlignmentFlag.AlignTop)
        
        content_layout.addLayout(header_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        content_layout.addWidget(separator)
        
        # ========== Tab Widget untuk pengorganisasian konten ==========
        tabs = QTabWidget()
        
        # Tab 1: Kredit
        credit_tab = QWidget()
        self.setup_credit_tab(credit_tab)
        tabs.addTab(credit_tab, "💰 Credits")
        
        # Tab 2: Statistik Penggunaan
        stats_tab = QWidget()
        self.setup_stats_tab(stats_tab)
        tabs.addTab(stats_tab, "📊 Statistics")
        
        # Tab 3: Riwayat Aktivitas
        history_tab = QWidget()
        self.setup_history_tab(history_tab)
        tabs.addTab(history_tab, "📜 History")
        
        # Tab 4: Pengaturan
        settings_tab = QWidget()
        self.setup_settings_tab(settings_tab)
        tabs.addTab(settings_tab, "⚙️ Settings")
        
        content_layout.addWidget(tabs)
        
        # Bagian Navigasi Ke Tab Lain
        navigation_group = QGroupBox("🧭 Navigation")
        navigation_layout = QHBoxLayout()
        
        # Tombol Kembali ke Subscription
        back_btn = QPushButton("↩️ Subscription Tab")
        back_btn.setStyleSheet(
            "font-size: 14px; padding: 10px; "
            "background-color: #4267B2; color: white; "
            "border-radius: 8px; border: none; font-weight: bold;"
        )
        back_btn.clicked.connect(self.to_subscription)
        navigation_layout.addWidget(back_btn)
        
        # Tombol ke Tab Tutorial
        tutorial_btn = QPushButton("❓ Tutorial Tab")
        tutorial_btn.setStyleSheet(
            "font-size: 14px; padding: 10px; "
            "background-color: #4267B2; color: white; "
            "border-radius: 8px; border: none; font-weight: bold;"
        )
        tutorial_btn.clicked.connect(self.to_tutorial)
        navigation_layout.addWidget(tutorial_btn)
        
        navigation_group.setLayout(navigation_layout)
        content_layout.addWidget(navigation_group)
        
        # App version dan Build info
        app_version = QLabel(f"StreamMate AI v{self.cfg.get('app_version', '1.0.0')}")
        app_version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_version.setStyleSheet("color: #666; font-size: 12px; margin-top: 10px;")
        content_layout.addWidget(app_version)
        
        # Build info
        build_info = QLabel(f"Build: {datetime.now().strftime('%Y%m%d')}")
        build_info.setAlignment(Qt.AlignmentFlag.AlignCenter) 
        build_info.setStyleSheet("color: #666; font-size: 12px;")
        content_layout.addWidget(build_info)
        
        # Set content widget to scroll area
        scroll_area.setWidget(content_widget)
        
        # Add scroll area to main layout
        main_layout.addWidget(scroll_area)
    
    def setup_credit_tab(self, tab):
        """PERBAIKAN 4: Setup tab informasi kredit dengan form layout yang benar."""
        layout = QVBoxLayout(tab)
        
        # Status dan Detail Paket
        status_group = QGroupBox("🎫 Package Status")
        status_layout = QFormLayout()
        
        self.paket_info = QLabel("Basic")
        self.paket_info.setStyleSheet("font-weight: bold; color: #1877F2;")
        status_layout.addRow("Active Package:", self.paket_info)
        
        self.expire_label = QLabel("No information available")
        status_layout.addRow("Valid Until:", self.expire_label)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Detail Kredit
        credit_group = QGroupBox("⏱️ Credit Details")
        credit_layout = QVBoxLayout()
        
        # Progress bar untuk kredit
        usage_label = QLabel("Remaining Credits:")
        credit_layout.addWidget(usage_label)
        
        self.usage_bar = QProgressBar()
        self.usage_bar.setMinimum(0)
        self.usage_bar.setMaximum(100)
        self.usage_bar.setValue(0)
        self.usage_bar.setFormat("%v/%m credits")
        self.usage_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 5px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #1877F2;
                border-radius: 5px;
            }
        """)
        credit_layout.addWidget(self.usage_bar)
        
        # PERBAIKAN 5: Form layout untuk detail kredit yang benar
        credit_form = QFormLayout()
        credit_form.addRow("Total Credits:", self.hours_credit)
        credit_form.addRow("Credits Used:", self.hours_used)
        credit_form.addRow("Remaining Credits:", self.hours_remaining)
        credit_form.addRow("Today's Usage:", self.today_usage)
        credit_form.addRow("Daily Limit:", QLabel("10 hours/day (credit reduction based on usage)"))
        
        credit_layout.addLayout(credit_form)
        
        # Tombol beli kredit 100.000
        buy_btn = QPushButton("💰 Buy 100,000 Credits")
        buy_btn.setStyleSheet("""
            QPushButton {
                background-color: #1877F2;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0C63D4;
            }
        """)
        buy_btn.clicked.connect(lambda: self.buy_credits(100_000))
        credit_layout.addWidget(buy_btn)
        
        # Tombol beli kredit 200.000 (Bonus)
        buy_bonus_btn = QPushButton("🎁 Buy 200,000 Credits (Bonus)")
        buy_bonus_btn.setStyleSheet("""
            QPushButton {
                background-color: #42B883;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #33A06F;
            }
        """)
        buy_bonus_btn.clicked.connect(lambda: self.buy_credits(200_000))
        credit_layout.addWidget(buy_bonus_btn)
        
        # Tabel penggunaan harian
        self.daily_table = QTableWidget()
        self.daily_table.setColumnCount(3)
        self.daily_table.setHorizontalHeaderLabels(["Date", "Credits Used", "% of Limit"])
        self.daily_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        credit_layout.addWidget(self.daily_table)
        
        # Notifikasi kredit
        self.notif_kredit = QCheckBox("Notify when credits are low (< 10 credits)")
        self.notif_kredit.setChecked(True)
        credit_layout.addWidget(self.notif_kredit)
        
        credit_group.setLayout(credit_layout)
        layout.addWidget(credit_group)
        
        # Refresh button
        refresh_layout = QHBoxLayout()
        refresh_layout.addStretch()
        
        self.auto_refresh_checkbox = QCheckBox("Auto-refresh (15s)")
        self.auto_refresh_checkbox.setChecked(True)
        self.auto_refresh_checkbox.toggled.connect(self.toggle_auto_refresh)
        refresh_layout.addWidget(self.auto_refresh_checkbox)
        
        refresh_btn = QPushButton("🔄 Refresh Data")
        refresh_btn.setStyleSheet("padding: 8px;")
        refresh_btn.clicked.connect(self.reload_profile)
        refresh_layout.addWidget(refresh_btn)
        
        layout.addLayout(refresh_layout)
        layout.addStretch()
    
    def setup_stats_tab(self, tab):
        """Setup tab statistik dengan tampilan yang lebih informatif."""
        layout = QVBoxLayout(tab)
        
        # Usage Overview
        overview_group = QGroupBox("📊 Usage Overview")
        overview_layout = QGridLayout()
        
        # Total Usage
        total_usage = QLabel("Total Usage")
        total_usage.setStyleSheet("font-weight: bold; color: #1877F2;")
        overview_layout.addWidget(total_usage, 0, 0)
        
        self.total_usage_value = QLabel("0 credits")
        self.total_usage_value.setStyleSheet("font-size: 18px; font-weight: bold;")
        overview_layout.addWidget(self.total_usage_value, 0, 1)
        
        # Average Daily Usage
        avg_usage = QLabel("Daily Average")
        avg_usage.setStyleSheet("font-weight: bold; color: #1877F2;")
        overview_layout.addWidget(avg_usage, 1, 0)
        
        self.avg_usage_value = QLabel("0 credits")
        self.avg_usage_value.setStyleSheet("font-size: 18px; font-weight: bold;")
        overview_layout.addWidget(self.avg_usage_value, 1, 1)
        
        # Peak Usage
        peak_usage = QLabel("Peak Usage")
        peak_usage.setStyleSheet("font-weight: bold; color: #1877F2;")
        overview_layout.addWidget(peak_usage, 2, 0)
        
        self.peak_usage_value = QLabel("0 credits")
        self.peak_usage_value.setStyleSheet("font-size: 18px; font-weight: bold;")
        overview_layout.addWidget(self.peak_usage_value, 2, 1)
        
        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)
        
        # Usage Calendar
        calendar_group = QGroupBox("📅 Usage Calendar")
        calendar_layout = QVBoxLayout()
        
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.clicked.connect(self.show_day_usage)
        calendar_layout.addWidget(self.calendar)
        
        # Day usage info
        self.day_usage_info = QLabel("Select a date to view details")
        self.day_usage_info.setStyleSheet("color: #666; font-style: italic;")
        calendar_layout.addWidget(self.day_usage_info)
        
        calendar_group.setLayout(calendar_layout)
        layout.addWidget(calendar_group)
        
        # Export Button
        export_btn = QPushButton("📤 Export Profile Data")
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #1877F2;
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #166FE5;
            }
        """)
        export_btn.clicked.connect(self.export_profile_data)
        layout.addWidget(export_btn)
        
        # Add stretch
        layout.addStretch()
    
    def setup_history_tab(self, tab):
        """Setup tab riwayat aktivitas."""
        layout = QVBoxLayout(tab)
        
        # Riwayat login
        login_group = QGroupBox("🔐 Login History")
        login_layout = QVBoxLayout()
        
        self.login_table = QTableWidget(5, 2)
        self.login_table.setHorizontalHeaderLabels(["Time", "Status"])
        self.login_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.login_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.login_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.login_table.setAlternatingRowColors(True)
        
        login_layout.addWidget(self.login_table)
        login_group.setLayout(login_layout)
        layout.addWidget(login_group)
        
        # Riwayat transaksi/pembelian
        trans_group = QGroupBox("💲 Transaction History")
        trans_layout = QVBoxLayout()
        
        self.trans_table = QTableWidget(5, 4)
        self.trans_table.setHorizontalHeaderLabels(["Date", "Package", "Amount", "Status"])
        self.trans_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.trans_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.trans_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.trans_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.trans_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.trans_table.setAlternatingRowColors(True)
        
        trans_layout.addWidget(self.trans_table)
        trans_group.setLayout(trans_layout)
        layout.addWidget(trans_group)
        
        # Kalender penggunaan
        calendar_group = QGroupBox("📆 Usage Calendar")
        calendar_layout = QVBoxLayout()
        
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.clicked.connect(self.show_day_usage)
        
        calendar_layout.addWidget(self.calendar)
        
        # Label untuk menampilkan penggunaan per hari
        self.day_usage_label = QLabel("Select a date to view usage details")
        self.day_usage_label.setStyleSheet("font-size: 12px; color: #666; background-color: #f8f9fa; padding: 8px; border-radius: 5px;")
        self.day_usage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        calendar_layout.addWidget(self.day_usage_label)
        
        calendar_group.setLayout(calendar_layout)
        layout.addWidget(calendar_group)
        
        layout.addStretch()
    
    def setup_settings_tab(self, tab):
        """Setup tab pengaturan pengguna."""
        layout = QVBoxLayout(tab)
        
        # Pengaturan profil
        profile_group = QGroupBox("👤 Profile Settings")
        profile_layout = QFormLayout()
        
        # Nama pengguna (edit)
        name_layout = QHBoxLayout()
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("User Name")
        name_layout.addWidget(self.username_edit)
        
        save_name_btn = QPushButton("💾 Save")
        save_name_btn.clicked.connect(self.save_username)
        save_name_btn.setMaximumWidth(100)
        name_layout.addWidget(save_name_btn)
        
        profile_layout.addRow("User Name:", name_layout)
        
        # Email (read-only)
        self.email_display = QLineEdit()
        self.email_display.setReadOnly(True)
        self.email_display.setStyleSheet("background-color: #f5f5f5;")
        profile_layout.addRow("Email:", self.email_display)
        
        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)
        
        # Opsi notifikasi
        notif_group = QGroupBox("🔔 Notification Options")
        notif_layout = QVBoxLayout()
        
        self.notif_kredit = QCheckBox("Notify when credits are low (< 10 credits)")
        self.notif_kredit.setChecked(True)
        notif_layout.addWidget(self.notif_kredit)
        
        self.notif_login = QCheckBox("Notify on login from new device")
        self.notif_login.setChecked(True)
        notif_layout.addWidget(self.notif_login)
        
        self.notif_update = QCheckBox("Notify when app update is available")
        self.notif_update.setChecked(True)
        notif_layout.addWidget(self.notif_update)
        
        notif_group.setLayout(notif_layout)
        layout.addWidget(notif_group)
        
        # Tombol Export Data
        export_btn = QPushButton("📤 Export Profile Data")
        export_btn.setStyleSheet(
            "font-size: 14px; padding: 10px; "
            "background-color: #1877F2; color: white; "
            "border-radius: 8px; border: none; font-weight: bold;"
        )
        export_btn.clicked.connect(self.export_profile_data)
        layout.addWidget(export_btn)

        # Check for Updates
        check_update_btn = QPushButton("🔄 Check for Updates")
        check_update_btn.setStyleSheet(
            "font-size: 14px; padding: 10px; "
            "background-color: #17a2b8; color: white; "
            "border-radius: 8px; border: none; font-weight: bold;"
        )
        check_update_btn.clicked.connect(self.check_for_updates)
        layout.addWidget(check_update_btn)
        
        # Simpan pengaturan
        save_settings_btn = QPushButton("💾 Save Settings")
        save_settings_btn.setStyleSheet(
            "font-size: 14px; padding: 10px; "
            "background-color: #4CAF50; color: white; "
            "border-radius: 8px; border: none; font-weight: bold;"
        )
        save_settings_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_settings_btn)
        
        layout.addStretch()
    
    def load_profile_data(self):
        """Muat data profil dan status penggunaan dari konfigurasi."""
        # Avatar
        avatar_path = Path("assets/user_avatar.png")
        if avatar_path.exists():
            pixmap = QPixmap(str(avatar_path))
            self.avatar_frame.setPixmap(pixmap)
        else:
            # Avatar default
            self.avatar_frame.setStyleSheet(
                "border: 2px solid #1877F2; border-radius: 60px; "
                "background-color: #e4e6eb; color: #1877F2; "
                "font-size: 48px; font-weight: bold; "
                "qproperty-alignment: AlignCenter;"
            )
            self.avatar_frame.setText("?")
        
        # Informasi User
        user_data = self.cfg.get("user_data", {})
        
        # Nama pengguna (jika ada)
        name = user_data.get("name", "")
        if not name:
            # Ekstrak nama dari email jika tersedia
            email = user_data.get("email", "")
            if email and "@" in email:
                name = email.split("@")[0].replace(".", " ").title()
            else:
                name = "StreamMate User"
        
        self.name_label.setText(name)
        
        # Update field username di tab settings
        if hasattr(self, "username_edit"):
            self.username_edit.setText(name)
        
        # Email
        email = user_data.get("email", "")
        self.email_label.setText(email)
        
        # Update email display di tab settings
        if hasattr(self, "email_display"):
            self.email_display.setText(email)
        
        # Last login
        last_login = user_data.get("last_login", "")
        if last_login:
            try:
                last_login_dt = datetime.fromisoformat(last_login)
                self.last_login_label.setText(f"Last login: {last_login_dt.strftime('%d %b %Y %H:%M')}")
            except:
                self.last_login_label.setText("Last login: N/A")
        else:
            self.last_login_label.setText("Last login: N/A")
        
        # Update informasi penggunaan
        self.update_usage_display()
        
        # Muat riwayat transaksi jika ada
        self.load_transaction_history()
        
        # Muat riwayat penggunaan harian
        self.load_daily_usage()
        
        # Muat statistik penggunaan
        self.load_usage_stats()
        
        # Update kalender
        self.update_calendar_data()
    
    def update_usage_display(self):
        """PERBAIKAN 6: Update tampilan penggunaan dengan fallback yang benar."""
        try:
            # Pastikan semua label sudah terinisialisasi
            if not hasattr(self, 'hours_credit'):
                logger.warning("hours_credit label not initialized")
                return
                
            # Cek data dari subscription_status.json
            subscription_file = Path("config/subscription_status.json")
            sub_data = {}
            has_subscription_file = False
            
            if subscription_file.exists():
                try:
                    with open(subscription_file, "r", encoding="utf-8") as f:
                        sub_data = json.load(f)
                        has_subscription_file = True
                except Exception as e:
                    logger.error(f"Error reading subscription file: {e}")
            
            # Pastikan status paket sesuai pilihan (basic/pro)
            selected_paket = self.cfg.get("paket", "basic").lower()
            
            # Set status paket
            self.paket_info.setText(selected_paket.capitalize())
            self.status_label.setText(f"Status: {selected_paket.capitalize()}")
            
            # Dapatkan informasi kredit
            hours_credit = 0
            hours_used = 0
            today_usage = 0
            
            if has_subscription_file:
                # 🎯 PERBAIKAN: Gunakan real_credit_tracker untuk konsistensi
                try:
                    from modules_server.real_credit_tracker import get_current_credit_balance
                    
                    # Gunakan credit tracker yang sudah handle VPS vs local logic
                    hours_credit = get_current_credit_balance()
                    
                    # Untuk hours_used, ambil dari subscription file
                    hours_used = float(sub_data.get("hours_used", 0))
                    
                    print(f"[PROFILE] Credit tracker balance: {hours_credit:.6f} remaining, {hours_used:.6f} used")
                        
                except Exception as tracker_error:
                    print(f"[PROFILE] Credit tracker failed: {tracker_error}")
                    # Fallback ke subscription file biasa
                    try:
                        hours_credit = float(sub_data.get("hours_credit", 0))
                        hours_used = float(sub_data.get("hours_used", 0))
                        print(f"[PROFILE] Using local subscription data: {hours_credit:.6f} credits")
                    except (ValueError, TypeError):
                        hours_credit = 0
                        hours_used = 0
                
                # Format tanggal kedaluwarsa
                if "expire_date" in sub_data:
                    try:
                        expire_date = datetime.fromisoformat(sub_data["expire_date"])
                        days_left = (expire_date - datetime.now()).days
                        self.expire_label.setText(f"Valid until: {expire_date.strftime('%d %b %Y')} ({days_left} days)")
                    except (ValueError, TypeError):
                        self.expire_label.setText("Expire date: Invalid format")
                
                # Cek pemakaian hari ini
                if "usage_stats" in sub_data:
                    today = datetime.now().date().isoformat()
                    if today in sub_data["usage_stats"]:
                        try:
                            today_usage = float(sub_data["usage_stats"][today])
                        except (ValueError, TypeError):
                            today_usage = 0
                
                self.today_usage.setText(f"{today_usage:.2f} credits")
            
            # PERBAIKAN 7: Fallback ke credit tracker jika tersedia
            elif has_credit_tracker:
                try:
                    usage = credit_tracker.get_daily_usage()
                    hours_credit = usage.get("total_hours", 0) * 60  # Convert jam ke kredit (asumsi 1 jam = 60 kredit)
                    today_usage = usage.get("total_hours", 0) * 60
                    self.today_usage.setText(f"{today_usage:.2f} credits")
                except Exception as e:
                    logger.error(f"Error getting credit tracker data: {e}")
                    today_usage = 0
                    self.today_usage.setText("0 credits")
            
            # Fallback ke validator lisensi jika tidak ada file subscription_status.json
            elif self.license_validator:
                try:
                    license_data = self.license_validator.validate()
                    hours_credit = license_data.get("credit_balance", 0)
                    hours_used = license_data.get("credit_used", 0)
                    
                    # Cek pemakaian hari ini dari validator
                    daily_usage = license_data.get("daily_usage", {})
                    today = datetime.now().date().isoformat()
                    today_usage = daily_usage.get(today, 0)
                    self.today_usage.setText(f"{today_usage:.2f} credits")
                except Exception as e:
                    logger.error(f"Error validating license: {e}")
                    today_usage = 0
                    self.today_usage.setText("0 credits")
            
            # 🎯 SISTEM BARU: Kredit berdasarkan pemakaian, Waktu berdasarkan akses harian
            self.hours_credit.setText(f"{hours_credit:.1f} credits")
            
            # Tampilkan penggunaan waktu aplikasi (bukan kredit)
            try:
                daily_stats = get_daily_usage_stats()
                time_used = daily_stats.get("total_hours_used", 0.0)
                time_remaining = daily_stats.get("remaining_hours", 10.0)
                
                self.hours_used.setText(f"{time_used:.1f}h / 10h daily limit")
                self.hours_remaining.setText(f"{hours_credit:.1f} credits available")
                
                print(f"[PROFILE] Credits: {hours_credit:.1f}, Daily usage: {time_used:.1f}h/10h")
                
            except Exception as e:
                # Fallback jika daily limit manager error
                self.hours_used.setText("0h / 10h daily limit")
                self.hours_remaining.setText(f"{hours_credit:.1f} credits available")
                print(f"[PROFILE] Daily limit manager error: {e}")
                print(f"[PROFILE] Credits: {hours_credit:.1f} (safe mode)")
                
            # Update remaining credit = credit yang tersedia (tanpa dikurangi waktu)
            remaining_credit = hours_credit
            
            # 🎯 UPDATE: Progress bar untuk waktu harian (bukan kredit)
            try:
                daily_stats = get_daily_usage_stats()
                time_used = daily_stats.get("total_hours_used", 0.0)
                time_limit = daily_stats.get("limit_hours", 10.0)
                
                # Progress bar untuk waktu harian
                self.usage_bar.setValue(int(time_used * 100))  # Convert to percentage scale
                self.usage_bar.setMaximum(int(time_limit * 100))
                self.usage_bar.setFormat(f"{time_used:.1f}h / {time_limit:.1f}h daily")
                
                # Warna berdasarkan penggunaan waktu
                percent_used = (time_used / time_limit) * 100 if time_limit > 0 else 0
                
            except Exception as e:
                # Fallback jika error
                percent_used = 0  # Default no time used
                self.usage_bar.setValue(0)
                self.usage_bar.setMaximum(1000)  # 10h * 100 
                self.usage_bar.setFormat("0h / 10h daily")
                
            # Set warna berdasarkan penggunaan waktu harian
            if percent_used > 80:  # More than 80% time used (Red - Warning)
                bar_color = "#ff6b6b"
            elif percent_used > 50:  # More than 50% time used (Yellow - Caution)
                bar_color = "#f9ca24"  
            else:  # Less than 50% time used (Green - Good)
                bar_color = "#6ab04c"
                
            self.usage_bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    text-align: center;
                    background-color: #f5f5f5;
                }}
                QProgressBar::chunk {{
                    background-color: {bar_color};
                    border-radius: 5px;
                }}
            """)
            
            # 🎯 UPDATE: Limit harian yang benar (10 jam akses, bukan kredit)
            self.daily_limit.setText("10 hours daily access limit")
            
            # Setelah update label kredit:
            try:
                # Import get_current_credit_balance function
                from modules_server.real_credit_tracker import get_current_credit_balance
                credit_balance = float(get_current_credit_balance())
                if hasattr(self.parent_window, 'paket') and self.parent_window.paket == "basic":
                    if credit_balance <= 50:
                        from PyQt6.QtWidgets import QMessageBox
                        QMessageBox.warning(self, "Credits Low", "Credits have dropped to 50 or below. You will be returned to the Subscription tab.")
                        self.to_subscription()
            except Exception as e:
                print(f"[AUTO-EXIT BASIC MODE] Error: {e}")
            
        except Exception as e:
            logger.error(f"Error updating usage display: {e}")
            # Fallback ke nilai default jika terjadi error
            self.hours_credit.setText("0 credits")
            self.hours_used.setText("0 credits")
            self.hours_remaining.setText("0 credits")
            self.today_usage.setText("0 credits")
            self.usage_bar.setValue(0)
            self.usage_bar.setMaximum(1)
            self.usage_bar.setFormat("0/0 credits")
    
    def load_transaction_history(self):
        """Muat riwayat transaksi dari log file jika tersedia."""
        try:
            if not hasattr(self, "trans_table"):
                return
                
            # Clear table
            self.trans_table.setRowCount(0)
            
            # Cek file log transaksi
            log_file = Path("logs/payment_transactions.jsonl")
            if not log_file.exists():
                # Coba file lain jika ada
                log_file = Path("logs/ipaymu_transactions.jsonl")
                if not log_file.exists():
                    return
            
            # Baca file log
            transactions = []
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        transactions.append(data)
                    except:
                        continue
            
            # Sort berdasarkan timestamp (terbaru dulu)
            transactions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            # Tampilkan 5 transaksi terakhir
            for i, trans in enumerate(transactions[:5]):
                timestamp = trans.get("timestamp", "")
                package = trans.get("package", "")
                amount = trans.get("amount", 0)
                status = trans.get("status", "")
                
                try:
                    # Format timestamp
                    dt = datetime.fromisoformat(timestamp)
                    timestamp_display = dt.strftime("%d %b %Y %H:%M")
                except:
                    timestamp_display = timestamp
                
                # Tambahkan row baru
                row = self.trans_table.rowCount()
                self.trans_table.insertRow(row)
                
                # Isi data
                self.trans_table.setItem(row, 0, QTableWidgetItem(timestamp_display))
                self.trans_table.setItem(row, 1, QTableWidgetItem(package.capitalize()))
                self.trans_table.setItem(row, 2, QTableWidgetItem(f"Rp {amount:,}"))
                
                # Status dengan warna
                status_item = QTableWidgetItem(status)
                if "success" in status.lower() or "paid" in status.lower():
                    status_item.setForeground(QColor("#4CAF50"))  # Green
                elif "pending" in status.lower():
                    status_item.setForeground(QColor("#FFC107"))  # Yellow
                else:
                    status_item.setForeground(QColor("#F44336"))  # Red
                    
                self.trans_table.setItem(row, 3, status_item)
                
        except Exception as e:
            logger.error(f"Error loading transaction history: {e}")
    
    def load_daily_usage(self):
        """Muat data penggunaan harian dengan fallback yang benar."""
        try:
            if not hasattr(self, "daily_table"):
                return
                
            # Clear table
            self.daily_table.setRowCount(0)
            
            # Dapatkan penggunaan harian
            daily_usage = {}
            
            # PERBAIKAN 8: Cek dari subscription_status.json terlebih dahulu
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists():
                try:
                    with open(subscription_file, "r", encoding="utf-8") as f:
                        sub_data = json.load(f)
                        if "usage_stats" in sub_data:
                            daily_usage = sub_data["usage_stats"]
                except Exception as e:
                    logger.error(f"Error reading subscription file: {e}")
            
            # Fallback ke credit tracker jika tersedia
            if not daily_usage and has_credit_tracker:
                try:
                    # Credit tracker mungkin menggunakan format berbeda
                    usage_file = Path("temp/daily_usage.json")
                    if usage_file.exists():
                        with open(usage_file, "r", encoding="utf-8") as f:
                            usage_data = json.load(f)
                            # Convert format jika perlu
                            daily_usage = {usage_data.get("date", ""): usage_data.get("total_hours", 0) * 60}
                except Exception as e:
                    logger.error(f"Error reading credit tracker data: {e}")
            
            # Fallback ke subscription_checker jika tersedia
            if not daily_usage and has_subscription_checker:
                try:
                    daily_usage = get_usage_history(7)
                except Exception as e:
                    logger.error(f"Error getting usage history: {e}")
            
            # Jika masih kosong, buat data dummy untuk tampilan
            if not daily_usage:
                today = datetime.now().date()
                for i in range(7):
                    day = (today - timedelta(days=i)).isoformat()
                    daily_usage[day] = 0
            
            # Sort berdasarkan tanggal (terbaru dulu)
            sorted_days = sorted(daily_usage.keys(), reverse=True)
            
            # Limit harian berdasarkan paket
            paket = self.cfg.get("paket", "basic").lower()
            daily_limit = 12 if paket == "pro" else 5
            
            # Tampilkan 7 hari terakhir
            for i, day in enumerate(sorted_days[:7]):
                usage = daily_usage.get(day, 0)
                
                try:
                    # Format tanggal
                    dt = datetime.fromisoformat(day)
                    date_display = dt.strftime("%d %b %Y")
                except:
                    date_display = day
                
                # Persentase dari limit
                percent = min(100, int((usage / daily_limit) * 100)) if daily_limit > 0 else 0
                
                # Tambahkan row baru
                row = self.daily_table.rowCount()
                self.daily_table.insertRow(row)
                
                # Isi data
                self.daily_table.setItem(row, 0, QTableWidgetItem(date_display))
                self.daily_table.setItem(row, 1, QTableWidgetItem(f"{usage:.2f} credits"))
                
                # Persentase dengan warna
                percent_item = QTableWidgetItem(f"{percent}%")
                if percent > 80:
                    percent_item.setForeground(QColor("#F44336"))  # Red
                elif percent > 50:
                    percent_item.setForeground(QColor("#FFC107"))  # Yellow
                else:
                    percent_item.setForeground(QColor("#4CAF50"))  # Green
                    
                self.daily_table.setItem(row, 2, percent_item)
                
        except Exception as e:
            logger.error(f"Error loading daily usage: {e}")
    
    def load_usage_stats(self):
        """Muat statistik penggunaan fitur dengan fallback."""
        try:
            if not hasattr(self, "stats_table"):
                return
            
            # Initialize counters
            translate_count = 0
            reply_count = 0
            live_count = 0
            talk_count = 0
            
            # PERBAIKAN 9: Coba baca dari credit tracker terlebih dahulu
            if has_credit_tracker:
                try:
                    usage = credit_tracker.get_daily_usage()
                    components = usage.get("components", {})
                    
                    # Map credit tracker components ke stats
                    translate_count = components.get("translate_words", 0)
                    reply_count = components.get("ai_requests", 0)
                    talk_count = components.get("stt_seconds", 0) // 10  # Estimasi dari detik STT
                    live_count = reply_count  # Live streaming = AI replies
                    
                except Exception as e:
                    logger.error(f"Error reading credit tracker stats: {e}")
            
            # Fallback ke file log tradisional
            if translate_count == 0:
                translate_log = Path("temp/translate_log.txt")
                if translate_log.exists():
                    try:
                        translate_count = len(translate_log.read_text(encoding="utf-8").splitlines())
                    except:
                        pass
            
            if reply_count == 0:
                reply_log = Path("temp/cohost_log.txt")
                if reply_log.exists():
                    try:
                        reply_count = len(reply_log.read_text(encoding="utf-8").splitlines())
                    except:
                        pass
            
            # Live count fallback
            if live_count == 0:
                live_count = reply_count
            
            # Talk count fallback
            if talk_count == 0:
                talk_count = translate_count // 2
            
            # Total
            total_count = translate_count + reply_count + talk_count
            
            # Update tabel
            self.stats_table.setItem(0, 1, QTableWidgetItem(str(translate_count)))
            self.stats_table.setItem(1, 1, QTableWidgetItem(str(reply_count)))
            self.stats_table.setItem(2, 1, QTableWidgetItem(str(live_count)))
            self.stats_table.setItem(3, 1, QTableWidgetItem(str(talk_count)))
            self.stats_table.setItem(4, 1, QTableWidgetItem(str(total_count)))
            
        except Exception as e:
            logger.error(f"Error loading usage stats: {e}")
    
    def update_calendar_data(self):
        """Update data kalender penggunaan dengan fallback."""
        try:
            if not hasattr(self, "calendar"):
                return
                
            # Dapatkan penggunaan harian
            daily_usage = {}
            
            # Cek dari subscription_status.json
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists():
                try:
                    with open(subscription_file, "r", encoding="utf-8") as f:
                        sub_data = json.load(f)
                        if "usage_stats" in sub_data:
                            daily_usage = sub_data["usage_stats"]
                except Exception as e:
                    logger.error(f"Error reading subscription file: {e}")
            
            # Fallback ke subscription_checker jika tersedia
            if not daily_usage and has_subscription_checker:
                try:
                    daily_usage = get_usage_history(30)  # 30 hari terakhir
                except Exception as e:
                    logger.error(f"Error getting usage history: {e}")
            
            # Set warna untuk tanggal dengan aktivitas
            from PyQt6.QtGui import QTextCharFormat
            
            # Reset format
            self.calendar.setDateTextFormat(QDate(), QTextCharFormat())
            
            # Limit harian
            paket = self.cfg.get("paket", "basic").lower()
            daily_limit = 12 if paket == "pro" else 5
            
            # Set format untuk setiap tanggal dengan aktivitas
            for day_str, usage in daily_usage.items():
                try:
                    dt = datetime.fromisoformat(day_str)
                    date = QDate(dt.year, dt.month, dt.day)
                    
                    # Format sesuai tingkat penggunaan
                    fmt = QTextCharFormat()
                    
                    if usage == 0:
                        continue  # Skip hari tanpa aktivitas
                    elif usage > daily_limit:
                        fmt.setBackground(QColor(255, 102, 102, 100))  # Red (over limit)
                    elif usage > daily_limit * 0.8:
                        fmt.setBackground(QColor(255, 204, 102, 100))  # Orange (near limit)
                    elif usage > daily_limit * 0.5:
                        fmt.setBackground(QColor(255, 255, 102, 100))  # Yellow (moderate)
                    else:
                        fmt.setBackground(QColor(102, 255, 102, 100))  # Green (low usage)
                    
                    self.calendar.setDateTextFormat(date, fmt)
                    
                except Exception as e:
                    logger.error(f"Error formatting calendar date {day_str}: {e}")
            
        except Exception as e:
            logger.error(f"Error updating calendar data: {e}")
    
    def show_day_usage(self, date):
        """Tampilkan penggunaan untuk tanggal tertentu."""
        try:
            # Konversi QDate ke string format ISO
            day_str = f"{date.year()}-{date.month():02d}-{date.day():02d}"
            
            # Cari penggunaan untuk tanggal ini
            usage = 0
            
            # Cek dari subscription_status.json
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists():
                try:
                    with open(subscription_file, "r", encoding="utf-8") as f:
                        sub_data = json.load(f)
                        if "usage_stats" in sub_data and day_str in sub_data["usage_stats"]:
                            usage = sub_data["usage_stats"][day_str]
                except Exception as e:
                    logger.error(f"Error reading subscription file: {e}")
            
            # Fallback ke subscription_checker jika tersedia
            if usage == 0 and has_subscription_checker:
                try:
                    daily_usage = get_usage_history(30)  # 30 hari terakhir
                    if day_str in daily_usage:
                        usage = daily_usage[day_str]
                except Exception as e:
                    logger.error(f"Error getting usage history: {e}")
            
            # Limit harian
            paket = self.cfg.get("paket", "basic").lower()
            daily_limit = 12 if paket == "pro" else 5
            
            # Persentase dari limit
            percent = min(100, int((usage / daily_limit) * 100)) if daily_limit > 0 else 0
            
            # Tampilkan info
            if usage > 0:
                self.day_usage_label.setText(
                    f"Date {date.toString('dd MMM yyyy')}: {usage:.2f} credits ({percent}% of daily limit)"
                )
                
                # Set warna teks sesuai tingkat penggunaan
                if percent > 80:
                    self.day_usage_label.setStyleSheet("font-size: 12px; color: #F44336; background-color: #f8f9fa; padding: 8px; border-radius: 5px;")
                elif percent > 50:
                    self.day_usage_label.setStyleSheet("font-size: 12px; color: #FFC107; background-color: #f8f9fa; padding: 8px; border-radius: 5px;")
                else:
                    self.day_usage_label.setStyleSheet("font-size: 12px; color: #4CAF50; background-color: #f8f9fa; padding: 8px; border-radius: 5px;")
            else:
                self.day_usage_label.setText(f"Date {date.toString('dd MMM yyyy')}: No usage")
                self.day_usage_label.setStyleSheet("font-size: 12px; color: #666; background-color: #f8f9fa; padding: 8px; border-radius: 5px;")
            
        except Exception as e:
            logger.error(f"Error showing day usage: {e}")
            self.day_usage_label.setText(f"Error: {str(e)}")
    
    def toggle_auto_refresh(self, checked):
        """Toggle auto refresh timer."""
        if checked:
            self.refresh_timer.start()
        else:
            self.refresh_timer.stop()
    
    def change_avatar(self):
        """Ubah avatar pengguna dengan opsi crop."""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "Select Avatar", "", "Images (*.png *.jpg *.jpeg)"
        )
        
        if file_path:
            try:
                # Pastikan folder assets ada
                assets_dir = Path("assets")
                assets_dir.mkdir(exist_ok=True)
                
                # Baca gambar dan resize dengan crop proporsional
                img = QImage(file_path)
                
                # Crop ke persegi
                size = min(img.width(), img.height())
                x = (img.width() - size) // 2
                y = (img.height() - size) // 2
                img = img.copy(x, y, size, size)
                
                # Resize ke 240x240
                img = img.scaled(240, 240, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                
                # Simpan sebagai avatar
                avatar_path = assets_dir / "user_avatar.png"
                img.save(str(avatar_path))
                
                # Update tampilan
                self.avatar_frame.setPixmap(QPixmap.fromImage(img))
                
                QMessageBox.information(self, "Avatar Updated", "Avatar updated successfully!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save avatar: {str(e)}")
    
    def buy_credits(self, hours):
        """Handle pembelian kredit"""
        reply = QMessageBox.question(
            self,
            "Purchase Confirmation",
            f"<b>Buy {hours} Credits?</b><br><br>"
            f"Price: Rp {hours * 1000:,}<br><br>"
            "Continue with purchase?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Navigate to subscription tab for purchase
            self.to_subscription()
    
    def to_subscription(self):
        """Navigasi ke tab Subscription dengan debugging dan fallback yang lebih baik"""
        from PyQt6.QtWidgets import QMessageBox
        import logging
        import traceback
        from ui.subscription_tab import SubscriptionTab # Import here to ensure it's available

        logger = logging.getLogger(__name__)

        if not self.parent_window:
            QMessageBox.information(
                self, "Navigation", 
                "Parent window not found. Please open Subscription tab manually."
            )
            return
            
        try:
            logger.info("Attempting to navigate to subscription tab")
            
            # METODE 1: Main tabs (TabWidget) - yang paling umum
            if hasattr(self.parent_window, 'main_tabs') and self.parent_window.main_tabs:
                logger.info("Found main_tabs, searching for existing subscription tab")
                
                # Cari tab subscription yang sudah ada
                for i in range(self.parent_window.main_tabs.count()):
                    tab_text = self.parent_window.main_tabs.tabText(i)
                    logger.info(f"Checking tab {i}: '{tab_text}'")
                    
                    if "subscription" in tab_text.lower() or "langganan" in tab_text.lower():
                        logger.info(f"Found existing subscription tab at index {i}")
                        self.parent_window.main_tabs.setCurrentIndex(i)
                        return
                
                # Jika tidak ada, buat subscription tab baru
                logger.info("No existing subscription tab found, creating new one")
                try:
                    self.parent_window.subscription_tab = SubscriptionTab(self.parent_window)
                    tab_index = self.parent_window.main_tabs.addTab(
                        self.parent_window.subscription_tab, 
                        "💰 Subscription"
                    )
                    self.parent_window.main_tabs.setCurrentIndex(tab_index)
                    logger.info(f"Created new subscription tab at index {tab_index}")
                    return
                    
                except Exception as e:
                    logger.error(f"Failed to create subscription tab: {e}")
                    
            # METODE 2: Stack widget
            elif hasattr(self.parent_window, 'stack') and self.parent_window.stack:
                logger.info("Found stack widget, attempting to show subscription tab")
                
                # Cek apakah subscription tab sudah ada
                if not hasattr(self.parent_window, 'subscription_tab') or self.parent_window.subscription_tab is None:
                    logger.info("Creating subscription tab for stack widget")
                    self.parent_window.subscription_tab = SubscriptionTab(self.parent_window)
                    self.parent_window.stack.addWidget(self.parent_window.subscription_tab)
                    
                self.parent_window.stack.setCurrentWidget(self.parent_window.subscription_tab)
                logger.info("Switched to subscription tab in stack widget")
                return
                
            # METODE 3: Direct method call (untuk developer mode)
            elif hasattr(self.parent_window, 'show_subscription_tab'):
                logger.info("Using direct method call")
                self.parent_window.show_subscription_tab()
                return
                
            # METODE 4: Signal emission sebagai fallback
            elif hasattr(self.parent_window, 'switch_to_subscription'):
                logger.info("Using signal emission")
                self.parent_window.switch_to_subscription()
                return
                
            # Jika semua metode gagal
            logger.warning("All navigation methods failed")
            QMessageBox.information(
                self, "Navigation", 
                "Could not find Subscription tab.\n"
                "Please open manually or restart application."
            )
            
        except Exception as e:
            logger.error(f"Error in to_subscription: {e}")
            traceback.print_exc()
            
            QMessageBox.warning(
                self, "Error", 
                f"Failed to open Subscription tab:\n{str(e)}\n\n"
                "Please restart application if problem persists."
            )
    
    def to_tutorial(self):
        """Navigasi ke tab Tutorial."""
        if self.parent_window:
            if hasattr(self.parent_window, 'main_tabs'):
                for i in range(self.parent_window.main_tabs.count()):
                    if "Tutorial" in self.parent_window.main_tabs.tabText(i):
                        self.parent_window.main_tabs.setCurrentIndex(i)
                        return
    
    def reload_profile(self):
        """Muat ulang data profil dengan force VPS sync."""
        try:
            # ✅ PERBAIKAN UTAMA: Force VPS sync sebelum reload data
            if self.parent_window and hasattr(self.parent_window, 'license_validator'):
                try:
                    print("[PROFILE] Force syncing from VPS server...")
                    license_data = self.parent_window.license_validator.validate(force_refresh=True)
                    print(f"[PROFILE] VPS sync result: {license_data}")
                except Exception as e:
                    print(f"[PROFILE] VPS sync error: {e}")
            
            # Load data profile setelah sync
            self.load_profile_data()
            
            QMessageBox.information(self, "Refresh", "Profile data refreshed from VPS server!")
            
        except Exception as e:
            logger.error(f"Error reloading profile: {e}")
            # Fallback ke reload normal tanpa VPS sync
            self.load_profile_data()
            QMessageBox.warning(self, "Refresh", f"Profile refreshed (VPS sync failed: {str(e)})")
    
    def edit_profile(self):
        """Edit profil dengan validasi."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Profile")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        # Form layout
        form = QFormLayout()
        
        # Name field
        name_edit = QLineEdit(self.name_label.text())
        name_edit.setPlaceholderText("Enter name")
        form.addRow("Name:", name_edit)
        
        # Email field (readonly)
        email_edit = QLineEdit(self.email_label.text())
        email_edit.setReadOnly(True)
        email_edit.setStyleSheet("background-color: #f0f0f0;")
        form.addRow("Email:", email_edit)
        
        layout.addLayout(form)
        
        # Buttons
        buttons = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #1877F2;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #166FE5;
            }
        """)
        save_btn.clicked.connect(lambda: self._save_profile(name_edit.text(), dialog))
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #e4e6eb;
                color: #050505;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #d8dadf;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        
        layout.addLayout(buttons)
        
        dialog.exec()
    
    def _save_profile(self, name, dialog):
        """Simpan perubahan profil."""
        # Update data user
        user_data = self.cfg.get("user_data", {})
        user_data["name"] = name
        
        # Simpan ke konfigurasi
        self.cfg.set("user_data", user_data)
        
        # Update tampilan
        self.name_label.setText(name)
        
        # Update field di tab settings
        if hasattr(self, "username_edit"):
            self.username_edit.setText(name)
        
        # Tutup dialog
        dialog.accept()
        
        QMessageBox.information(self, "Profile Updated", "Profile updated successfully!")
    
    def save_username(self):
        """Simpan username dari tab pengaturan."""
        name = self.username_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Name cannot be empty!")
            return
        
        # Update data user
        user_data = self.cfg.get("user_data", {})
        user_data["name"] = name
        
        # Simpan ke konfigurasi
        self.cfg.set("user_data", user_data)
        
        # Update tampilan
        self.name_label.setText(name)
        
        QMessageBox.information(self, "Profile Updated", "Username updated successfully!")
    
    def save_settings(self):
        """Simpan pengaturan dari tab settings."""
        # Simpan pengaturan notifikasi
        settings = {
            "notifications": {
                "credit_low": self.notif_kredit.isChecked(),
                "new_login": self.notif_login.isChecked(),
                "app_update": self.notif_update.isChecked()
            }
        }
        
        # Simpan ke konfigurasi
        self.cfg.set("profile_settings", settings)
        
        QMessageBox.information(self, "Settings Saved", "Profile settings saved successfully!")
    
    def export_profile_data(self):
        """Export data profil ke file JSON."""
        try:
            # Get current profile data
            profile_data = {
                "user_info": {
                    "name": self.name_label.text(),
                    "email": self.email_label.text(),
                    "status": self.status_label.text(),
                    "last_login": self.last_login_label.text()
                },
                "credit_info": {
                    "hours_credit": self.hours_credit.text(),
                    "hours_used": self.hours_used.text(),
                    "hours_remaining": self.hours_remaining.text(),
                    "today_usage": self.today_usage.text(),
                    "daily_limit": self.daily_limit.text()
                },
                "export_date": datetime.now().isoformat()
            }
            
            # Get file path from user
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Profile Data",
                f"streammate_profile_{datetime.now().strftime('%Y%m%d')}.json",
                "JSON Files (*.json)"
            )
            
            if file_path:
                # Save to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(profile_data, f, indent=4)
                    
                QMessageBox.information(
                    self,
                    "Export Success",
                    f"Profile data exported successfully to:\n{file_path}"
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export profile data:\n{str(e)}"
            )

    def check_for_updates(self):
        """Cek update aplikasi secara manual."""
        try:
            # Import update manager
            from modules_client.update_manager import get_update_manager
            from ui.update_dialog import UpdateDialog
            
            update_manager = get_update_manager()
            
            # Check updates secara manual
            update_manager.check_for_updates(manual=True)
            
            # Connect signal untuk handle hasil check
            def handle_update_available(update_info):
                # Disconnect untuk avoid multiple connections
                update_manager.update_available.disconnect(handle_update_available)
                
                # Show update dialog
                update_dialog = UpdateDialog(update_manager, self)
                update_dialog.set_update_info(update_info)
                update_dialog.exec()
            
            def handle_update_error(error_msg):
                # Disconnect untuk avoid multiple connections  
                update_manager.update_error.disconnect(handle_update_error)
                
                QMessageBox.warning(
                    self, "Update Error",
                    f"Failed to check for updates:\n\n{error_msg}"
                )
            
            # Connect signals
            update_manager.update_available.connect(handle_update_available)
            update_manager.update_error.connect(handle_update_error)
            
        except ImportError:
            QMessageBox.information(
                self, "Update Check",
                "Update system not available.\n\n"
                "Please download latest version from official website."
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Error",
                f"Failed to check for updates: {e}"
            )

    def logout(self):
        """Logout dari aplikasi."""
        if self.parent_window and hasattr(self.parent_window, 'logout'):
            self.parent_window.logout()
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Logout", "Please logout from the main application menu.")

    def analyze_engagement(self):
        """Menganalisis data dari log untuk memberikan insight."""
        # Path ke file log
        reply_log = get_app_data_path("cohost_log.txt")
        viewer_memory_file = get_app_data_path("viewer_memory.json")

        total_replies = 0
        author_counts = {}