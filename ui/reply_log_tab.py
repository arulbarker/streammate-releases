# ui/reply_log_tab.py
import json
from datetime import datetime, timedelta
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QLineEdit, QComboBox, QCheckBox, QFileDialog,
    QSplitter, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QTextCharFormat, QColor, QFont

# Import config manager
try:
    from modules_client.config_manager import ConfigManager
except ImportError:
    from modules_server.config_manager import ConfigManager

class ReplyLogTab(QWidget):
    """Tab khusus untuk menampilkan log balasan AI dengan fitur lengkap"""
    
    # Signal untuk refresh log
    logRefreshed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager("config/settings.json")
        
        # Path file log
        self.cohost_log_path = Path("temp/cohost_log.txt")
        self.memory_path = Path("config/viewer_memory.json")
        
        # State internal
        self.filter_author = ""
        self.filter_keyword = ""
        self.show_timestamp = True
        self.auto_scroll = True
        self.entries = []
        
        # Timer untuk auto-refresh
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.reload_log)
        
        # Setup UI
        self.init_ui()
        
        # Load initial data
        self.reload_log()
        
        # Start auto-refresh (setiap 5 detik)
        self.refresh_timer.start(5000)
    
    def init_ui(self):
        """Initialize UI components dengan layout baru"""
        self.main_layout = QVBoxLayout(self)
        
        # Header dengan informasi
        header_layout = QHBoxLayout()
        title = QLabel("📜 Log Balasan AI")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title)
        
        # Info label
        self.info_label = QLabel()
        self.info_label.setStyleSheet("color: gray;")
        header_layout.addWidget(self.info_label)
        
        header_layout.addStretch()
        self.main_layout.addLayout(header_layout)
        
        # BAGIAN 1: Log Balasan dan Detail Statistics di atas (Splitter)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Log viewer (sisi kiri)
        log_group = QGroupBox("💬 Log Balasan")
        log_layout = QVBoxLayout()
        
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                background-color: #f5f5f5;
                border: 1px solid #ddd;
            }
        """)
        log_layout.addWidget(self.log_view)
        
        log_group.setLayout(log_layout)
        splitter.addWidget(log_group)
        
        # Detail viewer (sisi kanan)
        detail_group = QGroupBox("📊 Detail Statistik")
        detail_layout = QVBoxLayout()
        
        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setMaximumWidth(400)
        detail_layout.addWidget(self.detail_view)
        
        detail_group.setLayout(detail_layout)
        splitter.addWidget(detail_group)
        
        # Set splitter sizes (70/30)
        splitter.setSizes([700, 300])
        self.main_layout.addWidget(splitter, stretch=1)  # Berikan stretch untuk membesar
        
        # BAGIAN 2: Filter Options di bawah (lebih kecil)
        filter_group = QGroupBox("🔍 Filter Options")
        filter_layout = QVBoxLayout()
        filter_layout.setSpacing(5)  # Kurangi spacing
        
        # Search controls dalam satu baris
        search_layout = QHBoxLayout()
        search_layout.setSpacing(5)  # Kurangi spacing
        
        # Filter by author
        search_layout.addWidget(QLabel("Author:"))
        self.author_input = QLineEdit()
        self.author_input.setPlaceholderText("Filter by author name...")
        self.author_input.textChanged.connect(self.apply_filters)
        search_layout.addWidget(self.author_input)
        
        # Filter by keyword
        search_layout.addWidget(QLabel("Keyword:"))
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("Search in messages...")
        self.keyword_input.textChanged.connect(self.apply_filters)
        search_layout.addWidget(self.keyword_input)
        
        # View mode selector
        search_layout.addWidget(QLabel("View:"))
        self.view_mode = QComboBox()
        self.view_mode.addItems(["All", "Today", "Last Hour", "VIP Only"])
        self.view_mode.currentTextChanged.connect(self.change_view_mode)
        search_layout.addWidget(self.view_mode)
        
        filter_layout.addLayout(search_layout)
        
        # Options dan controls dalam satu baris
        option_layout = QHBoxLayout()
        
        # Checkboxes
        self.timestamp_checkbox = QCheckBox("Show Timestamp")
        self.timestamp_checkbox.setChecked(self.show_timestamp)
        self.timestamp_checkbox.toggled.connect(self.toggle_timestamp)
        option_layout.addWidget(self.timestamp_checkbox)
        
        self.autoscroll_checkbox = QCheckBox("Auto-scroll")
        self.autoscroll_checkbox.setChecked(self.auto_scroll)
        self.autoscroll_checkbox.toggled.connect(lambda x: setattr(self, 'auto_scroll', x))
        option_layout.addWidget(self.autoscroll_checkbox)
        
        # Stats
        self.stats_label = QLabel()
        option_layout.addWidget(self.stats_label)
        
        # Action buttons
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.reload_log)
        option_layout.addWidget(refresh_btn)
        
        clear_filter_btn = QPushButton("❌ Clear Filters")
        clear_filter_btn.clicked.connect(self.clear_filters)
        option_layout.addWidget(clear_filter_btn)
        
        export_btn = QPushButton("💾 Export")
        export_btn.clicked.connect(self.export_log)
        option_layout.addWidget(export_btn)
        
        clear_log_btn = QPushButton("🗑️ Clear Log")
        clear_log_btn.clicked.connect(self.clear_log)
        option_layout.addWidget(clear_log_btn)
        
        filter_layout.addLayout(option_layout)
        
        filter_group.setLayout(filter_layout)
        filter_group.setMaximumHeight(120)  # Batasi tinggi untuk menghemat ruang
        self.main_layout.addWidget(filter_group)
    
    def reload_log(self):
        """Reload log dari file dengan parsing yang lebih baik"""
        try:
            self.entries.clear()
            
            # Load dari cohost_log.txt
            if self.cohost_log_path.exists():
                content = self.cohost_log_path.read_text(encoding="utf-8")
                
                # Parse setiap baris (format: author\tmessage\treply)
                for idx, line in enumerate(content.splitlines()):
                    if not line.strip():
                        continue
                    
                    try:
                        parts = line.split("\t")
                        if len(parts) >= 3:
                            author, message, reply = parts[0], parts[1], parts[2]
                            
                            # Estimasi timestamp dari posisi log
                            timestamp = datetime.now()
                            
                            entry = {
                                "timestamp": timestamp,
                                "author": author,
                                "message": message,
                                "reply": reply,
                                "index": idx
                            }
                            self.entries.append(entry)
                    except Exception as e:
                        print(f"Error parsing log line: {e}")
            
            # Update tampilan
            self.apply_filters()
            self.update_stats()
            
            # Emit signal
            self.logRefreshed.emit()
            
        except Exception as e:
            self.log_view.append(f"[ERROR] Gagal load log: {e}")
    
    def apply_filters(self):
        """Apply filters dan update display"""
        filtered_entries = self.entries.copy()
        
        # Filter by author
        filter_author = self.author_input.text().strip().lower()
        if filter_author:
            filtered_entries = [e for e in filtered_entries if filter_author in e["author"].lower()]
        
        # Filter by keyword
        filter_keyword = self.keyword_input.text().strip().lower()
        if filter_keyword:
            filtered_entries = [e for e in filtered_entries if 
                               filter_keyword in e["message"].lower() or 
                               filter_keyword in e["reply"].lower()]
        
        # Filter by view mode
        view_mode = self.view_mode.currentText()
        now = datetime.now()
        
        if view_mode == "Today":
            filtered_entries = [e for e in filtered_entries if e["timestamp"].date() == now.date()]
        elif view_mode == "Last Hour":
            hour_ago = now - timedelta(hours=1)
            filtered_entries = [e for e in filtered_entries if e["timestamp"] > hour_ago]
        elif view_mode == "VIP Only":
            # Load viewer memory untuk filter VIP
            vip_users = self.get_vip_users()
            filtered_entries = [e for e in filtered_entries if e["author"] in vip_users]
        
        # Update display
        self.display_entries(filtered_entries)
        
        # Update info
        self.info_label.setText(f"Showing {len(filtered_entries)} of {len(self.entries)} entries")
    
    def display_entries(self, entries):
        """Display filtered entries dengan formatting yang bagus"""
        self.log_view.clear()
        
        for entry in entries:
            # Format timestamp
            if self.show_timestamp:
                timestamp_str = entry["timestamp"].strftime("%H:%M:%S")
                header = f"[{timestamp_str}] {entry['author']}"
            else:
                header = entry["author"]
            
            # Add to display dengan warna berbeda
            cursor = self.log_view.textCursor()
            
            # Author header (bold blue)
            format = QTextCharFormat()
            format.setFontWeight(QFont.Weight.Bold)
            format.setForeground(QColor("blue"))
            cursor.insertText(f"👤 {header}\n", format)
            
            # Message (italic gray)
            format = QTextCharFormat()
            format.setFontItalic(True)
            format.setForeground(QColor("gray"))
            cursor.insertText(f"   💬 {entry['message']}\n", format)
            
            # Reply (normal black)
            format = QTextCharFormat()
            format.setForeground(QColor("black"))
            cursor.insertText(f"   🤖 {entry['reply']}\n\n", format)
        
        # Auto scroll if enabled
        if self.auto_scroll:
            self.log_view.verticalScrollBar().setValue(
                self.log_view.verticalScrollBar().maximum()
            )
    
    def update_stats(self):
        """Update statistik dan detail view"""
        total = len(self.entries)
        
        # Count unique authors
        unique_authors = set(e["author"] for e in self.entries)
        
        # Count by hour
        hour_counts = {}
        for entry in self.entries:
            hour = entry["timestamp"].hour
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        # Update stats label
        self.stats_label.setText(f"Total: {total} | Authors: {len(unique_authors)}")
        
        # Update detail view
        self.detail_view.clear()
        self.detail_view.append("📊 STATISTIK LOG BALASAN\n")
        self.detail_view.append(f"Total Interaksi: {total}")
        self.detail_view.append(f"Unique Authors: {len(unique_authors)}")
        self.detail_view.append("\n📈 TOP COMMENTERS:")
        
        # Count by author
        author_counts = {}
        for entry in self.entries:
            author = entry["author"]
            author_counts[author] = author_counts.get(author, 0) + 1
        
        # Sort and display top 10
        top_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        for author, count in top_authors:
            self.detail_view.append(f"  {author}: {count} messages")
        
        # Hour distribution
        self.detail_view.append("\n⏰ MESSAGES BY HOUR:")
        for hour in sorted(hour_counts.keys()):
            bar = "█" * min(20, hour_counts[hour])
            self.detail_view.append(f"  {hour:02d}:00 | {bar} {hour_counts[hour]}")
    
    def toggle_timestamp(self, checked):
        """Toggle timestamp display"""
        self.show_timestamp = checked
        self.apply_filters()
    
    def clear_filters(self):
        """Clear all filters"""
        self.author_input.clear()
        self.keyword_input.clear()
        self.view_mode.setCurrentIndex(0)
    
    def change_view_mode(self):
        """Handle view mode change"""
        self.apply_filters()
    
    def export_log(self):
        """Export log to file"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Log", 
                f"streammate_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "Text Files (*.txt);;CSV Files (*.csv)"
            )
            
            if file_path:
                if file_path.endswith('.csv'):
                    # Export as CSV
                    import csv
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(["Timestamp", "Author", "Message", "Reply"])
                        
                        for entry in self.entries:
                            writer.writerow([
                                entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                                entry["author"],
                                entry["message"],
                                entry["reply"]
                            ])
                else:
                    # Export as formatted text
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("STREAMMATE AI - LOG BALASAN\n")
                        f.write(f"Exported: {datetime.now()}\n")
                        f.write("=" * 50 + "\n\n")
                        
                        for entry in self.entries:
                            f.write(f"[{entry['timestamp']}] {entry['author']}\n")
                            f.write(f"Message: {entry['message']}\n")
                            f.write(f"Reply: {entry['reply']}\n")
                            f.write("-" * 30 + "\n")
                
                QMessageBox.information(self, "Export Success", f"Log exported to: {file_path}")
        
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")
    
    def clear_log(self):
        """Clear all log files after confirmation"""
        reply = QMessageBox.question(
            self, "Clear Logs",
            "Are you sure you want to clear all logs?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Backup first
                if self.cohost_log_path.exists():
                    backup_path = self.cohost_log_path.with_suffix('.bak')
                    self.cohost_log_path.rename(backup_path)
                
                # Create empty file
                self.cohost_log_path.write_text("")
                
                # Reload
                self.reload_log()
                
                QMessageBox.information(self, "Success", "Logs cleared successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear logs: {str(e)}")
    
    def get_vip_users(self):
        """Get list of VIP users from viewer memory"""
        vip_users = []
        
        try:
            if self.memory_path.exists():
                data = json.loads(self.memory_path.read_text(encoding="utf-8"))
                for user, info in data.items():
                    if info.get("status") == "vip":
                        vip_users.append(user)
        except Exception as e:
            print(f"Error loading VIP users: {e}")
        
        return vip_users
    
    def closeEvent(self, event):
        """Stop timer when tab is closed"""
        self.refresh_timer.stop()
        super().closeEvent(event)