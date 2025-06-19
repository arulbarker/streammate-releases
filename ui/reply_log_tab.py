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
from modules_server.config_manager import ConfigManager

# ✅ FIX: Impor fungsi path helper
from utils.path_util import get_app_data_path

class ReplyLogTab(QWidget):
    """Special tab for displaying AI reply logs with comprehensive features"""
    
    # Signal untuk refresh log
    logRefreshed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = ConfigManager("config/settings.json")
        
        # ✅ FIX: Gunakan fungsi helper untuk path log yang aman untuk EXE
        self.cohost_log_path = get_app_data_path("cohost_log.txt")
        self.memory_path = Path("config/viewer_memory.json")
        
        # State internal
        self.filter_author = ""
        self.filter_keyword = ""
        self.show_timestamp = True
        self.auto_scroll = True
        self.ai_replies = []  # ✅ UBAH: Hanya simpan AI replies
        self.filtered_replies = []
        
        # Timer untuk auto-refresh
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.reload_log)
        
        # Setup UI
        self.init_ui()
        
        # Load initial data
        self.reload_log()
        
        # Start auto-refresh - OPTIMASI: Interval lebih lambat
        self.refresh_timer.start(30000)  # ✅ OPTIMASI: Ubah dari 5 detik ke 30 detik
    
    def init_ui(self):
        """Initialize UI components dengan layout baru"""
        self.main_layout = QVBoxLayout(self)
        
        # Header dengan informasi
        header_layout = QHBoxLayout()
        title = QLabel("🤖 AI Reply Logs")  # ✅ UBAH: Lebih spesifik AI replies
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
        log_group = QGroupBox("🤖 AI Replies Only")  # ✅ UBAH: Jelas AI replies only
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
        detail_group = QGroupBox("📊 AI Reply Statistics")  # ✅ UBAH: AI Reply Statistics
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
        self.keyword_input.setPlaceholderText("Search in messages or replies...")
        self.keyword_input.textChanged.connect(self.apply_filters)
        search_layout.addWidget(self.keyword_input)
        
        # View mode selector - ✅ UBAH: Sesuaikan dengan AI replies only
        search_layout.addWidget(QLabel("View:"))
        self.view_mode = QComboBox()
        self.view_mode.addItems(["All AI Replies", "Today", "Last Hour", "VIP Only", "Recent 50"])
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
        """Muat ulang log dari file dan proses datanya dengan filter yang benar."""
        self.ai_replies.clear()
        
        try:
            if not self.cohost_log_path.exists():
                self.log_view.setPlainText("Log file tidak ditemukan. Mulai streaming untuk membuat log.")
                return

            with open(self.cohost_log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for idx, line in enumerate(lines):
                if not line.strip():
                    continue
                
                try:
                    parts = line.strip().split('\t')
                    
                    # Filter Utama: Harus punya 4 bagian DAN bagian ke-4 bukan status.
                    if len(parts) >= 4:
                        reply_or_status = parts[3]
                        
                        # Lewati baris status seperti '[NO-TRIGGER] Komentar diterima'
                        if reply_or_status.startswith('[') and 'Komentar diterima' in reply_or_status:
                            continue

                        # Jika lolos filter, ini adalah balasan AI asli.
                        timestamp_str, author, message = parts[0], parts[1], parts[2]
                        
                        try:
                            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            timestamp = datetime.now()

                        entry = {
                            "timestamp": timestamp,
                            "author": author,
                            "message": message,
                            "reply": reply_or_status,
                            "is_ai_reply": True,
                            "index": idx
                        }
                        self.ai_replies.append(entry)
                        
                except Exception as e:
                    print(f"Error parsing log line: {e} - Line: '{line.strip()}'")
            
            # Update tampilan setelah semua log diproses
            self.apply_filters()
            self.update_stats()

        except Exception as e:
            print(f"Failed to reload log file: {e}")
            self.log_view.setPlainText(f"Error reading log file: {e}")
    
    def apply_filters(self):
        """Apply filters dan update display - KHUSUS AI REPLIES"""
        filtered_replies = self.ai_replies.copy()  # ✅ UBAH: ai_replies
        
        # Filter by author
        filter_author = self.author_input.text().strip().lower()
        if filter_author:
            filtered_replies = [e for e in filtered_replies if filter_author in e["author"].lower()]
        
        # Filter by keyword
        filter_keyword = self.keyword_input.text().strip().lower()
        if filter_keyword:
            filtered_replies = [e for e in filtered_replies if 
                               filter_keyword in e["message"].lower() or 
                               filter_keyword in e["reply"].lower()]
        
        # Filter by view mode
        view_mode = self.view_mode.currentText()
        now = datetime.now()
        
        if view_mode == "Today":
            filtered_replies = [e for e in filtered_replies if e["timestamp"].date() == now.date()]
        elif view_mode == "Last Hour":
            hour_ago = now - timedelta(hours=1)
            filtered_replies = [e for e in filtered_replies if e["timestamp"] > hour_ago]
        elif view_mode == "VIP Only":
            # Load viewer memory untuk filter VIP
            vip_users = self.get_vip_users()
            filtered_replies = [e for e in filtered_replies if e["author"] in vip_users]
        elif view_mode == "Recent 50":
            # Ambil 50 AI replies terbaru
            filtered_replies = sorted(filtered_replies, key=lambda x: x["timestamp"], reverse=True)[:50]
        
        # Update display
        self.display_ai_replies(filtered_replies)  # ✅ UBAH: nama method
        
        # Update info
        self.info_label.setText(f"Showing {len(filtered_replies)} of {len(self.ai_replies)} AI replies")
    
    def display_ai_replies(self, ai_replies):  # ✅ UBAH: nama method dan parameter
        """Display filtered AI replies with nice formatting"""
        self.log_view.clear()
        
        for entry in ai_replies:
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
            
            # AI Reply (normal black with robot icon)
            format = QTextCharFormat()
            format.setForeground(QColor("black"))
            cursor.insertText(f"   🤖 {entry['reply']}\n\n", format)
        
        # Auto scroll if enabled
        if self.auto_scroll:
            self.log_view.verticalScrollBar().setValue(
                self.log_view.verticalScrollBar().maximum()
            )
    
    def update_stats(self):
        """Update statistics and detail view with AI replies info"""
        total_replies = len(self.ai_replies)  # ✅ UBAH: ai_replies
        
        # Count unique authors replied by AI
        unique_authors = set(e["author"] for e in self.ai_replies)
        
        # Count by hour
        hour_counts = {}
        for entry in self.ai_replies:
            hour = entry["timestamp"].hour
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        # Update stats label with AI replies info
        self.stats_label.setText(f"AI Replies: {total_replies} | Authors Replied: {len(unique_authors)}")
        
        # Update detail view
        self.detail_view.clear()
        self.detail_view.append("🤖 AI REPLY STATISTICS\n")
        self.detail_view.append(f"Total AI Replies: {total_replies}")
        self.detail_view.append(f"Unique Authors Replied: {len(unique_authors)}")
        
        # Average reply length
        if self.ai_replies:
            avg_reply_length = sum(len(e["reply"]) for e in self.ai_replies) / len(self.ai_replies)
            self.detail_view.append(f"Avg Reply Length: {avg_reply_length:.1f} chars")
        
        self.detail_view.append("\n📈 TOP REPLIED AUTHORS:")
        
        # Count by author
        author_counts = {}
        for entry in self.ai_replies:
            author = entry["author"]
            author_counts[author] = author_counts.get(author, 0) + 1
        
        # Sort and display top 10
        top_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        for author, count in top_authors:
            self.detail_view.append(f"  {author}: {count} replies")
        
        # Hour distribution for AI replies
        self.detail_view.append("\n⏰ AI REPLIES BY HOUR:")
        for hour in sorted(hour_counts.keys()):
            bar = "█" * min(20, hour_counts[hour])
            self.detail_view.append(f"  {hour:02d}:00 | {bar} {hour_counts[hour]}")
        
        # Recent activity
        if self.ai_replies:
            latest_reply = max(self.ai_replies, key=lambda x: x["timestamp"])
            self.detail_view.append(f"\n🕒 LATEST AI REPLY:")
            self.detail_view.append(f"  Time: {latest_reply['timestamp'].strftime('%H:%M:%S')}")
            self.detail_view.append(f"  Author: {latest_reply['author']}")
            self.detail_view.append(f"  Reply: {latest_reply['reply'][:50]}...")
    
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
                self, "Export AI Reply Log", 
                f"streammate_ai_replies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "Text Files (*.txt);;CSV Files (*.csv)"
            )
            
            if file_path:
                if file_path.endswith('.csv'):
                    # Export as CSV
                    import csv
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(["Timestamp", "Author", "Message", "Reply"])
                        
                        for entry in self.ai_replies:
                            writer.writerow([
                                entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                                entry["author"],
                                entry["message"],
                                entry["reply"]
                            ])
                else:
                    # Export as formatted text
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("STREAMMATE AI - AI REPLY LOGS\n")
                        f.write(f"Exported: {datetime.now()}\n")
                        f.write(f"Total AI Replies: {len(self.ai_replies)}\n")
                        f.write("=" * 50 + "\n\n")
                        
                        for entry in self.ai_replies:
                            f.write(f"[{entry['timestamp']}] {entry['author']}\n")
                            f.write(f"Message: {entry['message']}\n")
                            f.write(f"AI Reply: {entry['reply']}\n")
                            f.write("-" * 30 + "\n")
                
                QMessageBox.information(self, "Export Success", f"Log exported to: {file_path}")
        
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")
    
    def clear_log(self):
        """Clear all log files after confirmation"""
        reply = QMessageBox.question(
            self, "Clear AI Reply Logs",
            "Are you sure you want to clear all AI reply logs?\nThis action cannot be undone.",
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
                
                QMessageBox.information(self, "Success", "AI reply logs cleared successfully")
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
