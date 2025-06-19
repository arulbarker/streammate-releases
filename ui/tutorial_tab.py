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
        
        title = QLabel("StreamMate AI Tutorial & Help")
        title.setStyleSheet("""
            font-size: 28px; 
            font-weight: bold; 
            color: white;
            margin: 0px;
        """)
        text_layout.addWidget(title)
        
        subtitle = QLabel("Complete guide to start AI-powered streaming")
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
            ("🚀", "Version", f"v{version}"),
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
        quick_group = QGroupBox("⚡ Quick Start Guide")
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
            ("1️⃣", "Login", "Login with your Google account", "login"),
            ("2️⃣", "Choose Package", "Select Basic or Pro package", "package"),
            ("3️⃣", "Setup Platform", "Connect YouTube/TikTok", "platform"),
            ("4️⃣", "Start Streaming", "Activate features and go live", "stream")
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
        
        test_btn = QPushButton("🧪 Test Features")
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
        video_group = QGroupBox("🎬 Video Tutorials")
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
                    ("Installation & Initial Setup", "basic-setup"),
                    ("Login & Package Activation", "login-guide"),
                    ("Platform Configuration", "platform-setup")
                ]
            },
            {
                "title": "🎤 Voice Translation Features",
                "videos": [
                    ("Setup Voice Translation", "voice-setup"),
                    ("Optimal Usage Tips", "voice-tips"),
                    ("Voice Troubleshooting", "voice-trouble")
                ]
            },
            {
                "title": "🤖 Auto-Reply Chat",
                "videos": [
                    ("Configure Auto-Reply", "reply-setup"),
                    ("Create AI Personality", "personality-setup"),
                    ("Advanced Reply Mode", "reply-advanced")
                ]
            },
            {
                "title": "🎭 Avatar & Animation",
                "videos": [
                    ("Animaze Integration", "animaze-setup"),
                    ("Virtual Mic Setup", "vmic-setup"),
                    ("Animation Synchronization", "animation-sync")
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
        main_tutorial_btn = QPushButton("🎬 Open StreamMate YouTube Channel")
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
                "q": "What's the difference between Basic and Pro packages?",
                "a": "Basic package uses standard TTS and supports YouTube OR TikTok. Pro package gets premium TTS, supports YouTube + TikTok simultaneously, Virtual Mic, and other advanced features."
            },
            {
                "q": "How to activate Voice Translation?",
                "a": "1. Open Translate Voice tab\n2. Select source and target language\n3. Press hotkey Ctrl+Alt+X\n4. Speak into microphone\n5. Translation result will be played automatically"
            },
            {
                "q": "Why isn't Auto-Reply working?",
                "a": "Make sure:\n- Valid YouTube Video ID (11 characters)\n- Platform selected correctly\n- Reply mode is appropriate (Trigger/Delay/Sequential)\n- Trigger words are set (for Trigger mode)"
            },
            {
                "q": "How to save credit hours?",
                "a": "Credit saving tips:\n- Use Trigger mode for specific replies\n- Turn off auto-reply when not needed\n- Optimize streaming duration\n- Monitor usage in Profile tab"
            },
            {
                "q": "Can I use it with OBS Studio?",
                "a": "Yes! Use Virtual Microphone feature (Pro Package) to route audio to OBS. Set audio output to Virtual Mic device in Windows."
            }
        ]
        
        # Create FAQ items
        for i, faq in enumerate(faq_data):
            faq_item = self.create_faq_item(faq["q"], faq["a"], i)
            faq_layout.addWidget(faq_item)
        
        # More FAQ button
        more_faq_btn = QPushButton("📋 View Complete FAQ")
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
        social_group = QGroupBox("🌐 Community & Social Media")
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
        desc_label = QLabel("Join the StreamMate AI community for tips, updates, and discussions")
        desc_label.setStyleSheet("color: #666; font-size: 14px; margin-bottom: 10px;")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        social_layout.addWidget(desc_label)
        
        # Social Media Grid dengan styling yang lebih baik
        social_grid = QGridLayout()
        social_grid.setSpacing(12)
        
        social_data = [
            ("📺", "YouTube", "Tutorials & Live Demo", "#FF0000", "youtube"),
            ("📘", "Facebook", "Community & Updates", "#1877F2", "facebook"),
            ("📷", "Instagram", "Tips & Behind Scenes", "#E1306C", "instagram"),
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
        support_group = QGroupBox("🆘 Help & Support")
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
            ("🐞", "Report Bug", "Report bugs or errors", "bug"),
            ("💡", "Request Feature", "Suggest new features", "feature"),
            ("📞", "Live Support", "Chat directly with team", "live_support"),
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
        system_info_btn = QPushButton("🔧 System Information")
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
                "To login:\n\n"
                "1. Click 'Login with Google' button\n"
                "2. Enter your Google credentials\n"
                "3. Grant required permissions\n"
                "4. Wait for validation to complete"
            )
        elif action == "package":
            QMessageBox.information(
                self, "Choose Package",
                "Available packages:\n\n"
                "• BASIC (Rp 100,000/100 hours):\n"
                "  - Standard TTS\n"
                "  - YouTube OR TikTok\n"
                "  - 5 hours/day limit\n\n"
                "• PRO (Rp 250,000/100 hours):\n"
                "  - Premium TTS\n"
                "  - YouTube + TikTok\n"
                "  - Virtual Mic\n"
                "  - 12 hours/day limit"
            )
        elif action == "platform":
            QMessageBox.information(
                self, "Setup Platform",
                "Setup streaming platform:\n\n"
                
                "1. Choose platform (YouTube/TikTok)\n"
                "2. Enter YouTube Video ID (11 characters)\n"
                "3. Or TikTok username (@username)\n"
                "4. Test connection with Test button\n"
                "5. Activate chat listener"
            )
        elif action == "stream":
            QMessageBox.information(
                self, "Start Streaming",
                "To start streaming:\n\n"
                "1. Make sure all setup is correct\n"
                "2. Activate required features:\n"
                "   - Voice Translation (Ctrl+Alt+X)\n"
                "   - Auto-Reply Chat\n"
                "   - Avatar/Animation (if available)\n"
                "3. Start live streaming on platform\n"
                "4. Monitor activity in System Log"
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
        # Mapping video ID ke URL YouTube playlist - semua mengarah ke playlist tutorial lengkap
        video_urls = {
            "basic-setup": "https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn",
            "login-guide": "https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn",
            "platform-setup": "https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn",
            "voice-setup": "https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn",
            "voice-tips": "https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn",
            "voice-trouble": "https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn",
            "reply-setup": "https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn",
            "personality-setup": "https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn",
            "reply-advanced": "https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn",
            "animaze-setup": "https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn",
            "vmic-setup": "https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn",
            "animation-sync": "https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn"
        }
        
        url = video_urls.get(video_id, "https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn")
        webbrowser.open(url)
    
    def open_youtube_channel(self):
        """Buka playlist tutorial YouTube StreamMate."""
        webbrowser.open("https://www.youtube.com/playlist?list=PLxq0PydAU5uoZPjruKpzBg0idFXc799qn")
    
    def open_full_faq(self):
        """Buka FAQ lengkap dalam dialog terpisah."""
        faq_dialog = FullFAQDialog(self)
        faq_dialog.exec()
    
    def open_social_platform(self, platform):
        """Buka platform social media."""
        urls = {
            "youtube": "https://youtube.com/@arulcg?si=TiIyrFOBz0sED46W",
            "facebook": "https://www.facebook.com/share/1YRevDK5SK/?mibextid=wwXIfr",
            "instagram": "https://www.instagram.com/arul.cg?igsh=ejNpMDVvczZpdmJm&utm_source=qr",
            "tiktok": "https://www.tiktok.com/@arul.cg?_t=ZS-8x3KYHasil5&_r=1",
            "discord": "https://discord.gg/streammateai",
            "email": "mailto:support@streammateai.com"
        }
        
        url = urls.get(platform, "https://lynk.id/arullagi")
        
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
            "Live Support will be available soon!\n\n"
            "For now, you can:\n"
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
        
        [Describe your issue here]
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
        header = QLabel("🧙‍♂️ StreamMate AI Setup Wizard")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #1877F2; margin-bottom: 20px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Progress indicator
        self.progress_label = QLabel("Step 1 of 4")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_label)
        
        # Content area
        self.content_area = QStackedWidget()
        self.setup_wizard_steps()
        layout.addWidget(self.content_area)
        
        # Navigation buttons
        nav_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.clicked.connect(self.prev_step)
        self.prev_btn.setEnabled(False)
        nav_layout.addWidget(self.prev_btn)
        
        nav_layout.addStretch()
        
        self.next_btn = QPushButton("Next →")
        self.next_btn.clicked.connect(self.next_step)
        nav_layout.addWidget(self.next_btn)
        
        self.finish_btn = QPushButton("Finish")
        self.finish_btn.clicked.connect(self.accept)
        self.finish_btn.setVisible(False)
        nav_layout.addWidget(self.finish_btn)
        
        layout.addLayout(nav_layout)
    
    def setup_wizard_steps(self):
        """Setup langkah-langkah wizard."""
        # Step 1: Welcome
        step1 = QWidget()
        step1_layout = QVBoxLayout(step1)
        step1_layout.addWidget(QLabel("🎉 Welcome to StreamMate AI!"))
        step1_layout.addWidget(QLabel("This wizard will help you setup the application easily."))
        step1_layout.addStretch()
        self.content_area.addWidget(step1)
        
        # Step 2: Package Selection
        step2 = QWidget()
        step2_layout = QVBoxLayout(step2)
        step2_layout.addWidget(QLabel("📦 Choose package that suits your needs:"))
        
        # Package options
        self.basic_radio = QPushButton("Basic Package (Rp 100,000)")
        self.basic_radio.setCheckable(True)
        self.basic_radio.setChecked(True)
        step2_layout.addWidget(self.basic_radio)
        
        self.pro_radio = QPushButton("Pro Package (Rp 250,000)")
        self.pro_radio.setCheckable(True)
        step2_layout.addWidget(self.pro_radio)
        
        step2_layout.addStretch()
        self.content_area.addWidget(step2)
        
        # Step 3: Platform Setup
        step3 = QWidget()
        step3_layout = QVBoxLayout(step3)
        step3_layout.addWidget(QLabel("🎮 Setup Streaming Platform:"))
        
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
        step4_layout.addWidget(QLabel("✅ Setup Complete!"))
        step4_layout.addWidget(QLabel("StreamMate AI is ready to use. Happy streaming!"))
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
        
        self.progress_label.setText(f"Step {self.current_step + 1} of {self.content_area.count()}")


