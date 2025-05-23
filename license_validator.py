import os
import json
import time
import requests
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

# Fallback untuk config_manager
try:
    from modules_client.config_manager import ConfigManager
except ImportError:
    from modules_server.config_manager import ConfigManager

class LicenseValidator:
    def __init__(self, server_url="https://streammateai.com/api/license", testing_mode=False):
        self.cfg = ConfigManager("config/settings.json")
        self.server_url = server_url
        self.testing_mode = testing_mode  # Ini yang penting!
        self.last_refresh = 0
        self.cache_path = Path("temp/license_cache.json")
        self.cache_path.parent.mkdir(exist_ok=True)
        
        # TAMBAHAN: Set default cache untuk test mode
        if self.testing_mode:
            self._write_cache({
                "is_valid": True,
                "tier": "pro",
                "expire_date": "2099-12-31T23:59:59",  # Far future
                "daily_usage": {},
                "last_check": time.time()
            })

    def _is_dev_user(self):
        """Cek apakah pengguna adalah developer."""
        # Jika dalam testing mode, langsung return True
        if hasattr(self, 'testing_mode') and self.testing_mode:
            return True
            
        try:
            email = self.cfg.get("user_data", {}).get("email", "")
            dev_path = Path("config/dev_users.json")
            if dev_path.exists() and email:
                devs = json.loads(dev_path.read_text(encoding="utf-8"))
                return email in devs.get("emails", [])
        except Exception as e:
            print(f"[DEBUG] Gagal cek dev user: {e}")
        return False

    def _read_cache(self):
        """Baca cache lisensi dari file."""
        try:
            if self.cache_path.exists():
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[DEBUG] Gagal baca cache: {e}")
        return {}

    def _write_cache(self, data):
        """Tulis cache lisensi ke file."""
        try:
            self.cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[DEBUG] Gagal tulis cache: {e}")

    def _local_validation(self):
        """Validasi lisensi dari file lokal (fallback)."""
        try:
            local_path = Path("config/subscription_status.json")
            if local_path.exists():
                data = json.loads(local_path.read_text(encoding="utf-8"))
                expire_str = data.get("expired_at")
                if expire_str:
                    expire_date = datetime.fromisoformat(expire_str)
                    is_valid = expire_date > datetime.now()
                    return {
                        "is_valid": is_valid,
                        "tier": data.get("tier", "demo"),
                        "expire_date": expire_str,
                        "daily_usage": data.get("daily_usage", {}),
                        "last_check": time.time()
                    }
        except Exception as e:
            print(f"[DEBUG] Fallback validation error: {e}")
        
        # Default data jika tidak ada file
        return {
            "is_valid": False,
            "tier": "demo",
            "expire_date": None,
            "daily_usage": {},
            "last_check": time.time()
        }

    def _generate_hardware_id(self):
        """Generate hardware ID unik untuk client."""
        try:
            import uuid
            # Get machine-specific identifiers
            mac = uuid.getnode()
            # Combine with additional system info
            hw_string = f"{mac}-{os.name}-{os.getenv('USERNAME', '')}"
            # Create hash
            return hashlib.md5(hw_string.encode()).hexdigest()
        except Exception:
            # Fallback to random UUID if hardware ID generation fails
            return str(uuid.uuid4())

    def validate(self, force_refresh=False):
        # TAMBAHAN: Bypass untuk test mode
        if self.testing_mode:
            return {
                "is_valid": True,
                "tier": "pro",
                "expire_date": "2099-12-31T23:59:59",
                "daily_usage": {},
                "last_check": time.time()
            }
            
        # Developer selalu valid dengan tier pro
        if self._is_dev_user():
            return {
                "is_valid": True,
                "tier": "pro",
                "expire_date": (datetime.now() + timedelta(days=365)).isoformat(),
                "daily_usage": {},
                "last_check": time.time()
            }
        
        # Cek cache dari server terlebih dahulu
        if not force_refresh:
            try:
                user_data = self.cfg.get("user_data", {})
                email = user_data.get("email", "")
                
                if email:
                    response = requests.post(
                        "http://localhost:8000/api/license/validate",
                        json={"email": email, "force_refresh": False},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        server_data = response.json()
                        
                        # Jika server mengembalikan cached result
                        if server_data.get("cached", False):
                            print(f"[DEBUG] Using server cached license data")
                            return {
                                "is_valid": server_data.get("is_valid", False),
                                "tier": server_data.get("tier", "demo"),
                                "expire_date": server_data.get("expire_date"),
                                "daily_usage": server_data.get("daily_usage", {}),
                                "last_check": server_data.get("last_check", time.time())
                            }
                        
                        # Jika server melakukan fresh validation
                        elif server_data.get("is_valid", False):
                            print(f"[DEBUG] Using fresh server license validation")
                            return {
                                "is_valid": server_data.get("is_valid", False),
                                "tier": server_data.get("tier", "demo"),
                                "expire_date": server_data.get("expire_date"),
                                "daily_usage": server_data.get("daily_usage", {}),
                                "last_check": server_data.get("last_check", time.time())
                            }
                    else:
                        print(f"[DEBUG] Server license validation failed: {response.status_code}")
                        
            except requests.exceptions.RequestException as e:
                print(f"[DEBUG] Server license validation error: {e}")

        # Fallback ke cache lokal jika server tidak tersedia
        current_time = time.time()
        cache = self._read_cache()

        if not force_refresh and current_time - cache.get("last_check", 0) < 3600:
            print(f"[DEBUG] Using local cached license data as fallback")
            return cache
        
        # Coba validasi dengan server
        try:
            # Prepare data untuk dikirim ke server
            user_data = self.cfg.get("user_data", {})
            email = user_data.get("email", "")
            hw_id = self._generate_hardware_id()
            
            if not email:
                # Jika tidak ada email, langsung gunakan validasi lokal
                return self._local_validation()
            
            # Kirim request ke server
            response = requests.post(
                self.server_url, 
                json={
                    "email": email,
                    "hw_id": hw_id,
                    "version": self.cfg.get("app_version", "1.0.0")
                },
                timeout=5
            )
            
            # Jika server merespons
            if response.status_code == 200:
                data = response.json()
                # Update cache dan settings
                self._write_cache({
                    "is_valid": data.get("is_valid", False),
                    "tier": data.get("tier", "demo"),
                    "expire_date": data.get("expire_date"),
                    "daily_usage": data.get("daily_usage", {}),
                    "last_check": current_time
                })
                # Update paket di settings
                if data.get("tier"):
                    self.cfg.set("paket", data.get("tier"))
                return data
            
        except Exception as e:
            print(f"[DEBUG] Server validation error: {e}")
        
        # Fallback ke validasi lokal jika server tidak tersedia
        return self._local_validation()
    
    def track_usage(self, minutes=1):
        """Tambahkan penggunaan dan kirim ke server."""
        # Dev user tidak perlu track usage
        if self._is_dev_user():
            return True
        
        # Ambil data dari cache
        cache = self._read_cache()
        today = datetime.now().date().isoformat()
        
        # Update usage lokal
        daily = cache.get("daily_usage", {})
        daily[today] = round(daily.get(today, 0) + minutes/60, 2)
        cache["daily_usage"] = daily
        self._write_cache(cache)
        
        # Coba kirim ke server (async di background)
        try:
            import threading
            
            def send_usage():
                try:
                    user_data = self.cfg.get("user_data", {})
                    email = user_data.get("email", "")
                    if not email:
                        return
                    
                    # Kirim usage ke server
                    requests.post(
                        f"{self.server_url}/usage", 
                        json={
                            "email": email,
                            "hw_id": self._generate_hardware_id(),
                            "minutes": minutes
                        },
                        timeout=5
                    )
                except Exception as e:
                    print(f"[DEBUG] Send usage error: {e}")
            
            # Kirim di thread terpisah agar tidak blocking
            threading.Thread(target=send_usage, daemon=True).start()
        except Exception:
            pass
        
        return True
    
    def get_today_usage(self):
        """
        Dapatkan penggunaan hari ini dan batas.
        
        Returns:
            tuple: (tier, used_hours, limit_hours)
        """
        # Dev user tidak terbatas
        if self._is_dev_user():
            return "pro", 0, 24
        
        # Batas per tier (jam)
        LIMITS = {
            "demo": 0.5,   # 30 menit
            "basic": 5,    # 5 jam
            "pro": 12      # 12 jam
        }
        
        # Get data
        cache = self._read_cache()
        tier = cache.get("tier", "demo")
        today = datetime.now().date().isoformat()
        used = cache.get("daily_usage", {}).get(today, 0)
        limit = LIMITS.get(tier, 0.5)
        
        return tier, used, limit