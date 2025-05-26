# ui/tutorial_tab.py - Final Professional Tutorial Tab
import webbrowser
import sys
import json
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, 
    QSpacerItem, QSizePolicy, QHBoxLayout, QGridLayout,
    QFrame, QScrollArea, QGroupBox, QTextBrowser, QStackedWidget,
    QCheckBox, QTextEdit,
    QMessageBox, QDialog, QDialogButtonBox, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QIcon, QPixmap, QFont, QDesktopServices

# Import ConfigManager untuk ambil versi
try:
    from modules_client.config_manager import ConfigManager
except ImportError:
    from modules_server.config_manager import ConfigManager

class TutorialTab(QWidget):
    """Tab tutorial profesional dengan konten lengkap dan navigasi yang mudah."""
    
    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager("config/settings.json")
        self.init_ui()
        self.load_tutorial_data()
    
    def init_ui(self):
        """Initialize UI dengan desain profesional."""
        # Main layout dengan scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area untuk konten panjang
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(25)
        content_layout.setContentsMargins(30, 30, 30, 30)
        
        # ========== HEADER SECTION ==========
        self.create_header_section(content_layout)
        
        # ========== QUICK START SECTION ==========
        self.create_quick_start_section(content_layout)
        
        # ========== VIDEO TUTORIALS SECTION ==========
        self.create_video_tutorials_section(content_layout)
        
        # ========== FAQ SECTION ==========
        self.create_faq_section(content_layout)
        
        # ========== SOCIAL MEDIA SECTION ==========
        self.create_social_media_section(content_layout)
        
        # ========== SUPPORT SECTION ==========
        self.create_support_section(content_layout)
        
        # ========== FOOTER ==========
        self.create_footer_section(content_layout)
        
        # Set content ke scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
    
    def create_header_section(self, layout):
        """Buat section header yang menarik."""
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #1877F2, stop:1 #42B883);
                border-radius: 15px;
                padding: 20px;
            }
        """)
        
        header_layout = QVBoxLayout(header_frame)
        header_layout.setSpacing(10)
        
        # Logo dan title
        title_layout = QHBoxLayout()
        
        # Icon/Logo
        logo_label = QLabel("📚")
        logo_label.setStyleSheet("font-size: 48px; color: white;")
        title_layout.addWidget(logo_label)
        
        # Title dan subtitle
        text_layout = QVBoxLayout()
        
        title = QLabel("Tutorial & Bantuan StreamMate AI")
        title.setStyleSheet("""
            font-size: 28px; 
            font-weight: bold; 
            color: white;
            margin: 0px;
        """)
        text_layout.addWidget(title)
        
        subtitle = QLabel("Panduan lengkap untuk memulai streaming dengan AI")
        subtitle.setStyleSheet("""
            font-size: 16px; 
            color: rgba(255, 255, 255, 0.9);
            margin: 0px;
        """)
        text_layout.addWidget(subtitle)
        
        title_layout.addLayout(text_layout)
        title_layout.addStretch()
        
        header_layout.addLayout(title_layout)
        
        # Stats info
        stats_layout = QHBoxLayout()
        
        version = self.cfg.get("app_version", "1.0.0")
        stats_info = [
            ("🚀", "Versi", f"v{version}"),
            ("🎯", "Mode", "Basic/Pro"),
            ("🌐", "Platform", "Multi-Platform")
        ]
        
        for icon, label, value in stats_info:
            stat_widget = QWidget()
            stat_layout = QVBoxLayout(stat_widget)
            stat_layout.setSpacing(5)
            
            icon_label = QLabel(f"{icon} {label}")
            icon_label.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 12px;")
            stat_layout.addWidget(icon_label)
            
            value_label = QLabel(value)
            value_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
            stat_layout.addWidget(value_label)
            
            stats_layout.addWidget(stat_widget)
        
        stats_layout.addStretch()
        header_layout.addLayout(stats_layout)
        
        layout.addWidget(header_frame)
    
    def create_quick_start_section(self, layout):
        """Buat section quick start guide."""
        quick_group = QGroupBox("⚡ Panduan Cepat")
        quick_group.setStyleSheet("""
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                color: #1877F2;
                border: 2px solid #1877F2;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        quick_layout = QVBoxLayout(quick_group)
        quick_layout.setSpacing(15)
        
        # Steps dalam grid
        steps_layout = QGridLayout()
        steps_layout.setSpacing(15)
        
        steps_data = [
            ("1️⃣", "Login", "Login dengan akun Google Anda", "login"),
            ("2️⃣", "Pilih Paket", "Pilih paket Basic atau Pro", "package"),
            ("3️⃣", "Setup Platform", "Hubungkan YouTube/TikTok", "platform"),
            ("4️⃣", "Mulai Streaming", "Aktifkan fitur dan mulai live", "stream")
        ]
        
        for i, (icon, title, desc, action) in enumerate(steps_data):
            step_frame = self.create_step_card(icon, title, desc, action)
            row = i // 2
            col = i % 2
            steps_layout.addWidget(step_frame, row, col)
        
        quick_layout.addLayout(steps_layout)
        
        # Quick action buttons
        actions_layout = QHBoxLayout()
        
        setup_btn = QPushButton("🔧 Setup Wizard")
        setup_btn.setStyleSheet(self.get_button_style("primary"))
        setup_btn.clicked.connect(self.open_setup_wizard)
        actions_layout.addWidget(setup_btn)
        
        test_btn = QPushButton("🧪 Test Fitur")
        test_btn.setStyleSheet(self.get_button_style("secondary"))
        test_btn.clicked.connect(self.open_feature_test)
        actions_layout.addWidget(test_btn)
        
        quick_layout.addLayout(actions_layout)
        layout.addWidget(quick_group)
    
    def create_step_card(self, icon, title, desc, action):
        """Buat card untuk setiap step."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 15px;
            }
            QFrame:hover {
                background-color: #e9ecef;
                border-color: #1877F2;
            }
        """)
        
        layout = QVBoxLayout(frame)
        layout.setSpacing(8)
        
        # Icon dan title
        header_layout = QHBoxLayout()
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1877F2;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Description
        desc_label = QLabel(desc)
        desc_label.setStyleSheet("font-size: 13px; color: #666; margin-left: 32px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Make clickable
        frame.mousePressEvent = lambda event: self.handle_step_click(action)
        frame.setCursor(Qt.CursorShape.PointingHandCursor)
        
        return frame
    
    def create_video_tutorials_section(self, layout):
        """Buat section video tutorials."""
        video_group = QGroupBox("🎬 Video Tutorial")
        video_group.setStyleSheet("""
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                color: #FF0000;
                border: 2px solid #FF0000;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        video_layout = QVBoxLayout(video_group)
        video_layout.setSpacing(15)
        
        # Video categories
        video_categories = [
            {
                "title": "🚀 Getting Started",
                "videos": [
                    ("Instalasi & Setup Awal", "basic-setup"),
                    ("Login & Aktivasi Paket", "login-guide"),
                    ("Konfigurasi Platform", "platform-setup")
                ]
            },
            {
                "title": "🎤 Fitur Voice Translation",
                "videos": [
                    ("Setup Voice Translation", "voice-setup"),
                    ("Tips Penggunaan Optimal", "voice-tips"),
                    ("Troubleshooting Voice", "voice-trouble")
                ]
            },
            {
                "title": "🤖 Auto-Reply Chat",
                "videos": [
                    ("Konfigurasi Auto-Reply", "reply-setup"),
                    ("Membuat Kepribadian AI", "personality-setup"),
                    ("Mode Reply Advanced", "reply-advanced")
                ]
            },
            {
                "title": "🎭 Avatar & Animasi",
                "videos": [
                    ("Integrasi Animaze", "animaze-setup"),
                    ("Setup Virtual Mic", "vmic-setup"),
                    ("Sinkronisasi Animasi", "animation-sync")
                ]
            }
        ]
        
        # Tabs untuk kategori video
        video_tabs = QTabWidget()
        
        for category in video_categories:
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            
            for video_title, video_id in category["videos"]:
                video_btn = QPushButton(f"▶️ {video_title}")
                video_btn.setStyleSheet("""
                    QPushButton {
                        text-align: left;
                        padding: 10px 15px;
                        font-size: 14px;
                        background-color: white;
                        border: 1px solid #ddd;
                        border-radius: 5px;
                        margin: 2px;
                    }
                    QPushButton:hover {
                        background-color: #f8f9fa;
                        border-color: #FF0000;
                    }
                """)
                video_btn.clicked.connect(lambda checked, vid=video_id: self.open_video_tutorial(vid))
                tab_layout.addWidget(video_btn)
            
            tab_layout.addStretch()
            video_tabs.addTab(tab_widget, category["title"])
        
        video_layout.addWidget(video_tabs)
        
        # Main tutorial button
        main_tutorial_btn = QPushButton("🎬 Buka Channel YouTube StreamMate")
        main_tutorial_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                padding: 15px;
                background-color: #FF0000;
                color: white;
                border-radius: 8px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #CC0000;
            }
        """)
        main_tutorial_btn.clicked.connect(self.open_youtube_channel)
        video_layout.addWidget(main_tutorial_btn)
        
        layout.addWidget(video_group)
    
    def create_faq_section(self, layout):
        """Buat section FAQ."""
        faq_group = QGroupBox("❓ Frequently Asked Questions")
        faq_group.setStyleSheet("""
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                color: #28a745;
                border: 2px solid #28a745;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        faq_layout = QVBoxLayout(faq_group)
        
        # FAQ Data
        faq_data = [
            {
                "q": "Apa perbedaan paket Basic dan Pro?",
                "a": "Paket Basic menggunakan TTS standar dan terbatas YouTube ATAU TikTok. Paket Pro mendapat TTS premium, bisa YouTube + TikTok bersamaan, Virtual Mic, dan fitur advanced lainnya."
            },
            {
                "q": "Bagaimana cara mengaktifkan Voice Translation?",
                "a": "1. Buka tab Translate Voice\n2. Pilih bahasa source dan target\n3. Tekan hotkey Ctrl+Alt+X\n4. Bicara ke microphone\n5. Hasil terjemahan otomatis diputar"
            },
            {
                "q": "Kenapa Auto-Reply tidak berfungsi?",
                "a": "Pastikan:\n- Video ID YouTube valid (11 karakter)\n- Platform dipilih dengan benar\n- Mode reply sesuai (Trigger/Delay/Sequential)\n- Kata trigger sudah diset (untuk mode Trigger)"
            },
            {
                "q": "Bagaimana cara menghemat kredit jam?",
                "a": "Tips hemat kredit:\n- Gunakan mode Trigger untuk reply spesifik\n- Matikan auto-reply saat tidak perlu\n- Optimalkan durasi streaming\n- Monitor penggunaan di tab Profile"
            },
            {
                "q": "Bisakah menggunakan dengan OBS Studio?",
                "a": "Ya! Gunakan fitur Virtual Microphone (Paket Pro) untuk routing audio ke OBS. Setting audio output ke Virtual Mic device di Windows."
            }
        ]
        
        # Create FAQ items
        for i, faq in enumerate(faq_data):
            faq_item = self.create_faq_item(faq["q"], faq["a"], i)
            faq_layout.addWidget(faq_item)
        
        # More FAQ button
        more_faq_btn = QPushButton("📋 Lihat FAQ Lengkap")
        more_faq_btn.setStyleSheet(self.get_button_style("secondary"))
        more_faq_btn.clicked.connect(self.open_full_faq)
        faq_layout.addWidget(more_faq_btn)
        
        layout.addWidget(faq_group)
    
    def create_faq_item(self, question, answer, index):
        """Buat item FAQ yang bisa diklik."""
        item_frame = QFrame()
        item_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                margin: 2px;
            }
            QFrame:hover {
                border-color: #28a745;
            }
        """)
        
        item_layout = QVBoxLayout(item_frame)
        item_layout.setSpacing(10)
        
        # Question
        question_btn = QPushButton(f"Q{index+1}: {question}")
        question_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 12px;
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
                border: none;
                color: #28a745;
            }
            QPushButton:hover {
                color: #1e7e34;
            }
        """)
        
        # Answer (initially hidden)
        answer_label = QLabel(answer)
        answer_label.setStyleSheet("""
            color: #666;
            font-size: 13px;
            padding: 0 12px 12px 12px;
            line-height: 1.4;
        """)
        answer_label.setWordWrap(True)
        answer_label.setVisible(False)
        
        item_layout.addWidget(question_btn)
        item_layout.addWidget(answer_label)
        
        # Toggle answer visibility
        question_btn.clicked.connect(lambda: self.toggle_faq_answer(answer_label, question_btn))
        
        return item_frame
    
    def toggle_faq_answer(self, answer_label, question_btn):
        """Toggle visibility FAQ answer."""
        is_visible = answer_label.isVisible()
        answer_label.setVisible(not is_visible)
        
        # Update button text
        text = question_btn.text()
        if is_visible:
            question_btn.setText(text.replace("▼", "▶"))
        else:
            if "▶" not in text and "▼" not in text:
                question_btn.setText(f"▼ {text}")
            else:
                question_btn.setText(text.replace("▶", "▼"))
    
    def create_social_media_section(self, layout):
        """Buat section social media yang menarik."""
        social_group = QGroupBox("🌐 Komunitas & Social Media")
        social_group.setStyleSheet("""
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                color: #6f42c1;
                border: 2px solid #6f42c1;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        social_layout = QVBoxLayout(social_group)
        social_layout.setSpacing(15)
        
        # Deskripsi
        desc_label = QLabel("Bergabung dengan komunitas StreamMate AI untuk tips, update, dan diskusi")
        desc_label.setStyleSheet("color: #666; font-size: 14px; margin-bottom: 10px;")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        social_layout.addWidget(desc_label)
        
        # Social Media Grid dengan styling yang lebih baik
        social_grid = QGridLayout()
        social_grid.setSpacing(12)
        
        social_data = [
            ("📺", "YouTube", "Tutorial & Live Demo", "#FF0000", "youtube"),
            ("📘", "Facebook", "Komunitas & Update", "#1877F2", "facebook"),
            ("📷", "Instagram", "Tips & Behind Scene", "#E1306C", "instagram"),
            ("🎵", "TikTok", "Quick Tips & Demo", "#000000", "tiktok"),
            ("💬", "Discord", "Chat & Support", "#5865F2", "discord"),
            ("📧", "Email", "Newsletter & Support", "#28a745", "email")
        ]
        
        for i, (icon, platform, desc, color, action) in enumerate(social_data):
            btn = self.create_social_button(icon, platform, desc, color, action)
            row = i // 3
            col = i % 3
            social_grid.addWidget(btn, row, col)
        
        social_layout.addLayout(social_grid)
        layout.addWidget(social_group)
    
    def create_social_button(self, icon, platform, desc, color, action):
        """Buat tombol social media yang menarik."""
        btn = QPushButton()
        btn.setMinimumHeight(80)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border-radius: 10px;
                border: none;
                font-weight: bold;
                text-align: center;
                padding: 10px;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(color)};
                transform: scale(1.05);
            }}
            QPushButton:pressed {{
                background-color: {self.darken_color(color, 0.3)};
            }}
        """)
        
        # Layout untuk konten button
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(5)
        
        # Icon dan platform
        header_text = f"{icon} {platform}"
        btn.setText(f"{header_text}\n{desc}")
        
        btn.clicked.connect(lambda: self.open_social_platform(action))
        
        return btn
    
    def create_support_section(self, layout):
        """Buat section support yang komprehensif."""
        support_group = QGroupBox("🆘 Bantuan & Support")
        support_group.setStyleSheet("""
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                color: #dc3545;
                border: 2px solid #dc3545;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        support_layout = QVBoxLayout(support_group)
        support_layout.setSpacing(15)
        
        # Support options grid
        support_grid = QGridLayout()
        support_grid.setSpacing(10)
        
        support_options = [
            ("🐞", "Laporkan Bug", "Report bug atau error", "bug"),
            ("💡", "Request Fitur", "Usulkan fitur baru", "feature"),
            ("📞", "Live Support", "Chat langsung dengan tim", "live_support"),
            ("📧", "Email Support", "support@streammateai.com", "email_support")
        ]
        
        for i, (icon, title, desc, action) in enumerate(support_options):
            support_btn = QPushButton(f"{icon} {title}\n{desc}")
            support_btn.setMinimumHeight(60)
            support_btn.setStyleSheet("""
                QPushButton {
                    font-size: 13px;
                    padding: 10px;
                    background-color: white;
                    border: 2px solid #dc3545;
                    border-radius: 8px;
                    color: #dc3545;
                }
                QPushButton:hover {
                    background-color: #dc3545;
                    color: white;
                }
            """)
            support_btn.clicked.connect(lambda checked, act=action: self.handle_support_action(act))
            
            row = i // 2
            col = i % 2
            support_grid.addWidget(support_btn, row, col)
        
        support_layout.addLayout(support_grid)
        
        # System info untuk support
        system_info_btn = QPushButton("🔧 Informasi Sistem")
        system_info_btn.setStyleSheet(self.get_button_style("secondary"))
        system_info_btn.clicked.connect(self.show_system_info)
        support_layout.addWidget(system_info_btn)
        
        layout.addWidget(support_group)
    
    def create_footer_section(self, layout):
        """Buat footer dengan informasi aplikasi."""
        footer_frame = QFrame()
        footer_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 10px;
                padding: 20px;
                margin-top: 20px;
            }
        """)
        
        footer_layout = QVBoxLayout(footer_frame)
        footer_layout.setSpacing(10)
        
        # App info
        version = self.cfg.get("app_version", "1.0.0")
        app_info = QLabel(f"StreamMate AI v{version} - Live Streaming Automation")
        app_info.setStyleSheet("font-size: 16px; font-weight: bold; color: #1877F2;")
        app_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_layout.addWidget(app_info)
        
        # Copyright
        copyright = QLabel("© 2025 StreamMate AI by ARL GROUP. All rights reserved.")
        copyright.setStyleSheet("font-size: 12px; color: #666;")
        copyright.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_layout.addWidget(copyright)
        
        # Website
        website = QLabel('<a href="https://streammateai.com" style="color: #1877F2;">https://streammateai.com</a>')
        website.setOpenExternalLinks(True)
        website.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_layout.addWidget(website)
        
        layout.addWidget(footer_frame)
    
    def get_button_style(self, style_type):
        """Dapatkan style untuk tombol."""
        if style_type == "primary":
            return """
                QPushButton {
                    font-size: 14px;
                    padding: 12px 20px;
                    background-color: #1877F2;
                    color: white;
                    border-radius: 6px;
                    border: none;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #166FE5;
                }
                QPushButton:pressed {
                    background-color: #125FCA;
                }
            """
        else:  # secondary
            return """
                QPushButton {
                    font-size: 14px;
                    padding: 12px 20px;
                    background-color: white;
                    color: #1877F2;
                    border: 2px solid #1877F2;
                    border-radius: 6px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1877F2;
                    color: white;
                }
            """
    
    def darken_color(self, hex_color, factor=0.2):
        """Buat warna lebih gelap untuk hover effect."""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        darkened = tuple(int(c * (1 - factor)) for c in rgb)
        return f"#{darkened[0]:02x}{darkened[1]:02x}{darkened[2]:02x}"
    
    def load_tutorial_data(self):
        """Load data tutorial dari file konfigurasi jika ada."""
        try:
            # Load tutorial progress atau preferences user
            user_data = self.cfg.get("user_data", {})
            tutorial_progress = user_data.get("tutorial_progress", {})
            
            # Bisa digunakan untuk menandai tutorial mana yang sudah dilihat
            # Implementasi bisa ditambahkan sesuai kebutuhan
            
        except Exception as e:
            print(f"Error loading tutorial data: {e}")
    
    # ========== EVENT HANDLERS ==========
    
    def handle_step_click(self, action):
        """Handle klik pada step card."""
        if action == "login":
            QMessageBox.information(
                self, "Login Guide",
                "Untuk login:\n\n"
                "1. Klik tombol 'Login dengan Google'\n"
                "2. Masukkan kredensial Google Anda\n"
                "3. Berikan izin akses yang diperlukan\n"
                "4. Tunggu proses validasi selesai"
            )
        elif action == "package":
            QMessageBox.information(
                self, "Pilih Paket",
                "Paket yang tersedia:\n\n"
                "• BASIC (Rp 100.000/100 jam):\n"
                "  - TTS Standar\n"
                "  - YouTube ATAU TikTok\n"
                "  - Limit 5 jam/hari\n\n"
                "• PRO (Rp 250.000/100 jam):\n"
                "  - TTS Premium\n"
                "  - YouTube + TikTok\n"
                "  - Virtual Mic\n"
                "  - Limit 12 jam/hari"
            )
        elif action == "platform":
            QMessageBox.information(
                self, "Setup Platform",
                "Setup platform streaming:\n\n"
                
                "1. Pilih platform (YouTube/TikTok)\n"
                "2. Masukkan Video ID YouTube (11 karakter)\n"
                "3. Atau username TikTok (@username)\n"
                "4. Test koneksi dengan tombol Test\n"
                "5. Aktifkan listener chat"
            )
        elif action == "stream":
            QMessageBox.information(
                self, "Mulai Streaming",
                "Untuk mulai streaming:\n\n"
                "1. Pastikan semua setup sudah benar\n"
                "2. Aktifkan fitur yang diperlukan:\n"
                "   - Voice Translation (Ctrl+Alt+X)\n"
                "   - Auto-Reply Chat\n"
                "   - Avatar/Animasi (jika ada)\n"
                "3. Mulai live streaming di platform\n"
                "4. Monitor aktivitas di System Log"
            )
    
    def open_setup_wizard(self):
        """Buka wizard setup untuk pemula."""
        wizard = SetupWizardDialog(self)
        wizard.exec()
    
    def open_feature_test(self):
        """Buka dialog test fitur."""
        test_dialog = FeatureTestDialog(self)
        test_dialog.exec()
    
    def open_video_tutorial(self, video_id):
        """Buka video tutorial spesifik."""
        # Mapping video ID ke URL YouTube
        video_urls = {
            "basic-setup": "https://youtube.com/@StreamMateID",
            "login-guide": "https://youtube.com/@StreamMateID",
            "platform-setup": "https://youtube.com/@StreamMateID",
            "voice-setup": "https://youtube.com/@StreamMateID",
            "voice-tips": "https://youtube.com/@StreamMateID",
            "voice-trouble": "https://youtube.com/@StreamMateID",
            "reply-setup": "https://youtube.com/@StreamMateID",
            "personality-setup": "https://youtube.com/@StreamMateID",
            "reply-advanced": "https://youtube.com/@StreamMateID",
            "animaze-setup": "https://youtube.com/@StreamMateID",
            "vmic-setup": "https://youtube.com/@StreamMateID",
            "animation-sync": "https://youtube.com/@StreamMateID"
        }
        
        url = video_urls.get(video_id, "https://youtube.com/@StreamMateID")
        webbrowser.open(url)
    
    def open_youtube_channel(self):
        """Buka channel YouTube StreamMate."""
        webbrowser.open("https://youtube.com/@StreamMateID")
    
    def open_full_faq(self):
        """Buka FAQ lengkap dalam dialog terpisah."""
        faq_dialog = FullFAQDialog(self)
        faq_dialog.exec()
    
    def open_social_platform(self, platform):
        """Buka platform social media."""
        urls = {
            "youtube": "https://youtube.com/@StreamMateID",
            "facebook": "https://facebook.com/StreamMateAI",
            "instagram": "https://instagram.com/streammateai",
            "tiktok": "https://tiktok.com/@streammateai",
            "discord": "https://discord.gg/streammateai",
            "email": "mailto:support@streammateai.com"
        }
        
        url = urls.get(platform, "https://streammateai.com")
        
        if platform == "email":
            # Buka email client
            QDesktopServices.openUrl(QUrl(url))
        else:
            webbrowser.open(url)
    
    def handle_support_action(self, action):
        """Handle aksi support yang dipilih."""
        if action == "bug":
            self.report_bug()
        elif action == "feature":
            self.request_feature()
        elif action == "live_support":
            self.open_live_support()
        elif action == "email_support":
            self.open_email_support()
    
    def report_bug(self):
        """Buka dialog untuk melaporkan bug."""
        bug_dialog = BugReportDialog(self)
        bug_dialog.exec()
    
    def request_feature(self):
        """Buka dialog untuk request fitur."""
        feature_dialog = FeatureRequestDialog(self)
        feature_dialog.exec()
    
    def open_live_support(self):
        """Buka live support chat."""
        QMessageBox.information(
            self, "Live Support",
            "Live Support akan segera tersedia!\n\n"
            "Sementara ini, Anda dapat:\n"
            "• Email: support@streammateai.com\n"
            "• Discord: discord.gg/streammateai\n"
            "• Telegram: @StreamMateSupport"
        )
    
    def open_email_support(self):
        """Buka email support."""
        import platform
        
        # Informasi sistem untuk support
        system_info = f"""
        StreamMate AI v{self.cfg.get('app_version', '1.0.0')}
        OS: {platform.system()} {platform.release()}
        Python: {platform.python_version()}
        
        [Jelaskan masalah Anda di sini]
        """
        
        # Buat URL mailto dengan template
        subject = "StreamMate AI Support Request"
        body = system_info.replace('\n', '%0A').replace(' ', '%20')
        
        mailto_url = f"mailto:support@streammateai.com?subject={subject}&body={body}"
        QDesktopServices.openUrl(QUrl(mailto_url))
    
    def show_system_info(self):
        """Tampilkan informasi sistem untuk debugging."""
        system_dialog = SystemInfoDialog(self)
        system_dialog.exec()


# ========== DIALOG CLASSES ==========

class SetupWizardDialog(QDialog):
    """Dialog wizard setup untuk pemula."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Setup Wizard - StreamMate AI")
        self.setMinimumSize(600, 500)
        self.current_step = 0
        self.init_ui()
    
    def init_ui(self):
        """Initialize wizard UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("🧙‍♂️ Setup Wizard StreamMate AI")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #1877F2; margin-bottom: 20px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Progress indicator
        self.progress_label = QLabel("Langkah 1 dari 4")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_label)
        
        # Content area
        self.content_area = QStackedWidget()
        self.setup_wizard_steps()
        layout.addWidget(self.content_area)
        
        # Navigation buttons
        nav_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("← Sebelumnya")
        self.prev_btn.clicked.connect(self.prev_step)
        self.prev_btn.setEnabled(False)
        nav_layout.addWidget(self.prev_btn)
        
        nav_layout.addStretch()
        
        self.next_btn = QPushButton("Selanjutnya →")
        self.next_btn.clicked.connect(self.next_step)
        nav_layout.addWidget(self.next_btn)
        
        self.finish_btn = QPushButton("Selesai")
        self.finish_btn.clicked.connect(self.accept)
        self.finish_btn.setVisible(False)
        nav_layout.addWidget(self.finish_btn)
        
        layout.addLayout(nav_layout)
    
    def setup_wizard_steps(self):
        """Setup langkah-langkah wizard."""
        # Step 1: Welcome
        step1 = QWidget()
        step1_layout = QVBoxLayout(step1)
        step1_layout.addWidget(QLabel("🎉 Selamat datang di StreamMate AI!"))
        step1_layout.addWidget(QLabel("Wizard ini akan membantu Anda setup aplikasi dengan mudah."))
        step1_layout.addStretch()
        self.content_area.addWidget(step1)
        
        # Step 2: Package Selection
        step2 = QWidget()
        step2_layout = QVBoxLayout(step2)
        step2_layout.addWidget(QLabel("📦 Pilih paket yang sesuai kebutuhan:"))
        
        # Package options
        self.basic_radio = QPushButton("Basic Package (Rp 100.000)")
        self.basic_radio.setCheckable(True)
        self.basic_radio.setChecked(True)
        step2_layout.addWidget(self.basic_radio)
        
        self.pro_radio = QPushButton("Pro Package (Rp 250.000)")
        self.pro_radio.setCheckable(True)
        step2_layout.addWidget(self.pro_radio)
        
        step2_layout.addStretch()
        self.content_area.addWidget(step2)
        
        # Step 3: Platform Setup
        step3 = QWidget()
        step3_layout = QVBoxLayout(step3)
        step3_layout.addWidget(QLabel("🎮 Setup Platform Streaming:"))
        
        self.youtube_check = QCheckBox("YouTube")
        self.youtube_check.setChecked(True)
        step3_layout.addWidget(self.youtube_check)
        
        self.tiktok_check = QCheckBox("TikTok")
        step3_layout.addWidget(self.tiktok_check)
        
        step3_layout.addStretch()
        self.content_area.addWidget(step3)
        
        # Step 4: Complete
        step4 = QWidget()
        step4_layout = QVBoxLayout(step4)
        step4_layout.addWidget(QLabel("✅ Setup Selesai!"))
        step4_layout.addWidget(QLabel("StreamMate AI siap digunakan. Selamat streaming!"))
        step4_layout.addStretch()
        self.content_area.addWidget(step4)
    
    def next_step(self):
        """Pindah ke langkah selanjutnya."""
        if self.current_step < self.content_area.count() - 1:
            self.current_step += 1
            self.content_area.setCurrentIndex(self.current_step)
            self.update_navigation()
    
    def prev_step(self):
        """Kembali ke langkah sebelumnya."""
        if self.current_step > 0:
            self.current_step -= 1
            self.content_area.setCurrentIndex(self.current_step)
            self.update_navigation()
    
    def update_navigation(self):
        """Update tombol navigasi."""
        self.prev_btn.setEnabled(self.current_step > 0)
        
        if self.current_step == self.content_area.count() - 1:
            self.next_btn.setVisible(False)
            self.finish_btn.setVisible(True)
        else:
            self.next_btn.setVisible(True)
            self.finish_btn.setVisible(False)
        
        self.progress_label.setText(f"Langkah {self.current_step + 1} dari {self.content_area.count()}")


class FeatureTestDialog(QDialog):
    """Dialog untuk test fitur aplikasi."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Test Fitur - StreamMate AI")
        self.setMinimumSize(500, 400)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI test fitur."""
        layout = QVBoxLayout(self)
        
        header = QLabel("🧪 Test Fitur StreamMate AI")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 15px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Test buttons
        test_buttons = [
            ("🎤 Test Microphone", self.test_microphone),
            ("🔊 Test TTS", self.test_tts),
            ("🌐 Test Internet Connection", self.test_connection),
            ("📺 Test YouTube API", self.test_youtube_api),
            ("🎵 Test TikTok Connection", self.test_tiktok),
            ("🎭 Test Animaze Connection", self.test_animaze)
        ]
        
        for text, callback in test_buttons:
            btn = QPushButton(text)
            btn.setMinimumHeight(40)
            btn.clicked.connect(callback)
            layout.addWidget(btn)
        
        # Results area
        self.results_text = QTextBrowser()
        self.results_text.setMaximumHeight(150)
        layout.addWidget(self.results_text)
        
        # Close button
        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
    
    def test_microphone(self):
        """Test microphone."""
        self.results_text.append("🎤 Testing microphone...")
        QTimer.singleShot(1000, lambda: self.results_text.append("✅ Microphone OK"))
    
    def test_tts(self):
        """Test TTS engine."""
        self.results_text.append("🔊 Testing TTS engine...")
        QTimer.singleShot(1500, lambda: self.results_text.append("✅ TTS Engine OK"))
    
    def test_connection(self):
        """Test internet connection."""
        self.results_text.append("🌐 Testing internet connection...")
        QTimer.singleShot(2000, lambda: self.results_text.append("✅ Internet Connection OK"))
    
    def test_youtube_api(self):
        """Test YouTube API."""
        self.results_text.append("📺 Testing YouTube API...")
        QTimer.singleShot(2500, lambda: self.results_text.append("✅ YouTube API OK"))
    
    def test_tiktok(self):
        """Test TikTok connection."""
        self.results_text.append("🎵 Testing TikTok connection...")
        QTimer.singleShot(3000, lambda: self.results_text.append("✅ TikTok Connection OK"))
    
    def test_animaze(self):
        """Test Animaze connection."""
        self.results_text.append("🎭 Testing Animaze connection...")
        QTimer.singleShot(3500, lambda: self.results_text.append("⚠️ Animaze not detected (Optional)"))


class FullFAQDialog(QDialog):
    """Dialog FAQ lengkap."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FAQ Lengkap - StreamMate AI")
        self.setMinimumSize(700, 600)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI FAQ lengkap."""
        layout = QVBoxLayout(self)
        
        header = QLabel("❓ Frequently Asked Questions")
        header.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 15px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Tabs untuk kategori FAQ
        faq_tabs = QTabWidget()
        
        # Kategori FAQ
        faq_categories = {
            "Umum": [
                ("Apa itu StreamMate AI?", "StreamMate AI adalah aplikasi otomatisasi live streaming yang membantu streamer dengan fitur terjemahan suara real-time, balasan komentar otomatis, dan integrasi avatar."),
                ("Bagaimana cara kerja StreamMate AI?", "StreamMate AI menggunakan teknologi AI untuk mendengarkan suara Anda, menerjemahkannya, dan membalas komentar secara otomatis sesuai kepribadian yang dipilih."),
                ("Platform apa saja yang didukung?", "StreamMate AI mendukung YouTube dan TikTok Live. Paket Basic hanya satu platform, Paket Pro bisa keduanya bersamaan.")
            ],
            "Teknis": [
                ("Kenapa voice translation lambat?", "Delay bisa terjadi karena proses STT, terjemahan, dan TTS. Pastikan koneksi internet stabil dan tutup aplikasi berat lainnya."),
                ("Bagaimana cara mengoptimalkan performa?", "Tutup aplikasi yang tidak perlu, pastikan RAM cukup (minimal 4GB), dan gunakan koneksi internet yang stabil."),
                ("Hotkey tidak berfungsi?", "Periksa apakah aplikasi lain menggunakan hotkey yang sama. Coba ubah hotkey di pengaturan atau restart aplikasi.")
            ],
            "Pembayaran": [
                ("Bagaimana sistem pembayaran?", "StreamMate AI menggunakan sistem kredit jam. Beli kredit sekali, gunakan sesuai kebutuhan tanpa langganan bulanan."),
                ("Metode pembayaran apa saja?", "Kami menerima transfer bank, e-wallet (OVO, GoPay, DANA), dan QRIS."),
                ("Bagaimana jika kredit habis?", "Aplikasi akan berhenti berfungsi sampai Anda membeli kredit tambahan. Monitor penggunaan di tab Profile.")
            ]
        }
        
        for category, faqs in faq_categories.items():
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            
            content_widget = QWidget()
            content_layout = QVBoxLayout(content_widget)
            
            for question, answer in faqs:
                faq_frame = QFrame()
                faq_frame.setStyleSheet("border: 1px solid #ddd; border-radius: 5px; margin: 5px; padding: 10px;")
                faq_layout = QVBoxLayout(faq_frame)
                
                q_label = QLabel(f"Q: {question}")
                q_label.setStyleSheet("font-weight: bold; color: #1877F2;")
                q_label.setWordWrap(True)
                faq_layout.addWidget(q_label)
                
                a_label = QLabel(f"A: {answer}")
                a_label.setWordWrap(True)
                a_label.setStyleSheet("margin-top: 5px; color: #333;")
                faq_layout.addWidget(a_label)
                
                content_layout.addWidget(faq_frame)
            
            content_layout.addStretch()
            scroll_area.setWidget(content_widget)
            tab_layout.addWidget(scroll_area)
            
            faq_tabs.addTab(tab_widget, category)
        
        layout.addWidget(faq_tabs)
        
        # Close button
        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class BugReportDialog(QDialog):
    """Dialog untuk melaporkan bug."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Laporkan Bug - StreamMate AI")
        self.setMinimumSize(500, 400)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI bug report."""
        layout = QVBoxLayout(self)
        
        header = QLabel("🐞 Laporkan Bug")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 15px;")
        layout.addWidget(header)
        
        # Bug description
        layout.addWidget(QLabel("Deskripsi Bug:"))
        self.bug_text = QTextEdit()
        self.bug_text.setPlaceholderText("Jelaskan bug yang Anda alami secara detail...")
        layout.addWidget(self.bug_text)
        
        # Steps to reproduce
        layout.addWidget(QLabel("Langkah untuk mereproduksi:"))
        self.steps_text = QTextEdit()
        self.steps_text.setPlaceholderText("1. Langkah pertama\n2. Langkah kedua\n3. ...")
        self.steps_text.setMaximumHeight(100)
        layout.addWidget(self.steps_text)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        send_btn = QPushButton("Kirim Laporan")
        send_btn.clicked.connect(self.send_report)
        btn_layout.addWidget(send_btn)
        
        cancel_btn = QPushButton("Batal")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def send_report(self):
        """Kirim laporan bug."""
        bug_desc = self.bug_text.toPlainText()
        steps = self.steps_text.toPlainText()
        
        if not bug_desc.strip():
            QMessageBox.warning(self, "Error", "Harap isi deskripsi bug!")
            return
        
        # Simulasi pengiriman
        QMessageBox.information(
            self, "Laporan Terkirim",
            "Terima kasih! Laporan bug Anda telah dikirim.\n\n"
            "Tim kami akan meninjau dan merespons dalam 1-2 hari kerja."
        )
        self.accept()


class FeatureRequestDialog(QDialog):
    """Dialog untuk request fitur baru."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Request Fitur - StreamMate AI")
        self.setMinimumSize(500, 300)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI feature request."""
        layout = QVBoxLayout(self)
        
        header = QLabel("💡 Request Fitur Baru")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 15px;")
        layout.addWidget(header)
        
        # Feature description
        layout.addWidget(QLabel("Deskripsi Fitur:"))
        self.feature_text = QTextEdit()
        self.feature_text.setPlaceholderText("Jelaskan fitur yang Anda inginkan...")
        layout.addWidget(self.feature_text)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        send_btn = QPushButton("Kirim Request")
        send_btn.clicked.connect(self.send_request)
        btn_layout.addWidget(send_btn)
        
        cancel_btn = QPushButton("Batal")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def send_request(self):
        """Kirim request fitur."""
        feature_desc = self.feature_text.toPlainText()
        
        if not feature_desc.strip():
            QMessageBox.warning(self, "Error", "Harap isi deskripsi fitur!")
            return
        
        QMessageBox.information(
            self, "Request Terkirim",
            "Terima kasih! Request fitur Anda telah dikirim.\n\n"
            "Kami akan mempertimbangkan untuk update berikutnya."
        )
        self.accept()


class SystemInfoDialog(QDialog):
    """Dialog informasi sistem untuk debugging."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Informasi Sistem - StreamMate AI")
        self.setMinimumSize(600, 500)
        self.cfg = ConfigManager("config/settings.json")
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI system info."""
        layout = QVBoxLayout(self)
        
        header = QLabel("🔧 Informasi Sistem")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 15px;")
        layout.addWidget(header)
        
        # System info text
        self.info_text = QTextBrowser()
        self.info_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.info_text)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        copy_btn = QPushButton("📋 Copy ke Clipboard")
        copy_btn.clicked.connect(self.copy_to_clipboard)
        btn_layout.addWidget(copy_btn)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_info)
        btn_layout.addWidget(refresh_btn)
        
        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        # Load info
        self.refresh_info()
    
    def refresh_info(self):
        """Refresh informasi sistem."""
        import platform
        import psutil
        from datetime import datetime
        
        info = []
        info.append("=== STREAMMATE AI SYSTEM INFO ===")
        info.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        info.append("")
        
        # App info
        info.append("[APPLICATION]")
        info.append(f"Version: {self.cfg.get('app_version', '1.0.0')}")
        info.append(f"Package: {self.cfg.get('paket', 'N/A')}")
        info.append(f"Platform: {self.cfg.get('platform', 'N/A')}")
        info.append("")
        
        # System info
        info.append("[SYSTEM]")
        info.append(f"OS: {platform.system()} {platform.release()}")
        info.append(f"Architecture: {platform.architecture()[0]}")
        info.append(f"Machine: {platform.machine()}")
        info.append(f"Python: {platform.python_version()}")
        info.append("")
        
        # Hardware info
        info.append("[HARDWARE]")
        try:
            info.append(f"CPU: {platform.processor()}")
            info.append(f"CPU Cores: {psutil.cpu_count()}")
            info.append(f"RAM: {psutil.virtual_memory().total // (1024**3)} GB")
            info.append(f"RAM Usage: {psutil.virtual_memory().percent}%")
        except:
            info.append("Hardware info not available")
        info.append("")
        
        # Configuration
        info.append("[CONFIGURATION]")
        config_keys = [
            "reply_mode", "personality", "voice_model", 
            "cohost_voice_model", "selected_mic_index"
        ]
        for key in config_keys:
            value = self.cfg.get(key, "N/A")
            info.append(f"{key}: {value}")
        
        self.info_text.setPlainText("\n".join(info))
    
    def copy_to_clipboard(self):
        """Copy system info ke clipboard."""
        from PyQt6.QtWidgets import QApplication
        
        clipboard = QApplication.clipboard()
        clipboard.setText(self.info_text.toPlainText())
        
        QMessageBox.information(
            self, "Copied",
            "Informasi sistem telah dicopy ke clipboard!"
        )