import sys
# modules_server/real_credit_tracker.py
import json
import time
import logging
import pytz
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger('StreamMate')

class RealCreditTracker:
    """Tracker kredit berbasis penggunaan komponen aktual dengan multiplier 3x"""
    
    def __init__(self):
        self.config_file = Path("config/credit_config.json")
        self.subscription_file = Path("config/subscription_status.json")
        self.usage_file = Path("temp/daily_usage.json")
        
        # Gunakan timezone Indonesia (WIB) untuk konsistensi
        self.wib = pytz.timezone('Asia/Jakarta')
        
        # Load konfigurasi
        self.load_config()
        
        # Init daily usage file
        self.init_daily_usage()
        
    def load_config(self):
        """Load konfigurasi kredit"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                # Default config
                config = {
                    "daily_limit_hours": 10,
                    "credit_multiplier": 5,
                    "component_costs": {
                        # "stt_whisper": 0.01,  # Removed - using Super Direct Google STT
                        "stt_google": 0.1,
                        "tts_gtts": 0.02,
                        "tts_google": 0.05,
                        "ai_reply_base": 0.5,
                        "ai_reply_token": 0.005,
                        "translator_nllb": 0.02
                    },
                    "tracking_enabled": True
                }
                
            self.daily_limit = config.get("daily_limit_hours", 10)
            self.multiplier = config.get("credit_multiplier", 3)
            self.costs = config.get("component_costs", {})
            self.enabled = config.get("tracking_enabled", True)
            
            logger.info(f"Credit tracker loaded: {self.daily_limit}h limit, {self.multiplier}x multiplier")
            
        except Exception as e:
            logger.error(f"Error loading credit config: {e}")
            # Fallback ke default
            self.daily_limit = 10
            self.multiplier = 3
            self.costs = {}
            self.enabled = True

    def init_daily_usage(self):
        """Inisialisasi file usage harian"""
        # Gunakan tanggal WIB untuk konsistensi reset jam 00:00 WIB
        now_wib = datetime.now(self.wib)
        today = now_wib.strftime('%Y-%m-%d')
        
        try:
            if self.usage_file.exists():
                with open(self.usage_file, 'r', encoding='utf-8') as f:
                    usage = json.load(f)
                    
                # Reset jika hari berbeda
                if usage.get('date') != today:
                    usage = self.create_empty_usage(today)
            else:
                usage = self.create_empty_usage(today)
                
            # Simpan kembali
            self.usage_file.parent.mkdir(exist_ok=True, parents=True)
            with open(self.usage_file, 'w', encoding='utf-8') as f:
                json.dump(usage, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error init daily usage: {e}")
            
    def create_empty_usage(self, date):
        """Buat struktur usage kosong"""
        return {
            "date": date,
            "total_credits": 0.0,
            "total_hours": 0.0,
            "components": {
                "stt_seconds": 0,
                "tts_characters": 0,
                "ai_requests": 0,
                "ai_tokens": 0,
                "translate_words": 0
            },
            "sessions": []
        }

    def track_stt_usage(self, duration_seconds: float, stt_type: str = "google_stt") -> float:
        """Track penggunaan STT"""
        if not self.enabled:
            return 0.0
            
        cost_key = f"stt_{stt_type}"
        unit_cost = self.costs.get(cost_key, 0.1)  # ✅ DINAIKKAN: 0.01 → 0.1
        credits = duration_seconds * unit_cost * self.multiplier
        
        self.add_usage("stt_seconds", duration_seconds, credits)
        
        logger.info(f"STT Usage: {duration_seconds}s ({stt_type}) = {credits:.4f} credits")
        return credits

    def track_tts_usage(self, text: str, tts_type: str = "gtts") -> float:
        """Track penggunaan TTS"""
        if not self.enabled:
            return 0.0
            
        char_count = len(text)
        cost_key = f"tts_{tts_type}"
        unit_cost = self.costs.get(cost_key, 0.05)  # ✅ DINAIKKAN: 0.005 → 0.05 (10x lipat)
        credits = char_count * unit_cost * self.multiplier
        
        self.add_usage("tts_characters", char_count, credits)
        
        logger.info(f"TTS Usage: {char_count} chars ({tts_type}) = {credits:.4f} credits")
        return credits

    def track_ai_usage(self, tokens_used: int = 100) -> float:
        """Track penggunaan AI Reply"""
        if not self.enabled:
            return 0.0
            
        base_cost = self.costs.get("ai_reply_base", 0.5)     # ✅ DINAIKKAN: 0.1 → 0.5 (5x lipat)
        token_cost = tokens_used * self.costs.get("ai_reply_token", 0.005)  # ✅ DINAIKKAN: 0.001 → 0.005 (5x lipat)
        total_cost = (base_cost + token_cost) * self.multiplier
        
        self.add_usage("ai_requests", 1, base_cost * self.multiplier)
        self.add_usage("ai_tokens", tokens_used, token_cost * self.multiplier)
        
        logger.info(f"AI Usage: 1 request + {tokens_used} tokens = {total_cost:.4f} credits")
        return total_cost

    def track_translate_usage(self, word_count: int) -> float:
        """Track penggunaan translator"""
        if not self.enabled:
            return 0.0
            
        unit_cost = self.costs.get("translator_nllb", 0.02)  # ✅ DINAIKKAN: 0.005 → 0.02 (4x lipat)
        credits = word_count * unit_cost * self.multiplier
        
        self.add_usage("translate_words", word_count, credits)
        
        logger.info(f"Translate Usage: {word_count} words = {credits:.4f} credits")
        return credits

    def add_usage(self, component: str, amount: float, credits: float):
        """Tambah penggunaan ke file"""
        try:
            if not self.usage_file.exists():
                self.init_daily_usage()
                
            with open(self.usage_file, 'r', encoding='utf-8') as f:
                usage = json.load(f)
                
            # Update component usage
            usage["components"][component] = usage["components"].get(component, 0) + amount
            usage["total_credits"] += credits
            usage["total_hours"] = usage["total_credits"] / 60  # Konversi ke jam (asumsi 60 credit = 1 jam)
            
            # Tambah session entry dengan WIB timestamp
            now_wib = datetime.now(self.wib)
            usage["sessions"].append({
                "timestamp": now_wib.isoformat(),
                "component": component,
                "amount": amount,
                "credits": credits
            })
            
            # Simpan kembali
            with open(self.usage_file, 'w', encoding='utf-8') as f:
                json.dump(usage, f, indent=2)
                
            # Update subscription file juga
            self.update_subscription_usage(credits)
            
        except Exception as e:
            logger.error(f"Error adding usage: {e}")

    def _is_production_mode(self):
        """Check if running in production mode"""
        return getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS')

    def update_subscription_usage(self, credits_used: float):
        """PRODUCTION MODE: FORCE VPS sync - ignore local file in EXE mode"""
        try:
            # PRODUCTION MODE: Skip local file updates, FORCE VPS sync
            if self._is_production_mode():
                print(f"[PRODUCTION CREDIT] 🚀 EXE Mode - FORCE VPS sync only")
                print(f"[PRODUCTION CREDIT] 💳 Using: {credits_used:.4f} credits")
                
                # Get email for VPS sync
                try:
                    from modules_client.config_manager import ConfigManager
                    cfg = ConfigManager("config/settings.json")
                    user_data = cfg.get("user_data", {})
                    email = user_data.get("email", "")
                    
                    if email:
                        # FORCE immediate VPS sync without local file
                        hours_used = credits_used / 60
                        self._force_immediate_vps_sync(email, hours_used)
                    else:
                        logger.error("[PRODUCTION CREDIT] ❌ No email found for VPS sync!")
                        
                except Exception as e:
                    logger.error(f"[PRODUCTION CREDIT] ❌ VPS sync error: {e}")
                
                return  # Skip local file processing in production
            
            # DEVELOPMENT MODE: Normal local file processing
            if not self.subscription_file.exists():
                return
                
            with open(self.subscription_file, 'r', encoding='utf-8') as f:
                sub_data = json.load(f)
                
            # Update local file (development only)
            hours_used = credits_used / 60
            current_used = float(sub_data.get("hours_used", 0))
            new_total_used = round(current_used + hours_used, 4)
            
            # Update remaining credit
            current_credit = float(sub_data.get("hours_credit", 0))
            new_remaining_credit = max(0, current_credit - hours_used)
            
            sub_data["hours_used"] = new_total_used
            sub_data["hours_credit"] = new_remaining_credit
            # Update dengan WIB timestamp
            now_wib = datetime.now(self.wib)
            sub_data["updated_at"] = now_wib.isoformat()
            
            # Save local file
            with open(self.subscription_file, 'w', encoding='utf-8') as f:
                json.dump(sub_data, f, indent=2)
                
            logger.info(f"[DEVELOPMENT CREDIT] Local: -{hours_used:.4f}h, remaining: {new_remaining_credit:.4f}h")
            
            # Background VPS sync
            self._sync_usage_to_vps_async(hours_used, new_total_used, sub_data.get("email"))
            
        except Exception as e:
            logger.error(f"Error updating subscription: {e}")

    def _force_immediate_vps_sync(self, email: str, hours_used: float):
        """FORCE immediate VPS sync for production mode"""
        import requests
        import threading
        
        def immediate_sync():
            try:
                vps_url = "http://69.62.79.238:8000"
                credits_used = hours_used * 60  # Convert hours to credits
                payload = {
                    "email": email,
                    "credits_used": credits_used,  # ✅ FIX: Add credits_used as required by server
                    "hours_used": hours_used,      # Keep for backward compatibility
                    "timestamp": datetime.now().isoformat(),
                    "client_version": "1.0.0",
                    "sync_type": "production_immediate",
                    "force_update": True
                }
                
                logger.info(f"[PRODUCTION CREDIT] 🌐 Immediate VPS sync: {hours_used:.4f}h")
                
                response = requests.post(
                    f"{vps_url}/api/license/update_usage",
                    json=payload,
                    timeout=20,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    remaining = result.get('remaining_credit', 'unknown')
                    logger.info(f"[PRODUCTION CREDIT] ✅ VPS sync SUCCESS! Remaining: {remaining}")
                    
                    # Store VPS response for UI updates
                    self._store_vps_credit_response(result)
                    
                else:
                    logger.error(f"[PRODUCTION CREDIT] ❌ VPS sync FAILED: {response.status_code} - {response.text}")
                    
            except Exception as e:
                logger.error(f"[PRODUCTION CREDIT] ❌ VPS sync ERROR: {e}")
        
        # Run immediate sync in background
        sync_thread = threading.Thread(target=immediate_sync, daemon=True)
        sync_thread.start()

    def _store_vps_credit_response(self, vps_response):
        """Store VPS response for UI credit display"""
        try:
            # Create temp VPS credit file for UI
            vps_credit_file = Path("temp/vps_credit_response.json")
            vps_credit_file.parent.mkdir(exist_ok=True, parents=True)
            
            vps_data = {
                "remaining_credit": vps_response.get("remaining_credit", 0),
                "last_sync": datetime.now().isoformat(),
                "status": "success",
                "source": "vps_server"
            }
            
            with open(vps_credit_file, 'w', encoding='utf-8') as f:
                json.dump(vps_data, f, indent=2)
                
            logger.debug(f"[PRODUCTION CREDIT] 💾 Stored VPS credit response for UI")
            
        except Exception as e:
            logger.error(f"Error storing VPS credit response: {e}")

    def _sync_usage_to_vps_async(self, hours_used: float, total_used: float, email: str = None):
        """Sync usage ke VPS server secara asynchronous"""
        import threading
        import requests
        from modules_client.config_manager import ConfigManager
        
        def sync_worker():
            try:
                # Get email if not provided
                user_email = email
                if not user_email:
                    cfg = ConfigManager("config/settings.json")
                    user_data = cfg.get("user_data", {})
                    user_email = user_data.get("email", "")
                
                if not user_email:
                    logger.warning("No email found for VPS usage sync")
                    return
                
                # Sync ke VPS server
                vps_url = "http://69.62.79.238:8000"
                credits_used = hours_used * 60  # Convert hours to credits
                payload = {
                    "email": user_email,  # FIX: Use user_email instead of email
                    "credits_used": credits_used,  # ✅ FIX: Add credits_used as required by server
                    "hours_used": hours_used,  # Usage increment (keep for compatibility)
                    "total_hours_used": total_used,  # Total usage
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.debug(f"Syncing usage to VPS: {payload}")
                
                response = requests.post(
                    f"{vps_url}/api/license/update_usage",
                    json=payload,
                    timeout=15,  # Increase timeout for reliability
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    logger.debug(f"Usage synced to VPS successfully: +{hours_used:.4f}h")
                else:
                    logger.warning(f"VPS usage sync failed: {response.status_code} - {response.text}")
                    
            except Exception as e:
                logger.warning(f"VPS usage sync error: {e}")
                # Don't raise exception as this is background sync
        
        # Run in background thread
        sync_thread = threading.Thread(target=sync_worker, daemon=True)
        sync_thread.start()

    def get_daily_usage(self) -> Dict[str, Any]:
        """Dapatkan penggunaan hari ini"""
        try:
            if self.usage_file.exists():
                with open(self.usage_file, 'r', encoding='utf-8') as f:
                    usage = json.load(f)
                    
                return {
                    "total_hours": usage.get("total_hours", 0),
                    "total_credits": usage.get("total_credits", 0),
                    "limit_hours": self.daily_limit,
                    "remaining_hours": max(0, self.daily_limit - usage.get("total_hours", 0)),
                    "components": usage.get("components", {}),
                    "enabled": self.enabled
                }
            else:
                return {
                    "total_hours": 0,
                    "total_credits": 0,
                    "limit_hours": self.daily_limit,
                    "remaining_hours": self.daily_limit,
                    "components": {},
                    "enabled": self.enabled
                }
                
        except Exception as e:
            logger.error(f"Error getting daily usage: {e}")
            return {"error": str(e)}

    def check_credit_available(self, required_credits: float = 0.1) -> bool:
        """Cek apakah kredit masih tersedia"""
        usage = self.get_daily_usage()
        remaining = usage.get("remaining_hours", 0)
        required_hours = required_credits / 60
        
        return remaining >= required_hours

    def check_and_notify_low_credit(self) -> bool:
        """
        Cek kredit rendah dan tampilkan notifikasi.
        Returns: True jika kredit cukup, False jika tidak
        """
        try:
            usage = self.get_daily_usage()
            remaining_credits = usage.get("remaining_hours", 0) * 60  # Convert to credits
            
            # Ambil kredit dari subscription file yang lebih akurat
            subscription_file = Path("config/subscription_status.json")
            if subscription_file.exists():
                with open(subscription_file, 'r', encoding='utf-8') as f:
                    sub_data = json.load(f)
                    actual_credit = float(sub_data.get("hours_credit", 0))
            else:
                actual_credit = remaining_credits
            
            # Threshold notifikasi
            CRITICAL_THRESHOLD = 1.0    # < 1 kredit
            LOW_THRESHOLD = 5.0         # < 5 kredit
            WARNING_THRESHOLD = 10.0    # < 10 kredit
            
            if actual_credit < CRITICAL_THRESHOLD:
                self._show_credit_notification(
                    "❌ Kredit Habis!",
                    f"Kredit Anda tinggal {actual_credit:.1f}!\n\n"
                    f"Anda tidak dapat menggunakan fitur Auto-Reply.\n"
                    f"Silakan isi ulang kredit segera.",
                    "critical"
                )
                return False
                
            elif actual_credit < LOW_THRESHOLD:
                self._show_credit_notification(
                    "⚠️ Kredit Sangat Rendah",
                    f"Kredit Anda tinggal {actual_credit:.1f}!\n\n"
                    f"Estimasi tersisa: ~{int(actual_credit / 0.45)} auto-reply\n"
                    f"Silakan isi ulang kredit sebelum habis.",
                    "warning"
                )
                return True
                
            elif actual_credit < WARNING_THRESHOLD:
                self._show_credit_notification(
                    "ℹ️ Kredit Rendah",
                    f"Kredit Anda tinggal {actual_credit:.1f}\n\n"
                    f"Estimasi tersisa: ~{int(actual_credit / 0.45)} auto-reply\n"
                    f"Pertimbangkan untuk isi ulang kredit.",
                    "info"
                )
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking low credit: {e}")
            return True  # Default allow usage if error
    
    def _show_credit_notification(self, title: str, message: str, level: str):
        """Tampilkan notifikasi kredit dengan rate limiting."""
        import time
        
        # Rate limiting - max 1 notifikasi per 5 menit per level
        current_time = time.time()
        last_notif_key = f"last_credit_notif_{level}"
        
        if not hasattr(self, '_last_notifications'):
            self._last_notifications = {}
        
        last_time = self._last_notifications.get(last_notif_key, 0)
        if current_time - last_time < 300:  # 5 menit
            return
        
        self._last_notifications[last_notif_key] = current_time
        
        # Log notification
        logger.warning(f"Credit notification: {title} - {message}")
        
        # Tampilkan di console untuk debugging
        print(f"\n{'='*50}")
        print(f"NOTIFIKASI KREDIT: {title}")
        print(f"{'='*50}")
        print(message)
        print(f"{'='*50}\n")

    def get_available_credits(self) -> float:
        """Get available credits in hours - wrapper for get_current_credit_balance()"""
        try:
            return get_current_credit_balance()
        except Exception as e:
            logger.error(f"Error getting available credits: {e}")
            return 0.0

# Enhanced credit deduction functions
def force_credit_deduction(credits_used: float, description: str = "Auto-reply usage", extra_desc: str = None) -> bool:
    """Force immediate credit deduction and update"""
    try:
        # Use extra_desc if provided for more detailed description
        if extra_desc:
            description = f"{description} - {extra_desc}"
            
        from modules_client.config_manager import ConfigManager
        cfg = ConfigManager("config/settings.json")
        user_data = cfg.get("user_data", {})
        email = user_data.get("email", "")
        
        if not email:
            print(f"[CREDIT] ❌ No email found for credit deduction")
            return False
        
        hours_used = credits_used / 60  # Convert credits to hours
        
        print(f"[CREDIT] 💳 FORCING credit deduction: {credits_used:.4f} credits ({hours_used:.6f} hours)")
        print(f"[CREDIT] 📝 Description: {description}")
        
        # Force VPS deduction
        try:
            import requests
            vps_url = "http://69.62.79.238:8000"
            payload = {
                "email": email,
                "credits_used": credits_used,  # ✅ FIX: Use credits_used as required by server
                "hours_used": hours_used,      # Keep for backward compatibility
                "timestamp": datetime.now().isoformat(),
                "description": description,
                "force_deduction": True
            }
            
            print(f"[CREDIT] 🌐 Sending VPS deduction request...")
            
            response = requests.post(
                f"{vps_url}/api/license/update_usage",
                json=payload,
                timeout=20,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"[CREDIT] ✅ VPS deduction SUCCESS!")
                print(f"[CREDIT] 📊 Response: {result}")
                return True
            else:
                print(f"[CREDIT] ❌ VPS deduction FAILED: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"[CREDIT] ❌ VPS deduction ERROR: {e}")
            return False
            
    except Exception as e:
        print(f"[CREDIT] ❌ Force deduction error: {e}")
        return False

# Global instance
credit_tracker = RealCreditTracker()

def get_current_credit_balance() -> float:
    """Get current credit balance - prioritize LOCAL file for accuracy"""
    try:
        from modules_client.config_manager import ConfigManager
        cfg = ConfigManager("config/settings.json")
        user_data = cfg.get("user_data", {})
        email = user_data.get("email", "")
        
        if not email:
            return 0.0
        
        # PRIORITAS 1: Gunakan data lokal yang akurat (hasil real deduction)
        subscription_file = Path("config/subscription_status.json")
        if subscription_file.exists():
            with open(subscription_file, 'r', encoding='utf-8') as f:
                sub_data = json.load(f)
                credit_hours = float(sub_data.get("hours_credit", 0))
                
                # Cek apakah ada deduction lokal yang belum sync ke VPS
                last_deduction = sub_data.get("last_deduction", {})
                if last_deduction:
                    print(f"[CREDIT] 📄 Using LOCAL balance (accurate): {credit_hours:.4f} hours")
                    print(f"[CREDIT] 💡 Last deduction: {last_deduction.get('description', 'N/A')}")
                    return credit_hours
        
        # PRIORITAS 2: Coba VPS hanya jika lokal tidak ada/kosong  
        try:
            import requests
            vps_url = "http://69.62.79.238:8000"
            response = requests.post(
                f"{vps_url}/api/license/validate",
                json={"email": email},
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                vps_credit = data.get("data", {}).get("credit_balance", 0)
                
                # Jika ada data lokal, gunakan lokal karena lebih akurat
                if subscription_file.exists():
                    with open(subscription_file, 'r', encoding='utf-8') as f:
                        sub_data = json.load(f)
                        local_credit = float(sub_data.get("hours_credit", 0))
                        
                    # Bandingkan dan pilih yang paling masuk akal
                    if abs(local_credit - vps_credit) > 1.0:  # Perbedaan > 1 jam
                        print(f"[CREDIT] ⚖️ DISCREPANCY: Local={local_credit:.4f}h, VPS={vps_credit:.4f}h")
                        print(f"[CREDIT] 🎯 Using LOCAL (real deductions): {local_credit:.4f} hours")
                        return local_credit
                    else:
                        print(f"[CREDIT] ✅ VPS & Local synchronized: {vps_credit:.4f} hours")
                        return float(vps_credit)
                else:
                    print(f"[CREDIT] 🌐 VPS balance (no local): {vps_credit:.4f} hours")
                    return float(vps_credit)
                
        except Exception as e:
            print(f"[CREDIT] ⚠️ VPS check failed: {e}")
        
        # FALLBACK: Local file backup
        if subscription_file.exists():
            with open(subscription_file, 'r', encoding='utf-8') as f:
                sub_data = json.load(f)
                credit_hours = float(sub_data.get("hours_credit", 0))
                print(f"[CREDIT] 📄 Fallback local balance: {credit_hours:.4f} hours")
                return credit_hours
        
        return 0.0
        
    except Exception as e:
        print(f"[CREDIT] ❌ Error getting balance: {e}")
        return 0.0

def force_credit_deduction_v2(credits_used: float, description: str = "Auto-reply usage", extra_desc: str = None) -> bool:
    """Force immediate credit deduction and update - Enhanced version"""
    try:
        # Use extra_desc if provided for more detailed description
        if extra_desc:
            description = f"{description} - {extra_desc}"
            
        from modules_client.config_manager import ConfigManager
        cfg = ConfigManager("config/settings.json")
        user_data = cfg.get("user_data", {})
        email = user_data.get("email", "")
        
        if not email:
            print(f"[CREDIT] ❌ No email found for credit deduction")
            return False
        
        hours_used = credits_used / 60  # Convert credits to hours
        
        print(f"[CREDIT] 💳 FORCING credit deduction: {credits_used:.4f} credits ({hours_used:.6f} hours)")
        print(f"[CREDIT] 📝 Description: {description}")
        
        # Get current balance
        current_balance = get_current_credit_balance()
        
        if current_balance < hours_used:
            print(f"[CREDIT] ❌ Insufficient balance! Current: {current_balance:.4f}h, Required: {hours_used:.6f}h")
            return False
        
        # Force VPS deduction
        try:
            import requests
            vps_url = "http://69.62.79.238:8000"
            payload = {
                "email": email,
                "credits_used": credits_used,  # ✅ FIX: Use credits_used as required by server
                "hours_used": hours_used,      # Keep for backward compatibility
                "timestamp": datetime.now().isoformat(),
                "description": description,
                "force_deduction": True
            }
            
            print(f"[CREDIT] 🌐 Sending VPS deduction request...")
            
            response = requests.post(
                f"{vps_url}/api/license/update_usage",
                json=payload,
                timeout=20,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                new_balance = result.get("data", {}).get("remaining_credit", "unknown")
                print(f"[CREDIT] ✅ VPS deduction SUCCESS!")
                print(f"[CREDIT] 📊 New balance: {new_balance} hours")
                
                # Update local file to match VPS
                update_local_credit_file(new_balance, hours_used)
                
                # Create real-time notification
                create_credit_update_notification(credits_used, new_balance)
                
                return True
            else:
                print(f"[CREDIT] ❌ VPS deduction FAILED: {response.status_code} - {response.text}")
                
                # Try fallback local deduction
                return fallback_local_deduction(credits_used, description)
                
        except Exception as e:
            print(f"[CREDIT] ❌ VPS deduction ERROR: {e}")
            return fallback_local_deduction(credits_used, description)
            
    except Exception as e:
        print(f"[CREDIT] ❌ Force deduction error: {e}")
        return False

def fallback_local_deduction(credits_used: float, description: str) -> bool:
    """Fallback local credit deduction when VPS fails"""
    try:
        subscription_file = Path("config/subscription_status.json")
        if not subscription_file.exists():
            print(f"[CREDIT] ❌ No local subscription file found")
            return False
            
        with open(subscription_file, 'r', encoding='utf-8') as f:
            sub_data = json.load(f)
        
        hours_used = credits_used / 60
        current_credit = float(sub_data.get("hours_credit", 0))
        current_used = float(sub_data.get("hours_used", 0))
        
        if current_credit < hours_used:
            print(f"[CREDIT] ❌ Insufficient local credit: {current_credit:.4f}h < {hours_used:.6f}h")
            return False
        
        # Deduct locally
        new_credit = current_credit - hours_used
        new_used = current_used + hours_used
        
        sub_data["hours_credit"] = round(new_credit, 6)
        sub_data["hours_used"] = round(new_used, 6)
        sub_data["last_deduction"] = {
            "timestamp": datetime.now().isoformat(),
            "credits_used": credits_used,
            "description": description
        }
        sub_data["updated_at"] = datetime.now().isoformat()
        
        with open(subscription_file, 'w', encoding='utf-8') as f:
            json.dump(sub_data, f, indent=2)
        
        print(f"[CREDIT] ✅ LOCAL deduction SUCCESS!")
        print(f"[CREDIT] 📊 New balance: {new_credit:.4f} hours")
        
        create_credit_update_notification(credits_used, new_credit)
        
        return True
        
    except Exception as e:
        print(f"[CREDIT] ❌ Local deduction error: {e}")
        return False

def update_local_credit_file(new_balance: float, hours_used: float):
    """Update local credit file to match VPS"""
    try:
        subscription_file = Path("config/subscription_status.json")
        
        if subscription_file.exists():
            with open(subscription_file, 'r', encoding='utf-8') as f:
                sub_data = json.load(f)
        else:
            sub_data = {}
        
        current_used = float(sub_data.get("hours_used", 0))
        
        sub_data["hours_credit"] = float(new_balance)
        sub_data["hours_used"] = round(current_used + hours_used, 6)
        sub_data["last_vps_sync"] = datetime.now().isoformat()
        sub_data["source"] = "vps_sync"
        
        with open(subscription_file, 'w', encoding='utf-8') as f:
            json.dump(sub_data, f, indent=2)
            
        print(f"[CREDIT] 📄 Local file updated to match VPS")
        
    except Exception as e:
        print(f"[CREDIT] ⚠️ Failed to update local file: {e}")

def create_credit_update_notification(credits_used: float, new_balance: float):
    """Create notification for credit update"""
    try:
        # Create notification file for UI
        notification_file = Path("temp/credit_notification.json")
        notification_file.parent.mkdir(exist_ok=True, parents=True)
        
        notification_data = {
            "type": "credit_deduction",
            "credits_used": credits_used,
            "new_balance_hours": new_balance,
            "new_balance_credits": new_balance * 60,
            "timestamp": datetime.now().isoformat(),
            "message": f"Kredit berkurang {credits_used:.2f} credit. Sisa: {new_balance:.2f} jam"
        }
        
        with open(notification_file, 'w', encoding='utf-8') as f:
            json.dump(notification_data, f, indent=2)
            
        print(f"[CREDIT] 🔔 Notification created for UI")
        
    except Exception as e:
        print(f"[CREDIT] ⚠️ Failed to create notification: {e}")

# Enhanced credit tracker with forced deduction
def track_usage_with_forced_deduction(component: str, credits_used: float, description: str = None):
    """Track usage and force immediate credit deduction"""
    try:
        # Create description if not provided
        if not description:
            description = f"{component} usage"
        
        print(f"[CREDIT] 🎯 Tracking {component}: {credits_used:.4f} credits")
        
        # Force immediate deduction
        success = force_credit_deduction(credits_used, description)
        
        if success:
            # Also update local usage tracking
            credit_tracker.add_usage(component, 1, credits_used)
            print(f"[CREDIT] ✅ {component} usage tracked and deducted successfully")
        else:
            print(f"[CREDIT] ❌ {component} usage tracking failed - credit deduction failed")
            
        return success
        
    except Exception as e:
        print(f"[CREDIT] ❌ Error tracking {component} usage: {e}")
        return False