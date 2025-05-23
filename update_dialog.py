# ui/update_dialog.py
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

class UpdateDialog(QDialog):
    """Dialog untuk menampilkan update yang tersedia."""
    
    def __init__(self, update_manager, parent=None):
        super().__init__(parent)
        self.update_manager = update_manager
        self.update_info = None
        self.setWindowTitle("StreamMate AI - Update Available")
        self.setMinimumSize(500, 400)
        self.setMaximumSize(600, 500)
        self.init_ui()
        self.setup_connections()
    
    def init_ui(self):
        """Setup UI dialog."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Header dengan icon
        header_layout = QHBoxLayout()
        
        # Icon update
        icon_label = QLabel("🔄")
        icon_label.setStyleSheet("font-size: 32px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(50, 50)
        header_layout.addWidget(icon_label)
        
        # Title dan versi
        title_layout = QVBoxLayout()
        self.title_label = QLabel("Update Tersedia!")
        self.title_label.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold; 
            color: #1877F2;
            margin-bottom: 5px;
        """)
        
        self.version_label = QLabel("Versi baru tersedia")
        self.version_label.setStyleSheet("font-size: 14px; color: #666;")
        
        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.version_label)
        title_layout.addStretch()
        
        header_layout.addLayout(title_layout, 1)
        layout.addLayout(header_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # Changelog
        changelog_label = QLabel("What's New:")
        changelog_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
        layout.addWidget(changelog_label)
        
        self.changelog_text = QTextEdit()
        self.changelog_text.setPlainText("Memuat informasi update...")
        self.changelog_text.setMaximumHeight(150)
        self.changelog_text.setReadOnly(True)
        self.changelog_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 8px;
                background-color: #f8f9fa;
            }
        """)
        layout.addWidget(self.changelog_text)
        
        # File info
        self.info_label = QLabel("Ukuran: Mengecek...")
        self.info_label.setStyleSheet("color: #666; font-size: 12px; margin-top: 5px;")
        layout.addWidget(self.info_label)
        
        # Progress bar (hidden by default)
        self.progress_widget = QWidget()
        progress_layout = QVBoxLayout(self.progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        
        self.progress_label = QLabel("Downloading...")
        self.progress_label.setStyleSheet("font-size: 12px; color: #1877F2; margin-bottom: 5px;")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #1877F2;
                border-radius: 8px;
                background-color: rgba(255, 255, 255, 0.1);
                height: 20px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #1877F2;
                border-radius: 6px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_widget.setVisible(False)
        layout.addWidget(self.progress_widget)
        
        # Spacer
        layout.addStretch()
        
        # Options
        options_layout = QHBoxLayout()
        
        self.auto_install_check = QCheckBox("Install otomatis setelah download")
        self.auto_install_check.setChecked(True)
        self.auto_install_check.setStyleSheet("font-size: 12px;")
        options_layout.addWidget(self.auto_install_check)
        
        options_layout.addStretch()
        layout.addLayout(options_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Skip button
        self.skip_btn = QPushButton("Skip Versi Ini")
        self.skip_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f8f9fa;
                color: #666;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
        """)
        self.skip_btn.clicked.connect(self.skip_version)
        button_layout.addWidget(self.skip_btn)
        
        # Later button  
        self.later_btn = QPushButton("Ingatkan Nanti")
        self.later_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f8f9fa;
                color: #333;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
        """)
        self.later_btn.clicked.connect(self.remind_later)
        button_layout.addWidget(self.later_btn)
        
        # Download button (primary)
        self.download_btn = QPushButton("Download & Install")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #1877F2;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #166FE5;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        self.download_btn.clicked.connect(self.start_download)
        button_layout.addWidget(self.download_btn)
        
        layout.addLayout(button_layout)
    
    def setup_connections(self):
        """Setup signal connections."""
        if self.update_manager:
            self.update_manager.download_progress.connect(self.update_progress)
            self.update_manager.update_ready.connect(self.download_finished)
            self.update_manager.update_error.connect(self.download_error)
    
    def set_update_info(self, update_info):
        """Set informasi update."""
        self.update_info = update_info
        
        if update_info:
            # Update title dan versi
            version = update_info.get("tag_name", "Unknown")
            self.title_label.setText(f"StreamMate AI {version} tersedia!")
            self.version_label.setText(f"Versi saat ini: {self.update_manager.current_version} → {version}")
            
            # Update changelog
            changelog = update_info.get("changelog", update_info.get("body", "Tidak ada catatan perubahan"))
            if changelog:
                # Format changelog yang lebih baik
                formatted_changelog = self._format_changelog(changelog)
                self.changelog_text.setPlainText(formatted_changelog)
            else:
                self.changelog_text.setPlainText("• Perbaikan dan peningkatan performa\n• Bug fixes dan optimasi")
            
            # Update file info
            file_size = update_info.get("file_size", 0)
            if file_size > 0:
                size_mb = file_size / (1024 * 1024)
                self.info_label.setText(f"Ukuran: {size_mb:.1f} MB")
            else:
                self.info_label.setText("Ukuran: Tidak diketahui")
    
    def _format_changelog(self, changelog):
        """Format changelog untuk tampilan yang lebih baik."""
        if not changelog:
            return "• Perbaikan dan peningkatan performa\n• Bug fixes dan optimasi"
        
        # Jika sudah dalam format yang baik, return as is
        if changelog.startswith("•") or changelog.startswith("-") or changelog.startswith("*"):
            return changelog
        
        # Coba parse format markdown
        lines = changelog.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip header lines
            if line.startswith('#'):
                continue
            
            # Convert markdown list to bullet
            if line.startswith('- ') or line.startswith('* '):
                formatted_lines.append(f"• {line[2:]}")
            elif line:
                formatted_lines.append(f"• {line}")
        
        if formatted_lines:
            return '\n'.join(formatted_lines)
        else:
            return "• Perbaikan dan peningkatan performa\n• Bug fixes dan optimasi"
    
    def start_download(self):
        """Mulai download update."""
        if not self.update_manager or not self.update_info:
            return
        
        # Disable buttons
        self.download_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        
        # Show progress
        self.progress_widget.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Memulai download...")
        
        # Start download
        success = self.update_manager.download_update()
        if not success:
            self.download_error("Gagal memulai download")
    
    def update_progress(self, progress):
        """Update progress bar."""
        self.progress_bar.setValue(progress)
        self.progress_label.setText(f"Downloading... {progress}%")
    
    def download_finished(self, file_path):
        """Handle download selesai."""
        self.progress_label.setText("Download selesai!")
        self.progress_bar.setValue(100)
        
        if self.auto_install_check.isChecked():
            # Install otomatis
            reply = QMessageBox.question(
                self, "Install Update",
                "Download selesai. StreamMate akan ditutup dan diperbarui.\n\n"
                "Lanjutkan instalasi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.install_update(file_path)
            else:
                self.manual_install_info(file_path)
        else:
            self.manual_install_info(file_path)
    
    def download_error(self, error_msg):
        """Handle download error."""
        self.progress_widget.setVisible(False)
        
        # Re-enable buttons
        self.download_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.later_btn.setEnabled(True)
        
        QMessageBox.warning(
            self, "Download Error",
            f"Gagal download update:\n\n{error_msg}\n\nSilakan coba lagi nanti."
        )
    
    def install_update(self, file_path):
        """Install update."""
        if self.update_manager:
            success = self.update_manager.install_update()
            if success:
                self.accept()  # Close dialog
            else:
                QMessageBox.warning(
                    self, "Install Error",
                    "Gagal menginstall update. Silakan install manual."
                )
    
    def manual_install_info(self, file_path):
        """Tampilkan info untuk install manual."""
        QMessageBox.information(
            self, "Download Selesai",
            f"Update berhasil didownload ke:\n{file_path}\n\n"
            "Jalankan file tersebut untuk menginstall update."
        )
        self.accept()
    
    def skip_version(self):
        """Skip versi ini."""
        if self.update_info and self.update_manager.config:
            version = self.update_info.get("tag_name", "")
            self.update_manager.config.set("skipped_update_version", version)
            
        QMessageBox.information(
            self, "Update Dilewat",
            f"Versi {self.update_info.get('tag_name', 'ini')} akan dilewat.\n\n"
            "Anda masih akan mendapat notifikasi untuk versi yang lebih baru."
        )
        self.reject()
    
    def remind_later(self):
        """Ingatkan nanti (24 jam)."""
        if self.update_manager.config:
            from datetime import datetime, timedelta
            reminder_time = datetime.now() + timedelta(hours=24)
            self.update_manager.config.set("update_reminder_time", reminder_time.timestamp())

        QMessageBox.information(
            self, "Pengingat Diatur",
            "Anda akan diingatkan tentang update ini dalam 24 jam."
        )
        self.reject()

    def closeEvent(self, event):
        """Handle dialog close."""
        # Cancel download jika sedang berjalan
        if self.update_manager and hasattr(self.update_manager, 'cancel_download'):
            self.update_manager.cancel_download()

        super().closeEvent(event)