# ui/viewers_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTextEdit, QListWidget, QComboBox,
    QTabWidget, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView
)
from PyQt6.QtCore import Qt
from modules_client.viewer_memory import ViewerMemory

class ViewersTab(QWidget):
    """Tab untuk mengelola dan melihat informasi penonton."""
    
    def __init__(self):
        super().__init__()
        self.viewer_memory = ViewerMemory()
        self.init_ui()
        self.load_viewers()
    
    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("👥 Manajemen Penonton")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)
        
        # Main content
        content = QTabWidget()
        
        # Tab 1: Overview
        self.overview_tab = QWidget()
        self.setup_overview_tab()
        content.addTab(self.overview_tab, "📊 Overview")
        
        # Tab 2: Viewer List
        self.list_tab = QWidget()
        self.setup_list_tab()
        content.addTab(self.list_tab, "📋 Daftar Penonton")
        
        # Tab 3: Viewer Details
        self.detail_tab = QWidget()
        self.setup_detail_tab()
        content.addTab(self.detail_tab, "👤 Detail Penonton")
        
        layout.addWidget(content)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_viewers)
        button_layout.addWidget(refresh_btn)
        
        export_btn = QPushButton("💾 Export Data")
        export_btn.clicked.connect(self.export_data)
        button_layout.addWidget(export_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
    
    def setup_overview_tab(self):
        """Setup overview tab."""
        layout = QVBoxLayout(self.overview_tab)
        
        # Stats
        stats_group = QGroupBox("Statistik Penonton")
        stats_layout = QVBoxLayout()
        
        self.total_label = QLabel("Total Penonton: 0")
        stats_layout.addWidget(self.total_label)
        
        self.vip_label = QLabel("Penonton VIP: 0")
        stats_layout.addWidget(self.vip_label)
        
        self.regular_label = QLabel("Penonton Reguler: 0")
        stats_layout.addWidget(self.regular_label)
        
        self.new_label = QLabel("Penonton Baru: 0")
        stats_layout.addWidget(self.new_label)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Recent activity
        activity_group = QGroupBox("Aktivitas Terbaru")
        activity_layout = QVBoxLayout()
        
        self.activity_list = QListWidget()
        activity_layout.addWidget(self.activity_list)
        
        activity_group.setLayout(activity_layout)
        layout.addWidget(activity_group)
    
    def setup_list_tab(self):
        """Setup viewer list tab."""
        layout = QVBoxLayout(self.list_tab)
        
        # Filter options
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Filter:"))
        
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "VIP", "Regular", "New"])
        self.status_filter.currentTextChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.status_filter)
        
        filter_layout.addWidget(QLabel("Sort by:"))
        
        self.sort_by = QComboBox()
        self.sort_by.addItems(["Recent", "Interactions", "First Seen"])
        self.sort_by.currentTextChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.sort_by)
        
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)

