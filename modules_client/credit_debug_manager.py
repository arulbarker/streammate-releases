#!/usr/bin/env python3
"""
Credit Debug Manager - Sistem debug detail untuk tracking kredit
Untuk testing dan monitoring sistem billing StreamMate AI
"""

import json
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

class CreditDebugManager(QObject):
    """Manager untuk debug sistem kredit secara detail"""
    
    # Signals untuk real-time monitoring
    credit_updated = pyqtSignal(dict)  # {type, old_value, new_value, timestamp}
    usage_tracked = pyqtSignal(dict)   # {activity, minutes, remaining_credit}
    anomaly_detected = pyqtSignal(str) # Error message
    
    def __init__(self):
        super().__init__()
        
        # Paths
        self.debug_log_file = Path("logs/credit_debug.jsonl")
        self.subscription_file = Path("config/subscription_status.json") 
        self.session_file = Path("temp/current_session.json")
        
        # Ensure directories exist
        self.debug_log_file.parent.mkdir(exist_ok=True)
        
        # State tracking
        self.last_credit_check = 0
        self.monitoring_active = False
        self.credit_history = []
        self.usage_history = []
        
        # Timer untuk monitoring kontinyu
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._periodic_check)
        self.monitor_timer.setInterval(10000)  # Check setiap 10 detik
        
        # Initialize
        self._log_debug("system", "Credit Debug Manager initialized")
    
    def start_monitoring(self):
        """Mulai monitoring real-time kredit"""
        self.monitoring_active = True
        self.monitor_timer.start()
        self._log_debug("system", "Credit monitoring started")
        
        # Log initial state
        self._snapshot_current_state("monitoring_start")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring_active = False
        self.monitor_timer.stop()
        self._log_debug("system", "Credit monitoring stopped")
        
        # Generate summary report
        self._generate_monitoring_report()
    
    def _periodic_check(self):
        """Check berkala untuk detect perubahan kredit"""
        try:
            # Check subscription file changes
            if self.subscription_file.exists():
                current_data = self._read_subscription_data()
                
                # Compare dengan state sebelumnya
                if hasattr(self, '_last_subscription_data'):
                    changes = self._detect_credit_changes(
                        self._last_subscription_data, 
                        current_data
                    )
                    
                    if changes:
                        for change in changes:
                            self._log_debug("credit_change", change)
                            self.credit_updated.emit(change)
                
                self._last_subscription_data = current_data.copy()
            
            # Check session file untuk tracking usage
            if self.session_file.exists():
                session_data = self._read_session_data()
                if session_data.get("active", False):
                    self._track_active_session(session_data)
                    
        except Exception as e:
            self._log_debug("error", f"Periodic check failed: {e}")
            self.anomaly_detected.emit(f"Monitoring error: {e}")
    
    def _detect_credit_changes(self, old_data, new_data):
        """Detect perubahan pada kredit dan return detail changes"""
        changes = []
        
        # Fields yang dimonitor
        monitored_fields = [
            "hours_credit", "hours_used", "status", 
            "package", "expire_date", "updated_at"
        ]
        
        for field in monitored_fields:
            old_val = old_data.get(field)
            new_val = new_data.get(field)
            
            if old_val != new_val:
                change = {
                    "type": "field_change",
                    "field": field,
                    "old_value": old_val,
                    "new_value": new_val,
                    "timestamp": datetime.now().isoformat(),
                    "change_magnitude": self._calculate_magnitude(field, old_val, new_val)
                }
                changes.append(change)
        
        return changes
    
    def _calculate_magnitude(self, field, old_val, new_val):
        """Hitung magnitude perubahan untuk numeric fields"""
        if field in ["hours_credit", "hours_used"]:
            try:
                old_num = float(old_val or 0)
                new_num = float(new_val or 0)
                return new_num - old_num
            except (ValueError, TypeError):
                return 0
        return None
    
    def log_payment_completion(self, payment_data):
        """Log saat pembayaran selesai dan kredit ditambahkan"""
        debug_data = {
            "type": "payment_completion",
            "payment_data": payment_data,
            "timestamp": datetime.now().isoformat(),
            "subscription_before": self._read_subscription_data(),
        }
        
        self._log_debug("payment", debug_data)
        
        # Set flag untuk monitor update berikutnya
        self._expecting_credit_update = True
        self._payment_completion_time = time.time()
    
    def log_usage_start(self, activity_name, initial_credit):
        """Log saat mulai menggunakan fitur yang mengkonsumsi kredit"""
        usage_data = {
            "type": "usage_start", 
            "activity": activity_name,
            "initial_credit": initial_credit,
            "timestamp": datetime.now().isoformat(),
            "session_id": self._generate_session_id()
        }
        
        self._log_debug("usage", usage_data)
        self.usage_tracked.emit(usage_data)
    
    def log_usage_end(self, activity_name, final_credit, minutes_used):
        """Log saat selesai menggunakan fitur"""
        usage_data = {
            "type": "usage_end",
            "activity": activity_name, 
            "final_credit": final_credit,
            "minutes_used": minutes_used,
            "credit_consumed": minutes_used / 60.0,  # Convert to hours
            "timestamp": datetime.now().isoformat()
        }
        
        self._log_debug("usage", usage_data)
        self.usage_tracked.emit(usage_data)
        
        # Validate usage calculation
        self._validate_usage_calculation(usage_data)
    
    def _validate_usage_calculation(self, usage_data):
        """Validasi kalkulasi penggunaan kredit"""
        expected_credit_reduction = usage_data["credit_consumed"]
        
        # Check apakah kredit berkurang sesuai ekspektasi
        current_subscription = self._read_subscription_data()
        
        # Log untuk validation
        validation = {
            "type": "usage_validation",
            "expected_reduction": expected_credit_reduction,
            "current_credit": current_subscription.get("hours_credit", 0),
            "timestamp": datetime.now().isoformat(),
            "validation_passed": None  # Will be calculated
        }
        
        self._log_debug("validation", validation)
    
    def _snapshot_current_state(self, reason):
        """Ambil snapshot lengkap dari state saat ini"""
        snapshot = {
            "type": "state_snapshot",
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "subscription_data": self._read_subscription_data(),
            "session_data": self._read_session_data(),
            "system_info": {
                "monitoring_active": self.monitoring_active,
                "last_credit_check": self.last_credit_check
            }
        }
        
        self._log_debug("snapshot", snapshot)
        return snapshot
    
    def _read_subscription_data(self):
        """Read subscription data dengan error handling"""
        try:
            if self.subscription_file.exists():
                return json.loads(self.subscription_file.read_text(encoding="utf-8"))
        except Exception as e:
            self._log_debug("error", f"Failed to read subscription: {e}")
        return {}
    
    def _read_session_data(self):
        """Read session data dengan error handling"""
        try:
            if self.session_file.exists():
                return json.loads(self.session_file.read_text(encoding="utf-8"))
        except Exception as e:
            self._log_debug("error", f"Failed to read session: {e}")
        return {}
    
    def _track_active_session(self, session_data):
        """Track sesi yang sedang aktif"""
        session_start = session_data.get("start_time", 0)
        current_time = time.time()
        
        if session_start > 0:
            session_duration = current_time - session_start
            
            tracking_data = {
                "type": "active_session_tracking",
                "session_duration_seconds": session_duration,
                "session_duration_minutes": session_duration / 60.0,
                "feature": session_data.get("feature", "unknown"),
                "timestamp": datetime.now().isoformat()
            }
            
            self._log_debug("session_tracking", tracking_data)
    
    def _generate_session_id(self):
        """Generate unique session ID untuk tracking"""
        return f"debug_{int(time.time())}_{hash(threading.current_thread().ident) % 10000}"
    
    def _log_debug(self, category, data):
        """Log debug data ke file"""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "category": category,
                "thread_id": threading.current_thread().ident,
                "data": data
            }
            
            with open(self.debug_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                
            # Keep in memory untuk analysis
            if len(self.credit_history) > 1000:  # Limit memory usage
                self.credit_history = self.credit_history[-500:]
            self.credit_history.append(log_entry)
            
        except Exception as e:
            print(f"[CREDIT_DEBUG] Failed to log: {e}")
    
    def _generate_monitoring_report(self):
        """Generate laporan monitoring session"""
        if not self.credit_history:
            return
        
        report = {
            "report_type": "monitoring_session_summary",
            "session_start": self.credit_history[0].get("timestamp"),
            "session_end": datetime.now().isoformat(),
            "total_events": len(self.credit_history),
            "event_categories": {},
            "anomalies": [],
            "credit_changes": [],
            "usage_summary": {}
        }
        
        # Analyze events
        for entry in self.credit_history:
            category = entry.get("category", "unknown")
            report["event_categories"][category] = report["event_categories"].get(category, 0) + 1
            
            # Collect credit changes
            if category == "credit_change":
                report["credit_changes"].append(entry["data"])
        
        # Calculate usage statistics
        usage_events = [e for e in self.credit_history if e.get("category") == "usage"]
        if usage_events:
            total_usage_minutes = sum(
                e["data"].get("minutes_used", 0) 
                for e in usage_events 
                if e["data"].get("type") == "usage_end"
            )
            report["usage_summary"]["total_minutes"] = total_usage_minutes
            report["usage_summary"]["total_hours"] = total_usage_minutes / 60.0
        
        # Save report
        report_file = Path(f"logs/credit_debug_report_{int(time.time())}.json")
        report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        
        self._log_debug("report", f"Monitoring report saved: {report_file}")
        
        return report
    
    def get_debug_summary(self):
        """Get summary debug data untuk UI display"""
        recent_events = self.credit_history[-10:] if self.credit_history else []
        
        subscription_data = self._read_subscription_data()
        session_data = self._read_session_data()
        
        return {
            "current_credit": subscription_data.get("hours_credit", 0),
            "credit_used": subscription_data.get("hours_used", 0),
            "subscription_status": subscription_data.get("status", "unknown"),
            "active_session": session_data.get("active", False),
            "recent_events_count": len(recent_events),
            "monitoring_active": self.monitoring_active,
            "last_update": subscription_data.get("updated_at", "never")
        }
    
    def force_credit_test(self, test_scenario):
        """Force test scenario untuk debugging"""
        self._log_debug("test", f"Force test scenario: {test_scenario}")
        
        if test_scenario == "add_credit":
            # Simulate kredit ditambahkan
            self._simulate_credit_addition(5.0)  # Add 5 hours
            
        elif test_scenario == "consume_credit":
            # Simulate kredit dikonsumsi
            self._simulate_credit_consumption(0.5)  # Consume 30 minutes
            
        elif test_scenario == "payment_complete":
            # Simulate pembayaran selesai
            self._simulate_payment_completion("basic", 100000)
    
    def _simulate_credit_addition(self, hours):
        """Simulate penambahan kredit untuk testing"""
        current_data = self._read_subscription_data()
        current_credit = float(current_data.get("hours_credit", 0))
        new_credit = current_credit + hours
        
        current_data["hours_credit"] = new_credit
        current_data["updated_at"] = datetime.now().isoformat()
        
        self.subscription_file.write_text(
            json.dumps(current_data, indent=2), 
            encoding="utf-8"
        )
        
        self._log_debug("simulation", {
            "type": "credit_addition",
            "hours_added": hours,
            "old_credit": current_credit,
            "new_credit": new_credit
        })
    
    def _simulate_credit_consumption(self, hours):
        """Simulate konsumsi kredit untuk testing"""
        current_data = self._read_subscription_data()
        current_credit = float(current_data.get("hours_credit", 0))
        current_used = float(current_data.get("hours_used", 0))
        
        new_credit = max(0, current_credit - hours)
        new_used = current_used + hours
        
        current_data["hours_credit"] = new_credit
        current_data["hours_used"] = new_used
        current_data["updated_at"] = datetime.now().isoformat()
        
        self.subscription_file.write_text(
            json.dumps(current_data, indent=2),
            encoding="utf-8"
        )
        
        self._log_debug("simulation", {
            "type": "credit_consumption",
            "hours_consumed": hours,
            "old_credit": current_credit,
            "new_credit": new_credit,
            "total_used": new_used
        })
    
    def _simulate_payment_completion(self, package, amount):
        """Simulate pembayaran selesai"""
        payment_data = {
            "package": package,
            "amount": amount,
            "timestamp": datetime.now().isoformat(),
            "simulation": True
        }
        
        self.log_payment_completion(payment_data)
        
        # Simulate credit addition based on package
        if package == "basic":
            self._simulate_credit_addition(100.0)  # 100 hours
        elif package == "pro":
            self._simulate_credit_addition(200.0)  # 200 hours