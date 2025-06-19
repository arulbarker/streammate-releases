#!/usr/bin/env python3
"""
Performance Monitor untuk StreamMate AI
Monitoring network latency, memory usage, dan performa UI
"""

import time
import psutil
import requests
import threading
from pathlib import Path
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

class PerformanceMonitor(QObject):
    """Monitor performa aplikasi real-time"""
    
    # Signals untuk update UI
    performance_update = pyqtSignal(dict)
    network_status_changed = pyqtSignal(str, float)  # status, latency
    
    def __init__(self):
        super().__init__()
        
        # Server endpoints untuk testing
        self.servers = {
            "VPS": "http://69.62.79.238:8000",
            "Localhost": "http://localhost:8888"
        }
        
        # Performance data
        self.network_stats = {}
        self.memory_stats = {}
        self.ui_stats = {}
        
        # Monitoring state
        self.monitoring_active = False
        
        # Timer untuk monitoring berkelanjutan
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._collect_metrics)
        self.monitor_timer.setInterval(30000)  # Setiap 30 detik
        
    def start_monitoring(self):
        """Mulai monitoring performa"""
        self.monitoring_active = True
        self.monitor_timer.start()
        print("[PERF] Performance monitoring started")
        
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring_active = False
        self.monitor_timer.stop()
        print("[PERF] Performance monitoring stopped")
        
    def _collect_metrics(self):
        """Collect performance metrics"""
        if not self.monitoring_active:
            return
            
        # Collect network metrics in background thread
        threading.Thread(target=self._test_network_latency, daemon=True).start()
        
        # Collect memory metrics
        self._collect_memory_stats()
        
        # Emit combined update
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "network": self.network_stats,
            "memory": self.memory_stats,
            "ui": self.ui_stats
        }
        self.performance_update.emit(metrics)
        
    def _test_network_latency(self):
        """Test network latency ke server"""
        for name, url in self.servers.items():
            try:
                start_time = time.time()
                response = requests.get(f"{url}/api/health", timeout=5)
                latency = (time.time() - start_time) * 1000  # Convert to ms
                
                status = "good" if latency < 500 else "slow" if latency < 2000 else "poor"
                
                self.network_stats[name] = {
                    "latency_ms": round(latency, 2),
                    "status": status,
                    "success": response.status_code == 200,
                    "timestamp": datetime.now().isoformat()
                }
                
                if name == "VPS":  # Primary server
                    self.network_status_changed.emit(status, latency)
                    
            except Exception as e:
                self.network_stats[name] = {
                    "latency_ms": -1,
                    "status": "error",
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                
                if name == "VPS":
                    self.network_status_changed.emit("error", -1)
                    
    def _collect_memory_stats(self):
        """Collect memory usage stats"""
        process = psutil.Process()
        
        self.memory_stats = {
            "memory_mb": round(process.memory_info().rss / 1024 / 1024, 1),
            "cpu_percent": round(process.cpu_percent(), 1),
            "threads": process.num_threads(),
            "timestamp": datetime.now().isoformat()
        }
        
    def get_network_diagnosis(self):
        """Dapatkan diagnosis network performance"""
        if not self.network_stats.get("VPS"):
            return "Network belum ditest"
            
        vps_stats = self.network_stats["VPS"]
        
        if not vps_stats["success"]:
            return "❌ VPS Server tidak dapat diakses"
            
        latency = vps_stats["latency_ms"]
        
        if latency < 200:
            return f"✅ Network Excellent ({latency}ms) - VPS sangat responsif"
        elif latency < 500:
            return f"🟡 Network Good ({latency}ms) - VPS cukup responsif"
        elif latency < 1000:
            return f"🟠 Network Slow ({latency}ms) - VPS agak lambat, coba optimasi"
        else:
            return f"❌ Network Poor ({latency}ms) - VPS sangat lambat, perlu investigasi"
            
    def get_performance_tips(self):
        """Dapatkan tips optimasi berdasarkan kondisi saat ini"""
        tips = []
        
        # Network tips
        if self.network_stats.get("VPS", {}).get("latency_ms", 0) > 1000:
            tips.append("🌐 Network lambat: Coba restart router atau ganti provider internet")
            tips.append("🌐 Alternatif: Gunakan VPN untuk rute yang lebih baik")
            
        # Memory tips  
        memory_mb = self.memory_stats.get("memory_mb", 0)
        if memory_mb > 500:
            tips.append(f"🧠 Memory usage tinggi ({memory_mb}MB): Tutup aplikasi lain yang tidak perlu")
            
        cpu_percent = self.memory_stats.get("cpu_percent", 0)
        if cpu_percent > 50:
            tips.append(f"⚡ CPU usage tinggi ({cpu_percent}%): Kurangi timer refresh atau tutup tab yang tidak digunakan")
            
        if not tips:
            tips.append("✅ Performa aplikasi dalam kondisi baik")
            
        return tips
        
    def save_performance_log(self):
        """Simpan log performa ke file"""
        log_file = Path("logs/performance.log")
        log_file.parent.mkdir(exist_ok=True)
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "network": self.network_stats,
            "memory": self.memory_stats
        }
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{log_entry}\n") 