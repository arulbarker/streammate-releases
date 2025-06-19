import sys
import os
from pathlib import Path

def get_app_data_path(file_name: str) -> Path:
    """
    Mengembalikan path absolut ke file data (seperti log atau config),
    baik saat dijalankan sebagai script Python biasa atau sebagai frozen executable (exe).
    
    Ini memastikan bahwa file log dan konfigurasi selalu disimpan di samping
    file executable, bukan di direktori kerja yang mungkin berubah.
    
    Args:
        file_name (str): Nama file (misal: 'cohost_log.txt').
    
    Returns:
        Path: Objek Path absolut ke file tersebut.
    """
    # Cek apakah aplikasi sedang berjalan dalam mode 'frozen' (dibuat oleh PyInstaller)
    if getattr(sys, 'frozen', False):
        # Jika frozen, base path adalah direktori tempat .exe berada
        base_path = Path(sys.executable).parent
    else:
        # Jika tidak, base path adalah direktori root proyek (asumsi script dijalankan dari sana)
        # Kita naik satu level dari 'utils' ke root folder
        base_path = Path(__file__).resolve().parent.parent
        
    # Buat folder 'temp' jika belum ada di base_path
    temp_dir = base_path / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    # Kembalikan path lengkap ke file
    return temp_dir / file_name 