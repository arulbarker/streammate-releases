# ui/subscription_tab.py
import os
import json
import requests
import sys
import time  # Tambahkan import ini
import logging
logger = logging.getLogger('StreamMate')
from pathlib import Path
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QMessageBox, 
    QHBoxLayout, QProgressBar, QFrame, QGroupBox, QGridLayout,
    QSpacerItem, QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtGui import QFont, QDesktopServices, QColor
from PyQt6.QtCore import QUrl, Qt, QTimer
from modules_client.subscription_checker import get_checker


# Setup path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Import payment server check
try:
    from payment_server import check_server_running, start_server
except ImportError:
    # Fallback jika import gagal
    def check_server_running(port=5005):
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
            
    def start_server():
        import subprocess, os, sys, time
        if not check_server_running(5005):
            subprocess.Popen([
                sys.executable, 
                os.path.join(ROOT, "payment_server.py")
            ], 
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
            time.sleep(2)  # Wait for server to start
        return True

# Import ConfigManager dulu
try:
    from modules_client.config_manager import ConfigManager
except ImportError:
    from modules_server.config_manager import ConfigManager

# Import HourlySubscriptionChecker
try:
    from modules_client.subscription_checker import HourlySubscriptionChecker
except ImportError:
    # Buat dummy class kalau gak ada
    class HourlySubscriptionChecker:
        def __init__(self):
            self.cfg = ConfigManager("config/settings.json")
            
        def get_credit_info(self):
            return {
                "hours_credit": 100,
                "hours_used": 0
            }
            
        def start_tracking(self):
            pass
            
        def stop_tracking(self):
            pass
            
        def check_credit(self):
            return True

class SubscriptionTab(QWidget):
    def __init__(self, main_window=None):
        
        super().__init__()
        self.main_window = main_window
        self.cfg = ConfigManager("config/settings.json")
        self.hour_checker = HourlySubscriptionChecker()
        self.setObjectName("subscription_tab")
        
        # Timer untuk refresh otomatis
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(30000)  # 30 detik
        self.refresh_timer.timeout.connect(lambda: self.refresh_credit_info(True))
        
        # Setup UI
        self.init_ui()
        
        # Start timer
        self.refresh_timer.start()
        
        # Initial load
        self.refresh_credit_info(True)
    
    def init_ui(self):
        """Initialize UI elements"""
        # Layout utama
        main_layout = QVBoxLayout(self)

        # Buat ScrollArea untuk mengakomodasi konten panjang
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        # Widget konten yang akan di-scroll
        content_widget = QWidget()
        content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(20)

        # Header dengan Logout Button
        header_layout = QHBoxLayout()
        
        title = QLabel("StreamMate AI Basic")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        header_layout.addWidget(title)
        
        # Spacer
        header_layout.addStretch()
        
        # Tombol logout di header
        logout_btn = QPushButton("🚪 Logout")
        logout_btn.setStyleSheet(
            "font-size: 14px; padding: 8px 15px; "
            "background-color: #f44336; color: white; "
            "border-radius: 5px; border: none; font-weight: bold;"
        )
        logout_btn.clicked.connect(self.logout)
        header_layout.addWidget(logout_btn)
        
        content_layout.addLayout(header_layout)
        
        # Deskripsi
        desc = QLabel(
            "Sistem langganan per jam untuk StreamMate AI\n"
            "Basic: Rp 1.000 per jam (minimal 100 jam)"
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(desc)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        content_layout.addWidget(separator)
        
        # Status Kredit
        credit_group = QGroupBox("💰 Status Kredit")
        credit_layout = QVBoxLayout()
        
        # Kredit tersisa (tampil bulat)
        self.credit_label = QLabel("Kredit: 0 jam")
        self.credit_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.credit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit_layout.addWidget(self.credit_label)
        
        # Pemakaian (2 desimal)
        self.usage_label = QLabel("Total Pemakaian: 0.00 jam")
        self.usage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit_layout.addWidget(self.usage_label)
        
        # Progress bar
        self.credit_bar = QProgressBar()
        self.credit_bar.setRange(0, 100)
        self.credit_bar.setTextVisible(True)
        credit_layout.addWidget(self.credit_bar)

        # Session Status
        self.session_status = QLabel("")
        self.session_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        credit_layout.addWidget(self.session_status)      
        
        # Statistik penggunaan
        usage_stats_group = QGroupBox("📈 Statistik Penggunaan")
        usage_stats_layout = QVBoxLayout()
        self.usage_stats_label = QLabel("Memuat statistik...")
        self.usage_stats_label.setWordWrap(True)
        usage_stats_layout.addWidget(self.usage_stats_label)
        usage_stats_group.setLayout(usage_stats_layout)
        content_layout.addWidget(usage_stats_group)

        # Demo mode info
        self.demo_info = QLabel("")
        self.demo_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.demo_info.setStyleSheet("color: #4CAF50; font-weight: bold;")
        credit_layout.addWidget(self.demo_info)
        
        # Info tambahan
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: gray;")
        credit_layout.addWidget(self.info_label)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Status")
        refresh_btn.clicked.connect(self.refresh_credit_info)
        credit_layout.addWidget(refresh_btn)
        
        credit_group.setLayout(credit_layout)
        content_layout.addWidget(credit_group)

        self.access_btn = QPushButton("🚀 Akses Paket Basic")
        self.access_btn.setMinimumHeight(50)
        # Default style: Tombol merah (disabled) karena belum ada kredit
        self.access_btn.setStyleSheet(
                    "font-size: 16px; padding: 10px 20px; "
                    "background-color: #f44336; color: white; "
                    "border-radius: 8px; border: none; font-weight: bold;")
        self.access_btn.clicked.connect(self.access_package)
        self.access_btn.setEnabled(False)  # Default: dinonaktifkan
        content_layout.addWidget(self.access_btn)

        # Tambahan (optional): Tombol Pro jika ingin menampilkan kedua paket
        self.access_pro_btn = QPushButton("👑 Akses Paket Pro (Coming Soon)")
        self.access_pro_btn.setMinimumHeight(50)
        self.access_pro_btn.setStyleSheet(
                    "font-size: 16px; padding: 10px 20px; "
                    "background-color: #777777; color: white; "
                    "border-radius: 8px; border: none; font-weight: bold;")
        self.access_pro_btn.setEnabled(False)  # Selalu dinonaktifkan untuk sekarang
        content_layout.addWidget(self.access_pro_btn)

        # Tombol Demo
        demo_btn = QPushButton("🚀 Coba Demo Gratis (30 menit/hari)")
        demo_btn.setMinimumHeight(50)
        demo_btn.setStyleSheet(
            "font-size: 16px; padding: 10px 20px; "
            "background-color: #4267B2; color: white; "
            "border-radius: 8px; border: none; font-weight: bold;"
        )
        demo_btn.clicked.connect(self.start_demo)
        content_layout.addWidget(demo_btn)

        content_layout.addSpacing(10)
        
        # Separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        content_layout.addWidget(separator2)
        
        # Pembelian Kredit
        purchase_group = QGroupBox("🛒 Beli Kredit Jam")
        purchase_layout = QVBoxLayout()

        # Header perbandingan paket
        paket_title = QLabel("Pilih Paket yang Sesuai Kebutuhan")
        paket_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1877F2;")
        paket_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        purchase_layout.addWidget(paket_title)

        # Grid paket
        paket_grid = QGridLayout()
        paket_grid.setSpacing(15)

        # Paket Basic
        basic_group = QGroupBox("📊 BASIC")
        basic_group.setStyleSheet("QGroupBox { border: 2px solid #4267B2; border-radius: 8px; }")
        basic_layout = QVBoxLayout()

        basic_title = QLabel("Basic Package")
        basic_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1877F2;")
        basic_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        basic_layout.addWidget(basic_title)

        basic_desc = QLabel(
            "• Balasan Mode Trigger\n"
            "• YouTube ATAU TikTok\n"
            "• Suara Standard\n"
            "• kepribadian ceria\n"
            "• pengetahuan dari prompt\n"
            "• Balas donasi"
        )
        basic_desc.setStyleSheet("color: white;")
        basic_layout.addWidget(basic_desc)

        basic_price = QLabel("Rp 100.000 / 100 jam")
        basic_price.setStyleSheet("font-size: 14px; font-weight: bold; color: #1877F2;")
        basic_price.setAlignment(Qt.AlignmentFlag.AlignCenter)
        basic_layout.addWidget(basic_price)

        basic_group.setLayout(basic_layout)
        paket_grid.addWidget(basic_group, 0, 0)

        # Paket Pro
        pro_group = QGroupBox("👑 PRO (Coming Soon)")
        pro_group.setStyleSheet("QGroupBox { border: 2px solid #777777; border-radius: 8px; }")
        pro_layout = QVBoxLayout()

        pro_title = QLabel("Pro Package")
        pro_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #777777;")
        pro_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pro_layout.addWidget(pro_title)

        pro_desc = QLabel(
            "• Balasan mode Trigger,Delay,berurutan\n"
            "• Balas YouTube + TikTok Dual live streaming\n"
            "• Suara lebih natural\n"
            "• Pengetahuan dari pdf atau website\n"
            "• Virtual mic\n"
            "• viewers manajement\n"
            "• Animasi hotkey\n"
            "• Balas donasi"
        )
        pro_desc.setStyleSheet("color: white;")
        pro_layout.addWidget(pro_desc)

        pro_price = QLabel("Rp 250.000 / 100 jam")
        pro_price.setStyleSheet("font-size: 14px; font-weight: bold; color: #777777;")
        pro_price.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pro_layout.addWidget(pro_price)

        pro_group.setLayout(pro_layout)
        paket_grid.addWidget(pro_group, 0, 1)

        purchase_layout.addLayout(paket_grid)

        # Info harga
        price_info = QLabel(
            "Harga: Rp 1.000 per jam\n"
            "Minimal pembelian: 100 jam"
        )
        price_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        purchase_layout.addWidget(price_info)

        # Tombol beli
        buy_layout = QHBoxLayout()

        # Paket 100 jam
        btn_100 = QPushButton("💎 100 Jam\nRp 100.000")
        btn_100.setMinimumHeight(60)
        btn_100.setStyleSheet(
            "font-size: 14px; padding: 10px; "
            "background-color: #1877F2; color: white; "
            "border-radius: 5px; border: none; font-weight: bold;"
        )
        btn_100.clicked.connect(lambda: self.buy_credit(100, 100000))
        buy_layout.addWidget(btn_100)

        # Paket 200 jam (bonus)
        btn_200 = QPushButton("🎁 200 Jam\nRp 180.000)")
        btn_200.setMinimumHeight(60)
        btn_200.setStyleSheet(
            "font-size: 14px; padding: 10px; "
            "background-color: #1877F2; color: white; "
            "border-radius: 5px; border: none; font-weight: bold;"
        )
        btn_200.clicked.connect(lambda: self.buy_credit(200, 180000))
        buy_layout.addWidget(btn_200)

        # Paket Pro (disabled)
        btn_pro = QPushButton("👑 Pro Package\nRp 250.000)")
        btn_pro.setMinimumHeight(60)
        btn_pro.setEnabled(False)
        btn_pro.setStyleSheet(
            "font-size: 14px; padding: 10px; "
            "background-color: #777777; color: #cccccc; "
            "border-radius: 5px; border: none; font-weight: bold;"
        )
        buy_layout.addWidget(btn_pro)

        purchase_layout.addLayout(buy_layout)

        # Payment methods
        payment_info = QLabel("Metode Pembayaran: Transfer Bank, E-Wallet, QRIS")
        payment_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        payment_info.setStyleSheet("color: #606770; font-size: 12px;")
        purchase_layout.addWidget(payment_info)

        purchase_group.setLayout(purchase_layout)
        content_layout.addWidget(purchase_group)

        # Atur widget konten ke scroll area
        scroll_area.setWidget(content_widget)
        
        # Tambahkan scroll area ke layout utama
        main_layout.addWidget(scroll_area)

        # Atur size policy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


    
    def init_package_comparison(self):
        """Tampilkan perbandingan paket Basic dan Pro."""
        comparison_group = QGroupBox("🔄 Perbandingan Paket")
        comparison_layout = QVBoxLayout()

        # Judul
        title = QLabel("Perbandingan Paket Basic vs Pro")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1877F2;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        comparison_layout.addWidget(title)

        # Buat tabel perbandingan
        table = QTableWidget(11, 3)
        table.setStyleSheet(
            "QTableWidget { border: 1px solid #dddfe2; border-radius: 8px; }"
            "QHeaderView::section { background-color: #4267B2; color: white; padding: 6px; font-weight: bold; }"
            "QTableWidget::item { padding: 8px; }"
        )

        # Set header
        table.setHorizontalHeaderLabels(["Fitur", "Basic", "Pro"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        # Fitur-fitur
        features = [
            ("Terjemahan Suara", "Standar", "Premium Natural"),
            ("Auto-Reply", "Mode Trigger", "Semua Mode"),
            ("Kualitas Suara", "Standar", "Kualitas HD"),
            ("Live Platform", "YouTube ATAU TikTok", "YouTube + TikTok"),
            ("Kepribadian AI", "Terbatas", "Banyak Pilihan"),
            ("Durasi Harian", "5 jam/hari", "12 jam/hari"),
            ("Virtual Microphone", "❌", "✅"),
            ("Pemahaman Konteks", "❌", "✅"),
            ("Avatar Integration", "❌", "✅"),
            ("Batas Bahasa", "Indonesia-Inggris", "Multi-Bahasa"),
            ("Harga", "Rp 100.000 / 100 jam", "Rp 250.000 / 100 jam")
        ]

        # Isi tabel
        for i, (feature, basic, pro) in enumerate(features):
            # Fitur
            item = QTableWidgetItem(feature)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(i, 0, item)

            # Basic
            item = QTableWidgetItem(basic)
            if "❌" in basic:
                item.setForeground(QColor("#f03e3e"))
            elif "✅" in basic:
                item.setForeground(QColor("#40c057"))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 1, item)

            # Pro
            item = QTableWidgetItem(pro + (" 🔒" if i < len(features)-1 else ""))
            item.setForeground(QColor("#777777"))
            if "✅" in pro:
                item.setForeground(QColor("#40c057"))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 2, item)

        # Sesuaikan ukuran baris
        for i in range(table.rowCount()):
            table.setRowHeight(i, 40)

        comparison_layout.addWidget(table)

        comparison_group.setLayout(comparison_layout)
        self.layout().addWidget(comparison_group)

    def ensure_payment_server(self):
        """Pastikan server payment berjalan, mulai jika perlu."""
        try:
            # Cek server berjalan
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                server_running = s.connect_ex(('localhost', 5005)) == 0

            # Jika tidak berjalan, coba mulai
            if not server_running:
                import subprocess, sys, os
                server_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "payment_server.py")

                # Mulai server tanpa blocking
                if sys.platform == "win32":
                    subprocess.Popen([sys.executable, server_path], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
                else:
                    subprocess.Popen([sys.executable, server_path], start_new_session=True)

                # Tunggu server startup
                import time
                time.sleep(2)

                # Cek lagi
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    server_running = s.connect_ex(('localhost', 5005)) == 0

            return server_running, None
        except Exception as e:
            return False, str(e)

    def refresh_credit_info(self, silent=False):
        """Refresh info kredit dari server dan file subscription_status.json."""
        try:
            # TAMBAHAN: Skip untuk test mode
            if hasattr(self.main_window, 'license_validator') and self.main_window.license_validator.testing_mode:
                self.credit_label.setText("Kredit: ∞ jam (Test Mode)")
                self.usage_label.setText("Test Mode Active")
                self.credit_bar.setValue(0)
                self.info_label.setText("✅ Test Mode - Unlimited Access")
                
                # Update session status
                self.session_status.setText("⚪ Mode Test - Kredit tidak terhitung")
                self.session_status.setStyleSheet("color: #808080;")
                return

            # Skip untuk debug mode
            if self.cfg.get("debug_mode", False):
                self.credit_label.setText("Kredit: ∞ jam (Dev Mode)")
                self.usage_label.setText("Developer Mode Active")
                self.credit_bar.setValue(0)
                self.info_label.setText("✅ Developer Mode - Unlimited Access")
                
                # Update session status
                self.session_status.setText("⚪ Mode Developer - Kredit tidak terhitung")
                self.session_status.setStyleSheet("color: #808080;")
                return

            # Coba baca dari subscription_status.json
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists():
                try:
                    subscription_data = json.loads(subscription_file.read_text(encoding="utf-8"))

                    # Cek apakah ada expire_date (mode demo)
                    is_demo = False
                    demo_expire = None

                    if "expire_date" in subscription_data:
                        # PERBAIKAN: Handling timezone yang benar
                        expire_date_str = subscription_data["expire_date"]
                        try:
                            # PERBAIKAN: Handle timezone dengan lebih baik
                            if '+' in expire_date_str:
                                # Format dengan timezone
                                from datetime import timezone
                                expire_date = datetime.fromisoformat(expire_date_str)
                                now_time = datetime.now(timezone.utc)
                            else:
                                # Format tanpa timezone
                                expire_date = datetime.fromisoformat(expire_date_str)
                                now_time = datetime.now()

                            is_demo = True
                            demo_expire = expire_date
                        except ValueError as e:
                            print(f"[DEBUG] Format expire_date invalid: {e}")
                            # Fallback: parsing manual format timestamp jika perlu
                            try:
                                # Coba format tanpa mikrodetik
                                if 'T' in expire_date_str:
                                    date_part, time_part = expire_date_str.split('T')
                                    time_part = time_part.split('.')[0]  # Hapus mikrodetik
                                    expire_date_str = f"{date_part}T{time_part}"
                                    expire_date = datetime.fromisoformat(expire_date_str)
                                    now_time = datetime.now()
                                    is_demo = True
                                    demo_expire = expire_date
                            except Exception as parse_error:
                                print(f"[DEBUG] Fallback parsing juga gagal: {parse_error}")
                                is_demo = False

                    # Set kredit dan pemakaian
                    # PERBAIKAN: Pastikan kredit ditampilkan dalam format bulat (int) untuk UI yang lebih bersih
                    hours_credit = subscription_data.get("hours_credit", 0) if subscription_data.get("status") == "paid" else 0
                    hours_used = subscription_data.get("hours_used", 0)

                    # Update display
                    self.credit_label.setText(f"Kredit: {int(hours_credit)} jam")
                    self.usage_label.setText(f"Total Pemakaian: {hours_used:.2f} jam")

                    # Progress bar
                    if hours_credit + hours_used > 0:
                        usage_percent = (hours_used / (hours_credit + hours_used)) * 100
                        self.credit_bar.setValue(int(usage_percent))
                        self.credit_bar.setFormat(f"{int(usage_percent)}% terpakai")
                    else:
                        self.credit_bar.setValue(0)
                        self.credit_bar.setFormat("0%")

                    # Tombol akses selalu terlihat, tapi status enabled/disabled berdasarkan kredit
                    package_name = subscription_data.get('package', 'basic').capitalize()
                    # PERBAIKAN: Cek kredit lebih ketat
                    has_credit = hours_credit > 0 and subscription_data.get("status") == "paid"

                    self.access_btn.setText(f"🚀 Akses Paket {package_name}")
                    self.access_btn.setEnabled(has_credit)  # Aktifkan tombol jika ada kredit

                    # Ubah warna tombol berdasarkan status kredit
                    if has_credit:
                        # Hijau jika kredit tersedia
                        self.access_btn.setStyleSheet(
                            "font-size: 16px; padding: 10px 20px; "
                            "background-color: #4CAF50; color: white; "
                            "border-radius: 8px; border: none; font-weight: bold;"
                        )
                    else:
                        # Merah jika tidak ada kredit
                        self.access_btn.setStyleSheet(
                            "font-size: 16px; padding: 10px 20px; "
                            "background-color: #f44336; color: white; "
                            "border-radius: 8px; border: none; font-weight: bold;"
                        )

                    # Selalu tampilkan tombol akses
                    self.access_btn.setVisible(True)

                    # Demo info
                    if is_demo and demo_expire:
                        try:
                            # Gunakan now_time yang sudah disiapkan sebelumnya
                            if demo_expire > now_time:
                                remaining = demo_expire - now_time
                                days = remaining.days
                                hours = remaining.seconds // 3600
                                minutes = (remaining.seconds % 3600) // 60

                                if days > 0:
                                    self.demo_info.setText(f"🕒 Mode Demo: {days} hari {hours} jam tersisa")
                                else:
                                    self.demo_info.setText(f"🕒 Mode Demo: {hours} jam {minutes} menit tersisa")

                                self.demo_info.setStyleSheet("color: #FFA500; font-weight: bold;") # Orange color
                                self.info_label.setText("Demo aktif - 30 menit per hari")
                            else:
                                self.demo_info.setText("⚠️ Demo Expired")
                                self.demo_info.setStyleSheet("color: red; font-weight: bold;")
                                self.info_label.setText("Demo telah berakhir - silakan beli kredit")

                                # Tambahkan - Force disable access button
                                self.access_btn.setEnabled(False)
                                self.access_btn.setStyleSheet(
                                    "font-size: 16px; padding: 10px 20px; "
                                    "background-color: #f44336; color: white; "
                                    "border-radius: 8px; border: none; font-weight: bold;"
                                )
                        except TypeError as e:
                            # Error perbandingan timezone
                            print(f"[DEBUG] Error perbandingan timezone pada demo: {e}")
                            # Coba perbandingan tanpa timezone sebagai fallback
                            try:
                                if demo_expire.replace(tzinfo=None) > datetime.now():
                                    self.demo_info.setText("🕒 Mode Demo: Waktu tersisa (timezone error)")
                                    self.demo_info.setStyleSheet("color: #FFA500; font-weight: bold;")
                                else:
                                    self.demo_info.setText("⚠️ Demo Expired (timezone error)")
                                    self.demo_info.setStyleSheet("color: red; font-weight: bold;")

                                    # Nonaktifkan tombol akses
                                    self.access_btn.setEnabled(False)
                            except:
                                self.demo_info.setText("⚠️ Status demo tidak dapat ditentukan")
                                self.demo_info.setStyleSheet("color: red; font-weight: bold;")

                    else:
                        # Status info normal
                        self.demo_info.setText("")
                        if hours_credit <= 0:
                            self.info_label.setText("⚠️ Kredit habis! Silakan isi ulang.")
                            self.info_label.setStyleSheet("color: red; font-weight: bold;")
                        elif hours_credit < 10:
                            self.info_label.setText(f"⚠️ Kredit rendah! Sisa {int(hours_credit)} jam")
                            self.info_label.setStyleSheet("color: orange; font-weight: bold;")
                        else:
                            self.info_label.setText("✅ Kredit aktif")
                            self.info_label.setStyleSheet("color: green; font-weight: bold;")

                    # PERBAIKAN: Tambahkan indikator pembelian terbaru
                    if "updated_at" in subscription_data:
                        try:
                            updated_at = datetime.fromisoformat(subscription_data["updated_at"])
                            now = datetime.now()
                            if (now - updated_at).total_seconds() < 300:  # 5 menit terakhir
                                self.info_label.setText(self.info_label.text() + " | ✨ Pembelian baru berhasil!")
                        except:
                            pass

                    # Update session status
                    checker = self.hour_checker
                    if checker.is_tracking:
                        active_time = time.time() - checker.session_start
                        if checker.idle_state:
                            self.session_status.setText(f"⏸️ Sesi idle ({int(checker.session_active_time / 60)} menit aktif)")
                            self.session_status.setStyleSheet("color: #FFA500; font-weight: bold;")
                        else:
                            self.session_status.setText(f"🟢 Sesi aktif: {int((checker.session_active_time + (time.time() - checker.last_activity)) / 60)} menit")
                            self.session_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
                    else:
                        self.session_status.setText("⚪ Tidak ada sesi aktif")
                        self.session_status.setStyleSheet("color: #808080;")

                    # PERBAIKAN: Buat safe call untuk _update_main_features
                    try:
                        # Enable/disable main features dengan pengecekan yang lebih aman
                        self._safe_update_main_features(hours_credit > 0 or is_demo)
                    except Exception as e:
                        print(f"[DEBUG] Error updating features: {e}")

                    # TAMBAHAN: Paksa refresh kredit dari file
                    self.force_refresh_credit()
                    
                    # TAMBAHAN: Muat statistik penggunaan
                    self.load_usage_stats()

                    if not silent:
                        QMessageBox.information(self, "Refresh Berhasil", "Data kredit berhasil diperbarui.")

                    return
                except Exception as e:
                    if not silent:
                        print(f"[DEBUG] Error membaca subscription_status.json: {e}")
                        # Log detail error untuk debugging
                        import traceback
                        traceback.print_exc()

            # Fallback: tampilkan kredit 0
            self.credit_label.setText("Kredit: 0 jam")
            self.usage_label.setText("Total Pemakaian: 0.00 jam")
            self.credit_bar.setValue(0)
            self.credit_bar.setFormat("0%")
            self.info_label.setText("Belum ada kredit aktif")
            
            # Update session status (fallback)
            self.session_status.setText("⚪ Tidak ada sesi aktif")
            self.session_status.setStyleSheet("color: #808080;")

            # PERBAIKAN: Pastikan tombol akses dinonaktifkan
            self.access_btn.setEnabled(False)
            self.access_btn.setStyleSheet(
                "font-size: 16px; padding: 10px 20px; "
                "background-color: #f44336; color: white; "
                "border-radius: 8px; border: none; font-weight: bold;"
            )

        except Exception as e:
            if not silent:
                QMessageBox.warning(self, "Error", f"Gagal refresh: {str(e)}")
            # Log detail error untuk debugging
            import traceback
            traceback.print_exc()

    def force_refresh_credit(self):
        """Paksa refresh kredit dari file, bukan dari cache."""
        try:
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists():
                # Paksa baca ulang dari file untuk memastikan data terbaru
                with open(subscription_file, "r", encoding="utf-8") as f:
                    subscription_data = json.load(f)

                # Validasi tipe data untuk keamanan
                try:
                    hours_credit = float(subscription_data.get("hours_credit", 0))
                    hours_used = float(subscription_data.get("hours_used", 0))
                except (ValueError, TypeError):
                    hours_credit = 0
                    hours_used = 0

                # PERBAIKAN: Pastikan atribut hours_credit ada sebelum aksesnya
                if hasattr(self, 'hours_credit'):
                    # Update nilai kredit hanya jika berbeda dari yang ditampilkan
                    current_display = self.hours_credit.text().replace(" jam", "")
                    if current_display != str(hours_credit):
                        self.hours_credit.setText(f"{hours_credit} jam")
                        self.hours_credit.setStyleSheet("font-weight: bold; color: green;")
                        # Reset style setelah 3 detik
                        QTimer.singleShot(3000, lambda: self.hours_credit.setStyleSheet(""))

                if hasattr(self, 'hours_used'):
                    self.hours_used.setText(f"{hours_used:.2f} jam")

                # PERBAIKAN: Pastikan usage_bar ada sebelum diakses
                if hasattr(self, 'usage_bar'):
                    # Update progress bar hanya jika nilai berubah
                    total = hours_credit + hours_used
                    if total > 0:
                        percent_used = min(100, int((hours_used / total) * 100))
                        current_value = self.usage_bar.value()
                        if current_value != percent_used:
                            self.usage_bar.setValue(percent_used)
                            self.usage_bar.setFormat(f"{hours_used:.1f}/{total:.1f} jam ({percent_used}%)")

                # Perbarui info paket jika atribut ada
                if hasattr(self, 'paket_info'):
                    package_name = subscription_data.get("package", "basic").capitalize()
                    self.paket_info.setText(package_name)

                # Cek tanggal kedaluwarsa jika ada
                if "expire_date" in subscription_data and hasattr(self, 'expire_label'):
                    try:
                        expire_date = datetime.fromisoformat(subscription_data["expire_date"])
                        now = datetime.now()
                        if expire_date > now:
                            remaining = expire_date - now
                            days = remaining.days
                            hours = remaining.seconds // 3600
                            self.expire_label.setText(f"Berlaku hingga: {expire_date.strftime('%d %b %Y')} ({days}d {hours}h)")
                        else:
                            self.expire_label.setText("Sudah kedaluwarsa!")
                            self.expire_label.setStyleSheet("color: red; font-weight: bold;")
                    except Exception as e:
                        print(f"[DEBUG] Error parse expire_date: {e}")

                # Jika ada info penggunaan hari ini, tampilkan
                if "usage_stats" in subscription_data and hasattr(self, 'today_usage'):
                    today = datetime.now().date().isoformat()
                    if today in subscription_data["usage_stats"]:
                        today_usage = subscription_data["usage_stats"][today]
                        self.today_usage.setText(f"{today_usage:.2f} jam")

                # Log ke console untuk debugging
                print(f"[DEBUG] Force refresh credit completed: {hours_credit} jam")

                return True

        except Exception as e:
            print(f"[ERROR] Force refresh credit failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def load_usage_stats(self):
        """Muat statistik penggunaan dari subscription_status.json."""
        try:
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists():
                with open(subscription_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Ambil statistik penggunaan per hari
                stats = data.get("usage_stats", {})

                # Format informasi
                if stats:
                    stats_text = "Statistik Penggunaan:\n"
                    total_usage = 0

                    # Urutkan dari terbaru
                    sorted_days = sorted(stats.keys(), reverse=True)

                    for day in sorted_days[:7]:  # Tampilkan 7 hari terakhir
                        usage = stats.get(day, 0)
                        total_usage += usage
                        stats_text += f"• {day}: {usage:.2f} jam\n"

                    stats_text += f"\nTotal: {total_usage:.2f} jam"

                    # Update tampilan
                    if hasattr(self, 'usage_stats_label'):
                        self.usage_stats_label.setText(stats_text)
                else:
                    if hasattr(self, 'usage_stats_label'):
                        self.usage_stats_label.setText("Belum ada data penggunaan")

        except Exception as e:
            print(f"Error loading usage stats: {e}")
            if hasattr(self, 'usage_stats_label'):
                self.usage_stats_label.setText("Gagal memuat statistik penggunaan")

    def _safe_update_main_features(self, has_credit):
        """Enable/disable fitur utama dengan pengecekan aman."""
        # Cari tab CoHost di main window
        if not hasattr(self, 'main_window'):
            return

        if not hasattr(self.main_window, 'main_tabs'):
            return

        tabs = self.main_window.main_tabs
        if tabs is None:
            return

        try:
            for i in range(tabs.count()):
                tab_text = tabs.tabText(i)
                if "Cohost" in tab_text:
                    # Disable tab jika tidak ada kredit
                    tabs.setTabEnabled(i, has_credit)
                    if not has_credit:
                        tabs.setTabToolTip(i, "Kredit habis! Silakan isi ulang.")
        except Exception as e:
            print(f"[DEBUG] Error dalam _safe_update_main_features: {e}")

    def access_package(self):
        logger.info(f"Mencoba mengakses paket dari subscription_tab.py")
        """Akses paket yang sudah dibeli."""
        # Double-check kredit - tambahan keamanan meskipun tombol harusnya disabled jika tidak ada kredit
        subscription_file = Path("config/subscription_status.json")
        if subscription_file.exists():
            try:
                with open(subscription_file, "r", encoding="utf-8") as f:
                    subscription_data = json.load(f)

                # PERBAIKAN: Validasi lebih ketat untuk kredit jam
                try:
                    hours_credit = float(subscription_data.get("hours_credit", 0))
                except (ValueError, TypeError):
                    hours_credit = 0

                status = subscription_data.get("status", "")

                # PERBAIKAN: Validasi lebih ketat
                if hours_credit <= 0 or status != "paid":
                    QMessageBox.warning(
                        self,
                        "Kredit Tidak Tersedia",
                        f"Anda tidak memiliki kredit jam yang aktif.\n"
                        f"Status: {status}\nKredit: {hours_credit} jam\n\n"
                        "Silakan beli paket terlebih dahulu."
                    )

                    # Refresh UI untuk memastikan tombol disabled
                    self.refresh_credit_info(True)
                    return False

                # PERBAIKAN: Pastikan modus demo tidak bisa mengakses paket berbayar
                if subscription_data.get("transaction_status") == "demo":
                    QMessageBox.warning(
                        self,
                        "Mode Demo",
                        "Anda sedang dalam mode demo.\n"
                        "Silakan beli paket untuk mengakses fitur penuh."
                    )
                    return False

                # Jika valid, lanjutkan akses paket
                package = subscription_data.get("package", "basic")

                # PERBAIKAN: Simpan paket ke settings.json dengan benar
                self.cfg.set("paket", package)

                # PERBAIKAN: Tambahkan panggilan langsung ke pilih_paket tanpa restart
                if hasattr(self.main_window, 'pilih_paket'):
                    self.main_window.pilih_paket(package)

                    # PERBAIKAN: Tambahkan pesan sukses dan skip restart
                    QMessageBox.information(
                        self,
                        "Aktivasi Berhasil",
                        f"Paket {package.upper()} telah diaktifkan dengan sukses!"
                    )
                    return True
                else:
                    # Hanya jika pilih_paket tidak tersedia, tawarkan restart
                    restart_msg = QMessageBox.question(
                        self,
                        "Aktivasi Paket",
                        f"Paket {package.upper()} telah diaktifkan!\n\n"
                        "Namun diperlukan restart aplikasi.\n"
                        "Restart sekarang?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )

                    if restart_msg == QMessageBox.StandardButton.Yes:
                        # Restart aplikasi dengan skrip Python yang sama
                        import sys, os
                        python = sys.executable
                        os.execl(python, python, *sys.argv)
                        return True

                    return True

            except Exception as e:
                QMessageBox.warning(self, "Error", f"Gagal membaca data langganan: {str(e)}")
                import traceback
                traceback.print_exc()
                return False
        else:
            QMessageBox.warning(
                self,
                "Tidak Ada Paket Aktif",
                "Anda belum memiliki paket aktif.\nSilakan beli paket terlebih dahulu."
            )
            return False

    def buy_credit(self, hours, price):
        """Proses pembelian kredit dengan simulasi lokal."""
        # Dapatkan email dari konfigurasi
        email = self.cfg.get("user_data", {}).get("email")

        if not email:
            QMessageBox.warning(self, "Error", "Silakan login terlebih dahulu.")
            return

        # Konfirmasi pembelian
        reply = QMessageBox.question(
            self,
            "Konfirmasi Pembelian",
            f"Anda akan membeli {hours} jam kredit\n"
            f"Harga: Rp {price:,}\n\n"
            "Lanjutkan ke pembayaran?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Pastikan server pembayaran berjalan
        server_running, error_msg = self.ensure_payment_server()

        if not server_running:
            QMessageBox.critical(
                self,
                "Kesalahan Server",
                f"Tidak dapat menjalankan server payment: {error_msg or 'Unknown Error'}\n"
                "Coba restart aplikasi atau hubungi support."
            )
            return

        # Proses pembayaran
        try:
            import requests
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices

            # Tentukan paket berdasarkan jumlah jam
            package = "pro_bonus" if hours == 200 else ("pro" if hours > 100 else "basic")

            # Kirim request ke server lokal
            response = requests.post(
                "http://localhost:5005/create_transaction",
                json={
                    "email": email,
                    "package": package
                },
                timeout=15  # Tambah timeout
            )

            # Periksa respon
            if response.status_code == 200:
                data = response.json()

                if data.get("status") == "success":
                    # Buka halaman pembayaran di browser
                    redirect_url = data.get("redirect_url")
                    if redirect_url:
                        QDesktopServices.openUrl(QUrl(redirect_url))

                        QMessageBox.information(
                            self,
                            "Pembayaran",
                            "Halaman pembayaran telah dibuka di browser.\n\n"
                            "Setelah pembayaran berhasil, klik 'Refresh Status' "
                            "untuk memperbarui kredit Anda."
                        )
                    else:
                        QMessageBox.warning(
                            self,
                            "Error",
                            "Gagal mendapatkan URL pembayaran."
                        )
                else:
                    QMessageBox.warning(
                        self,
                        "Error",
                        f"Permintaan gagal: {data.get('message', 'Unknown error')}"
                    )
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Gagal terhubung ke server: {response.status_code}"
                )


        except requests.exceptions.ConnectionError:
            QMessageBox.warning(
                self,
                "Error Koneksi",
                "Tidak dapat terhubung ke server payment.\n"
                "Pastikan server berjalan dan coba lagi."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Kesalahan Sistem",
                f"Terjadi kesalahan: {str(e)}"
            )

    def _show_purchase_success_notification(self, hours):
        """Tampilkan notifikasi pembelian berhasil."""
        QMessageBox.information(
            self,
            "Pembelian Berhasil",
            f"Selamat! {hours} jam kredit telah ditambahkan ke akun Anda.\n\n"
            f"Total kredit jam Anda telah diperbarui.",
            QMessageBox.StandardButton.Ok
        )

    def _update_main_features(self, has_credit):
        """Enable/disable fitur utama berdasarkan kredit."""
        # Cari tab CoHost di main window
        if hasattr(self.main_window, 'main_tabs'):
            tabs = self.main_window.main_tabs
            if tabs is not None:  # TAMBAHKAN PENGECEKAN UNTUK MENCEGAH NILAI NONE
                for i in range(tabs.count()):
                    tab_text = tabs.tabText(i)
                    if "Cohost" in tab_text:
                        # Disable tab jika tidak ada kredit
                        tabs.setTabEnabled(i, has_credit)
                        if not has_credit:
                            tabs.setTabToolTip(i, "Kredit habis! Silakan isi ulang.")
    
    def show_history(self):
        """Tampilkan riwayat transaksi."""
        QMessageBox.information(self, "Riwayat", "Fitur riwayat akan segera tersedia dalam versi berikutnya.")
    
    def show_help(self):
        """Tampilkan bantuan."""
        help_text = """
        CARA MENGGUNAKAN SISTEM KREDIT JAM:
        
        1. Beli kredit jam (minimal 100 jam)
        2. Kredit akan otomatis terpotong saat menggunakan fitur
        3. Pemakaian dihitung per menit, dibulatkan ke atas per jam
        4. Mode Demo memberikan waktu 45 menit yang reset setiap hari
        5. Monitor sisa kredit di tab Subscription
        
        TIPS HEMAT KREDIT:
        - Gunakan mode Trigger untuk reply spesifik saja
        - Matikan auto-reply saat tidak diperlukan
        - Manfaatkan paket hemat untuk pembelian besar
        
        MASALAH PEMBAYARAN:
        - Jika halaman pembayaran diblokir oleh Internet Positif,
          gunakan VPN atau hubungi admin untuk bantuan.
        
        Butuh bantuan? Hubungi support@streammateai.com
        """
        
        QMessageBox.information(self, "Bantuan", help_text)

    def start_demo(self):
        """Mulai mode demo dengan validasi server."""
        try:
            # Dapatkan email user
            email = self.cfg.get("user_data", {}).get("email", "")
            if not email:
                QMessageBox.warning(
                    self, "Error", 
                    "Email tidak ditemukan. Silakan login terlebih dahulu."
                )
                return

            # Cek demo availability dari server
            import requests
            try:
                response = requests.post(
                    "http://localhost:8000/api/demo/check",
                    json={"email": email},
                    timeout=10
                )
                
                if response.status_code != 200:
                    QMessageBox.warning(
                        self, "Error Server",
                        "Tidak dapat terhubung ke server validasi demo.\n"
                        "Silakan coba lagi nanti."
                    )
                    return
                
                data = response.json()
                
                if not data.get("can_demo", False):
                    # Parse next reset time untuk tampilan yang lebih user-friendly
                    try:
                        from datetime import datetime, timedelta
                        next_reset = datetime.fromisoformat(data.get("next_reset", ""))
                        now = datetime.now()
                        time_diff = next_reset - now
                        hours = int(time_diff.total_seconds() // 3600)
                        minutes = int((time_diff.total_seconds() % 3600) // 60)
                        
                        QMessageBox.warning(
                            self, "Demo Tidak Tersedia",
                            f"Anda sudah menggunakan demo hari ini.\n"
                            f"Demo akan tersedia lagi dalam {hours} jam {minutes} menit."
                        )
                    except:
                        QMessageBox.warning(
                            self, "Demo Tidak Tersedia",
                            "Anda sudah menggunakan demo hari ini.\n"
                            "Silakan coba lagi besok."
                        )
                    return
                
            except requests.exceptions.RequestException as e:
                print(f"[DEBUG] Server connection error: {e}")
                QMessageBox.warning(
                    self, "Error Koneksi",
                    "Tidak dapat terhubung ke server.\n"
                    "Periksa koneksi internet Anda."
                )
                return

            # Konfirmasi demo
            reply = QMessageBox.question(
                self,
                "Konfirmasi Demo",
                "Mode demo akan aktif selama 30 menit.\n"
                "Setelah itu, aplikasi akan kembali ke layar awal.\n\n"
                "Lanjutkan?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Register demo usage ke server
                try:
                    response = requests.post(
                        "http://localhost:8000/api/demo/register",
                        json={"email": email},
                        timeout=10
                    )
                    
                    if response.status_code != 200:
                        QMessageBox.warning(
                            self, "Error",
                            "Gagal mendaftarkan demo. Silakan coba lagi."
                        )
                        return
                    
                    demo_data = response.json()
                    demo_expire_str = demo_data.get("demo_expires", "")
                    demo_expire = datetime.fromisoformat(demo_expire_str)
                    
                except requests.exceptions.RequestException as e:
                    print(f"[DEBUG] Demo register error: {e}")
                    QMessageBox.warning(
                        self, "Error",
                        "Tidak dapat mendaftarkan demo. Silakan coba lagi."
                    )
                    return

                # Set subscription status untuk demo (sama seperti sebelumnya)
                subscription_data = {
                    "email": email,
                    "package": "basic",
                    "status": "demo",
                    "hours_credit": 0.5,  # 30 menit
                    "hours_used": 0,
                    "start_date": datetime.now().isoformat(),
                    "expire_date": demo_expire_str,
                    "order_id": f"demo-{int(time.time())}",
                    "transaction_status": "demo",
                    "updated_at": datetime.now().isoformat()
                }

                subscription_file = Path("config/subscription_status.json")
                subscription_file.parent.mkdir(parents=True, exist_ok=True)
                subscription_file.write_text(json.dumps(subscription_data, indent=2), encoding="utf-8")

                # Set paket ke basic
                self.cfg.set("paket", "basic")

                # Refresh tampilan
                self.refresh_credit_info(True)

                # Masuk ke aplikasi dengan paket Basic
                QMessageBox.information(
                    self,
                    "Demo Aktif",
                    f"Mode demo aktif selama 30 menit hingga {demo_expire.strftime('%H:%M')}.\n"
                    "Selamat mencoba StreamMate AI!"
                )

                # Pilih paket melalui main_window (sama seperti sebelumnya)
                if hasattr(self, 'main_window') and self.main_window is not None:
                    if hasattr(self.main_window, 'pilih_paket'):
                        self.main_window.pilih_paket("basic")
                    else:
                        print("[ERROR] Metode pilih_paket tidak ditemukan di main_window")
                elif hasattr(self, 'parent') and self.parent is not None:
                    if hasattr(self.parent, 'pilih_paket'):
                        self.parent.pilih_paket("basic")
                    else:
                        print("[ERROR] Metode pilih_paket tidak ditemukan di parent")
                else:
                    print("[ERROR] Tidak dapat menemukan main_window atau parent")

        except Exception as e:
            print(f"[ERROR] Error in start_demo: {e}")
            QMessageBox.critical(
                self, "Error",
                f"Terjadi kesalahan saat memulai demo:\n{str(e)}"
            )

    
    def logout(self):
        """Logout dari aplikasi."""
        reply = QMessageBox.question(
            self, "Konfirmasi Logout",
            "Apakah Anda yakin ingin logout?\n\n"
            "Semua data sesi akan dihapus dan kredit akan direset.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # TAMBAHAN: Hapus subscription_status.json
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists():
                try:
                    
                    print("[INFO] Subscription file dihapus")
                except Exception as e:
                    print(f"[ERROR] Gagal hapus subscription file: {e}")

            # Clear token
            token_path = Path("config/google_token.json")
            if token_path.exists():
                try:
                    token_path.unlink()
                except Exception as e:
                    print(f"[ERROR] Gagal hapus token: {e}")

            # Hapus cache kredit
            credit_cache = Path("temp/license_cache.json")
            if credit_cache.exists():
                try:
                    
                    print("[INFO] License cache dihapus")
                except Exception as e:
                    print(f"[ERROR] Gagal hapus license cache: {e}")

            # Hapus session data
            session_file = Path("temp/current_session.json")
            if session_file.exists():
                try:
                    session_file.unlink()
                    print("[INFO] Session data dihapus")
                except Exception as e:
                    print(f"[ERROR] Gagal hapus session data: {e}")

            # Clear user data dari config
            self.cfg.set("user_data", {})
            self.cfg.set("paket", "")  # Reset paket

            QMessageBox.information(self, "Logout", "Anda berhasil logout dan semua data sesi dihapus.")

            # Kembali ke login tab
            if hasattr(self.main_window, 'stack') and hasattr(self.main_window, 'login_tab'):
                self.main_window.stack.setCurrentWidget(self.main_window.login_tab)
            else:
                # Fallback
                QMessageBox.information(self, "Restart", "Silakan restart aplikasi untuk login kembali.")
    
    def closeEvent(self, event):
        """Handle tab close."""
        self.refresh_timer.stop()
        super().closeEvent(event)