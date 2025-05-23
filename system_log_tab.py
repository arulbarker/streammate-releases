# ui/system_log_tab.py
import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QComboBox, QCheckBox, QFileDialog, QMessageBox,
    QGroupBox, QSpinBox, QSplitter, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCharFormat, QColor, QFont

# Import config manager
try:
    from modules_client.config_manager import ConfigManager
except ImportError:
    from modules_server.config_manager import ConfigManager

class SystemLogTab(QWidget):
    """Tab untuk menampilkan log aktivitas sistem StreamMate AI"""
    
    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager("config/settings.json")
        
        # Log files paths
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        self.system_log = self.log_dir / "system.log"
        self.tts_log = self.log_dir / "tts.log"
        self.animaze_log = self.log_dir / "animaze.log"
        self.error_log = Path("temp/error_log.txt")
        
        # Activity logs - buat file jika belum ada
        self.activity_log = self.log_dir / "activity.log"
        if not self.activity_log.exists():
            self.activity_log.write_text("")
        
        # State
        self.auto_scroll = True
        self.auto_refresh = True
        self.filter_level = "ALL"
        self.filter_module = "ALL"
        self.time_filter = "ALL"
        
        # Timer untuk auto-refresh
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.reload_logs)
        self.refresh_timer.setInterval(2000)  # 2 detik
        
        # Log aktivitas aplikasi
        self.log_activity("System Log Tab initialized")
        
        # Setup UI
        self.init_ui()
        
        # Initial load
        self.reload_logs()
        
        # Start auto refresh
        self.refresh_timer.start()
    
    def init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("📊 System Activity Monitor")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #1877F2;")
        layout.addWidget(header)
        
        # Deskripsi
        desc = QLabel("Monitor semua aktivitas StreamMate AI termasuk event sistem, TTS, AI response, dan interaksi sistem.")
        desc.setStyleSheet("color: #606060;")
        layout.addWidget(desc)
        
        # Control panel
        control_group = QGroupBox("⚙️ Filter & Controls")
        control_layout = QHBoxLayout()
        
        # Filter by time
        control_layout.addWidget(QLabel("Time:"))
        self.time_filter_combo = QComboBox()
        self.time_filter_combo.addItems(["ALL", "Today", "Last Hour", "Last 10 Minutes"])
        self.time_filter_combo.currentTextChanged.connect(self.apply_filters)
        control_layout.addWidget(self.time_filter_combo)
        
        # Filter by level
        control_layout.addWidget(QLabel("Level:"))
        self.level_filter = QComboBox()
        self.level_filter.addItems(["ALL", "INFO", "ACTION", "EVENT", "WARNING", "ERROR"])
        self.level_filter.currentTextChanged.connect(self.apply_filters)
        control_layout.addWidget(self.level_filter)
        
        # Filter by module
        control_layout.addWidget(QLabel("Module:"))
        self.module_filter = QComboBox()
        self.module_filter.addItems([
            "ALL", "SYSTEM", "TTS", "STT", "TRANSLATE", 
            "COHOST", "YOUTUBE", "TIKTOK", "ANIMAZE", "LICENSE",
            "USER", "PAYMENT", "VIRTUAL_MIC", "RAG", "OVERLAY"
        ])
        self.module_filter.currentTextChanged.connect(self.apply_filters)
        control_layout.addWidget(self.module_filter)
        
        # Options
        self.auto_scroll_check = QCheckBox("Auto-scroll")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.toggled.connect(lambda x: setattr(self, 'auto_scroll', x))
        control_layout.addWidget(self.auto_scroll_check)
        
        self.auto_refresh_check = QCheckBox("Auto-refresh")
        self.auto_refresh_check.setChecked(True)
        self.auto_refresh_check.toggled.connect(self.toggle_auto_refresh)
        control_layout.addWidget(self.auto_refresh_check)
        
        # Refresh interval
        control_layout.addWidget(QLabel("Interval:"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 30)
        self.interval_spin.setValue(2)
        self.interval_spin.setSuffix(" sec")
        self.interval_spin.valueChanged.connect(self.update_interval)
        control_layout.addWidget(self.interval_spin)
        
        control_layout.addStretch()
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # Tabs untuk berbagai jenis log
        log_tabs = QTabWidget()
        
        # Tab 1: Activity Log (utama)
        activity_tab = QWidget()
        activity_layout = QVBoxLayout(activity_tab)
        
        self.activity_view = QTextEdit()
        self.activity_view.setReadOnly(True)
        self.activity_view.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                background-color: #fafafa;
                color: #333333;
                border: 1px solid #e0e0e0;
            }
        """)
        activity_layout.addWidget(self.activity_view)
        
        log_tabs.addTab(activity_tab, "📋 Activity Log")
        
        # Tab 2: System Events
        system_tab = QWidget()
        system_layout = QVBoxLayout(system_tab)
        
        self.system_view = QTextEdit()
        self.system_view.setReadOnly(True)
        self.system_view.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                background-color: #f5f5f5;
                color: #333333;
                border: 1px solid #e0e0e0;
            }
        """)
        system_layout.addWidget(self.system_view)
        
        log_tabs.addTab(system_tab, "🔧 System Events")
        
        # Tab 3: Error Log
        error_tab = QWidget()
        error_layout = QVBoxLayout(error_tab)
        
        self.error_view = QTextEdit()
        self.error_view.setReadOnly(True)
        self.error_view.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                background-color: #fff8f8;
                color: #aa0000;
                border: 1px solid #ffcccc;
            }
        """)
        error_layout.addWidget(self.error_view)
        
        log_tabs.addTab(error_tab, "⚠️ Error Log")
        
        layout.addWidget(log_tabs)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 Refresh Now")
        refresh_btn.clicked.connect(self.reload_logs)
        button_layout.addWidget(refresh_btn)
        
        clear_btn = QPushButton("🗑️ Clear Display")
        clear_btn.clicked.connect(self.clear_displays)
        button_layout.addWidget(clear_btn)
        
        export_btn = QPushButton("💾 Export Logs")
        export_btn.clicked.connect(self.export_logs)
        button_layout.addWidget(export_btn)

        purge_btn = QPushButton("🧹 Purge Old Logs")
        purge_btn.clicked.connect(self.purge_old_logs)
        button_layout.addWidget(purge_btn)
        
        view_files_btn = QPushButton("📁 Open Log Folder")
        view_files_btn.clicked.connect(self.open_log_folder)
        button_layout.addWidget(view_files_btn)
        
        button_layout.addStretch()
        
        # Stats
        self.stats_label = QLabel("Ready")
        button_layout.addWidget(self.stats_label)
        
        layout.addLayout(button_layout)
    
    def log_activity(self, message, level="INFO", module="SYSTEM"):
        """Log aktivitas ke file activity.log"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] [{level}] [{module}] {message}\n"
            
            with open(self.activity_log, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Error logging activity: {e}")
    
    def reload_logs(self):
        """Reload all log files"""
        if not self.auto_refresh:
            return
        
        # Catat aktivitas reload
        self.log_activity("Reloading all logs", "INFO", "SYSTEM_LOG")
        
        # Clear previous logs
        all_activity_logs = []
        all_system_logs = []
        all_error_logs = []
        
        # Read activity log
        if self.activity_log.exists():
            try:
                with open(self.activity_log, 'r', encoding='utf-8') as f:
                    all_activity_logs = f.readlines()[-1000:]  # Last 1000 lines
            except Exception as e:
                print(f"Error reading activity log: {e}")
        
        # Read system logs
        log_files = [
            (self.system_log, "SYSTEM"),
            (self.tts_log, "TTS"),
            (self.animaze_log, "ANIMAZE")
        ]
        
        for log_path, source in log_files:
            if log_path.exists():
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()[-500:]  # Last 500 lines
                        for line in lines:
                            all_system_logs.append((source, line.strip()))
                except Exception as e:
                    print(f"Error reading {log_path}: {e}")
        
        # Read error log
        if self.error_log.exists():
            try:
                with open(self.error_log, 'r', encoding='utf-8') as f:
                    all_error_logs = f.readlines()[-500:]  # Last 500 lines
            except Exception as e:
                print(f"Error reading error log: {e}")
        
        # Apply filters and display
        self.display_activity_logs(all_activity_logs)
        self.display_system_logs(all_system_logs)
        self.display_error_logs(all_error_logs)
        
        # Update status label
        self.stats_label.setText(f"Activity: {len(all_activity_logs)}, System: {len(all_system_logs)}, Errors: {len(all_error_logs)}")
    
    def display_activity_logs(self, logs):
        """Display activity logs with color coding"""
        self.activity_view.clear()
        cursor = self.activity_view.textCursor()
        
        filtered_logs = self.filter_logs(logs)
        
        for line in filtered_logs:
            # Parse line components
            parts = line.split("] [", 2)
            if len(parts) >= 3:
                timestamp = parts[0].replace("[", "")
                level = parts[1]
                module_message = parts[2].split("] ", 1)
                
                if len(module_message) >= 2:
                    module = module_message[0]
                    message = module_message[1]
                    
                    # Format based on level
                    format_timestamp = QTextCharFormat()
                    format_timestamp.setForeground(QColor("#808080"))
                    
                    format_level = QTextCharFormat()
                    if "INFO" in level:
                        format_level.setForeground(QColor("#4CAF50"))  # Green
                    elif "ACTION" in level:
                        format_level.setForeground(QColor("#2196F3"))  # Blue
                    elif "EVENT" in level:
                        format_level.setForeground(QColor("#9C27B0"))  # Purple
                    elif "WARNING" in level:
                        format_level.setForeground(QColor("#FF9800"))  # Orange
                    elif "ERROR" in level:
                        format_level.setForeground(QColor("#F44336"))  # Red
                    else:
                        format_level.setForeground(QColor("#000000"))  # Black
                    
                    format_module = QTextCharFormat()
                    format_module.setForeground(QColor("#0288D1"))  # Blue
                    format_module.setFontWeight(QFont.Weight.Bold)
                    
                    format_message = QTextCharFormat()
                    format_message.setForeground(QColor("#000000"))  # Black
                    
                    # Write formatted text
                    cursor.insertText(f"[{timestamp}] ", format_timestamp)
                    cursor.insertText(f"[{level}] ", format_level)
                    cursor.insertText(f"[{module}] ", format_module)
                    cursor.insertText(f"{message}\n", format_message)
                else:
                    # Fallback if parsing fails
                    cursor.insertText(f"{line}\n")
            else:
                # Fallback if parsing fails
                cursor.insertText(f"{line}\n")
        
        # Auto scroll if enabled
        if self.auto_scroll:
            self.activity_view.verticalScrollBar().setValue(
                self.activity_view.verticalScrollBar().maximum()
            )
    
    def display_system_logs(self, logs):
        """Display system logs"""
        self.system_view.clear()
        cursor = self.system_view.textCursor()
        
        for source, line in logs:
            if not self.should_display(source, line):
                continue
                
            # Format based on content
            format_source = QTextCharFormat()
            format_source.setForeground(QColor("#1565C0"))  # Blue
            format_source.setFontWeight(QFont.Weight.Bold)
            
            format_line = QTextCharFormat()
            
            if "ERROR" in line:
                format_line.setForeground(QColor("#D32F2F"))  # Red
            elif "WARNING" in line:
                format_line.setForeground(QColor("#F57C00"))  # Orange
            elif "INFO" in line:
                format_line.setForeground(QColor("#388E3C"))  # Green
            elif "STARTUP" in line or "INIT" in line:
                format_line.setForeground(QColor("#7B1FA2"))  # Purple
            else:
                format_line.setForeground(QColor("#000000"))  # Black
            
            # Write formatted text
            cursor.insertText(f"[{source}] ", format_source)
            cursor.insertText(f"{line}\n", format_line)
        
        # Auto scroll if enabled
        if self.auto_scroll:
            self.system_view.verticalScrollBar().setValue(
                self.system_view.verticalScrollBar().maximum()
            )
    
    def display_error_logs(self, logs):
        """Display error logs"""
        self.error_view.clear()
        cursor = self.error_view.textCursor()
        
        for line in logs:
            # Parse timestamp and error message
            if "[" in line and "]" in line:
                parts = line.split("] ", 1)
                if len(parts) >= 2:
                    timestamp = parts[0].replace("[", "")
                    error_msg = parts[1]
                    
                    format_timestamp = QTextCharFormat()
                    format_timestamp.setForeground(QColor("#808080"))
                    
                    format_error = QTextCharFormat()
                    format_error.setForeground(QColor("#D32F2F"))  # Red
                    
                    cursor.insertText(f"[{timestamp}] ", format_timestamp)
                    cursor.insertText(f"{error_msg}\n", format_error)
                else:
                    cursor.insertText(f"{line}\n")
            else:
                cursor.insertText(f"{line}\n")
        
        # Auto scroll if enabled
        if self.auto_scroll:
            self.error_view.verticalScrollBar().setValue(
                self.error_view.verticalScrollBar().maximum()
            )
    
    def filter_logs(self, logs):
        """Filter logs based on time, level, and module"""
        filtered = []
        
        # Time filter
        time_filter = self.time_filter_combo.currentText()
        now = datetime.now()
        
        for line in logs:
            # Extract timestamp
            timestamp_str = ""
            if "[" in line and "]" in line:
                timestamp_str = line.split("]", 1)[0].replace("[", "").strip()
            
            try:
                # Parse timestamp
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                
                # Apply time filter
                if time_filter == "Today" and timestamp.date() != now.date():
                    continue
                elif time_filter == "Last Hour" and (now - timestamp).seconds > 3600:
                    continue
                elif time_filter == "Last 10 Minutes" and (now - timestamp).seconds > 600:
                    continue
                
                # Apply level and module filters
                if self.should_display_log(line):
                    filtered.append(line)
            except ValueError:
                # Fallback for unparseable timestamps
                if self.should_display_log(line):
                    filtered.append(line)
        
        return filtered
    
    def should_display_log(self, line):
        """Check if log line should be displayed based on level and module filters"""
        # Level filter
        level_filter = self.level_filter.currentText()
        if level_filter != "ALL" and f"[{level_filter}]" not in line:
            return False
        
        # Module filter
        module_filter = self.module_filter.currentText()
        if module_filter != "ALL":
            module_patterns = {
                "SYSTEM": ["SYSTEM", "STARTUP", "INIT"],
                "TTS": ["TTS", "SPEAK", "VOICE"],
                "STT": ["STT", "TRANSCRIBE", "SPEECH"],
                "TRANSLATE": ["TRANSLATE", "NLLB"],
                "COHOST": ["COHOST", "REPLY", "AI"],
                "YOUTUBE": ["YOUTUBE", "PYTCHAT"],
                "TIKTOK": ["TIKTOK", "TIKTOKLIVE"],
                "ANIMAZE": ["ANIMAZE", "AVATAR", "F1", "F2"],
                "LICENSE": ["LICENSE", "SUBSCRIPTION"],
                "USER": ["USER", "VIEWER", "PENONTON"],
                "PAYMENT": ["PAYMENT", "TRAKTEER", "MIDTRANS"],
                "VIRTUAL_MIC": ["VIRTUAL_MIC", "AUDIO"],
                "RAG": ["RAG", "KNOWLEDGE"],
                "OVERLAY": ["OVERLAY", "DISPLAY"]
            }
            
            patterns = module_patterns.get(module_filter, [])
            return any(pattern in line.upper() for pattern in patterns)
        
        return True
    
    def should_display(self, source, line):
        """Check if system log line should be displayed based on filters"""
        # Apply module filter
        module_filter = self.module_filter.currentText()
        if module_filter != "ALL" and module_filter != source.upper():
            return False
        
        # Apply level filter
        level_filter = self.level_filter.currentText()
        if level_filter != "ALL":
            level_patterns = {
                "INFO": ["INFO", "INIT", "STARTED"],
                "ACTION": ["ACTION", "EXEC", "RUNNING"],
                "EVENT": ["EVENT", "CALLBACK", "SIGNAL"],
                "WARNING": ["WARNING", "WARN", "CAUTION"],
                "ERROR": ["ERROR", "EXCEPTION", "FAIL"]
            }
            
            patterns = level_patterns.get(level_filter, [])
            return any(pattern in line.upper() for pattern in patterns)
        
        return True
    
    def apply_filters(self):
        """Apply current filters"""
        self.filter_level = self.level_filter.currentText()
        self.filter_module = self.module_filter.currentText()
        self.time_filter = self.time_filter_combo.currentText()
        self.reload_logs()
    
    def toggle_auto_refresh(self, checked):
        """Toggle auto refresh"""
        self.auto_refresh = checked
        if checked:
            self.refresh_timer.start()
        else:
            self.refresh_timer.stop()
    
    def update_interval(self, value):
        """Update refresh interval"""
        self.refresh_timer.setInterval(value * 1000)
    
    def clear_displays(self):
        """Clear all displays"""
        self.activity_view.clear()
        self.system_view.clear()
        self.error_view.clear()
    
    def export_logs(self):
        """Export logs to file"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Logs",
                f"streammate_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "Text Files (*.txt);;JSON Files (*.json)"
            )
            
            if file_path:
                # Log export activity
                self.log_activity(f"Exporting logs to {file_path}", "ACTION", "SYSTEM_LOG")
                
                if file_path.endswith('.json'):
                    # Export as JSON
                    log_data = {
                        "activity": self.activity_view.toPlainText().splitlines(),
                        "system": self.system_view.toPlainText().splitlines(),
                        "error": self.error_view.toPlainText().splitlines(),
                        "exported_at": datetime.now().isoformat(),
                        "app_version": self.cfg.get("app_version", "1.0.0")
                    }
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(log_data, f, indent=2)
                else:
                    # Export as plain text
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("==== STREAMMATE AI LOGS ====\n")
                        f.write(f"Exported: {datetime.now()}\n")
                        f.write(f"Version: {self.cfg.get('app_version', '1.0.0')}\n\n")
                        
                        f.write("==== ACTIVITY LOG ====\n")
                        f.write(self.activity_view.toPlainText())
                        f.write("\n\n")
                        
                        f.write("==== SYSTEM LOG ====\n")
                        f.write(self.system_view.toPlainText())
                        f.write("\n\n")
                        
                        f.write("==== ERROR LOG ====\n")
                        f.write(self.error_view.toPlainText())
                
                QMessageBox.information(self, "Export Success", f"Log berhasil diekspor ke: {file_path}")
        
        except Exception as e:
            self.log_activity(f"Export logs failed: {str(e)}", "ERROR", "SYSTEM_LOG")
            QMessageBox.critical(self, "Export Error", f"Gagal mengekspor: {str(e)}")
    
    def purge_old_logs(self):
        """Purge logs older than 30 days"""
        reply = QMessageBox.question(
            self, "Purge Old Logs",
            "Ini akan menghapus entri log yang lebih tua dari 30 hari. Lanjutkan?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Log purge activity
                self.log_activity("Purging logs older than 30 days", "ACTION", "SYSTEM_LOG")
                
                # Purge activity log
                if self.activity_log.exists():
                    self._purge_log_file(self.activity_log)
                
                # Purge other logs
                for log_path in [self.system_log, self.tts_log, self.animaze_log, self.error_log]:
                    if log_path.exists():
                        self._purge_log_file(log_path)
                
                # Reload logs
                self.reload_logs()
                
                QMessageBox.information(self, "Purge Complete", "Log lama berhasil dibersihkan")
            except Exception as e:
                self.log_activity(f"Purge logs failed: {str(e)}", "ERROR", "SYSTEM_LOG")
                QMessageBox.critical(self, "Purge Error", f"Gagal membersihkan log: {str(e)}")
    
    def _purge_log_file(self, log_path):
        """Purge old entries from a log file"""
        if not log_path.exists():
            return
        
        try:
            # Read all lines
            with open(log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Keep only entries from the last 30 days
            cutoff_date = datetime.now() - timedelta(days=30)
            filtered_lines = []
            
            for line in lines:
                timestamp_match = None
                
                # Try to extract timestamp using various formats
                if "[" in line and "]" in line:
                    timestamp_str = line.split("]", 1)[0].replace("[", "").strip()
                    try:
                        # Try standard format
                        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                        if timestamp >= cutoff_date:
                            filtered_lines.append(line)
                    except ValueError:
                        # If parsing fails, keep the line (better safe than sorry)
                        filtered_lines.append(line)
                else:
                    # No timestamp format found, keep the line
                    filtered_lines.append(line)
            
            # Write filtered lines back
            with open(log_path, 'w', encoding='utf-8') as f:
                f.writelines(filtered_lines)
                
            # Log results
            removed_count = len(lines) - len(filtered_lines)
            self.log_activity(f"Purged {removed_count} old entries from {log_path.name}", "INFO", "SYSTEM_LOG")
            
        except Exception as e:
            print(f"Error purging log file {log_path}: {e}")
            self.log_activity(f"Error purging {log_path.name}: {str(e)}", "ERROR", "SYSTEM_LOG")
    
    def open_log_folder(self):
        """Open log folder in file explorer"""
        try:
            # Log activity
            self.log_activity("Opening log folder", "ACTION", "SYSTEM_LOG")
            
            # Open folder based on platform
            if sys.platform == "win32":
                os.startfile(self.log_dir)
            elif sys.platform == "darwin":
                os.system(f"open {self.log_dir}")
            else:
                os.system(f"xdg-open {self.log_dir}")
        except Exception as e:
            self.log_activity(f"Failed to open log folder: {str(e)}", "ERROR", "SYSTEM_LOG")
            QMessageBox.warning(self, "Error", f"Tidak dapat membuka folder: {str(e)}")
    
    def create_log_entry(self, message, level="INFO", module="SYSTEM"):
        """Create a new log entry and refresh display"""
        # Log to activity log
        self.log_activity(message, level, module)
        
        # Refresh logs if auto-refresh is enabled
        if self.auto_refresh:
            self.reload_logs()
    
    def add_startup_entries(self):
        """Add startup entries to the activity log"""
        # Log startup info
        self.log_activity("System Log Tab initialized", "INFO", "SYSTEM_LOG")
        self.log_activity(f"StreamMate version: {self.cfg.get('app_version', '1.0.0')}", "INFO", "SYSTEM")
        self.log_activity(f"Platform: {sys.platform}", "INFO", "SYSTEM")
        self.log_activity(f"Python version: {sys.version.split()[0]}", "INFO", "SYSTEM")
        
        # Log available modules
        available_modules = []
        if Path("modules_client/translate_stt.py").exists():
            available_modules.append("STT")
        if Path("modules_server/tts_engine.py").exists():
            available_modules.append("TTS")
        if Path("modules_client/nlbb_translator.py").exists():
            available_modules.append("NLLB Translator")
        if Path("ui/virtual_mic_tab.py").exists():
            available_modules.append("Virtual Mic")
        
        self.log_activity(f"Available modules: {', '.join(available_modules)}", "INFO", "SYSTEM")
        
        # Log package info
        package = self.cfg.get("paket", "basic")
        self.log_activity(f"Active package: {package.capitalize()}", "INFO", "LICENSE")
    

    def closeEvent(self, event):
        """Stop timer when closed"""
        self.refresh_timer.stop()
        self.log_activity("System Log Tab closed", "INFO", "SYSTEM_LOG")
        super().closeEvent(event)
