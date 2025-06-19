#!/usr/bin/env python3
"""
Daily Limit Manager - Sistem Pembatasan Harian yang Aman
Membatasi akses aplikasi maksimal 10 jam per hari
Reset berdasarkan timezone Indonesia (WIB) untuk konsistensi
"""

import json
import os
import pytz
from datetime import datetime, date, timedelta
from pathlib import Path
import time

class DailyLimitManager:
    def __init__(self):
        self.limit_file = Path("temp/daily_usage_limit.json")
        self.limit_file.parent.mkdir(exist_ok=True)
        self.daily_limit_hours = 10.0  # 10 jam per hari
        self.session_start_time = None
        # Gunakan timezone Indonesia (WIB) karena VPS di India
        self.wib = pytz.timezone('Asia/Jakarta')
        
    def start_session(self):
        """Mulai sesi penggunaan dan catat waktu mulai"""
        try:
            self.session_start_time = time.time()
            # Gunakan tanggal WIB untuk konsistensi reset jam 00:00 WIB
            now_wib = datetime.now(self.wib)
            today = now_wib.date().isoformat()
            
            # Load existing data
            usage_data = self._load_usage_data()
            
            # Reset jika hari berbeda
            if usage_data.get("date") != today:
                usage_data = {
                    "date": today,
                    "total_hours_used": 0.0,
                    "sessions": [],
                    "is_limited": False
                }
            
            # Tambah sesi baru
            usage_data["sessions"].append({
                "start_time": self.session_start_time,
                "end_time": None,
                "duration": 0.0
            })
            
            self._save_usage_data(usage_data)
            print(f"[LIMIT] Session started at {now_wib.strftime('%H:%M:%S WIB')}")
            
        except Exception as e:
            print(f"[LIMIT] Error starting session: {e}")
    
    def end_session(self):
        """Akhiri sesi dan update durasi penggunaan"""
        try:
            if self.session_start_time is None:
                return 0.0
                
            session_duration = time.time() - self.session_start_time
            session_hours = session_duration / 3600.0  # Convert to hours
            
            # Gunakan tanggal WIB untuk konsistensi
            now_wib = datetime.now(self.wib)
            today = now_wib.date().isoformat()
            usage_data = self._load_usage_data()
            
            # Update sesi terakhir
            if usage_data.get("sessions"):
                last_session = usage_data["sessions"][-1]
                last_session["end_time"] = time.time()
                last_session["duration"] = session_hours
                
                # Update total usage
                usage_data["total_hours_used"] = usage_data.get("total_hours_used", 0.0) + session_hours
                
                # Check if limit exceeded
                if usage_data["total_hours_used"] >= self.daily_limit_hours:
                    usage_data["is_limited"] = True
                
                self._save_usage_data(usage_data)
                
                print(f"[LIMIT] Session ended: {session_hours:.2f}h used, Total today: {usage_data['total_hours_used']:.2f}h")
                
            self.session_start_time = None
            return session_hours
            
        except Exception as e:
            print(f"[LIMIT] Error ending session: {e}")
            return 0.0
    
    def can_start_app(self):
        """Cek apakah aplikasi masih bisa diakses hari ini"""
        try:
            # Gunakan tanggal WIB untuk konsistensi reset jam 00:00 WIB
            now_wib = datetime.now(self.wib)
            today = now_wib.date().isoformat()
            usage_data = self._load_usage_data()
            
            # Reset jika hari berbeda
            if usage_data.get("date") != today:
                return True, 0.0, self.daily_limit_hours
            
            total_used = usage_data.get("total_hours_used", 0.0)
            remaining = max(0, self.daily_limit_hours - total_used)
            
            can_access = total_used < self.daily_limit_hours
            
            return can_access, total_used, remaining
            
        except Exception as e:
            print(f"[LIMIT] Error checking access: {e}")
            return True, 0.0, self.daily_limit_hours  # Default allow access
    
    def get_usage_stats(self):
        """Dapatkan statistik penggunaan hari ini"""
        try:
            # Gunakan tanggal WIB untuk konsistensi
            now_wib = datetime.now(self.wib)
            today = now_wib.date().isoformat()
            usage_data = self._load_usage_data()
            
            if usage_data.get("date") != today:
                return {
                    "date": today,
                    "total_hours_used": 0.0,
                    "remaining_hours": self.daily_limit_hours,
                    "sessions_count": 0,
                    "is_limited": False,
                    "limit_hours": self.daily_limit_hours
                }
            
            total_used = usage_data.get("total_hours_used", 0.0)
            remaining = max(0, self.daily_limit_hours - total_used)
            
            return {
                "date": today,
                "total_hours_used": total_used,
                "remaining_hours": remaining,
                "sessions_count": len(usage_data.get("sessions", [])),
                "is_limited": usage_data.get("is_limited", False),
                "limit_hours": self.daily_limit_hours
            }
            
        except Exception as e:
            print(f"[LIMIT] Error getting stats: {e}")
            # Fallback dengan WIB date
            now_wib = datetime.now(self.wib)
            today_fallback = now_wib.date().isoformat()
            return {
                "date": today_fallback,
                "total_hours_used": 0.0,
                "remaining_hours": self.daily_limit_hours,
                "sessions_count": 0,
                "is_limited": False,
                "limit_hours": self.daily_limit_hours
            }
    
    def _load_usage_data(self):
        """Load data penggunaan dari file"""
        try:
            if self.limit_file.exists():
                with open(self.limit_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[LIMIT] Error loading usage data: {e}")
        
        return {"date": "", "total_hours_used": 0.0, "sessions": [], "is_limited": False}
    
    def _save_usage_data(self, data):
        """Simpan data penggunaan ke file"""
        try:
            with open(self.limit_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[LIMIT] Error saving usage data: {e}")

# Global instance
daily_limit_manager = DailyLimitManager()

def check_daily_access():
    """Fungsi helper untuk cek akses harian"""
    return daily_limit_manager.can_start_app()

def start_usage_session():
    """Fungsi helper untuk mulai sesi"""
    daily_limit_manager.start_session()

def end_usage_session():
    """Fungsi helper untuk akhiri sesi"""
    return daily_limit_manager.end_session()

def get_daily_usage_stats():
    """Fungsi helper untuk statistik"""
    return daily_limit_manager.get_usage_stats() 