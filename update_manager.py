# modules_client/update_manager.py
import os
import sys
import json
import zipfile
import tempfile
import shutil
import subprocess
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
import requests
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QMessageBox, QProgressDialog, QApplication

class UpdateDownloader(QObject):
    """Worker untuk download update file."""
    
    progress_updated = pyqtSignal(int)
    download_completed = pyqtSignal(str)
    download_failed = pyqtSignal(str)
    
    def __init__(self, download_url, save_path):
        super().__init__()
        self.download_url = download_url
        self.save_path = save_path
        self.is_cancelled = False
    
    def start(self):
        """Mulai download di thread terpisah."""
        thread = threading.Thread(target=self._download_worker, daemon=True)
        thread.start()
    
    def cancel(self):
        """Cancel download."""
        self.is_cancelled = True
    
    def _download_worker(self):
        """Worker untuk download file."""
        try:
            # Buat direktori jika belum ada
            Path(self.save_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Download dengan progress
            response = requests.get(self.download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.is_cancelled:
                        break
                        
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress_updated.emit(progress)
            
            if self.is_cancelled:
                # Hapus file jika dibatalkan
                if os.path.exists(self.save_path):
                    os.remove(self.save_path)
                self.download_failed.emit("Download dibatalkan")
            else:
                # Verifikasi file
                if os.path.exists(self.save_path) and os.path.getsize(self.save_path) > 0:
                    self.download_completed.emit(self.save_path)
                else:
                    self.download_failed.emit("File download tidak valid")
                    
        except Exception as e:
            self.download_failed.emit(f"Gagal download: {str(e)}")

class UpdateManager(QObject):
    """
    Manager untuk auto-update StreamMate AI
    Mirip sistem update OBS Studio
    """
    
    # Signals untuk komunikasi dengan UI
    update_available = pyqtSignal(dict)  # Info update tersedia
    download_progress = pyqtSignal(int)   # Progress download (0-100)
    update_ready = pyqtSignal(str)        # Update siap diinstall
    update_error = pyqtSignal(str)        # Error saat update
    
    def __init__(self, config_manager=None):
        super().__init__()
        self.config = config_manager
        self.current_version = self._get_current_version()
        self.github_repo = "arulbarker/streammate-releases"  # Sesuai dengan repo aktual
        self.api_url = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
        self.temp_dir = Path(tempfile.gettempdir()) / "streammate_update"
        
        # Status update
        self.update_info = None
        self.download_path = None
        self.is_checking = False
        self.is_downloading = False
        self.downloader = None
        
        # Timer untuk auto-check (24 jam sekali)
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_for_updates_silent)
        self.start_auto_check()
    
    def _get_current_version(self):
        """Ambil versi aplikasi saat ini."""
        try:
            if self.config:
                version = self.config.get("app_version", "1.0.0")
                # Hapus prefix 'v' jika ada
                return version.lstrip('v')
            
            # Fallback: baca dari file version
            version_file = Path("version.txt")
            if version_file.exists():
                version = version_file.read_text(encoding="utf-8").strip()
                return version.lstrip('v')
            
            return "1.0.0"
        except Exception as e:
            print(f"Error getting version: {e}")
            return "1.0.0"
    
    def start_auto_check(self):
        """Mulai auto-check update setiap 24 jam."""
        if self.config and self.config.get("auto_update_check", True):
            # Check saat startup (delay 30 detik)
            QTimer.singleShot(30000, self.check_for_updates_silent)
            
            # Check setiap 24 jam
            self.check_timer.start(24 * 60 * 60 * 1000)  # 24 jam dalam ms
    
    def check_for_updates_silent(self):
        """Check update tanpa mengganggu user (background)."""
        if self.is_checking:
            return
        
        self.is_checking = True
        thread = threading.Thread(target=self._check_updates_background, daemon=True)
        thread.start()
    
    def check_for_updates(self, show_no_update=True):
        """Check update dengan notifikasi ke user."""
        if self.is_checking:
            QMessageBox.information(
                None, "Update Check", 
                "Sedang memeriksa update, silakan tunggu..."
            )
            return
        
        self.is_checking = True
        self.show_no_update = show_no_update
        thread = threading.Thread(target=self._check_updates_interactive, daemon=True)
        thread.start()
    
    def _check_updates_background(self):
        """Background check untuk auto-update."""
        try:
            update_info = self._fetch_latest_release()
            if update_info and self._is_newer_version(update_info["tag_name"]):
                self.update_info = update_info
                self.update_available.emit(update_info)
        except Exception as e:
            print(f"Background update check failed: {e}")
        finally:
            self.is_checking = False
    
    def _check_updates_interactive(self):
        """Interactive check yang tampil notifikasi."""
        try:
            update_info = self._fetch_latest_release()
            
            if update_info and self._is_newer_version(update_info["tag_name"]):
                self.update_info = update_info
                self.update_available.emit(update_info)
            elif hasattr(self, 'show_no_update') and self.show_no_update:
                QTimer.singleShot(0, lambda: QMessageBox.information(
                    None, "Update Check",
                    f"Anda sudah menggunakan versi terbaru ({self.current_version})"
                ))
        except Exception as e:
            error_msg = f"Gagal memeriksa update: {str(e)}"
            self.update_error.emit(error_msg)
            if hasattr(self, 'show_no_update') and self.show_no_update:
                QTimer.singleShot(0, lambda: QMessageBox.warning(
                    None, "Update Error", error_msg
                ))
        finally:
            self.is_checking = False
    
    def _fetch_latest_release(self):
        """Ambil info release terbaru dari GitHub."""
        try:
            headers = {"Accept": "application/vnd.github.v3+json"}
            response = requests.get(self.api_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            release_data = response.json()
            
            # Filter asset Windows executable
            windows_asset = None
            for asset in release_data.get("assets", []):
                if asset["name"].endswith((".exe", ".zip")) and "windows" in asset["name"].lower():
                    windows_asset = asset
                    break
            
            if not windows_asset:
                # Jika tidak ada asset Windows spesifik, ambil yang pertama
                assets = release_data.get("assets", [])
                if assets:
                    windows_asset = assets[0]
                else:
                    raise Exception("Tidak ada file release yang tersedia")
            
            return {
                "tag_name": release_data["tag_name"],
                "name": release_data["name"],
                "body": release_data.get("body", "Tidak ada catatan perubahan"),
                "published_at": release_data["published_at"],
                "download_url": windows_asset["browser_download_url"],
                "file_size": windows_asset["size"],
                "filename": windows_asset["name"],
                "changelog": release_data.get("body", "• Perbaikan dan peningkatan performa\n• Bug fixes")
            }
        except Exception as e:
            raise Exception(f"Gagal mengambil info release: {str(e)}")
    
    def _is_newer_version(self, latest_version):
        """Cek apakah versi terbaru lebih baru dari versi saat ini."""
        try:
            # Hapus prefix 'v' jika ada
            current = self.current_version.lstrip('v')
            latest = latest_version.lstrip('v')
            
            # Parse versi (format: x.y.z)
            current_parts = [int(x) for x in current.split('.')]
            latest_parts = [int(x) for x in latest.split('.')]
            
            # Samakan panjang list
            max_len = max(len(current_parts), len(latest_parts))
            current_parts.extend([0] * (max_len - len(current_parts)))
            latest_parts.extend([0] * (max_len - len(latest_parts)))
            
            # Bandingkan
            return latest_parts > current_parts
        except Exception as e:
            print(f"Error comparing versions: {e}")
            return False
    
    def download_update(self):
        """Download update file."""
        if not self.update_info or self.is_downloading:
            return False
        
        self.is_downloading = True
        
        # Buat temp directory
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Path download
        filename = self.update_info["filename"]
        self.download_path = self.temp_dir / filename
        
        # Buat downloader
        self.downloader = UpdateDownloader(
            self.update_info["download_url"],
            str(self.download_path)
        )
        
        # Connect signals
        self.downloader.progress_updated.connect(self.download_progress.emit)
        self.downloader.download_completed.connect(self._on_download_completed)
        self.downloader.download_failed.connect(self._on_download_failed)
        
        # Mulai download
        self.downloader.start()
        return True
    
    def _on_download_completed(self, file_path):
        """Handler ketika download selesai."""
        self.is_downloading = False
        self.download_path = Path(file_path)
        self.update_ready.emit(file_path)
    
    def _on_download_failed(self, error_msg):
        """Handler ketika download gagal."""
        self.is_downloading = False
        self.update_error.emit(error_msg)
    
    def install_update(self):
        """Install update yang sudah didownload."""
        if not self.download_path or not self.download_path.exists():
            self.update_error.emit("File update tidak ditemukan")
            return False
        
        try:
            # Jika file .exe, jalankan langsung
            if self.download_path.suffix.lower() == '.exe':
                # Jalankan installer
                subprocess.Popen([str(self.download_path)], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
                
                # Tutup aplikasi setelah delay
                QTimer.singleShot(2000, self._close_application)
                return True
            
            # Jika file .zip, extract dan install
            elif self.download_path.suffix.lower() == '.zip':
                installer_script = self._create_installer_script()
                
                # Jalankan installer dan tutup aplikasi
                subprocess.Popen([sys.executable, installer_script], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
                
                # Tutup aplikasi
                QTimer.singleShot(1000, self._close_application)
                return True
            
            else:
                self.update_error.emit("Format file update tidak didukung")
                return False
                
        except Exception as e:
            self.update_error.emit(f"Gagal install update: {str(e)}")
            return False
    
    def _create_installer_script(self):
        """Buat script installer untuk update."""
        script_content = f'''
import os
import sys
import time
import shutil
import zipfile
from pathlib import Path

def install_update():
    try:
        # Tunggu aplikasi tutup
        time.sleep(3)
        
        # Path
        update_file = Path("{self.download_path}")
        app_dir = Path("{Path.cwd()}")
        backup_dir = app_dir / "backup_old_version"
        
        print("Memulai instalasi update...")
        
        # Backup versi lama
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        backup_dir.mkdir()
        
        # File yang perlu dibackup
        important_files = ["config", "temp", "logs", "assets"]
        for item in important_files:
            src = app_dir / item
            if src.exists():
                if src.is_file():
                    shutil.copy2(src, backup_dir / item)
                else:
                    shutil.copytree(src, backup_dir / item, dirs_exist_ok=True)
        
        # Extract update
        if update_file.suffix == ".zip":
            with zipfile.ZipFile(update_file, 'r') as zip_ref:
                zip_ref.extractall(app_dir)
        
        # Restore backup
        for item in important_files:
            backup_item = backup_dir / item
            target_item = app_dir / item
            if backup_item.exists():
                if target_item.exists():
                    if target_item.is_file():
                        target_item.unlink()
                    else:
                        shutil.rmtree(target_item)
                
                if backup_item.is_file():
                    shutil.copy2(backup_item, target_item)
                else:
                    shutil.copytree(backup_item, target_item)
        
        # Update version
        version_file = app_dir / "version.txt"
        version_file.write_text("{self.update_info['tag_name']}", encoding="utf-8")
        
        # Cleanup
        if update_file.exists():
            update_file.unlink()
        
        print("Update berhasil! Menjalankan aplikasi...")
        
        # Restart aplikasi
        main_exe = app_dir / "StreamMate_AI.exe"
        if main_exe.exists():
            os.system(f'start "" "{main_exe}"')
        else:
            main_py = app_dir / "main.py"
             if main_py.exists():
                os.system(f'cd "{app_dir}" && python main.py'))
        
    except Exception as e:
        print(f"Error saat install: {{e}}")
        input("Tekan Enter untuk keluar...")

if __name__ == "__main__":
    install_update()
'''
        
        # Simpan script
        script_path = self.temp_dir / "install_update.py"
        script_path.write_text(script_content, encoding="utf-8")
        
        return str(script_path)
    
    def _close_application(self):
        """Tutup aplikasi untuk install update."""
        app = QApplication.instance()
        if app:
            app.quit()
        else:
            sys.exit(0)
    
    def get_update_info(self):
        """Dapatkan info update yang tersedia."""
        return self.update_info
    
    def cleanup_temp(self):
        """Bersihkan file temporary."""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Error cleanup temp: {e}")
    
    def cancel_download(self):
        """Cancel download yang sedang berjalan."""
        if self.downloader:
            self.downloader.cancel()
        self.is_downloading = False