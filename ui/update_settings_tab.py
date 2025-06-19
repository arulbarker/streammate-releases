#!/usr/bin/env python3
"""
StreamMate AI Update Settings Tab
Tab untuk mengatur preferensi sistem update
"""

import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QGroupBox, QFormLayout,
    QCheckBox, QSpinBox, QComboBox, QTextEdit,
    QMessageBox, QProgressBar, QSizePolicy
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer

# Import update manager
try:
    from modules_client.update_manager import get_update_manager
    from ui.update_dialog import UpdateDialog
    UPDATE_MANAGER_AVAILABLE = True
except ImportError:
    UPDATE_MANAGER_AVAILABLE = False

class UpdateSettingsTab(QWidget):
    """Tab untuk pengaturan sistem update"""
    
    def __init__(self):
        super().__init__()
        self.update_manager = None
        
        if UPDATE_MANAGER_AVAILABLE:
            try:
                self.update_manager = get_update_manager()
            except Exception as e:
                print(f"[WARNING] Failed to get update manager: {e}")
        
        self.init_ui()
        self.load_settings()
        
        # Timer untuk refresh status
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.start(30000)  # Refresh setiap 30 detik
    
    def init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel("🔄 Update Settings")
        title_label.setStyleSheet("""
            font-size: 24px; 
            font-weight: bold; 
            color: #1877F2;
            margin: 10px 0px;
        """)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Check now button
        self.check_now_btn = QPushButton("Check for Updates")
        self.check_now_btn.setStyleSheet("""
            QPushButton {
                background-color: #1877F2;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 8px;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #166FE5;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        self.check_now_btn.clicked.connect(self.manual_check_updates)
        header_layout.addWidget(self.check_now_btn)
        
        layout.addLayout(header_layout)
        
        # Status section
        self.create_status_section(layout)
        
        # Settings section
        self.create_settings_section(layout)
        
        # Advanced section
        self.create_advanced_section(layout)
        
        layout.addStretch()
    
    def create_status_section(self, parent_layout):
        """Create status information section"""
        status_group = QGroupBox("Update Status")
        status_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 16px;
                margin-top: 10px;
                padding-top: 10px;
                border: 2px solid #ddd;
                border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background-color: white;
            }
        """)
        
        status_layout = QVBoxLayout(status_group)
        
        # Current version
        self.current_version_label = QLabel("Current version: Loading...")
        self.current_version_label.setStyleSheet("font-size: 14px; color: #333; margin: 5px;")
        status_layout.addWidget(self.current_version_label)
        
        # Last check
        self.last_check_label = QLabel("Last checked: Loading...")
        self.last_check_label.setStyleSheet("font-size: 14px; color: #666; margin: 5px;")
        status_layout.addWidget(self.last_check_label)
        
        # Update status
        self.update_status_label = QLabel("Status: Checking...")
        self.update_status_label.setStyleSheet("font-size: 14px; color: #333; margin: 5px;")
        status_layout.addWidget(self.update_status_label)
        
        parent_layout.addWidget(status_group)
    
    def create_settings_section(self, parent_layout):
        """Create settings configuration section"""
        settings_group = QGroupBox("Update Settings")
        settings_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 16px;
                margin-top: 10px;
                padding-top: 10px;
                border: 2px solid #ddd;
                border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background-color: white;
            }
        """)
        
        settings_layout = QFormLayout(settings_group)
        
        # Auto check checkbox
        self.auto_check_cb = QCheckBox("Automatic update check")
        self.auto_check_cb.setStyleSheet("font-size: 14px; margin: 5px;")
        self.auto_check_cb.stateChanged.connect(self.on_settings_changed)
        settings_layout.addRow("", self.auto_check_cb)
        
        # Check interval
        self.check_interval_spin = QSpinBox()
        self.check_interval_spin.setRange(1, 168)  # 1 hour to 1 week
        self.check_interval_spin.setSuffix(" hours")
        self.check_interval_spin.setStyleSheet("font-size: 14px; padding: 5px;")
        self.check_interval_spin.valueChanged.connect(self.on_settings_changed)
        settings_layout.addRow("Check interval:", self.check_interval_spin)
        
        # Auto download checkbox
        self.auto_download_cb = QCheckBox("Automatic download")
        self.auto_download_cb.setStyleSheet("font-size: 14px; margin: 5px;")
        self.auto_download_cb.stateChanged.connect(self.on_settings_changed)
        settings_layout.addRow("", self.auto_download_cb)
        
        # Update channel
        self.update_channel_combo = QComboBox()
        self.update_channel_combo.addItems(["Stable", "Beta", "Alpha"])
        self.update_channel_combo.setStyleSheet("font-size: 14px; padding: 5px;")
        self.update_channel_combo.currentTextChanged.connect(self.on_settings_changed)
        settings_layout.addRow("Update channel:", self.update_channel_combo)
        
        parent_layout.addWidget(settings_group)
    
    def create_advanced_section(self, parent_layout):
        """Create advanced settings section"""
        advanced_group = QGroupBox("Advanced Settings")
        advanced_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 16px;
                margin-top: 10px;
                padding-top: 10px;
                border: 2px solid #ddd;
                border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background-color: white;
            }
        """)
        
        advanced_layout = QVBoxLayout(advanced_group)
        
        # Update history
        history_label = QLabel("Update History:")
        history_label.setStyleSheet("font-weight: bold; font-size: 14px; margin: 10px 0px 5px 0px;")
        advanced_layout.addWidget(history_label)
        
        self.update_history_text = QTextEdit()
        self.update_history_text.setMaximumHeight(120)
        self.update_history_text.setReadOnly(True)
        self.update_history_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 8px;
                background-color: #f8f9fa;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        advanced_layout.addWidget(self.update_history_text)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        
        # Clear skipped versions
        clear_skipped_btn = QPushButton("Reset Skipped Versions")
        clear_skipped_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f8f9fa;
                color: #333;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
        """)
        clear_skipped_btn.clicked.connect(self.clear_skipped_versions)
        buttons_layout.addWidget(clear_skipped_btn)
        
        # Clear cache
        clear_cache_btn = QPushButton("Clear Update Cache")
        clear_cache_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f8f9fa;
                color: #333;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
        """)
        clear_cache_btn.clicked.connect(self.clear_update_cache)
        buttons_layout.addWidget(clear_cache_btn)
        
        buttons_layout.addStretch()
        
        # Save settings button
        save_btn = QPushButton("💾 Save Settings")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        save_btn.clicked.connect(self.save_settings)
        buttons_layout.addWidget(save_btn)
        
        advanced_layout.addLayout(buttons_layout)
        
        parent_layout.addWidget(advanced_group)
    
    def load_settings(self):
        """Load current settings"""
        if not self.update_manager:
            self.update_status_label.setText("Status: Update manager not available")
            self.check_now_btn.setEnabled(False)
            return
        
        try:
            # Get current version
            version = self.update_manager.current_version
            self.current_version_label.setText(f"Current version: {version}")
            
            # Get settings
            settings = self.update_manager.get_update_settings()
            
            self.auto_check_cb.setChecked(settings.get("auto_check", True))
            self.check_interval_spin.setValue(settings.get("check_interval", 24))
            self.auto_download_cb.setChecked(settings.get("auto_download", False))
            
            # Update last check time
            last_check = settings.get("last_check")
            if last_check:
                last_check_dt = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
                self.last_check_label.setText(f"Last checked: {last_check_dt.strftime('%d/%m/%Y %H:%M')}")
            else:
                self.last_check_label.setText("Last checked: Never")
            
            # Update history
            self.load_update_history()
            
            self.update_status_label.setText("Status: Ready")
            
        except Exception as e:
            self.update_status_label.setText(f"Status: Error - {e}")
    
    def load_update_history(self):
        """Load update history"""
        try:
            history_file = Path("temp/update_history.json")
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                
                history_text = ""
                for entry in history[-10:]:  # Show last 10 entries
                    date = entry.get("date", "Unknown")
                    action = entry.get("action", "Unknown")
                    version = entry.get("version", "Unknown")
                    history_text += f"{date}: {action} v{version}\n"
                
                self.update_history_text.setPlainText(history_text)
            else:
                self.update_history_text.setPlainText("No update history available")
                
        except Exception as e:
            self.update_history_text.setPlainText(f"Error loading history: {e}")
    
    def on_settings_changed(self):
        """Handle settings change"""
        # Auto save when settings change
        pass
    
    def save_settings(self):
        """Save current settings"""
        if not self.update_manager:
            QMessageBox.warning(self, "Error", "Update manager not available")
            return
        
        try:
            settings = {
                "auto_check": self.auto_check_cb.isChecked(),
                "check_interval": self.check_interval_spin.value(),
                "auto_download": self.auto_download_cb.isChecked()
            }
            
            self.update_manager.update_settings(settings)
            
            QMessageBox.information(
                self, "Saved",
                "Update settings successfully saved!"
            )
            
        except Exception as e:
            QMessageBox.warning(
                self, "Error",
                f"Failed to save settings: {e}"
            )
    
    def manual_check_updates(self):
        """Manual check for updates"""
        if not self.update_manager:
            QMessageBox.warning(self, "Error", "Update manager not available")
            return
        
        try:
            self.check_now_btn.setEnabled(False)
            self.check_now_btn.setText("Checking...")
            self.update_status_label.setText("Status: Checking for updates...")
            
            # Connect signals untuk handle hasil
            def handle_update_available(update_info):
                self.check_now_btn.setEnabled(True)
                self.check_now_btn.setText("Check for Updates")
                self.update_status_label.setText("Status: Update available!")
                
                # Show update dialog
                update_dialog = UpdateDialog(self.update_manager, self)
                update_dialog.set_update_info(update_info)
                update_dialog.exec()
                
                # Disconnect
                self.update_manager.update_available.disconnect(handle_update_available)
            
            def handle_update_error(error_msg):
                self.check_now_btn.setEnabled(True)
                self.check_now_btn.setText("Check for Updates")
                self.update_status_label.setText("Status: Error while checking")
                
                QMessageBox.warning(self, "Update Error", f"Failed to check for updates:\n\n{error_msg}")
                
                # Disconnect
                self.update_manager.update_error.disconnect(handle_update_error)
            
            # Connect signals
            self.update_manager.update_available.connect(handle_update_available)
            self.update_manager.update_error.connect(handle_update_error)
            
            # Start check
            self.update_manager.check_for_updates(manual=True)
            
            # Reset button setelah timeout
            QTimer.singleShot(30000, lambda: (
                self.check_now_btn.setEnabled(True),
                self.check_now_btn.setText("Check for Updates"),
                self.update_status_label.setText("Status: Ready")
            ))
            
        except Exception as e:
            self.check_now_btn.setEnabled(True)
            self.check_now_btn.setText("Check for Updates")
            self.update_status_label.setText("Status: Error")
            QMessageBox.warning(self, "Error", f"Failed to check for updates: {e}")
    
    def clear_skipped_versions(self):
        """Clear all skipped versions"""
        if not self.update_manager:
            return
        
        reply = QMessageBox.question(
            self, "Reset Skipped Versions",
            "Are you sure you want to reset all skipped versions?\n\n"
            "After reset, all versions will be shown again.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.update_manager.skip_version("")  # Clear skipped version
            QMessageBox.information(self, "Reset Complete", "Skipped versions successfully reset")
    
    def clear_update_cache(self):
        """Clear update cache files"""
        try:
            cache_dir = Path("temp/updates")
            if cache_dir.exists():
                for file in cache_dir.glob("*"):
                    file.unlink()
                cache_dir.rmdir()
            
            QMessageBox.information(self, "Cache Cleared", "Update cache successfully cleared")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to clear cache: {e}")
    
    def refresh_status(self):
        """Refresh status information"""
        if self.update_manager:
            self.load_settings() 