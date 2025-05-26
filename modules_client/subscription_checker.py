# modules_client/subscription_checker.py - line 1-10
import json
import time
import threading
import logging
import os
import requests  # TAMBAHKAN INI
from pathlib import Path
from datetime import datetime, timedelta

# Setup logging
logger = logging.getLogger('StreamMate')

# modules_client/subscription_checker.py - line 15-20
# Konstanta untuk sistem kredit
IDLE_TIMEOUT = 300  # 5 menit dalam detik
IDLE_WARNING = 180  # 3 menit dalam detik
MIN_SESSION_TIME = 120  # 2 menit dalam detik
SAVE_INTERVAL = 60  # Interval save status (1 menit dalam detik)

# Server API URLs
SERVER_BASE_URL = "http://localhost:8000"  # TAMBAHKAN INI

# Import debug manager
try:
    from .credit_debug_manager import CreditDebugManager
    DEBUG_MANAGER = CreditDebugManager()
    CREDIT_DEBUG_ENABLED = True
    print("[DEBUG] Credit Debug Manager loaded successfully in subscription_checker")
except ImportError as e:
    DEBUG_MANAGER = None
    CREDIT_DEBUG_ENABLED = False
    print(f"[DEBUG] Credit Debug Manager not available in subscription_checker: {e}")
# ===================================================================================

