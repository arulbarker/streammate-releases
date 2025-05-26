# modules_server/license_manager.py
import json
import time
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

class LicenseManager:
    """
    Pengelola lisensi per jam di sisi server.
    Basic: 100 jam = Rp 100.000
    """
    def __init__(self, db_path="license_data.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Inisialisasi database dengan sistem kredit jam."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabel utama lisensi dengan kredit jam
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            tier TEXT DEFAULT 'basic',
            hours_credit REAL DEFAULT 0,
            hours_used REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        # Tabel riwayat transaksi
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS transaction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            transaction_type TEXT,
            hours_amount REAL,
            price INTEGER,
            order_id TEXT,
            payment_status TEXT,
            created_at TEXT
        )
        ''')
        
        # Tabel pemakaian per hari (untuk statistik)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            date TEXT,
            hours_used REAL,
            sessions INTEGER DEFAULT 0,
            created_at TEXT,
            UNIQUE(email, date)
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_or_update_license(self, email, initial_hours=0):
        """Buat atau update lisensi user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            cursor.execute("SELECT id FROM licenses WHERE email = ?", (email,))
            exists = cursor.fetchone()
            
            if exists:
                cursor.execute('''
                    UPDATE licenses 
                    SET updated_at = ? 
                    WHERE email = ?
                ''', (now, email))
            else:
                cursor.execute('''
                    INSERT INTO licenses 
                    (email, tier, hours_credit, created_at, updated_at) 
                    VALUES (?, 'basic', ?, ?, ?)
                ''', (email, initial_hours, now, now))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error creating license: {e}")
            return False
        finally:
            conn.close()
    
    def add_hours_credit(self, email, hours, price, order_id):
        """Tambah kredit jam setelah pembayaran berhasil."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            # Pastikan user ada
            self.create_or_update_license(email)
            
            # Update hours_credit
            cursor.execute('''
                UPDATE licenses 
                SET hours_credit = hours_credit + ?, 
                    is_active = 1,
                    updated_at = ?
                WHERE email = ?
            ''', (hours, now, email))
            
            # Catat transaksi
            cursor.execute('''
                INSERT INTO transaction_history 
                (email, transaction_type, hours_amount, price, order_id, 
                 payment_status, created_at)
                VALUES (?, 'purchase', ?, ?, ?, 'success', ?)
            ''', (email, hours, price, order_id, now))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding hours credit: {e}")
            return False
        finally:
            conn.close()
    
    def use_hours_credit(self, email, minutes):
        """Kurangi kredit saat digunakan (otomatis dibulatkan ke atas per jam)."""
        # Bulatkan ke atas per jam
        hours = max(1.0, round(minutes / 60, 2))
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Cek sisa kredit
            cursor.execute('''
                SELECT hours_credit, hours_used 
                FROM licenses WHERE email = ?
            ''', (email,))
            result = cursor.fetchone()
            
            if not result or result[0] < hours:
                return False  # Tidak cukup kredit
            
            now = datetime.now()
            
            # Update kredit dan usage
            cursor.execute('''
                UPDATE licenses 
                SET hours_credit = ROUND(hours_credit - ?, 2), 
                    hours_used = ROUND(hours_used + ?, 2),
                    updated_at = ?
                WHERE email = ?
            ''', (hours, hours, now.isoformat(), email))
            
            # Update daily usage
            today = now.date().isoformat()
            cursor.execute('''
                INSERT INTO daily_usage (email, date, hours_used, sessions, created_at)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(email, date) 
                DO UPDATE SET 
                    hours_used = ROUND(hours_used + ?, 2),
                    sessions = sessions + 1
            ''', (email, today, hours, now.isoformat(), hours))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error using hours credit: {e}")
            return False
        finally:
            conn.close()
    
    def get_hours_info(self, email):
        """Get info kredit jam user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT hours_credit, hours_used, is_active, tier
                FROM licenses WHERE email = ?
            ''', (email,))
            
            result = cursor.fetchone()
            
            if result:
                credit, used, active, tier = result
                return {
                    "hours_credit": round(credit, 0),  # Tampil bulat untuk user
                    "hours_used": round(used, 2),      # 2 desimal untuk akurasi
                    "is_active": active and credit > 0,
                    "tier": tier,
                    "has_credit": credit > 0
                }
            
            # User belum terdaftar
            return {
                "hours_credit": 0,
                "hours_used": 0,
                "is_active": False,
                "tier": "basic",
                "has_credit": False
            }
        finally:
            conn.close()
    
    def get_usage_history(self, email, days=30):
        """Get riwayat pemakaian user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            since_date = (datetime.now() - timedelta(days=days)).date().isoformat()
            
            cursor.execute('''
                SELECT date, hours_used, sessions
                FROM daily_usage 
                WHERE email = ? AND date >= ?
                ORDER BY date DESC
            ''', (email, since_date))
            
            results = cursor.fetchall()
            
            return [{
                "date": row[0],
                "hours": round(row[1], 2),
                "sessions": row[2]
            } for row in results]
        finally:
            conn.close()
    
    def validate_license(self, email, hw_id=None):
        """Validasi lisensi untuk client."""
        hours_info = self.get_hours_info(email)
        
        return {
            "is_valid": hours_info["has_credit"],
            "tier": hours_info["tier"],
            "hours_credit": hours_info["hours_credit"],
            "hours_used": hours_info["hours_used"],
            "expire_date": None,  # Tidak ada expiry untuk sistem jam
            "message": "OK" if hours_info["has_credit"] else "Kredit habis"
        }