# modules_server/billing_security.py
import sqlite3
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

class BillingSecurityDB:
    """Database handler untuk billing security dan tracking."""
    
    def __init__(self, db_path: str = "billing_security.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Inisialisasi semua tabel yang diperlukan."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Demo usage tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS demo_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                usage_date TEXT NOT NULL,
                demo_count INTEGER DEFAULT 1,
                last_demo_time TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(email, usage_date)
            )
        ''')
        
        # Session tracking table dengan heartbeat
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                session_id TEXT NOT NULL UNIQUE,
                feature_name TEXT NOT NULL,
                start_time TEXT NOT NULL,
                last_heartbeat TEXT NOT NULL,
                active_seconds REAL DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        ''')
        
        # License cache table untuk server-side validation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS license_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                tier TEXT NOT NULL,
                is_valid INTEGER NOT NULL,
                expire_date TEXT,
                daily_usage TEXT, -- JSON string
                last_validation TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Email tracking table untuk logout/login management
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                last_login TEXT,
                last_logout TEXT,
                login_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"✅ Billing Security Database initialized: {self.db_path}")
    
    # ========== DEMO USAGE METHODS ==========
    
    def check_demo_usage(self, email: str) -> Dict[str, Any]:
        """Cek apakah user masih bisa menggunakan demo hari ini."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().date().isoformat()
        
        cursor.execute('''
            SELECT demo_count, last_demo_time FROM demo_usage 
            WHERE email = ? AND usage_date = ?
        ''', (email.lower(), today))
        
        result = cursor.fetchone()
        
        # Demo limit per hari (konfigurasi)
        DEMO_LIMIT_PER_DAY = 1
        
        if result:
            demo_count, last_demo_time = result
            can_demo = demo_count < DEMO_LIMIT_PER_DAY
            remaining_demos = max(0, DEMO_LIMIT_PER_DAY - demo_count)
        else:
            can_demo = True
            remaining_demos = DEMO_LIMIT_PER_DAY
        
        # Hitung next reset time (besok jam 00:00)
        tomorrow = datetime.now().date() + timedelta(days=1)
        next_reset = datetime.combine(tomorrow, datetime.min.time()).isoformat()
        
        conn.close()
        
        return {
            "can_demo": can_demo,
            "remaining_demos": remaining_demos,
            "next_reset": next_reset,
            "today": today
        }
    
    def register_demo_usage(self, email: str) -> Dict[str, Any]:
        """Register demo usage untuk user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().date().isoformat()
        now = datetime.now()
        now_str = now.isoformat()
        
        # Demo duration (30 menit)
        demo_duration_minutes = 30
        demo_expires = now + timedelta(minutes=demo_duration_minutes)
        
        # Cek apakah sudah pakai demo hari ini
        cursor.execute('''
            SELECT demo_count FROM demo_usage 
            WHERE email = ? AND usage_date = ?
        ''', (email.lower(), today))
        
        result = cursor.fetchone()
        
        if result and result[0] >= 1:
            conn.close()
            return {
                "success": False,
                "message": "Demo sudah digunakan hari ini",
                "can_retry_tomorrow": True
            }
        
        # Register demo usage
        cursor.execute('''
            INSERT OR REPLACE INTO demo_usage 
            (email, usage_date, demo_count, last_demo_time, created_at)
            VALUES (?, ?, 1, ?, ?)
        ''', (email.lower(), today, now_str, now_str))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "demo_expires": demo_expires.isoformat(),
            "duration_minutes": demo_duration_minutes
        }
    
    # ========== SESSION TRACKING METHODS ==========
    
    def start_session(self, email: str, feature_name: str, session_id: str = None) -> Dict[str, Any]:
        """Start user session tracking."""
        if not session_id:
            session_id = f"{email}_{feature_name}_{int(time.time())}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        # End existing active sessions untuk email + feature ini
        cursor.execute('''
            UPDATE user_sessions 
            SET is_active = 0, last_heartbeat = ?
            WHERE email = ? AND feature_name = ? AND is_active = 1
        ''', (now, email.lower(), feature_name))
        
        # Start new session
        cursor.execute('''
            INSERT INTO user_sessions 
            (email, session_id, feature_name, start_time, last_heartbeat, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (email.lower(), session_id, feature_name, now, now, now))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "session_id": session_id,
            "start_time": now
        }
    
    def heartbeat_session(self, session_id: str, active_seconds: float) -> Dict[str, Any]:
        """Update session heartbeat dan active time."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        # Update heartbeat dan active time
        cursor.execute('''
            UPDATE user_sessions 
            SET last_heartbeat = ?, active_seconds = active_seconds + ?
            WHERE session_id = ? AND is_active = 1
        ''', (now, active_seconds, session_id))
        
        if cursor.rowcount == 0:
            conn.close()
            return {"success": False, "message": "Session tidak ditemukan"}
        
        # Get total active time
        cursor.execute('''
            SELECT active_seconds FROM user_sessions WHERE session_id = ?
        ''', (session_id,))
        
        result = cursor.fetchone()
        total_active_time = result[0] if result else 0
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "total_active_time": total_active_time,
            "last_heartbeat": now
        }
    
    def end_session(self, session_id: str) -> Dict[str, Any]:
        """End session dan calculate final usage."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        # Get session info dan mark sebagai inactive
        cursor.execute('''
            SELECT email, feature_name, active_seconds FROM user_sessions
            WHERE session_id = ? AND is_active = 1
        ''', (session_id,))
        
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return {"success": False, "message": "Session aktif tidak ditemukan"}
        
        email, feature_name, active_seconds = result
        
        # Mark sebagai inactive
        cursor.execute('''
            UPDATE user_sessions 
            SET is_active = 0, last_heartbeat = ?
            WHERE session_id = ?
        ''', (now, session_id))
        
        # Calculate usage (round up ke menit terdekat, minimum 1 menit)
        total_minutes = active_seconds / 60.0
        credited_minutes = max(1, int(total_minutes + 0.99))  # Round up
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "email": email,
            "feature": feature_name,
            "total_minutes": round(total_minutes, 2),
            "credited_minutes": credited_minutes,
            "end_time": now
        }
    
    # ========== LICENSE CACHE METHODS ==========
    
    def get_license_cache(self, email: str, max_age_hours: int = 1) -> Optional[Dict[str, Any]]:
        """Get cached license validation result."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT tier, is_valid, expire_date, daily_usage, last_validation
            FROM license_cache WHERE email = ?
        ''', (email.lower(),))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return None
        
        tier, is_valid, expire_date, daily_usage_json, last_validation_str = result
        
        # Cek apakah cache masih valid (berdasarkan age)
        try:
            last_validation = datetime.fromisoformat(last_validation_str)
            if (datetime.now() - last_validation).total_seconds() > max_age_hours * 3600:
                return None  # Cache expired
        except ValueError:
            return None  # Invalid date format
        
        daily_usage = json.loads(daily_usage_json) if daily_usage_json else {}
        
        return {
            "tier": tier,
            "is_valid": bool(is_valid),
            "expire_date": expire_date,
            "daily_usage": daily_usage,
            "last_validation": last_validation_str,
            "cached": True
        }
    
    def set_license_cache(self, email: str, license_data: Dict[str, Any]) -> bool:
        """Set cached license validation result."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        daily_usage_json = json.dumps(license_data.get("daily_usage", {}))
        
        cursor.execute('''
            INSERT OR REPLACE INTO license_cache
            (email, tier, is_valid, expire_date, daily_usage, last_validation, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            email.lower(),
            license_data.get("tier", "basic"),
            int(license_data.get("is_valid", False)),
            license_data.get("expire_date"),
            daily_usage_json,
            now, now, now
        ))
        
        conn.commit()
        conn.close()
        return True
    
    # ========== EMAIL TRACKING METHODS ==========
    
    def track_email_activity(self, email: str, action: str) -> Dict[str, Any]:
        """Track email login/logout activity."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        # Get existing record
        cursor.execute('''
            SELECT login_count FROM email_tracking WHERE email = ?
        ''', (email.lower(),))
        
        result = cursor.fetchone()
        
        if result:
            login_count = result[0]
            if action == "login":
                login_count += 1
                cursor.execute('''
                    UPDATE email_tracking 
                    SET last_login = ?, login_count = ?, updated_at = ?
                    WHERE email = ?
                ''', (now, login_count, now, email.lower()))
            else:  # logout
                cursor.execute('''
                    UPDATE email_tracking 
                    SET last_logout = ?, updated_at = ?
                    WHERE email = ?
                ''', (now, now, email.lower()))
        else:
            # New email
            login_count = 1 if action == "login" else 0
            cursor.execute('''
                INSERT INTO email_tracking 
                (email, last_login, last_logout, login_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                email.lower(), 
                now if action == "login" else None,
                now if action == "logout" else None,
                login_count, now, now
            ))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "action": action,
            "login_count": login_count,
            "timestamp": now
        }
    
    def get_last_logout_email(self) -> Optional[str]:
        """Get email yang terakhir logout (untuk compatibility dengan sistem lama)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT email FROM email_tracking 
            WHERE last_logout IS NOT NULL 
            ORDER BY last_logout DESC LIMIT 1
        ''')
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    # ========== ADMIN/STATS METHODS ==========
    
    def get_admin_stats(self) -> Dict[str, Any]:
        """Get admin statistics untuk monitoring."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Demo usage stats
        cursor.execute('SELECT COUNT(*) FROM demo_usage')
        total_demos = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM demo_usage WHERE usage_date = ?', 
                      (datetime.now().date().isoformat(),))
        demos_today = cursor.fetchone()[0]
        
        # Active sessions
        cursor.execute('SELECT COUNT(*) FROM user_sessions WHERE is_active = 1')
        active_sessions = cursor.fetchone()[0]
        
        # Unique users
        cursor.execute('SELECT COUNT(DISTINCT email) FROM email_tracking')
        unique_users = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_demos": total_demos,
            "demos_today": demos_today,
            "active_sessions": active_sessions,
            "unique_users": unique_users,
            "timestamp": datetime.now().isoformat()
        }

# Global instance untuk digunakan di server.py
billing_db = BillingSecurityDB()