class HourlySubscriptionChecker:
    """Mengelola kredit waktu dengan sistem 'Active Session Plus'."""
    
    def __init__(self):
        """Inisialisasi sistem kredit."""
        self.subscription_file = Path("config/subscription_status.json")
        self.session_file = Path("temp/current_session.json")
        
        # State tracking
        self.is_tracking = False
        self.session_start = 0
        self.session_active_time = 0
        self.last_activity = 0
        self.idle_state = False
        self.active_feature = None
        
        # Callbacks
        self.on_idle_warning = None
        self.on_idle_timeout = None
        
        # Thread
        self.tracking_thread = None
        self._stop_thread = False
        
        # Load data
        self.load_data()
    
    def load_data(self):
        """Muat data langganan dan sesi saat ini."""
        # Load subscription status
        if self.subscription_file.exists():
            try:
                with open(self.subscription_file, 'r', encoding='utf-8') as f:
                    self.subscription_data = json.load(f)
            except Exception as e:
                logger.error(f"Error loading subscription data: {e}")
                self.subscription_data = {}
        else:
            self.subscription_data = {}
        
        # Load current session
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    self.session_data = json.load(f)
                    
                # Periksa apakah ada sesi yang tertunda (aplikasi crash)
                if self.session_data.get('active', False) and self.session_data.get('start_time', 0) > 0:
                    # Hitung waktu yang telah berlalu
                    elapsed = min(
                        time.time() - self.session_data.get('start_time', 0),
                        IDLE_TIMEOUT  # Maksimal idle timeout
                    )
                    
                    # Tambahkan ke aktif time jika valid
                    if elapsed > 0 and elapsed <= IDLE_TIMEOUT:
                        self.session_active_time = elapsed
                        logger.info(f"Recovered {elapsed:.1f} seconds from previous session")
            except Exception as e:
                logger.error(f"Error loading session data: {e}")
                self.session_data = {}
        else:
            self.session_data = {}
    
    def start_tracking(self, feature_name="general"):
        """Mulai pelacakan waktu aktif dengan server tracking."""
        if self.is_tracking:
            # Sudah tracking, ubah status ke aktif
            self.register_activity(feature_name)
            return
        
        # TAMBAHAN: Debug logging
        if CREDIT_DEBUG_ENABLED and DEBUG_MANAGER:
            current_subscription = self._get_current_subscription()
            initial_credit = current_subscription.get("hours_credit", 0)
            initial_used = current_subscription.get("hours_used", 0)
            DEBUG_MANAGER.log_usage_start(feature_name, initial_credit)
            logger.info(f"[CREDIT_DEBUG] Usage start logged: {feature_name} - Initial credit: {initial_credit}h")

        # Log detail untuk debugging
        DEBUG_MANAGER._log_debug("session_start_detail", {
            "feature_name": feature_name,
            "initial_credit": initial_credit,
            "initial_used": initial_used,
            "timestamp": datetime.now().isoformat(),
            "tracking_state": "starting"
        })
    # ========================================================

        # Set state
        self.is_tracking = True
        self.session_start = time.time()
        self.last_activity = time.time()
        self.idle_state = False
        self.active_feature = feature_name
        self.session_active_time = 0
        
        # Generate session ID
        email = self._get_user_email()
        self.current_session_id = f"{email}_{feature_name}_{int(time.time())}"
        
        # Start session di server
        try:
            response = requests.post(
                f"{SERVER_BASE_URL}/api/session/start",
                json={
                    "email": email,
                    "feature": feature_name,
                    "session_id": self.current_session_id
                },
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"Server session started: {self.current_session_id}")
            else:
                logger.warning(f"Failed to start server session: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error starting server session: {e}")
            # Continue dengan local tracking sebagai fallback
        
        # Update session data (local fallback)
        self.session_data = {
            'active': True,
            'start_time': self.session_start,
            'feature': feature_name,
            'last_activity': self.last_activity,
            'session_id': self.current_session_id
        }
        self._save_session()
        
        # Mulai thread tracking (sama seperti sebelumnya)
        self._stop_thread = False
        self.tracking_thread = threading.Thread(target=self._tracking_worker, daemon=True)
        self.tracking_thread.start()
        
        logger.info(f"Started time tracking for feature: {feature_name}")
    
    def stop_tracking(self):
        """Hentikan pelacakan waktu dan perbarui kredit dengan server sync."""
        if not self.is_tracking:
            return
        
        # Hentikan thread
        self._stop_thread = True
        if self.tracking_thread and self.tracking_thread.is_alive():
            self.tracking_thread.join(timeout=2.0)
        
        # Finalisasi sesi
        elapsed = time.time() - self.session_start
        total_active = self.session_active_time
        
        # Tambahkan waktu aktif terakhir jika tidak idle
        if not self.idle_state:
            time_since_last = time.time() - self.last_activity
            if time_since_last < IDLE_TIMEOUT:
                total_active += time_since_last
        
        # Minimum session time
        if total_active < MIN_SESSION_TIME and total_active > 0:
            total_active = MIN_SESSION_TIME
            logger.info(f"Applied minimum session time: {MIN_SESSION_TIME} seconds")
        
        # TAMBAHAN: Debug logging SEBELUM update kredit
        # =============================================
        if CREDIT_DEBUG_ENABLED and DEBUG_MANAGER:
            current_subscription = self._get_current_subscription()
            pre_update_credit = current_subscription.get("hours_credit", 0)
            pre_update_used = current_subscription.get("hours_used", 0)
            
            DEBUG_MANAGER._log_debug("session_stop_detail", {
                "feature_name": self.active_feature,
                "session_duration_seconds": elapsed,
                "active_time_seconds": total_active,
                "pre_update_credit": pre_update_credit,
                "pre_update_used": pre_update_used,
                "timestamp": datetime.now().isoformat(),
                "tracking_state": "stopping"
            })
            logger.info(f"[CREDIT_DEBUG] Session stopping: {self.active_feature} - {total_active:.1f}s active")
        # =============================================

        # End session di server
        server_minutes = 0
        if hasattr(self, 'current_session_id'):
            try:
                response = requests.post(
                    f"{SERVER_BASE_URL}/api/session/end",
                    json={"session_id": self.current_session_id},
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    server_minutes = data.get("credited_minutes", 0)
                    logger.info(f"Server session ended: {server_minutes} minutes credited")
                else:
                    logger.warning(f"Failed to end server session: {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error ending server session: {e}")
        
        # Hitung kredit lokal sebagai fallback
        minutes_used = max(1, int((total_active + 59) / 60))  # Bulat ke atas
        
        # Gunakan server minutes jika tersedia, otherwise gunakan lokal
        final_minutes = server_minutes if server_minutes > 0 else minutes_used
        
        # Update status
        self.is_tracking = False
        self.idle_state = False
        self.session_data = {
            'active': False,
            'last_session': {
                'feature': self.active_feature,
                'start': self.session_start,
                'duration': elapsed,
                'active_time': total_active,
                'minutes_used': final_minutes,
                'end_time': time.time(),
                'server_tracked': server_minutes > 0
            }
        }
        self._save_session()
        
        # TAMBAHAN: Debug logging sebelum update kredit
        if CREDIT_DEBUG_ENABLED and DEBUG_MANAGER:
            current_subscription = self._get_current_subscription()
            final_credit = current_subscription.get("hours_credit", 0)
            DEBUG_MANAGER.log_usage_end(
                self.active_feature, 
                final_credit, 
                final_minutes
            )

        # Update subscription credits jika ada sesi aktif
        if total_active > 0:
            self._update_credit_usage(final_minutes)
            logger.info(f"Session ended. Used {final_minutes} minutes of credit.")
        
        # TAMBAHAN: Debug logging SETELAH update kredit
        # =============================================
        if CREDIT_DEBUG_ENABLED and DEBUG_MANAGER:
            current_subscription = self._get_current_subscription()
            post_update_credit = current_subscription.get("hours_credit", 0)
            post_update_used = current_subscription.get("hours_used", 0)
            
            DEBUG_MANAGER.log_usage_end(
                self.active_feature, 
                post_update_credit, 
                final_minutes
            )
            
            # Log detail perubahan
            DEBUG_MANAGER._log_debug("credit_usage_applied", {
                "feature_name": self.active_feature,
                "minutes_charged": final_minutes,
                "hours_charged": final_minutes / 60.0,
                "pre_update_credit": pre_update_credit,
                "post_update_credit": post_update_credit,
                "pre_update_used": pre_update_used,
                "post_update_used": post_update_used,
                "credit_change": post_update_credit - pre_update_credit,
                "used_change": post_update_used - pre_update_used,
                "server_tracked": server_minutes > 0,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"[CREDIT_DEBUG] Usage end logged: {self.active_feature} - {final_minutes}min charged")
        # =============================================

        # Reset state
        self.session_start = 0
        self.session_active_time = 0
        self.last_activity = 0
        self.active_feature = None
        if hasattr(self, 'current_session_id'):
            delattr(self, 'current_session_id')
    
    def register_activity(self, feature_name=None):
        """Daftarkan aktivitas untuk menjaga sesi aktif."""
        if not self.is_tracking:
            # Jika tidak tracking, mulai tracking
            self.start_tracking(feature_name or "general")
            return
        
        # Update last activity time
        now = time.time()
        
        # Jika sedang idle, hitung waktu aktif sebelumnya
        if self.idle_state:
            # Reset idle state
            self.idle_state = False
            logger.info("Session resumed from idle state")
        else:
            # Tambahkan waktu aktif sejak aktivitas terakhir
            active_time = now - self.last_activity
            self.session_active_time += active_time
        
        # Update aktivitas terakhir dan fitur
        self.last_activity = now
        if feature_name:
            self.active_feature = feature_name
        
        # Update session data
        self.session_data['last_activity'] = now
        self.session_data['feature'] = self.active_feature
        self._save_session()
    
    def check_credit(self):
        """Periksa apakah kredit masih tersedia."""
        if not self.subscription_file.exists():
            return False
        
        try:
            with open(self.subscription_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Periksa status dan kredit
            if data.get('status') == 'paid' and data.get('hours_credit', 0) > 0:
                return True
            
            # Periksa mode demo
            if data.get('status') == 'demo':
                try:
                    expire = datetime.fromisoformat(data.get('expire_date', '2000-01-01'))
                    if expire > datetime.now():
                        return True
                except:
                    pass
                    
            return False
        except Exception as e:
            logger.error(f"Error checking credit: {e}")
            return False
    
    def get_credit_info(self):
        """Dapatkan info kredit saat ini."""
        if not self.subscription_file.exists():
            return {"hours_credit": 0, "hours_used": 0}
        
        try:
            with open(self.subscription_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return {
                "hours_credit": data.get('hours_credit', 0),
                "hours_used": data.get('hours_used', 0),
                "status": data.get('status', 'pending'),
                "package": data.get('package', 'basic')
            }
        except Exception as e:
            logger.error(f"Error getting credit info: {e}")
            return {"hours_credit": 0, "hours_used": 0}
    
    def _tracking_worker(self):
        """Thread worker untuk tracking waktu aktif dan idle."""
        last_save = time.time()
        
        while not self._stop_thread and self.is_tracking:
            now = time.time()
            time_since_last = now - self.last_activity
            
            # Periksa idle state
            if not self.idle_state and time_since_last >= IDLE_WARNING:
                # Masuk warning period
                if time_since_last >= IDLE_TIMEOUT:
                    # Masuk idle state
                    self.idle_state = True
                    logger.info("Session idle timeout reached")
                    
                    # Callback idle timeout
                    if self.on_idle_timeout:
                        try:
                            self.on_idle_timeout()
                        except Exception as e:
                            logger.error(f"Error in idle timeout callback: {e}")
                
                # Callback warning
                elif time_since_last >= IDLE_WARNING and self.on_idle_warning:
                    try:
                        self.on_idle_warning(IDLE_TIMEOUT - time_since_last)
                    except Exception as e:
                        logger.error(f"Error in idle warning callback: {e}")
            
            # Save interval dan heartbeat ke server
            if now - last_save >= SAVE_INTERVAL:
                # Tambahkan waktu aktif jika tidak idle
                if not self.idle_state:
                    active_time = now - self.last_activity
                    self.session_active_time += active_time
                    self.last_activity = now
                
                # Send heartbeat ke server
                if hasattr(self, 'current_session_id'):
                    try:
                        response = requests.post(
                            f"{SERVER_BASE_URL}/api/session/heartbeat",
                            json={
                                "session_id": self.current_session_id,
                                "active_seconds": SAVE_INTERVAL  # 60 detik interval
                            },
                            timeout=5
                        )
                        
                        if response.status_code == 200:
                            logger.debug(f"Heartbeat sent for session: {self.current_session_id}")
                        else:
                            logger.warning(f"Heartbeat failed: {response.status_code}")
                            
                    except requests.exceptions.RequestException as e:
                        logger.error(f"Error sending heartbeat: {e}")
                
                # Save session data (local fallback)
                self._save_session()
                last_save = now
            
            # Sleep
            time.sleep(1.0)

    def _get_user_email(self):
        """Get user email dari config."""
        try:
            from modules_client.config_manager import ConfigManager
            cfg = ConfigManager("config/settings.json")
            email = cfg.get("user_data", {}).get("email", "")
            if not email:
                email = "anonymous@streammate.local"
            return email.lower()
        except Exception as e:
            logger.error(f"Error getting user email: {e}")
            return "error@streammate.local"

    def _save_session(self):
        """Simpan status sesi saat ini."""
        try:
            # Buat direktori jika belum ada
            self.session_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(self.session_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving session data: {e}")
    
    def _update_credit_usage(self, minutes_used):
        """Update penggunaan kredit."""
        if not self.subscription_file.exists():
            return
        
        try:
            with open(self.subscription_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Skip jika bukan paid atau demo
            if data.get('status') not in ['paid', 'demo']:
                return
            
            # Konversi menit ke jam
            hours_used = minutes_used / 60.0
            
            # Update fields
            current_used = float(data.get('hours_used', 0))
            current_credit = float(data.get('hours_credit', 0))
            
            # Update
            data['hours_used'] = round(current_used + hours_used, 2)
            data['hours_credit'] = max(0, round(current_credit - hours_used, 2))
            data['updated_at'] = datetime.now().isoformat()
            
            # Tambahkan stats penggunaan jika belum ada
            if 'usage_stats' not in data:
                data['usage_stats'] = {}
            
            # Update stats harian
            today = datetime.now().strftime('%Y-%m-%d')
            if today not in data['usage_stats']:
                data['usage_stats'][today] = 0
            
            data['usage_stats'][today] = round(data['usage_stats'][today] + hours_used, 2)
            
            # Simpan
            with open(self.subscription_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Updated credit usage: -{hours_used:.2f} hours")
        except Exception as e:
            logger.error(f"Error updating credit usage: {e}")

    def _get_current_subscription(self):
        """Helper untuk get data subscription saat ini"""
        try:
            if self.subscription_file.exists():
                with open(self.subscription_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error reading subscription: {e}")
        return {}

# Global functions untuk penggunaan lebih mudah
_checker = None

def get_checker():
    """Dapatkan instance HourlySubscriptionChecker."""
    global _checker
    if _checker is None:
        _checker = HourlySubscriptionChecker()
    return _checker

def start_usage_tracking(feature="general"):
    """Mulai tracking penggunaan."""
    checker = get_checker()
    checker.start_tracking(feature)

def stop_usage_tracking():
    """Hentikan tracking penggunaan."""
    checker = get_checker()
    checker.stop_tracking()

def register_activity(feature=None):
    """Register activity untuk reset idle timer."""
    checker = get_checker()
    checker.register_activity(feature)

def get_credit_info():
    """Dapatkan info kredit."""
    checker = get_checker()
    return checker.get_credit_info()

def check_credit():
    """Periksa apakah kredit masih tersedia."""
    checker = get_checker()
    return checker.check_credit()

def set_idle_callbacks(warning_callback=None, timeout_callback=None):
    """Set callbacks untuk idle warning dan timeout."""
    checker = get_checker()
    checker.on_idle_warning = warning_callback
    checker.on_idle_timeout = timeout_callback

# Backwards compatibility functions
def add_usage(minutes=1):
    """Function lama untuk backward compatibility."""
    checker = get_checker()
    if checker.is_tracking:
        pass  # Handled by tracking system
    else:
        # Langsung kurangi kredit
        checker._update_credit_usage(minutes)

def get_today_usage():
    """Get usage hari ini (untuk backward compatibility)."""
    checker = get_checker()
    info = checker.get_credit_info()
    
    # Default values
    tier = info.get("package", "basic")
    usage = 0
    limit = 5 if tier == "basic" else 12  # Default limits
    
    # Get today's usage if available
    try:
        with open(checker.subscription_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'usage_stats' in data:
            today = datetime.now().strftime('%Y-%m-%d')
            usage = data['usage_stats'].get(today, 0)
    except:
        pass
    
    return tier, usage, limit

def time_until_next_day():
    """Mendapatkan waktu hingga hari berikutnya dalam detik."""
    now = datetime.now()
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return (tomorrow - now).total_seconds()