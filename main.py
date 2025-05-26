#!/usr/bin/env python3
"""
StreamMate AI - Live Streaming Automation
Main Entry Point - Final Version
"""

import sys
import os
import traceback
import json
import time
import importlib.util
import threading
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
import logging

# ========== CRITICAL: HIGH DPI SETUP SEBELUM IMPORT PYQT6 ==========
# Ini HARUS dipanggil sebelum QGuiApplication atau QApplication dibuat
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

# Root project directory PERTAMA
ROOT = os.path.dirname(os.path.abspath(__file__))

# Setup logging system SEBELUM import lainnya
LOG_DIR = Path(ROOT) / "logs"
LOG_DIR.mkdir(exist_ok=True)
SYSTEM_LOG = LOG_DIR / "system.log"

# Configure logging dengan format yang lebih informatif
logger = logging.getLogger('StreamMate')
logger.setLevel(logging.INFO)

# File handler dengan rotation
file_handler = RotatingFileHandler(
    SYSTEM_LOG, 
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)

# Format log yang lebih detail
formatter = logging.Formatter(
    '[%(asctime)s] [%(name)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ========== LOG STARTUP INFO ==========
logger.info("=" * 60)
logger.info("StreamMate AI Starting - Version 1.0.0")
logger.info(f"Python {sys.version}")
logger.info(f"Root directory: {ROOT}")
logger.info(f"Platform: {sys.platform}")
logger.info("=" * 60)

# ========== AUTO-DETECT MODE ==========
def detect_application_mode():
    """Auto-detect apakah ini development atau production mode"""
    
    # 1. Environment variable
    if os.getenv("STREAMMATE_DEV", "").lower() == "true":
        print("🧪 MODE: Development (Environment Variable)")
        return "development"
    
    # 2. Check dev_users.json
    dev_users_file = Path("config/dev_users.json")
    if dev_users_file.exists():
        print("👨‍💻 MODE: Development (Dev Users File Found)")
        return "development"
    
    # 3. Check if running from source dengan server.py
    server_file = Path("modules_server/server.py")
    if server_file.exists():
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 8000))
        sock.close()
        if result == 0:
            print("🔧 MODE: Development (Local Server Running)")
            return "development"
    
    # 4. Default: Production
    print("🚀 MODE: Production")
    return "production"

# Panggil detection
APP_MODE = detect_application_mode()
logger.info(f"Application mode: {APP_MODE}")

# Export ke environment untuk module lain
os.environ["STREAMMATE_APP_MODE"] = APP_MODE

# ========== SETUP PYTHON PATH ==========
# Add project paths to Python path SEBELUM import modules
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "modules_client"))
sys.path.insert(0, os.path.join(ROOT, "modules_server"))
sys.path.insert(0, os.path.join(ROOT, "ui"))
sys.path.insert(0, os.path.join(ROOT, "listeners"))

logger.info(f"Python path updated with {len(sys.path)} entries")

# ========== SEKARANG BARU IMPORT PYQT6 ==========
try:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QGuiApplication, QIcon, QPixmap
    from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen
    logger.info("PyQt6 imported successfully")
except ImportError as e:
    print(f"CRITICAL: PyQt6 not found: {e}")
    print("Please install PyQt6: pip install PyQt6")
    sys.exit(1)

