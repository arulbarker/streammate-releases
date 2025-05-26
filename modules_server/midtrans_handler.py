import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
import midtransclient
from pathlib import Path

# Load environment variables
load_dotenv()

class MidtransHandler:
    """Handler untuk integrasi Midtrans payment gateway."""
    
    def __init__(self, production=False):
        # Inisialisasi Midtrans client
        server_key = os.getenv("MIDTRANS_SERVER_KEY", "")
        client_key = os.getenv("MIDTRANS_CLIENT_KEY", "")
        
        if not server_key or not client_key:
            raise ValueError("Midtrans server key dan client key diperlukan")
        
        self.snap = midtransclient.Snap(
            is_production=production,
            server_key=server_key,
            client_key=client_key
        )
        
        # Load paket dan harga
        self._load_packages()
    
    def _load_packages(self):
        """Load konfigurasi paket dari file."""
        try:
            package_path = Path("config/packages.json")
            if package_path.exists():
                self.packages = json.loads(package_path.read_text(encoding="utf-8"))
            else:
                # Default packages
                self.packages = {
                    "basic": 50000,
                    "pro": 100000
                }
        except Exception as e:
            print(f"Error loading packages: {e}")
            # Fallback to default
            self.packages = {
                "basic": 50000,
                "pro": 100000
            }
    
    def create_transaction(self, email, package):
        """
        Buat transaksi baru di Midtrans.
        
        Args:
            email: Email pengguna
            package: Jenis paket (basic/pro)
            
        Returns:
            dict: Hasil pembuatan transaksi
        """
        # Validasi paket
        if package not in self.packages:
            return {
                "status": "error",
                "message": f"Paket tidak valid: {package}"
            }
        
        # Ambil harga
        price = self.packages.get(package)
        
        # Buat ID order (unik berdasarkan email, paket, dan waktu)
        timestamp = int(time.time())
        order_id = f"{email.replace('@', '_')}_{package}_{timestamp}"
        
        # Siapkan data transaksi
        transaction = {
            "transaction_details": {
                "order_id": order_id,
                "gross_amount": price
            },
            "customer_details": {
                "email": email,
                "first_name": email.split('@')[0]
            },
            "item_details": [{
                "id": package,
                "price": price,
                "quantity": 1,
                "name": f"StreamMate {package.capitalize()} Package"
            }],
            "callbacks": {
                "finish": "https://streammateai.com/payment/finish"
            }
        }
        
        try:
            # Buat transaksi di Midtrans
            response = self.snap.create_transaction(transaction)
            
            # Catat transaksi ke log
            self._log_transaction(order_id, email, package, price, "created")
            
            return {
                "status": "success",
                "redirect_url": response["redirect_url"],
                "token": response["token"],
                "order_id": order_id
            }
        
        except Exception as e:
            print(f"Error creating transaction: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def process_callback(self, callback_data):
        """
        Proses callback dari Midtrans.
        
        Args:
            callback_data: Data callback dari Midtrans
            
        Returns:
            dict: Hasil pemrosesan callback
        """
        try:
            # Ekstrak data penting
            transaction_status = callback_data.get("transaction_status")
            order_id = callback_data.get("order_id")
            
            if not order_id:
                return {
                    "success": False,
                    "message": "Order ID tidak ditemukan"
                }
            
            # Cek status transaksi
            if transaction_status not in ["settlement", "capture"]:
                self._log_transaction(order_id, "", "", 0, f"callback_{transaction_status}")
                return {
                    "success": False,
                    "message": f"Status transaksi: {transaction_status}"
                }
            
            # Parse order ID untuk mendapatkan email dan paket
            try:
                email_raw, package, _ = order_id.split('_', 2)
                email = email_raw.replace('_', '@')
            except ValueError:
                return {
                    "success": False,
                    "message": "Format Order ID tidak valid"
                }
            
            # Catat transaksi berhasil
            self._log_transaction(order_id, email, package, 0, "success")
            
            return {
                "success": True,
                "email": email,
                "package": package,
                "message": "Pembayaran berhasil"
            }
            
        except Exception as e:
            print(f"Error processing callback: {e}")
            return {
                "success": False,
                "message": str(e)
            }
    
    def _log_transaction(self, order_id, email, package, amount, status):
        """Catat transaksi ke file log."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / "payment_transactions.jsonl"
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "order_id": order_id,
            "email": email,
            "package": package,
            "amount": amount,
            "status": status
        }
        
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"Error logging transaction: {e}")