import json
import time
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import logging

class LicenseManager:
    """
    Pengelola lisensi berbasis kredit di sisi server.
    Konsep: 1 IDR = 1 Kredit.
    """
    def __init__(self, db_path="data/license_data.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_db()
        self._rename_old_columns()

    def _init_db(self):
        """Inisialisasi database dengan sistem kredit."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabel utama lisensi dengan kredit
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            tier TEXT DEFAULT 'basic',
            credit_balance REAL DEFAULT 0,
            credit_used REAL DEFAULT 0,
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
            credit_amount REAL,
            price REAL,
            order_id TEXT,
            description TEXT,
            created_at TEXT
        )
        ''')
        
        # Tabel riwayat penggunaan kredit
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS credit_usage_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            credit_deducted REAL,
            component TEXT,
            description TEXT,
            session_id TEXT,
            created_at TEXT
        )
        ''')
        
        conn.commit()
        conn.close()

    def _rename_old_columns(self):
        """
        Fungsi migrasi sekali jalan untuk mengubah nama kolom lama.
        Ini untuk menjaga data yang sudah ada.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Cek kolom di tabel 'licenses'
            cursor.execute("PRAGMA table_info(licenses)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'hours_credit' in columns:
                cursor.execute("ALTER TABLE licenses RENAME COLUMN hours_credit TO credit_balance")
            if 'hours_used' in columns:
                cursor.execute("ALTER TABLE licenses RENAME COLUMN hours_used TO credit_used")

            # Cek kolom di tabel 'transaction_history'
            cursor.execute("PRAGMA table_info(transaction_history)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'hours_amount' in columns:
                cursor.execute("ALTER TABLE transaction_history RENAME COLUMN hours_amount TO credit_amount")

            # Cek kolom di tabel 'credit_usage_history'
            cursor.execute("PRAGMA table_info(credit_usage_history)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'hours_deducted' in columns:
                cursor.execute("ALTER TABLE credit_usage_history RENAME COLUMN hours_deducted TO credit_deducted")

            conn.commit()
        except sqlite3.Error:
            # Mungkin gagal jika nama kolom sudah diubah, tidak apa-apa.
            pass
        finally:
            conn.close()
    
    def create_or_get_user(self, email):
        """Buat user jika belum ada, atau dapatkan data yang ada."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        try:
            cursor.execute("SELECT email FROM licenses WHERE email = ?", (email,))
            exists = cursor.fetchone()
            if not exists:
                cursor.execute(
                    "INSERT INTO licenses (email, created_at, updated_at) VALUES (?, ?, ?)",
                    (email, now, now)
                )
                conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error in create_or_get_user for {email}: {e}")
            return False
        finally:
            conn.close()

    def add_hours_credit(self, email, credits, price, order_id):
        """
        Fungsi utama untuk menambahkan kredit. Nama 'add_hours_credit' dipertahankan
        untuk backward compatibility dengan panggilan dari server_inti.py,
        tapi logikanya murni menggunakan KREDIT.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        try:
            self.create_or_get_user(email)
            
            # Update saldo kredit
            cursor.execute('''
                UPDATE licenses 
                SET credit_balance = credit_balance + ?, 
                    is_active = 1,
                    updated_at = ?
                WHERE email = ?
            ''', (credits, now, email))
            
            # Catat transaksi
            cursor.execute('''
                INSERT INTO transaction_history 
                (email, transaction_type, credit_amount, price, order_id, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (email, 'purchase', credits, price, order_id, f"Pembelian {credits} kredit", now))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error adding credit for {email}: {e}")
            return False
        finally:
            conn.close()

    def deduct_hours_credit(self, email, credits, component="", description="", session_id=""):
        """
        Fungsi utama untuk mengurangi kredit. Nama 'deduct_hours_credit' dipertahankan
        untuk backward compatibility, tapi logikanya murni KREDIT.
        """
        logger = logging.getLogger(__name__)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        try:
            logger.info(f"[DEDUCT] Starting deduction for {email}: {credits} credits")
            
            # Dapatkan saldo saat ini
            cursor.execute("SELECT credit_balance FROM licenses WHERE email = ?", (email,))
            current_balance = cursor.fetchone()
            
            logger.info(f"[DEDUCT] Current balance for {email}: {current_balance}")
            
            if current_balance is None:
                logger.error(f"[DEDUCT] User {email} not found in database")
                return False
                
            if current_balance[0] < credits:
                logger.warning(f"[DEDUCT] Insufficient balance for {email}: has {current_balance[0]}, needs {credits}")
                return False # Saldo tidak cukup

            # Update saldo dan total penggunaan
            logger.info(f"[DEDUCT] Updating balance for {email}: {current_balance[0]} - {credits} = {current_balance[0] - credits}")
            cursor.execute('''
                UPDATE licenses 
                SET credit_balance = credit_balance - ?, 
                    credit_used = credit_used + ?,
                    updated_at = ?
                WHERE email = ?
            ''', (credits, credits, now, email))
            
            # Catat penggunaan
            logger.info(f"[DEDUCT] Recording usage history for {email}")
            cursor.execute('''
                INSERT INTO credit_usage_history 
                (email, credit_deducted, component, description, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (email, credits, component, description, session_id, now))

            conn.commit()
            logger.info(f"[DEDUCT] Successfully deducted {credits} credits from {email}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"[DEDUCT] SQLite error for {email}: {e}")
            print(f"Error deducting credit for {email}: {e}")
            return False
        except Exception as e:
            logger.error(f"[DEDUCT] Unexpected error for {email}: {e}")
            print(f"Unexpected error deducting credit for {email}: {e}")
            return False
        finally:
            conn.close()
            
    def get_hours_info(self, email):
        """
        Fungsi utama untuk mendapatkan info kredit. Nama 'get_hours_info' dipertahankan
        untuk backward compatibility, tapi datanya adalah KREDIT.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT credit_balance, credit_used, is_active, tier, updated_at
                FROM licenses WHERE email = ?
            ''', (email,))
            result = cursor.fetchone()
            
            if result:
                balance, used, active, tier, updated_at = result
                # Menggunakan nama kunci yang konsisten dengan sistem kredit
                return {
                    "credit_balance": round(balance, 4),
                    "credit_used": round(used, 4),
                    "is_active": bool(active) and balance > 0,
                    "tier": tier,
                    "last_update": updated_at
                }
            
            # User belum terdaftar
            return {"credit_balance": 0, "credit_used": 0, "is_active": False}
        except sqlite3.Error as e:
            print(f"Error getting credit info for {email}: {e}")
            return {"credit_balance": 0, "credit_used": 0, "is_active": False}
        finally:
            conn.close()

    def get_transaction_history(self, email, days=30):
        """Get riwayat transaksi kredit."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            since_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            cursor.execute('''
                SELECT transaction_type, credit_amount, price, order_id, description, created_at
                FROM transaction_history 
                WHERE email = ? AND created_at >= ?
                ORDER BY created_at DESC
            ''', (email, since_date))
            
            results = cursor.fetchall()
            
            return [{
                "transaction_type": row[0],
                "credit_amount": round(row[1], 2),
                "price": row[2],
                "order_id": row[3],
                "description": row[4],
                "created_at": row[5]
            } for row in results]
            
        except sqlite3.Error as e:
            print(f"Error getting transaction history for {email}: {e}")
            return []
        finally:
            conn.close()

    def validate_license(self, email, hw_id=None):
        """Validasi lisensi dan kembalikan data kredit."""
        info = self.get_hours_info(email)
        is_valid = info.get("is_active", False)
        return {"valid": is_valid, **info}

    def add_credit(self, email, credits, price, order_id):
        """
        Alias untuk add_hours_credit untuk konsistensi nama dengan sistem kredit baru.
        Ini adalah fungsi yang seharusnya dipanggil oleh server_inti.py.
        """
        return self.add_hours_credit(email, credits, price, order_id)
    
    def get_credit_info(self, email):
        """
        Alias untuk get_hours_info untuk konsistensi dengan server_inti.py
        """
        return self.get_hours_info(email)
    
    def deduct_credit(self, email, credits, component="", description="", session_id=""):
        """
        Alias untuk deduct_hours_credit untuk konsistensi nama dengan sistem kredit baru.
        Ini adalah fungsi yang seharusnya dipanggil oleh server_inti.py.
        """
        return self.deduct_hours_credit(email, credits, component, description, session_id)

    def get_credit_info(self, email):
        """
        Alias untuk get_hours_info untuk konsistensi nama dengan sistem kredit baru.
        Ini adalah fungsi yang seharusnya dipanggil oleh server_inti.py.
        """
        return self.get_hours_info(email)