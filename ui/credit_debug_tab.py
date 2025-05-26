#!/usr/bin/env python3
"""
Credit Debug Tab - UI untuk monitoring dan testing sistem kredit
Hanya aktif untuk developer dan testing mode
"""

import json
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QGridLayout, QSpinBox, QComboBox,
    QCheckBox, QProgressBar, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont

try:
    from modules_client.credit_debug_manager import CreditDebugManager
    from modules_client.config_manager import ConfigManager
    DEBUG_AVAILABLE = True
except ImportError:
    DEBUG_AVAILABLE = False

class CreditDebugTab(QWidget):
    """Tab untuk debug dan monitoring sistem kredit"""
    
    def __init__(self):
        super().__init__()
        
        if not DEBUG_AVAILABLE:
            self._create_unavailable_ui()
            return
        
        # Initialize components
        self.cfg = ConfigManager("config/settings.json")
        self.debug_manager = CreditDebugManager()
        
        # Setup UI
        self.init_ui()
        self.setup_connections()
        
        # Start monitoring
        self.debug_manager.start_monitoring()
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(5000)  # Update setiap 5 detik
    
    def _create_unavailable_ui(self):
        """UI saat debug manager tidak tersedia"""
        layout = QVBoxLayout(self)
        
        label = QLabel("Credit Debug Manager tidak tersedia.\nHanya untuk developer mode.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: red; font-size: 14px;")
        layout.addWidget(label)
    
    def init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Header
        header = QLabel("🔍 Credit Debug & Monitoring")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #1877F2;")
        layout.addWidget(header)
        
        # Tab widget untuk organize sections
        tab_widget = QTabWidget()
        
        # Real-time Monitoring Tab
        monitoring_tab = self._create_monitoring_tab()
        tab_widget.addTab(monitoring_tab, "📊 Real-time Monitor")
        
        # Credit Testing Tab
        testing_tab = self._create_testing_tab()
        tab_widget.addTab(testing_tab, "🧪 Credit Testing")
        
        # Log Viewer Tab
        log_tab = self._create_log_viewer_tab()
        tab_widget.addTab(log_tab, "📋 Debug Logs")
        
        # Reports Tab
        reports_tab = self._create_reports_tab()
        tab_widget.addTab(reports_tab, "📈 Reports")
        
        layout.addWidget(tab_widget)
    
    def _create_monitoring_tab(self):
        """Create real-time monitoring tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Current Status Group
        status_group = QGroupBox("📊 Current Credit Status")
        status_layout = QGridLayout(status_group)
        
        self.current_credit_label = QLabel("0.0")
        self.credit_used_label = QLabel("0.0")
        self.subscription_status_label = QLabel("unknown")
        self.last_update_label = QLabel("never")
        
        status_layout.addWidget(QLabel("Current Credit (hours):"), 0, 0)
        status_layout.addWidget(self.current_credit_label, 0, 1)
        status_layout.addWidget(QLabel("Credit Used (hours):"), 1, 0)
        status_layout.addWidget(self.credit_used_label, 1, 1)
        status_layout.addWidget(QLabel("Status:"), 2, 0)
        status_layout.addWidget(self.subscription_status_label, 2, 1)
        status_layout.addWidget(QLabel("Last Update:"), 3, 0)
        status_layout.addWidget(self.last_update_label, 3, 1)
        
        layout.addWidget(status_group)
        
        # Monitoring Controls
        controls_group = QGroupBox("🎮 Monitoring Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        self.monitoring_checkbox = QCheckBox("Enable Real-time Monitoring")
        self.monitoring_checkbox.setChecked(True)
        controls_layout.addWidget(self.monitoring_checkbox)
        
        btn_snapshot = QPushButton("📸 Take Snapshot")
        btn_snapshot.clicked.connect(self.take_snapshot)
        controls_layout.addWidget(btn_snapshot)
        
        btn_generate_report = QPushButton("📋 Generate Report")
        btn_generate_report.clicked.connect(self.generate_report)
        controls_layout.addWidget(btn_generate_report)
        
        layout.addWidget(controls_group)
        
        # Recent Events Table
        events_group = QGroupBox("⚡ Recent Events")
        events_layout = QVBoxLayout(events_group)
        
        self.events_table = QTableWidget()
        self.events_table.setColumnCount(4)
        self.events_table.setHorizontalHeaderLabels(["Time", "Type", "Description", "Impact"])
        self.events_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        events_layout.addWidget(self.events_table)
        
        layout.addWidget(events_group)
        
        return widget
    
    def _create_testing_tab(self):
        """Create testing controls tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Credit Manipulation Group
        credit_group = QGroupBox("💰 Credit Manipulation")
        credit_layout = QGridLayout(credit_group)
        
        # Add Credit
        credit_layout.addWidget(QLabel("Add Credit (hours):"), 0, 0)
        self.add_credit_spin = QSpinBox()
        self.add_credit_spin.setRange(1, 1000)
        self.add_credit_spin.setValue(5)
        credit_layout.addWidget(self.add_credit_spin, 0, 1)
        
        btn_add_credit = QPushButton("➕ Add Credit")
        btn_add_credit.clicked.connect(self.test_add_credit)
        credit_layout.addWidget(btn_add_credit, 0, 2)
        
        # Consume Credit
        credit_layout.addWidget(QLabel("Consume Credit (minutes):"), 1, 0)
        self.consume_credit_spin = QSpinBox()
        self.consume_credit_spin.setRange(1, 360)
        self.consume_credit_spin.setValue(30)
        credit_layout.addWidget(self.consume_credit_spin, 1, 1)
        
        btn_consume_credit = QPushButton("➖ Consume Credit")
        btn_consume_credit.clicked.connect(self.test_consume_credit)
        credit_layout.addWidget(btn_consume_credit, 1, 2)
        
        layout.addWidget(credit_group)
        
        # Payment Simulation Group
        payment_group = QGroupBox("💳 Payment Simulation")
        payment_layout = QGridLayout(payment_group)
        
        payment_layout.addWidget(QLabel("Package:"), 0, 0)
        self.package_combo = QComboBox()
        self.package_combo.addItems(["basic", "pro"])
        payment_layout.addWidget(self.package_combo, 0, 1)
        
        btn_simulate_payment = QPushButton("💳 Simulate Payment")
        btn_simulate_payment.clicked.connect(self.test_simulate_payment)
        payment_layout.addWidget(btn_simulate_payment, 0, 2)
        
        layout.addWidget(payment_group)
        
        # Session Simulation Group
        session_group = QGroupBox("⏱️ Session Simulation")
        session_layout = QGridLayout(session_group)
        
        session_layout.addWidget(QLabel("Activity:"), 0, 0)
        self.activity_combo = QComboBox()
        self.activity_combo.addItems(["cohost_basic", "translate_basic", "cohost_pro", "translate_pro"])
        session_layout.addWidget(self.activity_combo, 0, 1)
        
        session_layout.addWidget(QLabel("Duration (minutes):"), 1, 0)
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 180)
        self.duration_spin.setValue(10)
        session_layout.addWidget(self.duration_spin, 1, 1)
        
        btn_simulate_session = QPushButton("▶️ Simulate Session")
        btn_simulate_session.clicked.connect(self.test_simulate_session)
        session_layout.addWidget(btn_simulate_session, 1, 2)
        
        layout.addWidget(session_group)
        
        # Testing Results
        results_group = QGroupBox("📋 Testing Results")
        results_layout = QVBoxLayout(results_group)
        
        self.testing_results = QTextEdit()
        self.testing_results.setMaximumHeight(200)
        self.testing_results.setReadOnly(True)
        results_layout.addWidget(self.testing_results)
        
        layout.addWidget(results_group)
        
        return widget
    
    def _create_log_viewer_tab(self):
        """Create debug log viewer tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Log Controls
        controls_group = QGroupBox("🎛️ Log Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        btn_refresh_logs = QPushButton("🔄 Refresh Logs")
        btn_refresh_logs.clicked.connect(self.refresh_logs)
        controls_layout.addWidget(btn_refresh_logs)
        
        btn_clear_logs = QPushButton("🗑️ Clear Logs")
        btn_clear_logs.clicked.connect(self.clear_logs)
        controls_layout.addWidget(btn_clear_logs)
        
        btn_export_logs = QPushButton("💾 Export Logs")
        btn_export_logs.clicked.connect(self.export_logs)
        controls_layout.addWidget(btn_export_logs)
        
        # Filter controls
        self.log_filter_combo = QComboBox()
        self.log_filter_combo.addItems(["All", "credit_change", "usage", "payment", "error", "system"])
        self.log_filter_combo.currentTextChanged.connect(self.filter_logs)
        controls_layout.addWidget(QLabel("Filter:"))
        controls_layout.addWidget(self.log_filter_combo)
        
        controls_layout.addStretch()
        layout.addWidget(controls_group)
        
        # Log Display
        log_group = QGroupBox("📄 Debug Logs")
        log_layout = QVBoxLayout(log_group)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 9))
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #dcdcdc;
                border: 1px solid #555;
            }
        """)
        log_layout.addWidget(self.log_display)
        
        layout.addWidget(log_group)
        
        return widget
    
    def _create_reports_tab(self):
        """Create reports and analytics tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Report Generation
        report_group = QGroupBox("📈 Report Generation")
        report_layout = QGridLayout(report_group)
        
        report_layout.addWidget(QLabel("Report Type:"), 0, 0)
        self.report_type_combo = QComboBox()
        self.report_type_combo.addItems([
            "Credit Usage Summary",
            "Payment History",
            "Session Analytics", 
            "Error Analysis",
            "Full Debug Report"
        ])
        report_layout.addWidget(self.report_type_combo, 0, 1)
        
        btn_generate_report = QPushButton("📋 Generate Report")
        btn_generate_report.clicked.connect(self.generate_custom_report)
        report_layout.addWidget(btn_generate_report, 0, 2)
        
        layout.addWidget(report_group)
        
        # Report Display
        report_display_group = QGroupBox("📊 Report Results")
        report_display_layout = QVBoxLayout(report_display_group)
        
        self.report_display = QTextEdit()
        self.report_display.setReadOnly(True)
        self.report_display.setFont(QFont("Consolas", 9))
        report_display_layout.addWidget(self.report_display)
        
        layout.addWidget(report_display_group)
        
        # Statistics Summary
        stats_group = QGroupBox("📊 Quick Statistics")
        stats_layout = QGridLayout(stats_group)
        
        self.total_events_label = QLabel("0")
        self.credit_changes_label = QLabel("0") 
        self.usage_sessions_label = QLabel("0")
        self.errors_count_label = QLabel("0")
        
        stats_layout.addWidget(QLabel("Total Events:"), 0, 0)
        stats_layout.addWidget(self.total_events_label, 0, 1)
        stats_layout.addWidget(QLabel("Credit Changes:"), 0, 2)
        stats_layout.addWidget(self.credit_changes_label, 0, 3)
        stats_layout.addWidget(QLabel("Usage Sessions:"), 1, 0)
        stats_layout.addWidget(self.usage_sessions_label, 1, 1)
        stats_layout.addWidget(QLabel("Errors:"), 1, 2)
        stats_layout.addWidget(self.errors_count_label, 1, 3)
        
        layout.addWidget(stats_group)
        
        return widget
    
    def setup_connections(self):
        """Setup signal connections dengan debug manager"""
        if hasattr(self, 'debug_manager'):
            self.debug_manager.credit_updated.connect(self.on_credit_updated)
            self.debug_manager.usage_tracked.connect(self.on_usage_tracked)
            self.debug_manager.anomaly_detected.connect(self.on_anomaly_detected)
    
    @pyqtSlot(dict)
    def on_credit_updated(self, change_data):
        """Handle credit update signal"""
        field = change_data.get("field", "unknown")
        old_val = change_data.get("old_value", "")
        new_val = change_data.get("new_value", "")
        timestamp = change_data.get("timestamp", "")
        
        # Add to events table
        self._add_event_to_table(
            timestamp.split('T')[1][:8] if 'T' in timestamp else timestamp,
            "Credit Change",
            f"{field}: {old_val} → {new_val}",
            change_data.get("change_magnitude", "")
        )
    
    @pyqtSlot(dict)
    def on_usage_tracked(self, usage_data):
        """Handle usage tracking signal"""
        activity = usage_data.get("activity", "unknown")
        usage_type = usage_data.get("type", "unknown")
        timestamp = usage_data.get("timestamp", "")
        
        description = f"{activity} - {usage_type}"
        if usage_type == "usage_end":
            minutes = usage_data.get("minutes_used", 0)
            description += f" ({minutes} min)"
        
        self._add_event_to_table(
            timestamp.split('T')[1][:8] if 'T' in timestamp else timestamp,
            "Usage",
            description,
            usage_data.get("credit_consumed", "")
        )
    
    @pyqtSlot(str)
    def on_anomaly_detected(self, error_message):
        """Handle anomaly detection"""
        self._add_event_to_table(
            datetime.now().strftime("%H:%M:%S"),
            "ERROR",
            error_message,
            "⚠️"
        )
        
        # Also add to testing results if visible
        if hasattr(self, 'testing_results'):
            self.testing_results.append(f"[ERROR] {error_message}")
    
    def _add_event_to_table(self, time_str, event_type, description, impact):
        """Add event ke events table"""
        if not hasattr(self, 'events_table'):
            return
            
        row = self.events_table.rowCount()
        self.events_table.insertRow(row)
        
        self.events_table.setItem(row, 0, QTableWidgetItem(time_str))
        self.events_table.setItem(row, 1, QTableWidgetItem(event_type))
        self.events_table.setItem(row, 2, QTableWidgetItem(description))
        self.events_table.setItem(row, 3, QTableWidgetItem(str(impact)))
        
        # Keep only last 50 events
        if self.events_table.rowCount() > 50:
            self.events_table.removeRow(0)
        
        # Auto scroll to bottom
        self.events_table.scrollToBottom()
    
    def update_display(self):
        """Update display dengan data terbaru"""
        if not hasattr(self, 'debug_manager'):
            return
            
        try:
            summary = self.debug_manager.get_debug_summary()
            
            # Update status labels
            self.current_credit_label.setText(f"{summary['current_credit']:.2f}")
            self.credit_used_label.setText(f"{summary['credit_used']:.2f}")
            self.subscription_status_label.setText(summary['subscription_status'])
            self.last_update_label.setText(summary['last_update'])
            
            # Update monitoring checkbox dari debug manager
            if hasattr(self, 'monitoring_checkbox'):
                self.monitoring_checkbox.setChecked(summary['monitoring_active'])
            
            # Update statistics
            if hasattr(self, 'debug_manager') and hasattr(self.debug_manager, 'credit_history'):
                events = self.debug_manager.credit_history
                
                self.total_events_label.setText(str(len(events)))
                
                credit_changes = len([e for e in events if e.get('category') == 'credit_change'])
                self.credit_changes_label.setText(str(credit_changes))
                
                usage_sessions = len([e for e in events if e.get('category') == 'usage'])
                self.usage_sessions_label.setText(str(usage_sessions))
                
                errors = len([e for e in events if e.get('category') == 'error'])
                self.errors_count_label.setText(str(errors))
                
        except Exception as e:
            print(f"[CREDIT_DEBUG_TAB] Update error: {e}")
    
    # Testing Methods
    def test_add_credit(self):
        """Test menambah kredit"""
        hours = self.add_credit_spin.value()
        
        if hasattr(self, 'debug_manager'):
            self.debug_manager.force_credit_test("add_credit")
            self.debug_manager._simulate_credit_addition(hours)
            
            self.testing_results.append(f"✅ Added {hours} hours credit")
            self.testing_results.append(f"Timestamp: {datetime.now().isoformat()}")
    
    def test_consume_credit(self):
        """Test mengkonsumsi kredit"""
        minutes = self.consume_credit_spin.value()
        hours = minutes / 60.0
        
        if hasattr(self, 'debug_manager'):
            self.debug_manager.force_credit_test("consume_credit")
            self.debug_manager._simulate_credit_consumption(hours)
            
            self.testing_results.append(f"➖ Consumed {minutes} minutes ({hours:.2f} hours) credit")
            self.testing_results.append(f"Timestamp: {datetime.now().isoformat()}")
    
    def test_simulate_payment(self):
        """Test simulasi pembayaran"""
        package = self.package_combo.currentText()
        
        if hasattr(self, 'debug_manager'):
            self.debug_manager.force_credit_test("payment_complete")
            
            # Simulate berdasarkan package
            if package == "basic":
                amount = 100000
                hours = 100
            else:  # pro
                amount = 250000
                hours = 200
            
            self.debug_manager._simulate_payment_completion(package, amount)
            
            self.testing_results.append(f"💳 Simulated {package} payment: Rp {amount:,}")
            self.testing_results.append(f"Expected credit addition: {hours} hours")
            self.testing_results.append(f"Timestamp: {datetime.now().isoformat()}")
    
    def test_simulate_session(self):
        """Test simulasi sesi penggunaan"""
        activity = self.activity_combo.currentText()
        duration = self.duration_spin.value()
        
        if hasattr(self, 'debug_manager'):
            # Get current credit
            summary = self.debug_manager.get_debug_summary()
            initial_credit = summary['current_credit']
            
            # Log session start
            self.debug_manager.log_usage_start(activity, initial_credit)
            
            # Simulate usage selama duration
            hours_consumed = duration / 60.0
            self.debug_manager._simulate_credit_consumption(hours_consumed)
            
            # Log session end
            final_credit = initial_credit - hours_consumed
            self.debug_manager.log_usage_end(activity, final_credit, duration)
            
            self.testing_results.append(f"⏱️ Simulated {activity} session: {duration} minutes")
            self.testing_results.append(f"Credit consumed: {hours_consumed:.2f} hours")
            self.testing_results.append(f"Timestamp: {datetime.now().isoformat()}")
    
    def take_snapshot(self):
        """Ambil snapshot state saat ini"""
        if hasattr(self, 'debug_manager'):
            snapshot = self.debug_manager._snapshot_current_state("manual_snapshot")
            
            self.testing_results.append("📸 Snapshot taken")
            self.testing_results.append(f"Timestamp: {datetime.now().isoformat()}")
            self.testing_results.append("Check debug logs for details")
    
    def generate_report(self):
        """Generate monitoring report"""
        if hasattr(self, 'debug_manager'):
            report = self.debug_manager._generate_monitoring_report()
            
            self.testing_results.append("📋 Monitoring report generated")
            if report:
                self.testing_results.append(f"Total events: {report.get('total_events', 0)}")
                self.testing_results.append(f"Credit changes: {len(report.get('credit_changes', []))}")
                
                usage_summary = report.get('usage_summary', {})
                if usage_summary:
                    total_hours = usage_summary.get('total_hours', 0)
                    self.testing_results.append(f"Total usage: {total_hours:.2f} hours")
    
    def refresh_logs(self):
        """Refresh log display"""
        self.load_debug_logs()
    
    def clear_logs(self):
        """Clear debug logs"""
        if hasattr(self, 'debug_manager'):
            try:
                # Clear log file
                if self.debug_manager.debug_log_file.exists():
                    self.debug_manager.debug_log_file.unlink()
                
                # Clear memory
                self.debug_manager.credit_history.clear()
                
                # Clear display
                self.log_display.clear()
                
                self.testing_results.append("🗑️ Debug logs cleared")
                
            except Exception as e:
                self.testing_results.append(f"❌ Failed to clear logs: {e}")
    
    def export_logs(self):
        """Export logs ke file"""
        if hasattr(self, 'debug_manager'):
            try:
                export_file = Path(f"logs/credit_debug_export_{int(datetime.now().timestamp())}.json")
                
                export_data = {
                    "export_timestamp": datetime.now().isoformat(),
                    "events": self.debug_manager.credit_history,
                    "summary": self.debug_manager.get_debug_summary()
                }
                
                export_file.write_text(
                    json.dumps(export_data, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
                
                self.testing_results.append(f"💾 Logs exported to: {export_file}")
                
            except Exception as e:
                self.testing_results.append(f"❌ Export failed: {e}")
    
    def filter_logs(self, filter_type):
        """Filter logs berdasarkan tipe"""
        self.load_debug_logs(filter_type)
    
    def load_debug_logs(self, filter_category="All"):
        """Load dan display debug logs"""
        if not hasattr(self, 'debug_manager'):
            return
            
        try:
            if not self.debug_manager.debug_log_file.exists():
                self.log_display.setText("No debug logs found.")
                return
            
            # Read log file
            lines = self.debug_manager.debug_log_file.read_text(encoding="utf-8").splitlines()
            
            # Parse dan filter logs
            filtered_logs = []
            for line in lines:
                try:
                    log_entry = json.loads(line)
                    category = log_entry.get("category", "unknown")
                    
                    if filter_category == "All" or category == filter_category:
                        # Format untuk display
                        timestamp = log_entry.get("timestamp", "")
                        if 'T' in timestamp:
                            time_part = timestamp.split('T')[1][:8]
                        else:
                            time_part = timestamp
                        
                        data = log_entry.get("data", {})
                        if isinstance(data, dict):
                            data_str = json.dumps(data, indent=2)
                        else:
                            data_str = str(data)
                        
                        log_line = f"[{time_part}] [{category.upper()}] {data_str}"
                        filtered_logs.append(log_line)
                        
                except json.JSONDecodeError:
                    continue
            
            # Display logs (keep last 100 lines)
            display_logs = filtered_logs[-100:] if len(filtered_logs) > 100 else filtered_logs
            self.log_display.setText("\n".join(display_logs))
            
            # Auto scroll to bottom
            scrollbar = self.log_display.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
        except Exception as e:
            self.log_display.setText(f"Error loading logs: {e}")
    
    def generate_custom_report(self):
        """Generate custom report berdasarkan tipe yang dipilih"""
        report_type = self.report_type_combo.currentText()
        
        if not hasattr(self, 'debug_manager'):
            self.report_display.setText("Debug manager not available")
            return
        
        try:
            if report_type == "Credit Usage Summary":
                report = self._generate_usage_summary()
            elif report_type == "Payment History":
                report = self._generate_payment_history()
            elif report_type == "Session Analytics":
                report = self._generate_session_analytics()
            elif report_type == "Error Analysis":
                report = self._generate_error_analysis()
            else:  # Full Debug Report
                report = self.debug_manager._generate_monitoring_report()
            
            # Display report
            if isinstance(report, dict):
                formatted_report = json.dumps(report, indent=2, ensure_ascii=False)
            else:
                formatted_report = str(report)
            
            self.report_display.setText(formatted_report)
            
        except Exception as e:
            self.report_display.setText(f"Error generating report: {e}")
    
    def _generate_usage_summary(self):
        """Generate usage summary report"""
        events = self.debug_manager.credit_history
        
        usage_events = [e for e in events if e.get('category') == 'usage']
        
        summary = {
            "report_type": "Credit Usage Summary",
            "generated_at": datetime.now().isoformat(),
            "total_usage_events": len(usage_events),
            "activities": {},
            "total_credit_consumed": 0
        }
        
        for event in usage_events:
            data = event.get('data', {})
            if data.get('type') == 'usage_end':
                activity = data.get('activity', 'unknown')
                minutes = data.get('minutes_used', 0)
                
                if activity not in summary['activities']:
                    summary['activities'][activity] = {
                        'sessions': 0,
                        'total_minutes': 0,
                        'total_hours': 0
                    }
                
                summary['activities'][activity]['sessions'] += 1
                summary['activities'][activity]['total_minutes'] += minutes
                summary['activities'][activity]['total_hours'] = minutes / 60.0
                
                summary['total_credit_consumed'] += minutes / 60.0
        
        return summary
    
    def _generate_payment_history(self):
        """Generate payment history report"""
        events = self.debug_manager.credit_history
        
        payment_events = [e for e in events if e.get('category') == 'payment']
        
        history = {
            "report_type": "Payment History",
            "generated_at": datetime.now().isoformat(),
            "total_payments": len(payment_events),
            "payments": []
        }
        
        for event in payment_events:
            data = event.get('data', {})
            payment_info = {
                "timestamp": event.get('timestamp'),
                "package": data.get('package_name', 'unknown'),
                "amount": data.get('price', 0),
                "hours_added": data.get('hours', 0),
                "order_id": data.get('order_id', 'unknown')
            }
            history['payments'].append(payment_info)
        
        return history
    
    def _generate_session_analytics(self):
        """Generate session analytics report"""
        events = self.debug_manager.credit_history
        
        session_events = [e for e in events if e.get('category') == 'session_tracking']
        
        analytics = {
            "report_type": "Session Analytics",  
            "generated_at": datetime.now().isoformat(),
            "total_sessions": len(session_events),
            "average_session_duration": 0,
            "longest_session": 0,
            "shortest_session": float('inf'),
            "features_used": {}
        }
        
        total_duration = 0
        for event in session_events:
            data = event.get('data', {})
            duration = data.get('session_duration_minutes', 0)
            feature = data.get('feature', 'unknown')
            
            total_duration += duration
            analytics['longest_session'] = max(analytics['longest_session'], duration)
            analytics['shortest_session'] = min(analytics['shortest_session'], duration)
            
            if feature not in analytics['features_used']:
                analytics['features_used'][feature] = 0
            analytics['features_used'][feature] += 1
        
        if session_events:
            analytics['average_session_duration'] = total_duration / len(session_events)
        
        if analytics['shortest_session'] == float('inf'):
            analytics['shortest_session'] = 0
        
        return analytics
    
    def _generate_error_analysis(self):
        """Generate error analysis report"""
        events = self.debug_manager.credit_history
        
        error_events = [e for e in events if e.get('category') == 'error']
        
        analysis = {
            "report_type": "Error Analysis",
            "generated_at": datetime.now().isoformat(),
            "total_errors": len(error_events),
            "error_types": {},
            "recent_errors": []
        }
        
        for event in error_events:
            data = event.get('data', {})
            error_msg = str(data)
            
            # Simple error categorization
            if 'subscription' in error_msg.lower():
                error_type = 'subscription_error'
            elif 'payment' in error_msg.lower():
                error_type = 'payment_error'
            elif 'session' in error_msg.lower():
                error_type = 'session_error'
            else:
                error_type = 'other_error'
            
            if error_type not in analysis['error_types']:
                analysis['error_types'][error_type] = 0
            analysis['error_types'][error_type] += 1
            
            # Keep recent errors (last 10)
            if len(analysis['recent_errors']) < 10:
                analysis['recent_errors'].append({
                    "timestamp": event.get('timestamp'),
                    "error": error_msg
                })
        
        return analysis
    
    def closeEvent(self, event):
        """Handle close event"""
        if hasattr(self, 'debug_manager'):
            self.debug_manager.stop_monitoring()
        
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        
        super().closeEvent(event)