# ========== GLOBAL EXCEPTION HANDLER ==========
def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler dengan logging yang lebih baik"""
    if issubclass(exc_type, KeyboardInterrupt):
        logger.info("Application interrupted by user (Ctrl+C)")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    # Format error message dengan full traceback
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    
    # Log error
    logger.critical(f"Uncaught Exception: {exc_type.__name__}: {exc_value}")
    logger.critical(f"Traceback:\n{error_msg}")
    
    # Save error to temp file untuk debugging
    error_log_path = Path(ROOT) / "temp" / "error_log.txt"
    error_log_path.parent.mkdir(exist_ok=True)
    
    try:
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now().isoformat()}] CRITICAL ERROR:\n")
            f.write(error_msg)
            f.write("\n" + "="*80 + "\n")
        logger.info(f"Error details saved to: {error_log_path}")
    except Exception as log_error:
        logger.error(f"Failed to write error log: {log_error}")
    
    # Show error dialog jika QApplication sudah ada
    try:
        if QApplication.instance():
            QMessageBox.critical(
                None, 
                "StreamMate AI - Critical Error",
                f"Application encountered a critical error:\n\n"
                f"{exc_type.__name__}: {exc_value}\n\n"
                f"Error details have been saved to:\n{error_log_path}\n\n"
                f"Please report this issue to support@streammateai.com"
            )
    except Exception:
        pass

# Install global exception handler
sys.excepthook = handle_exception

def check_dependencies():
    """Check critical dependencies sebelum aplikasi dimulai"""
    logger.info("Checking critical dependencies...")
    
    required_modules = {
        'PyQt6': 'pip install PyQt6',
        'requests': 'pip install requests',
        'sounddevice': 'pip install sounddevice',
        'soundfile': 'pip install soundfile',
        'keyboard': 'pip install keyboard',
        'pathlib': 'Built-in module'
    }
    
    missing_modules = []
    
    for module, install_cmd in required_modules.items():
        try:
            if module == 'PyQt6':
                # PyQt6 sudah diimport di atas
                continue
            else:
                __import__(module)
            logger.debug(f"✓ {module} - OK")
        except ImportError:
            missing_modules.append((module, install_cmd))
            logger.error(f"✗ {module} - MISSING")
    
    if missing_modules:
        error_msg = "Missing required dependencies:\n\n"
        for module, cmd in missing_modules:
            error_msg += f"• {module}: {cmd}\n"
        
        logger.error("Critical dependencies missing!")
        print(error_msg)
        return False
    
    logger.info("All critical dependencies OK")
    return True

def initialize_directories():
    """Initialize required directories dengan error handling"""
    logger.info("Initializing directory structure...")
    
    required_dirs = [
        "temp", "logs", "config", "knowledge", 
        "knowledge_bases", "avatars", "assets",
        "temp/cache", "resources"
    ]
    
    for directory in required_dirs:
        dir_path = Path(ROOT) / directory
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"✓ Directory created/verified: {directory}")
        except Exception as e:
            logger.error(f"✗ Failed to create directory {directory}: {e}")
            return False
    
    logger.info("Directory structure initialized successfully")
    return True

def initialize_configuration():
    """Initialize system configuration dengan validation"""
    logger.info("Initializing configuration system...")
    
    try:
        # Import ConfigManager
        from modules_client.config_manager import ConfigManager
        
        config_file = Path(ROOT) / "config" / "settings.json"
        cfg = ConfigManager(str(config_file))
        
        # Set default configuration values
        defaults = {
            "app_version": "1.0.0",
            "debug_mode": False,
            "use_remote_api": False,
            "api_base_url": "http://localhost:8000",
            "platform": "YouTube",
            "reply_mode": "Trigger",
            "personality": "Ceria",
            "reply_language": "Indonesia",
            "voice_model": "id-ID-Standard-A",
            "cohost_voice_model": "id-ID-Standard-A",
            "selected_mic_index": 0,
            "trigger_words": ["bro", "bang", "?"],
            "translate_hotkey": "Ctrl+Alt+X",
            "cohost_hotkey": "Ctrl+Alt+C",
            "paket": "basic",
            "animasi_hotkey": {
                "enabled": True,
                "start_tts": "F1",
                "end_tts": "F2"
            }
        }
        
        # Apply defaults if not present
        config_updated = False
        for key, value in defaults.items():
            if key not in cfg.data:
                cfg.set(key, value)
                config_updated = True
                logger.debug(f"Set default config: {key} = {value}")
        
        if config_updated:
            logger.info("Configuration updated with default values")
        
        # Sync package information dari subscription_status.json jika ada
        subscription_file = Path(ROOT) / "config" / "subscription_status.json"
        if subscription_file.exists():
            try:
                with open(subscription_file, 'r', encoding='utf-8') as f:
                    sub_data = json.load(f)
                    
                if sub_data.get("status") == "paid":
                    package = sub_data.get("package", "basic")
                    current_package = cfg.get("paket")
                    
                    if current_package != package:
                        cfg.set("paket", package)
                        logger.info(f"Synced package from subscription: {package}")
            except Exception as e:
                logger.warning(f"Failed to sync subscription package: {e}")
        
        logger.info("Configuration system initialized successfully")
        return cfg
        
    except ImportError as e:
        logger.error(f"Failed to import ConfigManager: {e}")
        return None
    except Exception as e:
        logger.error(f"Configuration initialization error: {e}")
        return None

def preload_chat_listener():
    """Preload chat listener module untuk performa lebih baik"""
    logger.info("Preloading chat listener module...")
    
    try:
        chat_listener_path = Path(ROOT) / "listeners" / "chat_listener.py"
        if chat_listener_path.exists():
            spec = importlib.util.spec_from_file_location("chat_listener", chat_listener_path)
            chat_listener_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(chat_listener_module)
            logger.info("Chat listener module preloaded successfully")
            return chat_listener_module
        else:
            logger.warning(f"Chat listener not found at: {chat_listener_path}")
            return None
    except Exception as e:
        logger.error(f"Failed to preload chat listener: {e}")
        return None

def check_payment_server():
    """Check dan start payment server jika perlu"""
    logger.info("Checking payment server status...")
    
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex(('localhost', 5005))
            server_running = (result == 0)
        
        if server_running:
            logger.info("Payment server is already running on port 5005")
            return True
        else:
            logger.info("Payment server not running, attempting to start...")
            
            # Try to start payment server
            try:
                import subprocess
                server_path = Path(ROOT) / "payment_server.py"
                
                if server_path.exists():
                    if sys.platform == "win32":
                        subprocess.Popen(
                            [sys.executable, str(server_path)],
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                        )
                    else:
                        subprocess.Popen(
                            [sys.executable, str(server_path)],
                            start_new_session=True
                        )
                    
                    # Wait dan check lagi
                    time.sleep(2)
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        result = s.connect_ex(('localhost', 5005))
                        if result == 0:
                            logger.info("Payment server started successfully")
                            return True
                        else:
                            logger.warning("Payment server failed to start")
                            return False
                else:
                    logger.warning("Payment server file not found")
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to start payment server: {e}")
                return False
                
    except Exception as e:
        logger.error(f"Error checking payment server: {e}")
        return False

def create_splash_screen(app):
    """Create splash screen untuk startup yang lebih profesional"""
    try:
        # Create simple splash screen jika icon tersedia
        icon_path = Path(ROOT) / "resources" / "splash.png"
        if not icon_path.exists():
            # Create simple colored splash
            splash_pixmap = QPixmap(400, 200)
            splash_pixmap.fill(Qt.GlobalColor.blue)
        else:
            splash_pixmap = QPixmap(str(icon_path))
        
        splash = QSplashScreen(splash_pixmap)
        splash.show()
        
        # Process events untuk show splash
        app.processEvents()
        
        return splash
    except Exception as e:
        logger.warning(f"Could not create splash screen: {e}")
        return None

def main():
    """Main application entry point dengan error handling lengkap"""
    logger.info("Starting main application...")
    
    # ========== 1. CHECK DEPENDENCIES ==========
    if not check_dependencies():
        logger.critical("Critical dependencies missing, exiting...")
        return 1
    
    # ========== 2. INITIALIZE DIRECTORIES ==========
    if not initialize_directories():
        logger.critical("Failed to initialize directories, exiting...")
        return 1
    
    # ========== 3. SET HIGH DPI POLICY (PENTING!) ==========
    # Ini HARUS dipanggil SEBELUM QApplication dibuat
    try:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        logger.info("High DPI scale factor policy set successfully")
    except Exception as e:
        logger.warning(f"Could not set High DPI policy: {e}")
    
    # ========== 4. CREATE QAPPLICATION ==========
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("StreamMate AI - Live Streaming Automation")
        app.setOrganizationName("StreamMate")
        app.setApplicationVersion("1.0.0")
        
        # Set style
        app.setStyle("Fusion")
        
        logger.info("QApplication created successfully")
    except Exception as e:
        logger.critical(f"Failed to create QApplication: {e}")
        return 1
    
    # ========== 5. CREATE SPLASH SCREEN ==========
    splash = create_splash_screen(app)
    if splash:
        splash.showMessage("Initializing StreamMate AI...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter)
        app.processEvents()
    
    # ========== 6. INITIALIZE CONFIGURATION ==========
    cfg = initialize_configuration()
    if not cfg:
        logger.critical("Configuration initialization failed, exiting...")
        if splash:
            splash.close()
        return 1
    
    if splash:
        splash.showMessage("Loading system components...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter)
        app.processEvents()
    
    # ========== 7. PRELOAD MODULES ==========
    chat_listener_module = preload_chat_listener()
    
    # ========== 8. CHECK PAYMENT SERVER ==========
    payment_server_ok = check_payment_server()
    if not payment_server_ok:
        logger.warning("Payment server not available - payment features may not work")
    
    if splash:
        splash.showMessage("Starting user interface...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter)
        app.processEvents()
    
    # ========== 9. CREATE MAIN WINDOW ==========
    try:
        from ui.main_window import MainWindow
        
        window = MainWindow()
        
        # Pass chat listener module jika berhasil diload
        if chat_listener_module and hasattr(window, 'set_chat_listener_module'):
            window.set_chat_listener_module(chat_listener_module)
        
        # Set app icon jika ada
        icon_path = Path(ROOT) / "resources" / "app_icon.png"
        if icon_path.exists():
            window.setWindowIcon(QIcon(str(icon_path)))
            app.setWindowIcon(QIcon(str(icon_path)))
        
        logger.info("Main window created successfully")
        
    except ImportError as e:
        logger.critical(f"Failed to import MainWindow: {e}")
        if splash:
            splash.close()
        QMessageBox.critical(
            None, "Import Error", 
            f"Failed to import MainWindow:\n\n{e}\n\n"
            "Please check your installation and try again."
        )
        return 1
    except Exception as e:
        logger.critical(f"Failed to create main window: {e}")
        if splash:
            splash.close()
        QMessageBox.critical(
            None, "Startup Error",
            f"Failed to create main window:\n\n{e}\n\n"
            "Check error_log.txt for details."
        )
        return 1
    
    # ========== 10. SHOW MAIN WINDOW ==========
    try:
        # Close splash before showing main window
        if splash:
            splash.finish(window)
        
        window.show()
        logger.info("Main window displayed successfully")
        
        # Log aplikasi siap
        logger.info("StreamMate AI started successfully")
        logger.info(f"Application ready after {time.time() - __import__('time').time():.2f}s")
        
    except Exception as e:
        logger.critical(f"Failed to show main window: {e}")
        return 1
    
    # ========== 11. START EVENT LOOP ==========
    try:
        logger.info("Starting Qt event loop...")
        exit_code = app.exec()
        logger.info(f"Application exited with code: {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 0
    except Exception as e:
        logger.critical(f"Event loop error: {e}")
        return 1
    finally:
        # Cleanup
        logger.info("Performing cleanup...")
        try:
            # Stop any running timers atau threads jika perlu
            pass
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

def run_development_mode():
    """Mode khusus untuk development dengan debug verbose"""
    print("="*60)
    print("StreamMate AI - DEVELOPMENT MODE")
    print("="*60)
    
    # Set debug mode
    logging.getLogger().setLevel(logging.DEBUG)
    
    # Additional debug info
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print(f"Root directory: {ROOT}")
    print(f"Python path entries: {len(sys.path)}")
    
    # Run main dengan extra debugging
    try:
        return main()
    except Exception as e:
        print(f"DEVELOPMENT MODE ERROR: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    # Check development mode
    if "--dev" in sys.argv or os.getenv("STREAMMATE_DEV"):
        exit_code = run_development_mode()
    else:
        exit_code = main()
    
    # Final cleanup dan exit
    logger.info("StreamMate AI shutdown complete")
    sys.exit(exit_code)