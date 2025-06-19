"""
StreamMate AI - Automatic Cache Management System
Mengelola cache PyTchat, temporary files, dan data lama secara otomatis
"""

import json
import os
import shutil
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

class AutoCacheManager:
    """Automatic cache management with scheduled cleanup"""
    
    def __init__(self):
        self.root_path = Path.cwd()
        self.last_cleanup_file = Path("config/last_cleanup.json")
        self.cleanup_settings = {
            "weekly_cleanup": True,
            "cleanup_interval_days": 7,
            "keep_viewer_memory_days": 30,
            "keep_logs_days": 14,
            "keep_temp_files_days": 3,
            "max_cache_size_mb": 500
        }
        
        # Cache locations untuk cleanup
        self.cache_locations = [
            Path.home() / ".cache" / "pytchat",
            Path(tempfile.gettempdir()) / "pytchat",
            self.root_path / "temp" / "pytchat_cache",
            self.root_path / "cache" / "pytchat",
            self.root_path / "temp",
            self.root_path / "logs" / "temp",
        ]
        
        # Files untuk cleanup berkala
        self.cleanup_patterns = [
            "temp/**/*.tmp",
            "temp/**/*.cache", 
            "temp/**/*_buffer.txt",
            "temp/**/*_history.json",
            "logs/**/*.log.old",
            "cache/**/*.pkl",
            "**/__pycache__/**",
        ]
        
        self._load_cleanup_history()
        self._start_background_monitor()
    
    def _load_cleanup_history(self):
        """Load riwayat cleanup terakhir"""
        try:
            if self.last_cleanup_file.exists():
                with open(self.last_cleanup_file, 'r', encoding='utf-8') as f:
                    self.cleanup_history = json.load(f)
            else:
                self.cleanup_history = {
                    "last_weekly_cleanup": None,
                    "last_cache_cleanup": None,
                    "total_cleanups": 0,
                    "total_freed_mb": 0
                }
        except Exception as e:
            print(f"[CACHE] Error loading cleanup history: {e}")
            self.cleanup_history = {
                "last_weekly_cleanup": None,
                "last_cache_cleanup": None,
                "total_cleanups": 0,
                "total_freed_mb": 0
            }
    
    def _save_cleanup_history(self):
        """Simpan riwayat cleanup"""
        try:
            self.last_cleanup_file.parent.mkdir(exist_ok=True)
            with open(self.last_cleanup_file, 'w', encoding='utf-8') as f:
                json.dump(self.cleanup_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[CACHE] Error saving cleanup history: {e}")
    
    def _start_background_monitor(self):
        """Start background thread untuk monitoring cache"""
        def monitor_worker():
            while True:
                try:
                    # Check setiap jam
                    time.sleep(3600)
                    
                    # Check apakah perlu weekly cleanup
                    if self._should_run_weekly_cleanup():
                        print("[CACHE] 🧹 Running scheduled weekly cleanup...")
                        self.run_weekly_cleanup()
                        
                    # Check apakah cache terlalu besar
                    if self._check_cache_size_exceeded():
                        print("[CACHE] 🗑️ Cache size exceeded, running emergency cleanup...")
                        self.emergency_cache_cleanup()
                        
                except Exception as e:
                    print(f"[CACHE] Monitor error: {e}")
        
        monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
        monitor_thread.start()
        print("[CACHE] ✅ Background cache monitor started")
    
    def _should_run_weekly_cleanup(self) -> bool:
        """Check apakah perlu weekly cleanup"""
        if not self.cleanup_settings["weekly_cleanup"]:
            return False
            
        last_cleanup = self.cleanup_history.get("last_weekly_cleanup")
        if not last_cleanup:
            return True
            
        try:
            last_date = datetime.fromisoformat(last_cleanup)
            days_since = (datetime.now() - last_date).days
            return days_since >= self.cleanup_settings["cleanup_interval_days"]
        except:
            return True
    
    def _check_cache_size_exceeded(self) -> bool:
        """Check apakah ukuran cache melebihi limit"""
        total_size_mb = 0
        
        for cache_location in self.cache_locations:
            if cache_location.exists():
                try:
                    total_size_mb += self._get_directory_size_mb(cache_location)
                except:
                    continue
        
        max_size = self.cleanup_settings["max_cache_size_mb"]
        return total_size_mb > max_size
    
    def _get_directory_size_mb(self, path: Path) -> float:
        """Hitung ukuran direktori dalam MB"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except:
                        continue
        except:
            pass
        return total_size / (1024 * 1024)  # Convert to MB
    
    def run_weekly_cleanup(self) -> Dict:
        """Jalankan weekly cleanup komprehensif"""
        print("[CACHE] 🧹 Starting comprehensive weekly cleanup...")
        
        cleanup_stats = {
            "start_time": datetime.now().isoformat(),
            "freed_mb": 0,
            "files_deleted": 0,
            "directories_cleaned": 0,
            "errors": []
        }
        
        try:
            # 1. Clear PyTchat caches
            print("[CACHE] Clearing PyTchat caches...")
            freed_mb = self._clear_pytchat_caches()
            cleanup_stats["freed_mb"] += freed_mb
            
            # 2. Clear temporary files
            print("[CACHE] Clearing temporary files...")
            freed_mb, files_deleted = self._clear_temp_files()
            cleanup_stats["freed_mb"] += freed_mb
            cleanup_stats["files_deleted"] += files_deleted
            
            # 3. Clear old logs
            print("[CACHE] Clearing old logs...")
            freed_mb, files_deleted = self._clear_old_logs()
            cleanup_stats["freed_mb"] += freed_mb
            cleanup_stats["files_deleted"] += files_deleted
            
            # 4. Clear old viewer memory data
            print("[CACHE] Cleaning old viewer memory...")
            self._cleanup_old_viewer_memory()
            
            # 5. Clear Python cache
            print("[CACHE] Clearing Python cache...")
            freed_mb = self._clear_python_cache()
            cleanup_stats["freed_mb"] += freed_mb
            
            # 6. Optimize remaining files
            print("[CACHE] Optimizing remaining cache files...")
            self._optimize_cache_files()
            
            # Update cleanup history
            self.cleanup_history["last_weekly_cleanup"] = datetime.now().isoformat()
            self.cleanup_history["total_cleanups"] += 1
            self.cleanup_history["total_freed_mb"] += cleanup_stats["freed_mb"]
            self._save_cleanup_history()
            
            cleanup_stats["end_time"] = datetime.now().isoformat()
            print(f"[CACHE] ✅ Weekly cleanup completed:")
            print(f"         📁 Files deleted: {cleanup_stats['files_deleted']}")
            print(f"         💾 Space freed: {cleanup_stats['freed_mb']:.1f} MB")
            
            return cleanup_stats
            
        except Exception as e:
            cleanup_stats["errors"].append(str(e))
            print(f"[CACHE] ❌ Weekly cleanup error: {e}")
            return cleanup_stats
    
    def _clear_pytchat_caches(self) -> float:
        """Clear semua PyTchat cache locations"""
        total_freed_mb = 0
        
        for cache_location in self.cache_locations:
            if cache_location.exists() and cache_location.name.lower().find('pytchat') != -1:
                try:
                    size_before = self._get_directory_size_mb(cache_location)
                    shutil.rmtree(cache_location)
                    total_freed_mb += size_before
                    print(f"[CACHE] Cleared: {cache_location} ({size_before:.1f} MB)")
                except Exception as e:
                    print(f"[CACHE] Failed to clear {cache_location}: {e}")
        
        return total_freed_mb
    
    def _clear_temp_files(self) -> tuple:
        """Clear temporary files berdasarkan age"""
        total_freed_mb = 0
        files_deleted = 0
        cutoff_date = datetime.now() - timedelta(days=self.cleanup_settings["keep_temp_files_days"])
        
        temp_dirs = [
            self.root_path / "temp",
            Path(tempfile.gettempdir()) / "streammate",
        ]
        
        for temp_dir in temp_dirs:
            if not temp_dir.exists():
                continue
                
            for file_path in temp_dir.rglob("*"):
                if file_path.is_file():
                    try:
                        # Check file age
                        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_time < cutoff_date:
                            size_mb = file_path.stat().st_size / (1024 * 1024)
                            file_path.unlink()
                            total_freed_mb += size_mb
                            files_deleted += 1
                    except Exception as e:
                        print(f"[CACHE] Failed to delete {file_path}: {e}")
        
        return total_freed_mb, files_deleted
    
    def _clear_old_logs(self) -> tuple:
        """Clear log files yang lebih dari retention period"""
        total_freed_mb = 0
        files_deleted = 0
        cutoff_date = datetime.now() - timedelta(days=self.cleanup_settings["keep_logs_days"])
        
        log_dirs = [
            self.root_path / "logs",
        ]
        
        for log_dir in log_dirs:
            if not log_dir.exists():
                continue
                
            for log_file in log_dir.rglob("*.log*"):
                if log_file.is_file():
                    try:
                        file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                        if file_time < cutoff_date:
                            size_mb = log_file.stat().st_size / (1024 * 1024)
                            log_file.unlink()
                            total_freed_mb += size_mb
                            files_deleted += 1
                    except Exception as e:
                        print(f"[CACHE] Failed to delete {log_file}: {e}")
        
        return total_freed_mb, files_deleted
    
    def _cleanup_old_viewer_memory(self):
        """Cleanup old viewer memory data"""
        try:
            from .viewer_memory import ViewerMemory
            viewer_memory = ViewerMemory()
            viewer_memory._cleanup_old_data()
            print("[CACHE] Viewer memory cleanup completed")
        except Exception as e:
            print(f"[CACHE] Failed to cleanup viewer memory: {e}")
    
    def _clear_python_cache(self) -> float:
        """Clear Python __pycache__ directories"""
        total_freed_mb = 0
        
        for pycache_dir in self.root_path.rglob("__pycache__"):
            if pycache_dir.is_dir():
                try:
                    size_before = self._get_directory_size_mb(pycache_dir)
                    shutil.rmtree(pycache_dir)
                    total_freed_mb += size_before
                except Exception as e:
                    print(f"[CACHE] Failed to clear {pycache_dir}: {e}")
        
        return total_freed_mb
    
    def _optimize_cache_files(self):
        """Optimize cache files yang tersisa"""
        # Compress log files yang besar
        for log_file in self.root_path.rglob("*.log"):
            if log_file.is_file():
                try:
                    size_mb = log_file.stat().st_size / (1024 * 1024)
                    if size_mb > 10:  # Compress files > 10MB
                        # Implement compression logic if needed
                        pass
                except:
                    pass
    
    def emergency_cache_cleanup(self) -> Dict:
        """Emergency cleanup ketika cache terlalu besar"""
        print("[CACHE] 🚨 Running emergency cache cleanup...")
        
        cleanup_stats = {
            "freed_mb": 0,
            "files_deleted": 0
        }
        
        # Clear semua cache agresif
        for cache_location in self.cache_locations:
            if cache_location.exists():
                try:
                    size_before = self._get_directory_size_mb(cache_location)
                    shutil.rmtree(cache_location)
                    cleanup_stats["freed_mb"] += size_before
                    print(f"[CACHE] Emergency cleared: {cache_location} ({size_before:.1f} MB)")
                except Exception as e:
                    print(f"[CACHE] Emergency cleanup failed for {cache_location}: {e}")
        
        # Update history
        self.cleanup_history["last_cache_cleanup"] = datetime.now().isoformat()
        self._save_cleanup_history()
        
        return cleanup_stats
    
    def manual_cleanup(self) -> Dict:
        """Manual cleanup yang bisa dipanggil dari UI"""
        return self.run_weekly_cleanup()
    
    def get_cache_stats(self) -> Dict:
        """Get statistik cache saat ini"""
        stats = {
            "total_cache_size_mb": 0,
            "cache_locations": [],
            "last_cleanup": self.cleanup_history.get("last_weekly_cleanup"),
            "total_cleanups": self.cleanup_history.get("total_cleanups", 0),
            "total_freed_mb": self.cleanup_history.get("total_freed_mb", 0)
        }
        
        for cache_location in self.cache_locations:
            if cache_location.exists():
                size_mb = self._get_directory_size_mb(cache_location)
                stats["total_cache_size_mb"] += size_mb
                stats["cache_locations"].append({
                    "path": str(cache_location),
                    "size_mb": size_mb,
                    "exists": True
                })
            else:
                stats["cache_locations"].append({
                    "path": str(cache_location),
                    "size_mb": 0,
                    "exists": False
                })
        
        return stats

# Global instance
auto_cache_manager = AutoCacheManager()

def get_cache_manager():
    """Get global cache manager instance"""
    return auto_cache_manager 