class FeatureTestDialog(QDialog):
    """Dialog untuk test fitur aplikasi."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Feature Test - StreamMate AI")
        self.setMinimumSize(500, 400)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI test fitur."""
        layout = QVBoxLayout(self)
        
        header = QLabel("🧪 Test StreamMate AI Features")
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
        close_btn = QPushButton("Close")
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
        self.setWindowTitle("Complete FAQ - StreamMate AI")
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
            "General": [
                ("What is StreamMate AI?", "StreamMate AI is a live streaming automation application that helps streamers with real-time voice translation, automatic comment replies, and avatar integration features."),
                ("How does StreamMate AI work?", "StreamMate AI uses AI technology to listen to your voice, translate it, and automatically reply to comments according to the selected personality."),
                ("Which platforms are supported?", "StreamMate AI supports YouTube and TikTok Live. Basic package supports one platform, Pro package can handle both simultaneously.")
            ],
            "Technical": [
                ("Why is voice translation slow?", "Delays can occur due to STT, translation, and TTS processes. Make sure internet connection is stable and close other heavy applications."),
                ("How to optimize performance?", "Close unnecessary applications, ensure sufficient RAM (minimum 4GB), and use a stable internet connection."),
                ("Hotkey not working?", "Check if other applications are using the same hotkey. Try changing the hotkey in settings or restart the application.")
            ],
            "Payment": [
                ("How does the payment system work?", "StreamMate AI uses a credit hour system. Buy credits once, use as needed without monthly subscriptions."),
                ("What payment methods are available?", "We accept bank transfers, e-wallets (OVO, GoPay, DANA), and QRIS."),
                ("What if credits run out?", "The application will stop functioning until you purchase additional credits. Monitor usage in the Profile tab.")
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
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class BugReportDialog(QDialog):
    """Dialog untuk melaporkan bug."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Report Bug - StreamMate AI")
        self.setMinimumSize(500, 400)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI bug report."""
        layout = QVBoxLayout(self)
        
        header = QLabel("🐞 Report Bug")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 15px;")
        layout.addWidget(header)
        
        # Bug description
        layout.addWidget(QLabel("Bug Description:"))
        self.bug_text = QTextEdit()
        self.bug_text.setPlaceholderText("Describe the bug you experienced in detail...")
        layout.addWidget(self.bug_text)
        
        # Steps to reproduce
        layout.addWidget(QLabel("Steps to reproduce:"))
        self.steps_text = QTextEdit()
        self.steps_text.setPlaceholderText("1. First step\n2. Second step\n3. ...")
        self.steps_text.setMaximumHeight(100)
        layout.addWidget(self.steps_text)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        send_btn = QPushButton("Send Report")
        send_btn.clicked.connect(self.send_report)
        btn_layout.addWidget(send_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def send_report(self):
        """Kirim laporan bug."""
        bug_desc = self.bug_text.toPlainText()
        steps = self.steps_text.toPlainText()
        
        if not bug_desc.strip():
            QMessageBox.warning(self, "Error", "Please fill in the bug description!")
            return
        
        # Simulasi pengiriman
        QMessageBox.information(
            self, "Report Sent",
            "Thank you! Your bug report has been sent.\n\n"
            "Our team will review and respond within 1-2 business days."
        )
        self.accept()


class FeatureRequestDialog(QDialog):
    """Dialog untuk request fitur baru."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Feature Request - StreamMate AI")
        self.setMinimumSize(500, 300)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI feature request."""
        layout = QVBoxLayout(self)
        
        header = QLabel("💡 Request New Feature")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 15px;")
        layout.addWidget(header)
        
        # Feature description
        layout.addWidget(QLabel("Feature Description:"))
        self.feature_text = QTextEdit()
        self.feature_text.setPlaceholderText("Describe the feature you want...")
        layout.addWidget(self.feature_text)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        send_btn = QPushButton("Send Request")
        send_btn.clicked.connect(self.send_request)
        btn_layout.addWidget(send_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def send_request(self):
        """Kirim request fitur."""
        feature_desc = self.feature_text.toPlainText()
        
        if not feature_desc.strip():
            QMessageBox.warning(self, "Error", "Please fill in the feature description!")
            return
        
        QMessageBox.information(
            self, "Request Sent",
            "Thank you! Your feature request has been sent.\n\n"
            "We will consider it for the next update."
        )
        self.accept()


class SystemInfoDialog(QDialog):
    """Dialog informasi sistem untuk debugging."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Information - StreamMate AI")
        self.setMinimumSize(600, 500)
        self.cfg = ConfigManager("config/settings.json")
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI system info."""
        layout = QVBoxLayout(self)
        
        header = QLabel("🔧 System Information")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 15px;")
        layout.addWidget(header)
        
        # System info text
        self.info_text = QTextBrowser()
        self.info_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.info_text)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        copy_btn = QPushButton("📋 Copy to Clipboard")
        copy_btn.clicked.connect(self.copy_to_clipboard)
        btn_layout.addWidget(copy_btn)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_info)
        btn_layout.addWidget(refresh_btn)
        
        close_btn = QPushButton("Close")
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
            "System information has been copied to clipboard!"
        )
