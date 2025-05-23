# ui/profile_tab.py
import os
import json
import requests
import sys
import time
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
try:
    from modules_client.config_manager import ConfigManager
except ImportError:
    from modules_server.config_manager import ConfigManager

# Impor validator lisensi jika ada
try:
    from modules_client.license_validator import LicenseValidator
    has_license_validator = True
except ImportError:
    has_license_validator = False
    
# Impor subscription checker untuk melihat detail penggunaan
try:
    from modules_client.subscription_checker import get_today_usage, get_usage_history
    has_subscription_checker = True
except ImportError:
    has_subscription_checker = False

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
        
        # Timer untuk auto refresh
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(15000)  # Refresh tiap 15 detik
        self.refresh_timer.timeout.connect(self.update_usage_display)
        
        # Setup UI
        self.init_ui()
        
        # Muat data
        self.load_profile_data()
        
        # Mulai timer refresh
        self.refresh_timer.start()
    
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
        
        self.name_label = QLabel("Nama Pengguna")
        self.name_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #1877F2;")
        user_info.addWidget(self.name_label)
        
        self.email_label = QLabel("email@example.com")
        self.email_label.setStyleSheet("font-size: 16px; color: #666;")
        user_info.addWidget(self.email_label)
        
        self.status_label = QLabel("Status: Basic")
        self.status_label.setStyleSheet("font-size: 16px; color: #1a73e8; font-weight: bold;")
        user_info.addWidget(self.status_label)
        
        # Label untuk last login
        self.last_login_label = QLabel("Login terakhir: -")
        self.last_login_label.setStyleSheet("font-size: 13px; color: #888;")
        user_info.addWidget(self.last_login_label)
        
        # Row untuk tombol avatar dan edit
        buttons_row = QHBoxLayout()
        
        # Tombol ubah avatar
        avatar_btn = QPushButton("🖼️ Ubah Avatar")
        avatar_btn.setStyleSheet("padding: 8px; background-color: #e4e6eb; color: #050505; border-radius: 6px; border: none;")
        avatar_btn.clicked.connect(self.change_avatar)
        buttons_row.addWidget(avatar_btn)
        
        # Tombol edit profil
        edit_btn = QPushButton("✏️ Edit Profil")
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
        
        # Tab 1: Kredit Jam
        credit_tab = QWidget()
        self.setup_credit_tab(credit_tab)
        tabs.addTab(credit_tab, "💰 Kredit Jam")
        
        # Tab 2: Statistik Penggunaan
        stats_tab = QWidget()
        self.setup_stats_tab(stats_tab)
        tabs.addTab(stats_tab, "📊 Statistik")
        
        # Tab 3: Riwayat Aktivitas
        history_tab = QWidget()
        self.setup_history_tab(history_tab)
        tabs.addTab(history_tab, "📜 Riwayat")
        
        # Tab 4: Pengaturan
        settings_tab = QWidget()
        self.setup_settings_tab(settings_tab)
        tabs.addTab(settings_tab, "⚙️ Pengaturan")
        
        content_layout.addWidget(tabs)
        
        # Bagian Navigasi Ke Tab Lain
        navigation_group = QGroupBox("🧭 Navigasi")
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
        """Setup tab informasi kredit dan status paket dengan detail."""
        layout = QVBoxLayout(tab)
        
        # Status dan Detail Paket
        status_group = QGroupBox("🎫 Status Paket")
        status_layout = QFormLayout()
        
        self.paket_info = QLabel("Basic")
        self.paket_info.setStyleSheet("font-weight: bold; color: #1877F2;")
        status_layout.addRow("Paket Aktif:", self.paket_info)
        
        self.expire_label = QLabel("Tidak ada informasi")
        status_layout.addRow("Masa Berlaku:", self.expire_label)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Detail Kredit Jam
        credit_group = QGroupBox("⏱️ Detail Kredit Jam")
        credit_layout = QVBoxLayout()
        
        # Progress bar kredit yang lebih menarik
        usage_layout = QVBoxLayout()
        usage_layout.setSpacing(5)
        
        usage_label = QLabel("Sisa Kredit Jam:")
        usage_label.setStyleSheet("font-weight: bold;")
        usage_layout.addWidget(usage_label)
        
        self.usage_bar = QProgressBar()
        self.usage_bar.setRange(0, 100)
        self.usage_bar.setValue(50)
        self.usage_bar.setTextVisible(True)
        self.usage_bar.setFormat("%v/%m jam")
        self.usage_bar.setMinimumHeight(25)
        self.usage_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
                background-color: #f5f5f5;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 5px;
            }
        """)
        usage_layout.addWidget(self.usage_bar)
        
        # Statistik detail
        credit_details = QFormLayout()
        credit_details.setVerticalSpacing(8)
        
        self.hours_credit = QLabel("0 jam")
        self.hours_credit.setStyleSheet("font-weight: bold;")
        credit_details.addRow("Total Kredit:", self.hours_credit)
        
        self.hours_used = QLabel("0 jam")
        credit_details.addRow("Jam Terpakai:", self.hours_used)
        
        self.hours_remaining = QLabel("0 jam")
        self.hours_remaining.setStyleSheet("font-weight: bold; color: #4CAF50;")
        credit_details.addRow("Sisa Jam:", self.hours_remaining)
        
        self.today_usage = QLabel("0 jam")
        credit_details.addRow("Pemakaian Hari Ini:", self.today_usage)
        
        self.daily_limit = QLabel("5 jam/hari")
        credit_details.addRow("Limit Harian:", self.daily_limit)
        
        # Tambahkan estimasi
        self.estimate_label = QLabel("~ hari")
        self.estimate_label.setStyleSheet("font-style: italic; color: #666;")
        credit_details.addRow("Estimasi Habis:", self.estimate_label)
        
        credit_layout.addLayout(usage_layout)
        credit_layout.addLayout(credit_details)
        
        credit_group.setLayout(credit_layout)
        layout.addWidget(credit_group)
        
        # Beli kredit
        recharge_group = QGroupBox("💳 Isi Ulang Kredit")
        recharge_layout = QHBoxLayout()
        
        buy_btn = QPushButton("💰 Beli Kredit 100 Jam")
        buy_btn.setStyleSheet(
            "font-size: 14px; padding: 10px; "
            "background-color: #4CAF50; color: white; "
            "border-radius: 8px; border: none; font-weight: bold;"
        )
        buy_btn.clicked.connect(lambda: self.buy_credit(100))
        recharge_layout.addWidget(buy_btn)
        
        buy_bonus_btn = QPushButton("🎁 Beli 200 Jam (Bonus)")
        buy_bonus_btn.setStyleSheet(
            "font-size: 14px; padding: 10px; "
            "background-color: #FF9800; color: white; "
            "border-radius: 8px; border: none; font-weight: bold;"
        )
        buy_bonus_btn.clicked.connect(lambda: self.buy_credit(200))
        recharge_layout.addWidget(buy_bonus_btn)
        
        recharge_group.setLayout(recharge_layout)
        layout.addWidget(recharge_group)
        
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
        """Setup tab statistik penggunaan."""
        layout = QVBoxLayout(tab)
        
        # ========== Statistik Penggunaan Fitur ==========
        feature_group = QGroupBox("📊 Statistik Penggunaan Fitur")
        feature_layout = QVBoxLayout()
        
        # Tabel statistik
        self.stats_table = QTableWidget(5, 2)
        self.stats_table.setHorizontalHeaderLabels(["Fitur", "Jumlah"])
        self.stats_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.stats_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.setStyleSheet("""
            QTableWidget {
                alternate-background-color: #f5f5f5;
                gridline-color: #ddd;
            }
            QHeaderView::section {
                background-color: #1877F2;
                color: white;
                padding: 5px;
                font-weight: bold;
            }
        """)
        
        # Setup baris tabel dengan placeholder
        features = ["Terjemahan Suara", "Balasan Chat", "Live Streaming", "Hold-to-Talk", "Total"]
        for i, feature in enumerate(features):
            self.stats_table.setItem(i, 0, QTableWidgetItem(feature))
            self.stats_table.setItem(i, 1, QTableWidgetItem("0"))
        
        feature_layout.addWidget(self.stats_table)
        feature_group.setLayout(feature_layout)
        layout.addWidget(feature_group)
        
        # ========== Penggunaan Per Hari ==========
        usage_group = QGroupBox("📅 Penggunaan Per Hari (7 Hari Terakhir)")
        usage_layout = QVBoxLayout()
        
        # Tabel statistik penggunaan per hari
        self.daily_table = QTableWidget(7, 3)
        self.daily_table.setHorizontalHeaderLabels(["Tanggal", "Jam Digunakan", "% dari Limit"])
        self.daily_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.daily_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.daily_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.daily_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.daily_table.setAlternatingRowColors(True)
        self.daily_table.setStyleSheet("""
            QTableWidget {
                alternate-background-color: #f5f5f5;
                gridline-color: #ddd;
            }
            QHeaderView::section {
                background-color: #1877F2;
                color: white;
                padding: 5px;
                font-weight: bold;
            }
        """)
        
        usage_layout.addWidget(self.daily_table)
        usage_group.setLayout(usage_layout)
        layout.addWidget(usage_group)
        
        # Catatan penjelasan
        note = QLabel(
            "📝 <b>Catatan:</b> Statistik penggunaan diperbarui setiap 15 detik. "
            "Limit harian bervariasi sesuai paket Anda."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #666; font-size: 12px; margin-top: 10px; background-color: #f8f9fa; padding: 8px; border-radius: 5px;")
        layout.addWidget(note)
        
        layout.addStretch()
    
    def setup_history_tab(self, tab):
        """Setup tab riwayat aktivitas."""
        layout = QVBoxLayout(tab)
        
        # Riwayat login
        login_group = QGroupBox("🔐 Riwayat Login")
        login_layout = QVBoxLayout()
        
        self.login_table = QTableWidget(5, 2)
        self.login_table.setHorizontalHeaderLabels(["Waktu", "Status"])
        self.login_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.login_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.login_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.login_table.setAlternatingRowColors(True)
        
        login_layout.addWidget(self.login_table)
        login_group.setLayout(login_layout)
        layout.addWidget(login_group)
        
        # Riwayat transaksi/pembelian
        trans_group = QGroupBox("💲 Riwayat Transaksi")
        trans_layout = QVBoxLayout()
        
        self.trans_table = QTableWidget(5, 4)
        self.trans_table.setHorizontalHeaderLabels(["Tanggal", "Paket", "Jumlah", "Status"])
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
        calendar_group = QGroupBox("📆 Kalender Penggunaan")
        calendar_layout = QVBoxLayout()
        
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.clicked.connect(self.show_day_usage)
        
        calendar_layout.addWidget(self.calendar)
        
        # Label untuk menampilkan penggunaan per hari
        self.day_usage_label = QLabel("Pilih tanggal untuk melihat detail penggunaan")
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
        profile_group = QGroupBox("👤 Pengaturan Profil")
        profile_layout = QFormLayout()
        
        # Nama pengguna (edit)
        name_layout = QHBoxLayout()
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Nama Pengguna")
        name_layout.addWidget(self.username_edit)
        
        save_name_btn = QPushButton("💾 Simpan")
        save_name_btn.clicked.connect(self.save_username)
        save_name_btn.setMaximumWidth(100)
        name_layout.addWidget(save_name_btn)
        
        profile_layout.addRow("Nama Pengguna:", name_layout)
        
        # Email (read-only)
        self.email_display = QLineEdit()
        self.email_display.setReadOnly(True)
        self.email_display.setStyleSheet("background-color: #f5f5f5;")
        profile_layout.addRow("Email:", self.email_display)
        
        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)
        
        # Opsi notifikasi
        notif_group = QGroupBox("🔔 Opsi Notifikasi")
        notif_layout = QVBoxLayout()
        
        self.notif_kredit = QCheckBox("Notifikasi saat kredit rendah (< 10 jam)")
        self.notif_kredit.setChecked(True)
        notif_layout.addWidget(self.notif_kredit)
        
        self.notif_login = QCheckBox("Notifikasi login dari perangkat baru")
        self.notif_login.setChecked(True)
        notif_layout.addWidget(self.notif_login)
        
        self.notif_update = QCheckBox("Notifikasi saat ada update aplikasi")
        self.notif_update.setChecked(True)
        notif_layout.addWidget(self.notif_update)
        
        notif_group.setLayout(notif_layout)
        layout.addWidget(notif_group)
        
        # Tombol untuk verifikasi identitas
        verify_btn = QPushButton("🔐 Verifikasi Identitas")
        verify_btn.setStyleSheet(
            "font-size: 14px; padding: 10px; "
            "background-color: #1877F2; color: white; "
            "border-radius: 8px; border: none; font-weight: bold;"
        )
        verify_btn.clicked.connect(self.verify_identity)
        layout.addWidget(verify_btn)
        
        # Tombol Export Data
        export_btn = QPushButton("📤 Export Data Profil")
        export_btn.setStyleSheet(
            "font-size: 14px; padding: 10px; "
            "background-color: #1877F2; color: white; "
            "border-radius: 8px; border: none; font-weight: bold;"
        )
        export_btn.clicked.connect(self.export_profile_data)
        layout.addWidget(export_btn)

        # Tambahkan setelah tombol Export Data
        check_update_btn = QPushButton("🔄 Check for Updates")
        check_update_btn.setStyleSheet(
            "font-size: 14px; padding: 10px; "
            "background-color: #17a2b8; color: white; "
            "border-radius: 8px; border: none; font-weight: bold;"
        )
        check_update_btn.clicked.connect(self.check_for_updates)
        layout.addWidget(check_update_btn)
        
        # Simpan pengaturan
        save_settings_btn = QPushButton("💾 Simpan Pengaturan")
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
                name = "Pengguna StreamMate"
        
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
                self.last_login_label.setText(f"Login terakhir: {last_login_dt.strftime('%d %b %Y %H:%M')}")
            except:
                self.last_login_label.setText("Login terakhir: N/A")
        else:
            self.last_login_label.setText("Login terakhir: N/A")
        
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
        """Update tampilan penggunaan dan status kredit jam secara real-time dan detail."""
        try:
            # Cek jika data abis dari subscription_status.json
            subscription_file = Path("config/subscription_status.json")
            sub_data = {}
            has_subscription_file = False
            
            if subscription_file.exists():
                try:
                    with open(subscription_file, "r", encoding="utf-8") as f:
                        sub_data = json.load(f)
                        has_subscription_file = True
                except Exception as e:
                    print(f"Error reading subscription file: {e}")
            
            # Pastikan status paket sesuai pilihan (basic/pro)
            selected_paket = self.cfg.get("paket", "basic").lower()
            
            # Set status paket
            self.paket_info.setText(selected_paket.capitalize())
            self.status_label.setText(f"Status: {selected_paket.capitalize()}")
            
            # Dapatkan informasi kredit
            hours_credit = 0
            hours_used = 0
            expire_date = None
            
            if has_subscription_file:
                # Ambil kredit dari subscription_status.json (sumber paling akurat)
                status = sub_data.get("status", "")
                
                # PERBAIKAN: Pastikan nilai numerik dibaca dengan benar
                try:
                    hours_credit = float(sub_data.get("hours_credit", 0))
                    hours_used = float(sub_data.get("hours_used", 0))
                except (ValueError, TypeError):
                    hours_credit = 0
                    hours_used = 0
                
                # Format tanggal kedaluwarsa
                if "expire_date" in sub_data:
                    try:
                        expire_date = datetime.fromisoformat(sub_data["expire_date"])
                        days_left = (expire_date - datetime.now()).days
                        self.expire_label.setText(f"Berlaku hingga: {expire_date.strftime('%d %b %Y')} ({days_left} hari)")
                    except (ValueError, TypeError):
                        self.expire_label.setText("Expire date: Format tidak valid")
                
                # PERBAIKAN: Cek pemakaian hari ini
                today_usage = 0
                if "usage_stats" in sub_data:
                    today = datetime.now().date().isoformat()
                    if today in sub_data["usage_stats"]:
                        try:
                            today_usage = float(sub_data["usage_stats"][today])
                        except (ValueError, TypeError):
                            today_usage = 0
                
                self.today_usage.setText(f"{today_usage:.2f} jam")
            
            # Fallback ke validator lisensi jika tidak ada file subscription_status.json
            elif self.license_validator:
                license_data = self.license_validator.validate()
                hours_credit = license_data.get("hours_credit", 0)
                hours_used = license_data.get("hours_used", 0)
                
                # Cek pemakaian hari ini dari validator
                today_usage = 0
                daily_usage = license_data.get("daily_usage", {})
                today = datetime.now().date().isoformat()
                today_usage = daily_usage.get(today, 0)
                self.today_usage.setText(f"{today_usage:.2f} jam")
            
            # Update informasi jam kredit
            self.hours_credit.setText(f"{hours_credit:.2f} jam")
            self.hours_used.setText(f"{hours_used:.2f} jam")
            self.hours_remaining.setText(f"{hours_credit:.2f} jam")
            
            # Update progress bar
            total_hours = hours_credit + hours_used
            if total_hours > 0:
                percent_used = int((hours_used / total_hours) * 100)
                self.usage_bar.setValue(int(hours_used))
                self.usage_bar.setMaximum(int(total_hours))
                self.usage_bar.setFormat(f"{hours_credit:.1f}/{total_hours:.1f} jam")
                
                # Set warna berdasarkan penggunaan
                if percent_used > 80:
                    self.usage_bar.setStyleSheet("""
                        QProgressBar {
                            border: 1px solid #ccc;
                            border-radius: 5px;
                            text-align: center;
                            background-color: #f5f5f5;
                        }
                        QProgressBar::chunk {
                            background-color: #ff6b6b;
                            border-radius: 5px;
                        }
                    """)
                elif percent_used > 50:
                    self.usage_bar.setStyleSheet("""
                        QProgressBar {
                            border: 1px solid #ccc;
                            border-radius: 5px;
                            text-align: center;
                            background-color: #f5f5f5;
                        }
                        QProgressBar::chunk {
                            background-color: #f9ca24;
                            border-radius: 5px;
                        }
                    """)
                else:
                    self.usage_bar.setStyleSheet("""
                        QProgressBar {
                            border: 1px solid #ccc;
                            border-radius: 5px;
                            text-align: center;
                            background-color: #f5f5f5;
                        }
                        QProgressBar::chunk {
                            background-color: #6ab04c;
                            border-radius: 5px;
                        }
                    """)
            else:
                self.usage_bar.setValue(0)
                self.usage_bar.setMaximum(1)
                self.usage_bar.setFormat("0/0 jam")
            
            # Update limit harian berdasarkan paket
            if selected_paket == "pro":
                self.daily_limit.setText("12 jam/hari")
            else:
                self.daily_limit.setText("5 jam/hari")
            
            # Estimasi waktu tersisa
            if hours_credit > 0 and today_usage > 0:
                # Jika ada penggunaan hari ini, kita estimasi berdasarkan rata-rata penggunaan
                days_left = int(hours_credit / today_usage)
                self.estimate_label.setText(f"~ {days_left} hari (berdasarkan pemakaian hari ini)")
            elif hours_credit > 0:
                # Jika tidak ada penggunaan hari ini, ambil rata-rata dari 7 hari terakhir
                if has_subscription_checker and hasattr(get_usage_history, "__call__"):
                    usage_history = get_usage_history(7)
                    if usage_history and sum(usage_history.values()) > 0:
                        avg_daily = sum(usage_history.values()) / len(usage_history)
                        if avg_daily > 0:
                            days_left = int(hours_credit / avg_daily)
                            self.estimate_label.setText(f"~ {days_left} hari (rata-rata 7 hari terakhir)")
                        else:
                            self.estimate_label.setText("~ N/A (tidak ada penggunaan)")
                    else:
                        self.estimate_label.setText("~ N/A (data tidak tersedia)")
                else:
                    self.estimate_label.setText("~ N/A (tidak dapat menghitung)")
            else:
                self.estimate_label.setText("0 hari (kredit habis)")
        
        except Exception as e:
            print(f"Error updating usage display: {e}")
            import traceback
            traceback.print_exc()
    
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
                log_file = Path("logs/payment_server_transactions.jsonl")
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
            print(f"Error loading transaction history: {e}")
    
    def load_daily_usage(self):
        """Muat data penggunaan harian."""
        try:
            if not hasattr(self, "daily_table"):
                return
                
            # Clear table
            self.daily_table.setRowCount(0)
            
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
                    print(f"Error reading subscription file: {e}")
            
            # Jika daily_usage kosong dan ada subscription_checker
            if not daily_usage and has_subscription_checker and hasattr(get_usage_history, "__call__"):
                daily_usage = get_usage_history(7)
            
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
                percent = min(100, int((usage / daily_limit) * 100))
                
                # Tambahkan row baru
                row = self.daily_table.rowCount()
                self.daily_table.insertRow(row)
                
                # Isi data
                self.daily_table.setItem(row, 0, QTableWidgetItem(date_display))
                self.daily_table.setItem(row, 1, QTableWidgetItem(f"{usage:.2f} jam"))
                
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
            print(f"Error loading daily usage: {e}")
    
    def load_usage_stats(self):
        """Muat statistik penggunaan fitur."""
        try:
            if not hasattr(self, "stats_table"):
                return
            
            # Coba baca statistik terjemahan
            translate_count = 0
            translate_log = Path("temp/translate_log.txt")
            if translate_log.exists():
                translate_count = len(translate_log.read_text(encoding="utf-8").splitlines())
            
            # Coba baca statistik balasan
            reply_count = 0
            reply_log = Path("temp/cohost_log.txt")
            if reply_log.exists():
                reply_count = len(reply_log.read_text(encoding="utf-8").splitlines())
            
            # Coba baca statistik live streaming
            live_count = 0
            # Belum ada log khusus, saat ini sama dengan reply_count
            live_count = reply_count
            
            # Coba baca statistik hold-to-talk
            talk_count = 0
            # Belum ada log khusus, saat ini estimasi dari translate_count
            talk_count = translate_count // 2
            
            # Total
            total_count = translate_count + reply_count
            
            # Update tabel
            self.stats_table.setItem(0, 1, QTableWidgetItem(str(translate_count)))
            self.stats_table.setItem(1, 1, QTableWidgetItem(str(reply_count)))
            self.stats_table.setItem(2, 1, QTableWidgetItem(str(live_count)))
            self.stats_table.setItem(3, 1, QTableWidgetItem(str(talk_count)))
            self.stats_table.setItem(4, 1, QTableWidgetItem(str(total_count)))
            
        except Exception as e:
            print(f"Error loading usage stats: {e}")
    
    def update_calendar_data(self):
        """Update data kalender penggunaan."""
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
                    print(f"Error reading subscription file: {e}")
            
            # Jika daily_usage kosong dan ada subscription_checker
            if not daily_usage and has_subscription_checker and hasattr(get_usage_history, "__call__"):
                daily_usage = get_usage_history(30)  # 30 hari terakhir
            
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
                    print(f"Error formatting calendar date {day_str}: {e}")
            
        except Exception as e:
            print(f"Error updating calendar data: {e}")
    
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
                    print(f"Error reading subscription file: {e}")
            
            # Jika tidak ada data dan ada subscription_checker
            if usage == 0 and has_subscription_checker and hasattr(get_usage_history, "__call__"):
                daily_usage = get_usage_history(30)  # 30 hari terakhir
                if day_str in daily_usage:
                    usage = daily_usage[day_str]
            
            # Limit harian
            paket = self.cfg.get("paket", "basic").lower()
            daily_limit = 12 if paket == "pro" else 5
            
            # Persentase dari limit
            percent = min(100, int((usage / daily_limit) * 100))
            
            # Tampilkan info
            if usage > 0:
                self.day_usage_label.setText(
                    f"Tanggal {date.toString('dd MMM yyyy')}: {usage:.2f} jam ({percent}% dari limit harian)"
                )
                
                # Set warna teks sesuai tingkat penggunaan
                if percent > 80:
                    self.day_usage_label.setStyleSheet("font-size: 12px; color: #F44336; background-color: #f8f9fa; padding: 8px; border-radius: 5px;")
                elif percent > 50:
                    self.day_usage_label.setStyleSheet("font-size: 12px; color: #FFC107; background-color: #f8f9fa; padding: 8px; border-radius: 5px;")
                else:
                    self.day_usage_label.setStyleSheet("font-size: 12px; color: #4CAF50; background-color: #f8f9fa; padding: 8px; border-radius: 5px;")
            else:
                self.day_usage_label.setText(f"Tanggal {date.toString('dd MMM yyyy')}: Tidak ada penggunaan")
                self.day_usage_label.setStyleSheet("font-size: 12px; color: #666; background-color: #f8f9fa; padding: 8px; border-radius: 5px;")
            
        except Exception as e:
            print(f"Error showing day usage: {e}")
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
            self, "Pilih Avatar", "", "Gambar (*.png *.jpg *.jpeg)"
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
                
                QMessageBox.information(self, "Avatar Diperbarui", "Avatar berhasil diperbarui!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Gagal menyimpan avatar: {str(e)}")
    
    def buy_credit(self, hours=100):
        """Buka tab langganan untuk membeli kredit dengan jumlah tertentu."""
        # PERBAIKAN: Metode yang lebih robust untuk navigasi ke tab Subscription
        if self.parent_window:
            # Cek akses ke tab Subscription dengan beberapa pendekatan
            subscription_tab_found = False
            
            # Pendekatan 1: Cek jika tab ada di main_tabs
            if hasattr(self.parent_window, 'main_tabs'):
                for i in range(self.parent_window.main_tabs.count()):
                    if "Subscription" in self.parent_window.main_tabs.tabText(i):
                        self.parent_window.main_tabs.setCurrentIndex(i)
                        subscription_tab_found = True
                        break
            
            # Pendekatan 2: Cek jika subscription_tab ada di parent_window
            if not subscription_tab_found and hasattr(self.parent_window, 'subscription_tab'):
                if hasattr(self.parent_window, 'stack'):
                    try:
                        self.parent_window.stack.setCurrentWidget(self.parent_window.subscription_tab)
                        subscription_tab_found = True
                    except:
                        pass
            
            # Pendekatan 3: Jika ada metode to_subscription di parent
            if not subscription_tab_found and hasattr(self.parent_window, 'to_subscription'):
                try:
                    self.parent_window.to_subscription()
                    subscription_tab_found = True
                except:
                    pass
            
            # Jika masih belum bisa navigasi, coba buat tab baru
            if not subscription_tab_found:
                try:
                    from ui.subscription_tab import SubscriptionTab
                    subscription_tab = SubscriptionTab(self.parent_window)
                    self.parent_window.subscription_tab = subscription_tab
                    self.parent_window.stack.addWidget(subscription_tab)
                    self.parent_window.stack.setCurrentWidget(subscription_tab)
                    subscription_tab_found = True
                except Exception as e:
                    print(f"Error creating subscription tab: {e}")
            
            # Jika sukses, kirim info jumlah jam yang ingin dibeli
            if subscription_tab_found and hasattr(self.parent_window, 'subscription_tab'):
                # Jika ada metode buy_credit di subscription_tab
                if hasattr(self.parent_window.subscription_tab, 'buy_credit'):
                    try:
                        # Jalankan metode buy_credit dengan parameter jam
                        QTimer.singleShot(100, lambda: self.parent_window.subscription_tab.buy_credit(hours, hours * 1000))
                    except:
                        pass
            
            # Jika gagal semua pendekatan
            if not subscription_tab_found:
                QMessageBox.information(
                    self, 
                    "Beli Kredit Jam", 
                    f"Silakan buka tab Subscription untuk membeli {hours} jam kredit."
                )

    def to_subscription(self):
        """Navigasi langsung ke tab Subscription dengan metode yang lebih robust."""
        # Gunakan metode buy_credit tanpa parameter untuk buka tab subscription
        self.buy_credit()
    
    def to_tutorial(self):
        """Navigasi ke tab Tutorial."""
        if self.parent_window:
            if hasattr(self.parent_window, 'main_tabs'):
                for i in range(self.parent_window.main_tabs.count()):
                    if "Tutorial" in self.parent_window.main_tabs.tabText(i):
                        self.parent_window.main_tabs.setCurrentIndex(i)
                        return
    
    def reload_profile(self):
        """Muat ulang data profil."""
        self.load_profile_data()
        QMessageBox.information(self, "Refresh", "Data profil berhasil dimuat ulang!")
    
    def edit_profile(self):
        """Edit profil pengguna."""
        # Dialog edit profil
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Profil")
        dialog.setMinimumWidth(400)
        
        layout = QGridLayout(dialog)
        
        # Nama
        layout.addWidget(QLabel("Nama:"), 0, 0)
        name_input = QLineEdit()
        name_input.setText(self.name_label.text())
        layout.addWidget(name_input, 0, 1)
        
        # Email (readonly)
        layout.addWidget(QLabel("Email:"), 1, 0)
        email_input = QLineEdit()
        email_input.setText(self.email_label.text())
        email_input.setReadOnly(True)
        layout.addWidget(email_input, 1, 1)
        
        # Tombol
        save_btn = QPushButton("Simpan")
        save_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        cancel_btn = QPushButton("Batal")
        
        layout.addWidget(save_btn, 2, 0)
        layout.addWidget(cancel_btn, 2, 1)
        
        # Connect signals
        save_btn.clicked.connect(lambda: self._save_profile(name_input.text(), dialog))
        cancel_btn.clicked.connect(dialog.reject)
        
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
        
        QMessageBox.information(self, "Profil Diperbarui", "Profil berhasil diperbarui!")
    
    def save_username(self):
        """Simpan username dari tab pengaturan."""
        name = self.username_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Nama tidak boleh kosong!")
            return
        
        # Update data user
        user_data = self.cfg.get("user_data", {})
        user_data["name"] = name
        
        # Simpan ke konfigurasi
        self.cfg.set("user_data", user_data)
        
        # Update tampilan
        self.name_label.setText(name)
        
        QMessageBox.information(self, "Profil Diperbarui", "Nama pengguna berhasil diperbarui!")
    
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
        
        QMessageBox.information(self, "Pengaturan Disimpan", "Pengaturan profil berhasil disimpan!")
    
    def verify_identity(self):
        """Verifikasi identitas pengguna."""
        QMessageBox.information(
            self, 
            "Verifikasi Identitas", 
            "Fitur verifikasi identitas akan segera tersedia.\n\n"
            "Verifikasi identitas memberikan perlindungan tambahan untuk akun Anda."
        )
    
    def export_profile_data(self):
        """Export data profil pengguna."""
        try:
            # Get save location
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Data Profil",
                f"streammate_profile_{datetime.now().strftime('%Y%m%d')}.json",
                "JSON Files (*.json)"
            )

            if not file_path:
                return

            # Collect profile data
            user_data = self.cfg.get("user_data", {})

            profile_data = {
                "user_info": user_data,
                "subscription_info": {},
                "usage_statistics": {},
                "settings": self.cfg.get("profile_settings", {}),
                "export_timestamp": datetime.now().isoformat()
            }

            # Add subscription data if available
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists():
                try:
                    with open(subscription_file, "r", encoding="utf-8") as f:
                        profile_data["subscription_info"] = json.load(f)
                except Exception as e:
                    print(f"Error reading subscription data: {e}")

            # Add usage statistics
            try:
                # Terjemahan stats
                translate_log = Path("temp/translate_log.txt")
                if translate_log.exists():
                    profile_data["usage_statistics"]["translate_count"] = len(
                        translate_log.read_text(encoding="utf-8").splitlines()
                    )

                # Reply stats
                reply_log = Path("temp/cohost_log.txt")
                if reply_log.exists():
                    profile_data["usage_statistics"]["reply_count"] = len(
                        reply_log.read_text(encoding="utf-8").splitlines()
                    )

                # Transaction history
                trans_log = Path("logs/payment_transactions.jsonl")
                if trans_log.exists():
                    transactions = []
                    with open(trans_log, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                transactions.append(json.loads(line))
                            except:
                                continue
                    profile_data["transaction_history"] = transactions
            except Exception as e:
                print(f"Error collecting usage statistics: {e}")

            # Save to file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(profile_data, f, indent=2, ensure_ascii=False)

            QMessageBox.information(
                self, "Export Berhasil",
                f"Data profil berhasil diekspor ke:\n{file_path}"
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Export Gagal",
                f"Gagal mengekspor data profil:\n{str(e)}"
            )
    def logout(self):
        """Logout dari aplikasi dengan konfirmasi."""
        reply = QMessageBox.question(
            self, "Konfirmasi Logout",
            "Apakah Anda yakin ingin logout?\n\n"
            "Semua data sesi akan dihapus.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Stop refresh timer
                self.refresh_timer.stop()

                # Call parent window logout if available
                if self.parent_window and hasattr(self.parent_window, 'logout'):
                    self.parent_window.logout()
                else:
                    # Fallback logout process
                    self._perform_logout()

            except Exception as e:
                QMessageBox.critical(
                    self, "Logout Error",
                    f"Terjadi kesalahan saat logout:\n{str(e)}"
                )

    def _perform_logout(self):
        """Perform logout process manually."""
        try:
            # Clear Google token
            token_path = Path("config/google_token.json")
            if token_path.exists():
                token_path.unlink()

            # Clear user data from config
            self.cfg.set("user_data", {})

            # Clear cache files
            cache_files = [
                "temp/license_cache.json",
                "temp/current_session.json"
            ]

            for cache_file in cache_files:
                cache_path = Path(cache_file)
                if cache_path.exists():
                    try:
                        cache_path.unlink()
                    except:
                        pass

            QMessageBox.information(
                self, "Logout Berhasil",
                "Anda telah berhasil logout.\nSilakan restart aplikasi untuk login kembali."
            )

        except Exception as e:
            print(f"Error in logout process: {e}")

    def check_for_updates(self):
        """Cek update aplikasi (placeholder untuk fitur masa depan)."""
        QMessageBox.information(
            self, "Cek Update",
            "Fitur cek update otomatis akan segera tersedia.\n\n"
            "Saat ini Anda menggunakan StreamMate AI versi terbaru."
        )

    def check_for_updates(self):
        """Manual check untuk update."""
        if self.parent_window and hasattr(self.parent_window, 'check_for_updates_manual'):
            self.parent_window.check_for_updates_manual()
        else:
            QMessageBox.information(
                self, "Update Check",
                "Fitur update check tidak tersedia.\n"
                "Silakan download versi terbaru dari:\n"
                "https://github.com/StreamMateAI/StreamMate/releases"
            )

    def show_app_info(self):
        """Tampilkan informasi aplikasi."""
        app_version = self.cfg.get("app_version", "1.0.0")

        info_text = f"""
        <h2>StreamMate AI</h2>
        <p><b>Versi:</b> {app_version}</p>
        <p><b>Build:</b> {datetime.now().strftime('%Y%m%d')}</p>
        <p><b>Platform:</b> Windows/Linux</p>
        <p><b>Framework:</b> PyQt6 + Python</p>

        <h3>Fitur Utama:</h3>
        <ul>
            <li>Terjemahan Suara Real-time</li>
            <li>Auto-Reply Chat Streaming</li>
            <li>Integrasi Avatar & Animasi</li>
            <li>Virtual Microphone</li>
            <li>Multi-Platform Support</li>
        </ul>

        <h3>Dukungan:</h3>
        <p>Email: support@streammateai.com</p>
        <p>Website: https://streammateai.com</p>

        <p><i>© 2025 StreamMate AI. All rights reserved.</i></p>
        """

        # Create custom dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Tentang StreamMate AI")
        dialog.setMinimumSize(500, 400)

        layout = QVBoxLayout(dialog)

        # Info label with rich text
        info_label = QLabel(info_text)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Scroll area for long content
        scroll = QScrollArea()
        scroll.setWidget(info_label)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        # Close button
        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()