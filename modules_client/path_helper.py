"""
StreamMate AI - Path Helper
Handles paths for both development and frozen executable
"""

import os
import sys
from pathlib import Path

def get_root_path():
    """Get root path yang bekerja untuk dev dan production"""
    if getattr(sys, 'frozen', False):
        # Running as exe
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).resolve().parent.parent

def get_thirdparty_path():
    """Get thirdparty path"""
    return get_root_path() / "thirdparty"

def get_ffmpeg_path():
    """Get FFmpeg executable path"""
    ffmpeg = get_thirdparty_path() / "ffmpeg" / "bin" / "ffmpeg.exe"
    if not ffmpeg.exists():
        # Fallback to system ffmpeg
        return "ffmpeg"
    return str(ffmpeg)

def get_whisper_path():
    """DEPRECATED: Whisper removed, using Super Direct Google STT only"""
    return None

def get_config_path(filename):
    """Get config file path"""
    return get_root_path() / "config" / filename

def get_logs_path():
    """Get logs directory path"""
    logs_dir = get_root_path() / "logs"
    logs_dir.mkdir(exist_ok=True)
    return logs_dir

def get_temp_path():
    """Get temp directory path"""
    temp_dir = get_root_path() / "temp"
    temp_dir.mkdir(exist_ok=True)
    return temp_dir

# Set environment variables for external tools
ROOT = get_root_path()
os.environ['STREAMMATE_ROOT'] = str(ROOT)
os.environ['THIRDPARTY_PATH'] = str(get_thirdparty_path())

# Add ffmpeg to PATH if exists
ffmpeg_dir = get_thirdparty_path() / "ffmpeg" / "bin"
if ffmpeg_dir.exists():
    current_path = os.environ.get('PATH', '')
    if str(ffmpeg_dir) not in current_path:
        os.environ['PATH'] = str(ffmpeg_dir) + os.pathsep + current_path

print(f"[PATH_HELPER] Root: {ROOT}")
print(f"[PATH_HELPER] Thirdparty: {get_thirdparty_path()}")