# Tabel viewers
        self.viewers_table = QTableWidget()
        self.viewers_table.setColumnCount(4)
        self.viewers_table.setHorizontalHeaderLabels(["Nama", "Status", "Interaksi", "Terakhir Aktif"])
        self.viewers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.viewers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.viewers_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.viewers_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.viewers_table.clicked.connect(self.on_viewer_selected)
        layout.addWidget(self.viewers_table)
        
    def setup_detail_tab(self):
        """Setup viewer detail tab."""
        layout = QVBoxLayout(self.detail_tab)
        
        # Viewer info
        info_group = QGroupBox("Informasi Penonton")
        info_layout = QVBoxLayout()
        
        self.viewer_name = QLabel("Pilih penonton di tab Daftar Penonton")
        self.viewer_name.setStyleSheet("font-size: 16px; font-weight: bold;")
        info_layout.addWidget(self.viewer_name)
        
        self.viewer_status = QLabel("Status: -")
        info_layout.addWidget(self.viewer_status)
        
        self.viewer_stats = QLabel("Interaksi: - | Pertama kali: - | Terakhir aktif: -")
        info_layout.addWidget(self.viewer_stats)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Interaction history
        history_group = QGroupBox("Riwayat Interaksi")
        history_layout = QVBoxLayout()
        
        self.interaction_list = QListWidget()
        history_layout.addWidget(self.interaction_list)
        
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)
        
        # Actions
        action_layout = QHBoxLayout()
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["new", "regular", "vip"])
        action_layout.addWidget(self.status_combo)
        
        update_btn = QPushButton("📝 Update Status")
        update_btn.clicked.connect(self.update_viewer_status)
        action_layout.addWidget(update_btn)
        
        delete_btn = QPushButton("🗑️ Hapus Data")
        delete_btn.clicked.connect(self.delete_viewer)
        action_layout.addWidget(delete_btn)
        
        layout.addLayout(action_layout)
    
    def load_viewers(self):
        """Load viewers data from memory."""
        memory_data = self.viewer_memory.memory_data
        
        # Update overview stats
        total = len(memory_data)
        vip_count = sum(1 for v in memory_data.values() if v.get("status") == "vip")
        regular_count = sum(1 for v in memory_data.values() if v.get("status") == "regular")
        new_count = sum(1 for v in memory_data.values() if v.get("status") == "new")
        
        self.total_label.setText(f"Total Penonton: {total}")
        self.vip_label.setText(f"Penonton VIP: {vip_count}")
        self.regular_label.setText(f"Penonton Reguler: {regular_count}")
        self.new_label.setText(f"Penonton Baru: {new_count}")
        
        # Update recent activity
        self.activity_list.clear()
        recent_activity = []
        
        for name, data in memory_data.items():
            for interaction in data.get("recent_interactions", [])[-3:]:  # Last 3 interactions
                time_str = interaction.get("time", "")[:16].replace("T", " ")  # Simple format: "YYYY-MM-DD HH:MM"
                recent_activity.append((time_str, name, interaction.get("message", "")))
        
        # Sort by time (newest first)
        recent_activity.sort(reverse=True)
        
        # Add to list
        for time_str, name, message in recent_activity[:20]:  # Show only last 20
            self.activity_list.addItem(f"[{time_str}] {name}: {message[:50]}{'...' if len(message) > 50 else ''}")
        
        # Apply filters to update the viewers table
        self.apply_filters()
    
    def apply_filters(self):
        """Apply filters to viewers list."""
        memory_data = self.viewer_memory.memory_data
        filtered_data = []
        
        # Filter by status
        status_filter = self.status_filter.currentText()
        if status_filter != "All":
            status_filter = status_filter.lower()
            
            for name, data in memory_data.items():
                if data.get("status") == status_filter:
                    filtered_data.append((name, data))
        else:
            filtered_data = list(memory_data.items())
        
        # Sort by selected option
        sort_by = self.sort_by.currentText()
        if sort_by == "Recent":
            filtered_data.sort(key=lambda x: x[1].get("last_seen", ""), reverse=True)
        elif sort_by == "Interactions":
            filtered_data.sort(key=lambda x: x[1].get("comment_count", 0), reverse=True)
        elif sort_by == "First Seen":
            filtered_data.sort(key=lambda x: x[1].get("first_seen", ""))
        
        # Update table
        self.viewers_table.setRowCount(len(filtered_data))
        
        for i, (name, data) in enumerate(filtered_data):
            # Name
            self.viewers_table.setItem(i, 0, QTableWidgetItem(name))
            
            # Status
            status = data.get("status", "new").capitalize()
            status_item = QTableWidgetItem(status)
            if status == "Vip":
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            elif status == "Regular":
                status_item.setForeground(Qt.GlobalColor.blue)
            self.viewers_table.setItem(i, 1, status_item)
            
            # Interactions
            self.viewers_table.setItem(i, 2, QTableWidgetItem(str(data.get("comment_count", 0))))
            
            # Last seen
            last_seen = data.get("last_seen", "")[:16].replace("T", " ")
            self.viewers_table.setItem(i, 3, QTableWidgetItem(last_seen))
    
    def on_viewer_selected(self):
        """Handle viewer selection in table."""
        selected_items = self.viewers_table.selectedItems()
        if not selected_items:
            return
        
        # Get viewer name from first column
        row = selected_items[0].row()
        name = self.viewers_table.item(row, 0).text()
        
        # Load viewer details
        self.load_viewer_details(name)
    
    def load_viewer_details(self, name):
        """Load and display viewer details."""
        viewer_data = self.viewer_memory.get_viewer_info(name)
        if not viewer_data:
            return
        
        # Update viewer info
        self.viewer_name.setText(name)
        self.viewer_status.setText(f"Status: {viewer_data.get('status', 'new').capitalize()}")
        
        first_seen = viewer_data.get("first_seen", "")[:16].replace("T", " ")
        last_seen = viewer_data.get("last_seen", "")[:16].replace("T", " ")
        
        self.viewer_stats.setText(
            f"Interaksi: {viewer_data.get('comment_count', 0)} | "
            f"Pertama kali: {first_seen} | "
            f"Terakhir aktif: {last_seen}"
        )
        
        # Set status combobox
        status_index = self.status_combo.findText(viewer_data.get("status", "new"))
        if status_index >= 0:
            self.status_combo.setCurrentIndex(status_index)
        
        # Update interaction history
        self.interaction_list.clear()
        
        for interaction in viewer_data.get("recent_interactions", []):
            time_str = interaction.get("time", "")[:16].replace("T", " ")
            message = interaction.get("message", "")
            reply = interaction.get("reply", "")
            
            item_text = f"[{time_str}] 💬 {message}\n"
            item_text += f"🤖 {reply}"
            
            self.interaction_list.addItem(item_text)
    
    def update_viewer_status(self):
        """Update viewer status."""
        selected_items = self.viewers_table.selectedItems()
        if not selected_items:
            return
        
        # Get viewer name from first column
        row = selected_items[0].row()
        name = self.viewers_table.item(row, 0).text()
        
        # Update status
        new_status = self.status_combo.currentText()
        
        if name in self.viewer_memory.memory_data:
            self.viewer_memory.memory_data[name]["status"] = new_status
            self.viewer_memory._save_memory()
            
            # Refresh
            self.load_viewers()
            self.load_viewer_details(name)
    
    def delete_viewer(self):
        """Delete viewer data."""
        selected_items = self.viewers_table.selectedItems()
        if not selected_items:
            return
        
        # Get viewer name from first column
        row = selected_items[0].row()
        name = self.viewers_table.item(row, 0).text()
        
        # Confirm deletion
        from PyQt6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self, 
            'Konfirmasi Hapus',
            f'Yakin ingin menghapus data penonton "{name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if name in self.viewer_memory.memory_data:
                del self.viewer_memory.memory_data[name]
                self.viewer_memory._save_memory()
                
                # Reset detail view
                self.viewer_name.setText("Pilih penonton di tab Daftar Penonton")
                self.viewer_status.setText("Status: -")
                self.viewer_stats.setText("Interaksi: - | Pertama kali: - | Terakhir aktif: -")
                self.interaction_list.clear()
                
                # Refresh
                self.load_viewers()
    
    def export_data(self):
        """Export viewers data to CSV."""
        from PyQt6.QtWidgets import QFileDialog
        import csv
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Data Penonton", "", "CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Nama", "Status", "Interaksi", "Pertama Kali", "Terakhir Aktif"])
                
                for name, data in self.viewer_memory.memory_data.items():
                    writer.writerow([
                        name,
                        data.get("status", "new"),
                        data.get("comment_count", 0),
                        data.get("first_seen", "")[:16].replace("T", " "),
                        data.get("last_seen", "")[:16].replace("T", " ")
                    ])
            
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Export Berhasil", f"Data berhasil diekspor ke {file_path}")
            
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Export Gagal", f"Gagal mengekspor data: {str(e)}")