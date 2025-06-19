#!/usr/bin/env python3
"""
StreamMate AI Update Manager
Sistem untuk mengecek, download, dan install update otomatis
"""

import os
import json
import time
import hashlib
import requests
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread
from PyQt6.QtWidgets import QMessageBox

# Import config manager
try:
    from modules_client.config_manager import ConfigManager
except ImportError:
    from modules_server.config_manager import ConfigManager

class UpdateDownloader(QThread):
    """Thread untuk download update in background"""
    
    progress_updated = pyqtSignal(int)  # Progress percentage
    download_finished = pyqtSignal(str)  # File path
    download_error = pyqtSignal(str)  # Error message
    
    def __init__(self, download_url, file_path):
        super().__init__()
        self.download_url = download_url
        self.file_path = file_path
        self.cancelled = False
    
    def run(self):
        """Download file dengan progress tracking"""
        try:
            response = requests.get(self.download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            
            with open(self.file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.cancelled:
                        break
                        
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress_updated.emit(progress)
            
            if not self.cancelled:
                self.download_finished.emit(self.file_path)
            
        except Exception as e:
            self.download_error.emit(str(e))
    
    def cancel(self):
        """Cancel download"""
        self.cancelled = True

class UpdateManager(QObject):
    """Manager untuk sistem update StreamMate AI"""
    
    # Signals
    update_available = pyqtSignal(dict)  # Update info
    download_progress = pyqtSignal(int)  # Progress percentage
    update_ready = pyqtSignal(str)  # File path
    update_error = pyqtSignal(str)  # Error message
    
    def __init__(self):
        super().__init__()
        
        # Configuration
        self.config = ConfigManager("config/settings.json")
        self.current_version = self._get_current_version()
        self.update_server_url = "https://api.streammate-ai.com"  # Website API endpoint
        
        # GitHub repository info
        self.github_owner = "arulbarker"
        self.github_repo = "streammate-releases"
        
        # File paths
        self.version_file = Path("version.txt")
        self.download_dir = Path("temp/updates")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # State
        self.checking_updates = False
        self.downloading = False
        self.download_thread = None
        
        # Timer untuk check periodic
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_for_updates)
        
        # Load settings
        self._load_update_settings()
        
        print(f"[UPDATE] UpdateManager initialized - Current version: {self.current_version}")
    
    def _get_current_version(self):
        """Get current version dari version.txt"""
        try:
            if self.version_file.exists():
                with open(self.version_file, 'r', encoding='utf-8') as f:
                    version = f.read().strip()
                    # Remove 'V.' prefix if exists
                    if version.startswith('V.'):
                        version = version[2:]
                    return version
            return "1.0.0"
        except Exception as e:
            print(f"[UPDATE] Error reading version: {e}")
            return "1.0.0"
    
    def _load_update_settings(self):
        """Load update preferences dari config"""
        self.auto_check = self.config.get("auto_check_updates", True)
        self.check_interval = self.config.get("update_check_interval", 24)  # hours
        self.auto_download = self.config.get("auto_download_updates", False)
        self.skipped_version = self.config.get("skipped_update_version", "")
        self.last_check = self.config.get("last_update_check", 0)
        
        # Start timer jika auto check enabled
        if self.auto_check:
            self.start_periodic_check()
    
    def start_periodic_check(self):
        """Mulai periodic check untuk updates"""
        # Check setiap 6 jam (bisa disesuaikan)
        interval_ms = 6 * 60 * 60 * 1000  # 6 hours
        self.check_timer.start(interval_ms)
        
        # Check immediately jika sudah lama tidak check
        last_check_time = datetime.fromtimestamp(self.last_check)
        time_since_check = datetime.now() - last_check_time
        
        if time_since_check.total_seconds() > (self.check_interval * 3600):
            # Delay 30 detik setelah startup
            QTimer.singleShot(30000, self.check_for_updates)
    
    def check_for_updates(self, manual=False):
        """Check apakah ada update tersedia"""
        if self.checking_updates:
            return
        
        self.checking_updates = True
        
        try:
            # Update last check time
            self.last_check = time.time()
            self.config.set("last_update_check", self.last_check)
            
            print(f"[UPDATE] Checking for updates... Current: {self.current_version}")
            
            # Get update info dari server/API
            update_info = self._fetch_update_info()
            
            if update_info and self._is_newer_version(update_info.get("version")):
                # Check jika versi ini sudah di-skip
                if not manual and update_info.get("version") == self.skipped_version:
                    print(f"[UPDATE] Version {update_info.get('version')} was skipped")
                    return
                
                # Check reminder time
                reminder_time = self.config.get("update_reminder_time", 0)
                if not manual and reminder_time > time.time():
                    print(f"[UPDATE] Update reminder scheduled for later")
                    return
                
                print(f"[UPDATE] New version available: {update_info.get('version')}")
                self.update_available.emit(update_info)
                
                # Auto download jika enabled
                if self.auto_download and not manual:
                    self.download_update(update_info)
            else:
                if manual:
                    QMessageBox.information(
                        None, "Update Check",
                        f"Anda sudah menggunakan versi terbaru ({self.current_version})"
                    )
                print(f"[UPDATE] No updates available")
                
        except Exception as e:
            error_msg = f"Gagal mengecek update: {e}"
            print(f"[UPDATE] Error: {error_msg}")
            if manual:
                QMessageBox.warning(None, "Update Error", error_msg)
            self.update_error.emit(error_msg)
            
        finally:
            self.checking_updates = False
    
    def _fetch_update_info(self):
        """Fetch informasi update dari server/API website atau GitHub"""
        try:
            # 1. Try primary API endpoint (your website)
            api_url = f"{self.update_server_url}/api/version/latest"
            try:
                response = requests.get(api_url, timeout=10)
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                print(f"[UPDATE] Website API error: {e}, trying GitHub...")
            
            # 2. Try GitHub update-info.json
            github_json_url = f"https://raw.githubusercontent.com/{self.github_owner}/{self.github_repo}/main/update-info.json"
            try:
                response = requests.get(github_json_url, timeout=10)
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                print(f"[UPDATE] GitHub JSON error: {e}, trying GitHub releases...")
            
            # 3. Try GitHub releases API
            github_api_url = f"https://api.github.com/repos/{self.github_owner}/{self.github_repo}/releases/latest"
            response = requests.get(github_api_url, timeout=10)
            
            if response.status_code == 200:
                github_data = response.json()
                
                # Convert GitHub format ke format kita
                return {
                    "version": github_data.get("tag_name", "").lstrip("v"),
                    "download_url": self._get_download_url_from_github(github_data),
                    "changelog": github_data.get("body", ""),
                    "release_date": github_data.get("published_at", ""),
                    "file_size": self._get_file_size_from_github(github_data)
                }
            
            # 4. Fallback: Hardcoded check (untuk testing)
            return self._get_fallback_update_info()
            
        except Exception as e:
            print(f"[UPDATE] Error fetching update info: {e}")
            return None
    
    def _get_fallback_update_info(self):
        """Fallback update info untuk testing atau emergency"""
        # Bisa diubah manual untuk testing
        fallback_version = "1.0.2"
        
        if self._is_newer_version(fallback_version):
            return {
                "version": fallback_version,
                "download_url": f"https://github.com/{self.github_owner}/{self.github_repo}/releases/download/v{fallback_version}/StreamMateAI_v{fallback_version}.zip",
                "changelog": "• Perbaikan bug pada sistem update\n• Peningkatan performa\n• UI improvements",
                "release_date": datetime.now().isoformat(),
                "file_size": 50 * 1024 * 1024  # 50MB
            }
        return None
    
    def _is_newer_version(self, new_version):
        """Check apakah versi baru lebih tinggi dari current"""
        if not new_version:
            return False
        
        try:
            # Parse version numbers (e.g., "1.0.1" -> [1, 0, 1])
            current_parts = [int(x) for x in self.current_version.split('.')]
            new_parts = [int(x) for x in new_version.split('.')]
            
            # Pad dengan 0 jika length berbeda
            max_len = max(len(current_parts), len(new_parts))
            current_parts += [0] * (max_len - len(current_parts))
            new_parts += [0] * (max_len - len(new_parts))
            
            return new_parts > current_parts
            
        except ValueError:
            # Fallback ke string comparison jika parsing gagal
            return new_version > self.current_version
    
    def download_update(self, update_info=None):
        """Download update file"""
        if self.downloading:
            return False
        
        if not update_info:
            print("[UPDATE] No update info provided for download")
            return False
        
        try:
            download_url = update_info.get("download_url")
            if not download_url:
                self.update_error.emit("Download URL tidak tersedia")
                return False
            
            # Prepare download path
            version = update_info.get("version", "unknown")
            
            # Determine file extension based on URL
            if download_url.lower().endswith(".zip"):
                filename = f"StreamMateAI_v{version}.zip"
            else:
                filename = f"StreamMateAI_v{version}.exe"
                
            file_path = self.download_dir / filename
            
            # Remove existing file
            if file_path.exists():
                file_path.unlink()
            
            print(f"[UPDATE] Starting download: {download_url}")
            
            # Start download in background thread
            self.downloading = True
            self.download_thread = UpdateDownloader(download_url, str(file_path))
            self.download_thread.progress_updated.connect(self.download_progress.emit)
            self.download_thread.download_finished.connect(self._download_completed)
            self.download_thread.download_error.connect(self._download_failed)
            self.download_thread.start()
            
            return True
            
        except Exception as e:
            error_msg = f"Gagal memulai download: {e}"
            print(f"[UPDATE] Error: {error_msg}")
            self.update_error.emit(error_msg)
            return False
    
    def _download_completed(self, file_path):
        """Handle download selesai"""
        self.downloading = False
        print(f"[UPDATE] Download completed: {file_path}")
        
        # Verify file
        if Path(file_path).exists() and Path(file_path).stat().st_size > 0:
            self.update_ready.emit(file_path)
        else:
            self.update_error.emit("File download corrupt atau kosong")
    
    def _download_failed(self, error_msg):
        """Handle download error"""
        self.downloading = False
        print(f"[UPDATE] Download failed: {error_msg}")
        self.update_error.emit(f"Download gagal: {error_msg}")
    
    def cancel_download(self):
        """Cancel ongoing download"""
        if self.download_thread and self.downloading:
            self.download_thread.cancel()
            self.download_thread.wait(3000)  # Wait max 3 seconds
            self.downloading = False
    
    def install_update(self, file_path=None):
        """Install update dan restart aplikasi"""
        if not file_path:
            return False
        
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                print(f"[UPDATE] Update file not found: {file_path}")
                return False
            
            print(f"[UPDATE] Installing update: {file_path}")
            
            # Method 1: Run installer EXE dan exit aplikasi
            if file_path.suffix.lower() == '.exe':
                # Start installer - HIDE CMD WINDOW
                subprocess.Popen([str(file_path)], shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=subprocess.SW_HIDE) if os.name == 'nt' else None)
                
                # Exit aplikasi untuk allow installation
                QTimer.singleShot(1000, self._exit_application)
                return True
            
            # Method 2: Extract ZIP dan restart aplikasi
            elif file_path.suffix.lower() == '.zip':
                # Lokasi aplikasi saat ini
                current_dir = os.path.dirname(os.path.abspath(__file__))
                app_dir = os.path.dirname(current_dir)  # Parent directory of modules_client
                
                # Buat batch script untuk update
                update_script = Path(self.download_dir) / "update_script.bat"
                
                # Isi script untuk Windows
                script_content = f"""
@echo off
echo Updating StreamMate AI...
timeout /t 2 /nobreak > nul
echo Extracting files...
powershell -command "Expand-Archive -Force '{file_path}' '{app_dir}'"
echo Update complete!
echo Starting StreamMate AI...
start "" "{app_dir}\\StreamMateAI.exe"
del "{file_path}"
del "%~f0"
                """
                
                # Tulis script
                with open(update_script, 'w') as f:
                    f.write(script_content)
                
                # Jalankan script dan keluar aplikasi
                subprocess.Popen([str(update_script)], shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=subprocess.SW_HIDE) if os.name == 'nt' else None)
                
                # Exit aplikasi untuk allow installation
                QTimer.singleShot(1000, self._exit_application)
                return True
            
            return False
            
        except Exception as e:
            print(f"[UPDATE] Install error: {e}")
            return False
    
    def _exit_application(self):
        """Exit aplikasi untuk installation"""
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.quit()
    
    def skip_version(self, version):
        """Skip versi tertentu"""
        self.config.set("skipped_update_version", version)
        print(f"[UPDATE] Skipped version: {version}")
    
    def set_reminder(self, hours=24):
        """Set reminder untuk update"""
        reminder_time = time.time() + (hours * 3600)
        self.config.set("update_reminder_time", reminder_time)
        print(f"[UPDATE] Reminder set for {hours} hours")
    
    def get_update_settings(self):
        """Get current update settings"""
        return {
            "auto_check": self.auto_check,
            "check_interval": self.check_interval,
            "auto_download": self.auto_download,
            "last_check": datetime.fromtimestamp(self.last_check).isoformat() if self.last_check else None
        }
    
    def update_settings(self, settings):
        """Update settings"""
        for key, value in settings.items():
            if key == "auto_check":
                self.auto_check = value
                self.config.set("auto_check_updates", value)
                if value:
                    self.start_periodic_check()
                else:
                    self.check_timer.stop()
            elif key == "check_interval":
                self.check_interval = value
                self.config.set("update_check_interval", value)
            elif key == "auto_download":
                self.auto_download = value
                self.config.set("auto_download_updates", value)
    
    def _get_download_url_from_github(self, github_data):
        """Extract download URL dari GitHub release"""
        assets = github_data.get("assets", [])
        
        # Prioritaskan file ZIP terlebih dahulu
        for asset in assets:
            if asset.get("name", "").endswith(".zip"):
                return asset.get("browser_download_url")
        
        # Jika tidak ada ZIP, coba cari EXE
        for asset in assets:
            if asset.get("name", "").endswith(".exe"):
                return asset.get("browser_download_url")
        
        # Jika tidak ada asset, gunakan tag name untuk membuat URL
        tag_name = github_data.get("tag_name", "")
        if tag_name:
            return f"https://github.com/{self.github_owner}/{self.github_repo}/releases/download/{tag_name}/StreamMateAI_{tag_name}.zip"
        
        return None
    
    def _get_file_size_from_github(self, github_data):
        """Extract file size dari GitHub release"""
        assets = github_data.get("assets", [])
        
        # Prioritaskan file ZIP terlebih dahulu
        for asset in assets:
            if asset.get("name", "").endswith(".zip"):
                return asset.get("size", 0)
        
        # Jika tidak ada ZIP, coba cari EXE
        for asset in assets:
            if asset.get("name", "").endswith(".exe"):
                return asset.get("size", 0)
        
        return 0

# Global instance
update_manager = None

def get_update_manager():
    """Get global update manager instance"""
    global update_manager
    if not update_manager:
        update_manager = UpdateManager()
    return update_manager 