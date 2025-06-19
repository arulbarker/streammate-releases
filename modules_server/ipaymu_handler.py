# modules_server/ipaymu_handler.py - SANDBOX MODE UNTUK DEBUGGING
import os
import json
import time
import requests
import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class IPaymuHandler:
    def __init__(self):
        # PRODUCTION MODE - REAL CREDENTIALS
        self.mode = "production"  # Set mode explicitly
        self.base_url = "https://my.ipaymu.com"
        
        # Production credentials
        self.va = "1179005157914468"
        self.api_key = "C3CF720D-8347-4EA3-8DC9-BAC2DEF046AC"
        
        print(f"🚀 iPaymu PRODUCTION MODE")
        print(f"📱 VA: {self.va}")
        print(f"🔑 API Key: {self.api_key[:20]}...")
        
        if not self.api_key or not self.va:
            raise ValueError("Production credentials tidak tersedia")

        self.payment_url = f"{self.base_url}/api/v2/payment"
        self.transaction_url = f"{self.base_url}/api/v2/transaction"

        self._load_packages()
        self._test_connection()

    def _test_connection(self):
        """Test koneksi ke server iPaymu PRODUCTION."""
        test_url = f"{self.base_url}/api/v2/balance"
        print("\n🔌 TESTING KONEKSI KE IPAYMU PRODUCTION...")
        
        try:
            body_for_test = {"account": self.va}
            body_str_for_test = json.dumps(body_for_test, separators=(',', ':'))
            
            signature_test = self._generate_signature(body_str_for_test, http_method="POST")
            timestamp_test = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'va': self.va,
                'signature': signature_test,
                'timestamp': timestamp_test
            }
            
            response = requests.post(test_url, headers=headers, data=body_str_for_test, timeout=10) 
            
            print(f"✅ Test Koneksi iPaymu Production: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("Status") == 200:
                    balance = result.get("Data", {}).get("Balance", "Unknown")
                    print(f"💰 Saldo Production: Rp {balance:,.0f}" if isinstance(balance, (int, float)) else f"💰 Saldo: {balance}")
                    print("✅ KONEKSI PRODUCTION BERHASIL!")
                else:
                    print(f"⚠️ Response Status: {result.get('Status')} - {result.get('Message', 'Unknown')}")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                if response.text:
                    print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ GAGAL TERHUBUNG KE IPAYMU PRODUCTION: {e}")

    def _load_packages(self):
        """Load packages configuration - SECURE SERVER-BASED"""
        try:
            # HARDCODED PACKAGES - NO FILE ACCESS NEEDED
            # Ini lebih aman dari pada load dari file JSON
            if self.mode == "sandbox":
                # Sandbox packages - testing prices
                self.packages = {
                    "basic": {"price": 10000, "credits": 100000, "description": "Paket Basic Sandbox - 100.000 Kredit [TESTING]"},
                    "pro": {"price": 20000, "credits": 250000, "description": "Paket Pro Sandbox - 250.000 Kredit [TESTING]"}
                }
            else:
                # Production packages - real prices - HARDCODED FOR SECURITY
                self.packages = {
                    "basic": {"price": 100000, "credits": 100000, "description": "Paket Basic - 100.000 Kredit"},
                    "pro": {"price": 250000, "credits": 250000, "description": "Paket Pro - 250.000 Kredit"}
                }
                
            print(f"📦 Packages loaded successfully - {self.mode.upper()} mode")
            print(f"📦 Available packages: {list(self.packages.keys())}")
            
        except Exception as e:
            print(f"❌ Error in package loading: {e}")
            # Ultimate fallback - production defaults
            self.packages = {
                "basic": {"price": 100000, "credits": 100000, "description": "Paket Basic Production"},
                "pro": {"price": 250000, "credits": 250000, "description": "Paket Pro Production"}
            }

    def _generate_signature(self, payload_str, http_method="POST"):
        """Generate signature untuk iPaymu API."""
        # Hash body
        body_hash = hashlib.sha256(payload_str.encode()).hexdigest()
        
        # String to sign: METHOD:VA:BodyHash:ApiKey
        string_to_sign = f"{http_method.upper()}:{self.va}:{body_hash}:{self.api_key}"
        
        # Generate signature dengan HMAC-SHA256
        signature = hmac.new(
            self.api_key.encode(),
            string_to_sign.encode(),
            hashlib.sha256
        ).hexdigest()

        print(f"🔐 Signature generated for {http_method} request")
        return signature
    
    def create_transaction(self, email, package_name, price=None):
        """Buat transaksi REAL di iPaymu Production."""
        # Validasi paket
        package_info = self.packages.get(package_name)
        if not package_info or 'price' not in package_info:
            return {"status": "error", "message": f"Paket '{package_name}' tidak valid"}

        # Use provided price or fallback to package price
        actual_price = price if price is not None else package_info['price']
        credits = package_info.get('credits', 100000)
        
        # Generate unique order ID
        timestamp = int(time.time())
        username = email.split('@')[0].replace('.', '_').replace('-', '_')
        order_id = f"SM_{username}_{package_name}_{timestamp}"

        # URLs - SESUAIKAN DENGAN SERVER_INTI.PY
        base_url = os.getenv("APP_BASE_URL", "http://69.62.79.238:8000")  # Server inti di port 8000
        
        return_url = f"{base_url}/payment_completed?status=success&order_id={order_id}&email={email}"
        cancel_url = f"{base_url}/payment_completed?status=canceled&order_id={order_id}&email={email}"
        notify_url = f"{base_url}/api/payment/callback"  # Callback ke server_inti.py

        # Payload untuk iPaymu API V2 - PRODUCTION
        payload = {
            "product": [f"StreamMate AI {package_name.capitalize()}"],
            "qty": [1],
            "price": [actual_price],
            "description": [f"StreamMate AI {package_name.capitalize()} - {credits:,} kredit streaming"],
            "returnUrl": return_url,
            "cancelUrl": cancel_url,
            "notifyUrl": notify_url,
            "referenceId": order_id,
            "buyerName": email.split('@')[0],
            "buyerEmail": email,
            "buyerPhone": "08123456789",  # Default phone
            "paymentMethod": "qris",
            "paymentChannel": "qris"
        }

        payload_str = json.dumps(payload, separators=(',', ':'))
        signature = self._generate_signature(payload_str, http_method="POST")
        timestamp_str = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'signature': signature,
            'va': self.va,
            'timestamp': timestamp_str
        }

        print(f"💳 Creating PRODUCTION transaction for {email} - {package_name} (Rp {actual_price:,})")
        print(f"🔗 Return URL: {return_url}")
        print(f"🔗 Cancel URL: {cancel_url}")
        print(f"🔗 Notify URL: {notify_url}")

        try:
            response = requests.post(self.payment_url, headers=headers, data=payload_str, timeout=30)
            
            print(f"📡 iPaymu Production Response: {response.status_code}")
            print(f"📡 Response Body: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get("Status") == 200:
                    data = result.get("Data", {})
                    payment_url = data.get("Url")
                    session_id = data.get("SessionID", "")

                    # Log transaksi
                    self._log_transaction(order_id, email, package_name, actual_price, "created_success", data)

                    print(f"✅ PRODUCTION Transaction created: {order_id}")
                    print(f"🔗 Payment URL: {payment_url}")

                    return {
                        "status": "success",
                        "redirect_url": payment_url,
                        "token": session_id,
                        "order_id": order_id,
                        "amount": actual_price,
                        "package": package_name
                    }
                else:
                    error_msg = result.get("Message", "Unknown iPaymu error")
                    self._log_transaction(order_id, email, package_name, actual_price, f"error_status_{result.get('Status')}", result)
                    
                    return {
                        "status": "error",
                        "message": f"iPaymu Production Error: {error_msg}",
                        "detail": result
                    }
            else:
                self._log_transaction(order_id, email, package_name, actual_price, f"http_error_{response.status_code}", {"response": response.text})
                
                return {
                    "status": "error",
                    "message": f"HTTP Error {response.status_code} dari iPaymu Production",
                    "detail": response.text
                }

        except requests.exceptions.Timeout:
            self._log_transaction(order_id, email, package_name, actual_price, "timeout_error", {"timeout": 30})
            return {"status": "error", "message": "Koneksi ke iPaymu Production timeout"}
            
        except Exception as e:
            self._log_transaction(order_id, email, package_name, actual_price, "exception_error", {"error": str(e)})
            return {"status": "error", "message": f"Error: {str(e)}"}
    
    def process_callback(self, callback_data):
        """Process callback dari iPaymu PRODUCTION - ENHANCED VERSION."""
        try:
            print(f"📨 [PRODUCTION] Processing iPaymu callback: {callback_data}")
            
            # Enhanced callback data parsing
            status_code = callback_data.get("status_code") or callback_data.get("Status")
            status_desc = callback_data.get("status", "").lower()
            order_id = (callback_data.get("reference_id") or 
                       callback_data.get("referenceId") or
                       callback_data.get("trx_id") or
                       callback_data.get("transaction_id"))
            
            # Get amount dari callback
            amount = callback_data.get("amount") or callback_data.get("total")
            
            print(f"🔍 [DEBUG] Status Code: {status_code}")
            print(f"🔍 [DEBUG] Status Desc: {status_desc}")
            print(f"🔍 [DEBUG] Order ID: {order_id}")
            print(f"🔍 [DEBUG] Amount: {amount}")
            
            if not order_id:
                self._log_transaction("", "", "", 0, "callback_no_order_id", callback_data)
                return {"success": False, "message": "Order ID tidak ditemukan dalam callback"}

            # Enhanced success detection untuk production
            is_success = (
                str(status_code) == "000" or 
                str(status_code) == "200" or 
                status_desc in ["berhasil", "success", "paid", "settlement", "completed", "capture"] or
                callback_data.get("transaction_status") == "capture"
            )

            print(f"🔍 [DEBUG] Payment Success: {is_success}")

            if not is_success:
                self._log_transaction(order_id, "", "", 0, f"callback_failed_{status_desc}_{status_code}", callback_data)
                return {"success": False, "message": f"Payment failed: {status_desc} (Code: {status_code})"}

            # Parse order ID: SM_username_package_timestamp
            parts = order_id.split('_')
            if len(parts) < 4:
                self._log_transaction(order_id, "", "", 0, "callback_invalid_format", callback_data)
                return {"success": False, "message": f"Invalid order ID format: {order_id}"}

            username = parts[1]
            package_name = parts[2]
            
            # Enhanced email reconstruction - coba beberapa domain
            possible_emails = [
                f"{username}@gmail.com",
                f"{username}@yahoo.com", 
                f"{username}@email.com",
                callback_data.get("buyer_email", ""),
                callback_data.get("email", "")
            ]
            
            email = None
            for possible_email in possible_emails:
                if possible_email and "@" in possible_email:
                    email = possible_email
                    break
            
            if not email:
                email = f"{username}@gmail.com"  # Fallback
            
            self._log_transaction(order_id, email, package_name, amount or 0, "callback_success", callback_data)
            
            print(f"✅ [PRODUCTION] Payment successful: {order_id} - {email} - {package_name}")
            
            return {
                "success": True,
                "email": email,
                "package": package_name,
                "order_id": order_id,
                "amount": amount,
                "message": "Payment berhasil diproses di PRODUCTION"
            }
            
        except Exception as e:
            print(f"❌ [PRODUCTION] Error processing callback: {e}")
            self._log_transaction("", "", "", 0, f"callback_exception_{str(e)}", callback_data)
            return {"success": False, "message": f"Callback processing error: {str(e)}"}

    def _log_transaction(self, order_id, email, package_name, amount, status, details=None):
        """Log transaksi ke file."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "ipaymu_transactions.jsonl"
        
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "order_id": order_id,
            "email": email,
            "package": package_name,
            "amount": amount,
            "status": status,
            "details": details or {}
        }
        
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Error logging transaction: {e}")

    def get_package_info(self, package_name):
        """Get informasi paket."""
        return self.packages.get(package_name, {})
    
    def list_packages(self):
        """List semua paket yang tersedia."""
        return self.packages