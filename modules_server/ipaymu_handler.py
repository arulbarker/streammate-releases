# modules_server/ipaymu_handler.py
import os
import json
import time
import requests
import hashlib
import hmac
# Removed base64 as it's not used
from datetime import datetime, timezone # Ensure timezone is imported
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class IPaymuHandler:
    def __init__(self, sandbox=False):
        self.sandbox = sandbox
        if self.sandbox:
            self.base_url = "https://sandbox.ipaymu.com"
            # PERBAIKAN: Gunakan kredensial sandbox yang benar
            self.va = os.getenv("IPAYMU_SANDBOX_VA", "0000009516425913")
            self.api_key = os.getenv("IPAYMU_SANDBOX_API_KEY", "SANDBOXE1498BCD-9D73-4607-A2EB-FA78939BBC45")
            print(f"🧪 iPaymu SANDBOX mode - VA: {self.va}, API Key: {self.api_key[:20]}...")
        else:
            self.base_url = "https://my.ipaymu.com"
            # Production credentials
            self.va = os.getenv("IPAYMU_VA", "1179005157914468")
            self.api_key = os.getenv("IPAYMU_API_KEY", "C3CF720D-8347-4EA3-8DC9-BAC2DEF046AC")
            print(f"🚀 iPaymu PRODUCTION mode - VA: {self.va}, API Key: {self.api_key[:20]}...")
        if not self.api_key:
            raise ValueError("IPAYMU_API_KEY environment variable is required")

        self.payment_url = f"{self.base_url}/api/v2/payment"
        self.transaction_url = f"{self.base_url}/api/v2/transaction"

        self._load_packages()
        self._test_connection() # Call after all members are initialized

    def _test_connection(self):
        """Test koneksi ke server iPaymu menggunakan endpoint balance (POST)."""
        # PERBAIKAN: Skip test connection untuk sandbox di development mode
        if self.sandbox and os.getenv("STREAMMATE_DEV", "").lower() == "true":
            print("⚠️ DEVELOPMENT MODE - Using sandbox without credential test")
            return True
            
        test_url = f"{self.base_url}/api/v2/balance"
        print("\n🔌 TESTING KONEKSI KE IPAYMU...")
        
        try:
            body_for_test = {"account": self.va}
            body_str_for_test = json.dumps(body_for_test, separators=(',', ':'))
            
            # Use the central signature generation method
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
            
            print(f"✅ Test Koneksi ke iPaymu Balance Endpoint ({test_url})")
            print(f"VA Used: {self.va}")
            print(f"API Key Used (first 10 chars): {self.api_key[:10]}...")
            print(f"Status Code: {response.status_code}")
            try:
                print(f"Response Body: {response.json()}")
            except requests.exceptions.JSONDecodeError:
                print(f"Response Body (Non-JSON): {response.text}")

            if response.status_code == 200 and response.json().get("Status") == 200:
                print("✅ KONEKSI DAN AUTENTIKASI KE IPAYMU BERHASIL (CEK SALDO SUKSES)")
            elif response.status_code == 401:
                print("❌ KONEKSI BERHASIL, TAPI AUTENTIKASI GAGAL (SIGNATURE/KEY SALAH) saat test balance.")
                print("   HARAP PERIKSA IPAYMU_VA DAN IPAYMU_API_KEY DI FILE .env ANDA.")
            else:
                print(f"⚠️ TEST KONEKSI MENGEMBALIKAN STATUS {response.status_code}. Periksa response body.")
        except requests.exceptions.RequestException as e:
            print(f"❌ GAGAL TERHUBUNG KE IPAYMU SAAT TEST ({type(e).__name__}): {e}")
        except Exception as e:
            print(f"⚠️ ERROR TIDAK DIKETAHUI SAAT TEST KONEKSI: {str(e)}")

    def _load_packages(self):
        """Load konfigurasi paket dari file."""
        try:
            package_path = Path("config/packages.json")
            if package_path.exists():
                self.packages = json.loads(package_path.read_text(encoding="utf-8"))
                # Ensure loaded packages also have the nested structure
                for pkg_name, pkg_data in self.packages.items():
                    if not isinstance(pkg_data, dict) or 'price' not in pkg_data:
                        print(f"⚠️ Peringatan: Paket '{pkg_name}' di packages.json tidak memiliki struktur {'price': ...}. Menggunakan default.")
                        # Fallback to a default structure or raise error
                        self.packages[pkg_name] = {"price": pkg_data if isinstance(pkg_data, int) else 0, "hours": 0} # Basic fallback
            else:
                # Default packages with nested structure
                self.packages = {
                    "basic": {"price": 100000, "hours": 100},
                    "pro": {"price": 250000, "hours": 200}
                }
        except Exception as e:
            print(f"Error loading packages.json: {e}. Using default packages.")
            # Fallback to default with nested structure
            self.packages = {
                "basic": {"price": 100000, "hours": 100},
                "pro": {"price": 250000, "hours": 200}
            }

    # Sesudah (perbaikan signature generation)
    def _generate_signature(self, payload_str, http_method="POST"):
        # URL lengkap sesuai dengan jenis request
        # Catatan: Pastikan self.base_url sudah mengarah ke base URL API iPaymu
        # dan endpoint /api/v2/payment adalah endpoint yang benar
        url = f"{self.base_url}/api/v2/payment"

        # Hash body
        body_hash = hashlib.sha256(payload_str.encode()).hexdigest()

        # String yang akan di-sign
        # Periksa dokumentasi iPaymu apakah URL (variabel 'url' di atas)
        # perlu dimasukkan ke dalam string_to_sign ini.
        # Versi terbaru iPaymu V2 tampaknya TIDAK menggunakan URL di string_to_sign
        # Hanya VA, body_hash, dan API Key.
        # String to sign seharusnya formatnya: VA:BodyHash:ApiKey
        # string_to_sign = f"{self.va}:{body_hash}:{self.api_key}" # Kemungkinan ini yang benar untuk V2

        # Jika dokumentasi Anda menunjukkan URL HARUS masuk (biasanya versi lama atau endpoint khusus):
        # string_to_sign = f"{http_method.upper()}:{self.va}:{url}:{body_hash}:{self.api_key}" # Contoh format jika URL masuk

        # Menggunakan format yang Anda berikan (tanpa URL):
        string_to_sign = f"{http_method.upper()}:{self.va}:{body_hash}:{self.api_key}"


        # Generate signature dengan HMAC-SHA256
        # Pastikan menggunakan API Key sebagai kunci HMAC
        signature = hmac.new(
            self.api_key.encode(),
            string_to_sign.encode(),
            hashlib.sha256
        ).hexdigest()

        print(f"DEBUG Signature Generation:")
        print(f"  - HTTP method: {http_method.upper()}")
        print(f"  - VA: {self.va}")
        print(f"  - Body hash: {body_hash}")
        print(f"  - String to sign: {string_to_sign}")
        print(f"  - Generated signature: {signature}")

        return signature
    
    def create_transaction(self, email, package_name):
        """
        Buat transaksi baru di iPaymu.

        Args:
            email: Email pengguna
            package_name: Jenis paket (basic/pro/pro_bonus)

        Returns:
            dict: Hasil pembuatan transaksi
        """
        # Validasi paket
        package_info = self.packages.get(package_name)
        if not package_info or 'price' not in package_info:
            return {"status": "error", "message": f"Paket '{package_name}' tidak valid atau detail harga tidak ditemukan."}

        # Ambil harga dan jumlah jam
        actual_price = package_info['price']
        hours = package_info.get('hours', 100)

        import time
        timestamp = int(time.time())  

        # Buat ID order (unik berdasarkan email, paket, dan waktu)
        timestamp_order = int(time.time())
        username = email.split('@')[0]
        order_id = f"{username}_{package_name}_{timestamp}"

        # URL untuk callback dan redirect
        # Jika ini berjalan di VPS dan diakses dari luar, base_url harus domain/IP publik
        # Jika ini hanya untuk internal server dan client aplikasi yang sama, localhost mungkin ok
        base_url = "http://localhost:5005"  # Gunakan URL lokal untuk testing

        # Sebaiknya gunakan os.getenv untuk URL ini juga agar mudah diganti di VPS
        # base_url = os.getenv("APP_BASE_URL", "http://localhost:5005")
        # return_url = os.getenv("IPAYMU_RETURN_URL", f"{base_url}/payment_completed?status=success&order_id={order_id}")
        # cancel_url = os.getenv("IPAYMU_CANCEL_URL", f"{base_url}/payment_completed?status=canceled&order_id={order_id}")
        # notify_url = os.getenv("IPAYMU_NOTIFY_URL", f"{base_url}/payment_callback")

        return_url = f"{base_url}/payment_completed?status=success&order_id={order_id}"
        cancel_url = f"{base_url}/payment_completed?status=canceled&order_id={order_id}"
        notify_url = f"{base_url}/payment_callback" # Notify URL ini yang dipanggil iPaymu ke server Anda

        # Sesuaikan dengan dokumentasi iPaymu terbaru (payload untuk create transaction V2)
        payload = {
            "product": [f"StreamMate AI {package_name.capitalize()} Package"],
            "qty": [1],
            "price": [actual_price],
            "description": [f"{hours} jam kredit StreamMate AI"],
            "returnUrl": return_url,
            "cancelUrl": cancel_url,
            "notifyUrl": notify_url, # Ini harus bisa diakses publik oleh iPaymu
            "referenceId": order_id,
            "buyerName": email.split('@')[0],
            "buyerEmail": email,
            "buyerPhone": "08123456789", # Pastikan format nomor telepon benar
            # Tambahkan paymentMethod sesuai dokumentasi
            "paymentMethod": "qris",  # Bisa diganti dengan metode lain jika diperlukan
            "paymentChannel": "qris"    # Bisa diganti dengan channel lain jika diperlukan
        }

        # Konversi payload ke JSON string
        # Penting: Gunakan separators=(',', ':') untuk memastikan tidak ada spasi
        # setelah koma atau titik dua di string JSON, ini sering diminta oleh API
        payload_str = json.dumps(payload, separators=(',', ':'))

        # Generate timestamp (format YYYYMMDDHHmmss)
        request_timestamp = datetime.now(timezone.utc)
        request_timestamp_str = request_timestamp.strftime('%Y%m%d%H%M%S')

        # Generate signature
        # Pastikan metode _generate_signature menggunakan string_to_sign yang benar
        # sesuai dokumentasi iPaymu V2 (biasanya VA:BodyHash:ApiKey)
        signature = self._generate_signature(payload_str, http_method="POST")

        # Siapkan headers
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'signature': signature,
            'va': self.va, # VA production iPaymu
            'timestamp': request_timestamp_str,
            # Jika ada header tambahan yang diminta dokumentasi iPaymu V2, tambahkan di sini
            # Misalnya: 'api-key': self.api_key # Tergantung dokumentasi
        }

        # URL Endpoint iPaymu Sandbox
        # self.payment_url harus sudah diatur ke URL sandbox yang benar, misal:
        # https://sandbox.ipaymu.com/api/v2/payment
        # Pastikan ini sudah dikonfigurasi dengan benar di tempat lain di kelas Anda
        # atau melalui variabel lingkungan/konfigurasi.

        # Log untuk debugging
        print(f"========== DEBUG IPAYMU REQUEST ==========")
        print(f"URL Tujuan: {self.payment_url}")
        print(f"VA: {self.va}")
        print(f"Headers: {headers}")
        print(f"Payload: {payload_str}") # Cetak string JSON yang dikirim
        print(f"=========================================")

        try:
            # Kirim request ke iPaymu
            # Gunakan 'data=payload_str' untuk mengirim string JSON yang sudah dibuat
            # Jika menggunakan 'json=payload', requests akan otomatis melakukan json.dumps
            # tapi mungkin tidak dengan separators=(',', ':') yang spesifik.
            # Jadi, lebih aman pakai data=payload_str jika API sensitif spasi.
            response = requests.post(self.payment_url, headers=headers, data=payload_str, timeout=30)

            # Log response untuk debugging
            print(f"========== DEBUG IPAYMU RESPONSE ==========")
            print(f"Status code: {response.status_code}")
            print(f"Response text: {response.text}") # Cetak response dalam bentuk teks
            try:
                print(f"Response JSON: {response.json()}") # Coba cetak juga dalam bentuk JSON jika valid
            except json.JSONDecodeError:
                print("Response is not valid JSON.")
            print(f"============================================")


            # Proses response berdasarkan status code
            if response.status_code == 200:
                try:
                    result = response.json()

                    # Cek status dari iPaymu (Status 200 dari body JSON menandakan berhasil)
                    if result.get("Status") == 200:
                        data = result.get("Data", {})
                        payment_url_ipaymu = data.get("Url") # Ini URL redirect ke halaman pembayaran iPaymu
                        session_id = data.get("SessionID", "")

                        # Log transaksi berhasil
                        self._log_transaction(order_id, email, package_name, actual_price, "created_ipaymu", data)

                        # Return success
                        return {
                            "status": "success",
                            "redirect_url": payment_url_ipaymu,
                            "token": session_id,
                            "order_id": order_id
                        }
                    else:
                        # Jika status dari iPaymu bukan 200 (biasanya ada di field 'Status' di body respon)
                        # Ini menandakan kesalahan validasi data permintaan oleh iPaymu
                        # Pesan error biasanya ada di field 'Message'
                        self._log_transaction(
                            order_id,
                            email,
                            package_name,
                            actual_price,
                            f"error_ipaymu_status_{result.get('Status')}",
                            result # Log seluruh body respon iPaymu
                        )

                        # Gunakan fallback ke simulasi jika mode sandbox aktif
                        # Ini membantu pengujian alur meskipun iPaymu menolak permintaan
                        if self.sandbox:
                            # Log fallback
                            print(f"⚠️ IPAYMU Status Error {result.get('Status')}. Fallback ke simulasi pembayaran lokal.")
                            self._log_transaction(
                                order_id,
                                email,
                                package_name,
                                actual_price,
                                "fallback_to_simulation_ipaymu_status_error",
                                {"ipaymu_error_status": result.get('Status'), "message": result.get('Message')}
                            )

                            # Return simulasi URL
                            return {
                                "status": "success", # Status ini menandakan bahwa *aplikasi lokal* berhasil membuat alur simulasi
                                "redirect_url": f"{base_url}/payment_simulation?order_id={order_id}", # URL ke handler simulasi lokal Anda
                                "token": f"sim_{timestamp_order}", # Token simulasi
                                "order_id": order_id,
                                "message": f"Menggunakan simulasi pembayaran lokal (iPaymu status error {result.get('Status')}: {result.get('Message', 'Unknown')})"
                            }


                        # Jika bukan mode sandbox, kembalikan error yang sebenarnya dari iPaymu
                        return {
                            "status": "error",
                            "message": result.get("Message", "Unknown iPaymu error"),
                            "detail": result
                        }
                except json.JSONDecodeError as json_error:
                    # Error parsing JSON dari respon iPaymu (respon tidak valid JSON)
                    print(f"❌ ERROR PARSING JSON DARI IPAYMU: {json_error}")
                    self._log_transaction(
                        order_id,
                        email,
                        package_name,
                        actual_price,
                        "error_parsing_json",
                        {"error": str(json_error), "response_text": response.text, "status_code": response.status_code}
                    )

                    # Fallback ke simulasi jika mode sandbox aktif
                    if self.sandbox:
                        print(f"⚠️ JSON Parse Error. Fallback ke simulasi pembayaran lokal.")
                        self._log_transaction(
                            order_id,
                            email,
                            package_name,
                            actual_price,
                            "fallback_to_simulation_json_error",
                             {"error": str(json_error), "response_text": response.text}
                        )
                        return {
                            "status": "success", # Status ini menandakan bahwa *aplikasi lokal* berhasil membuat alur simulasi
                            "redirect_url": f"{base_url}/payment_simulation?order_id={order_id}",
                            "token": f"sim_json_error_{timestamp_order}",
                            "order_id": order_id,
                            "message": "Menggunakan simulasi pembayaran lokal (Error parsing response iPaymu)"
                        }

                    # Jika bukan mode sandbox, kembalikan error parsing
                    return {"status": "error", "message": "Error parsing iPaymu response", "detail": response.text}

            else:
                # Jika status code bukan 200 (misal: 400 Bad Request, 401 Unauthorized, 500 Internal Server Error, dll)
                error_msg = f"HTTP Error dari iPaymu: {response.status_code}"
                detail = None

                try:
                    # Coba parse body respon sebagai JSON (terkadang iPaymu mengirim error detail dalam JSON)
                    detail = response.json()
                    if isinstance(detail, dict) and "Message" in detail:
                         error_msg += f" - {detail['Message']}" # Tambahkan pesan dari body JSON jika ada
                except json.JSONDecodeError:
                    # Jika body respon bukan JSON, gunakan teksnya
                    detail = response.text

                # Log error HTTP
                print(f"❌ ERROR HTTP DARI IPAYMU: {response.status_code} - {error_msg}")
                self._log_transaction(
                    order_id,
                    email,
                    package_name,
                    actual_price,
                    f"error_http_{response.status_code}",
                    {"status_code": response.status_code, "detail": detail}
                )

                # Fallback ke simulasi jika mode sandbox aktif
                if self.sandbox:
                    print(f"⚠️ HTTP Error {response.status_code}. Fallback ke simulasi pembayaran lokal.")
                    self._log_transaction(
                        order_id,
                        email,
                        package_name,
                        actual_price,
                        "fallback_to_simulation_http_error",
                        {"status_code": response.status_code, "detail": detail}
                    )
                    return {
                        "status": "success", # Status ini menandakan bahwa *aplikasi lokal* berhasil membuat alur simulasi
                        "redirect_url": f"{base_url}/payment_simulation?order_id={order_id}",
                        "token": f"sim_http{response.status_code}_{timestamp_order}",
                        "order_id": order_id,
                        "message": f"Menggunakan simulasi pembayaran lokal (HTTP Error {response.status_code})"
                    }

                # Jika bukan mode sandbox, kembalikan error HTTP
                return {"status": "error", "message": error_msg, "detail": detail}


        except requests.exceptions.Timeout:
            # Menangani error timeout saat request ke iPaymu
            print(f"⚠️ TIMEOUT KONEKSI KE IPAYMU ({self.payment_url})")
            self._log_transaction(order_id, email, package_name, actual_price, "error_timeout")

            # Fallback ke simulasi jika mode sandbox aktif
            if self.sandbox:
                print(f"⚠️ Timeout. Fallback ke simulasi pembayaran lokal.")
                self._log_transaction(
                    order_id,
                    email,
                    package_name,
                    actual_price,
                    "fallback_to_simulation_timeout",
                     {"url": self.payment_url, "timeout": 30}
                )
                return {
                    "status": "success", # Status ini menandakan bahwa *aplikasi lokal* berhasil membuat alur simulasi
                    "redirect_url": f"{base_url}/payment_simulation?order_id={order_id}",
                    "token": f"sim_timeout_{timestamp_order}",
                    "order_id": order_id,
                    "message": "Menggunakan simulasi pembayaran lokal (iPaymu timeout)"
                }

            # Jika bukan mode sandbox, kembalikan error timeout
            return {"status": "error", "message": "Request to iPaymu timed out."}

        except requests.exceptions.RequestException as e:
            # Menangani error koneksi lainnya (misal: DNS error, connection refused, dll.)
            print(f"⚠️ ERROR KONEKSI KE IPAYMU: {type(e).__name__} - {str(e)}")
            self._log_transaction(order_id, email, package_name, actual_price, "error_connection", {"error_type": type(e).__name__, "error_message": str(e)})

            # Fallback ke simulasi jika mode sandbox aktif
            if self.sandbox:
                print(f"⚠️ Koneksi Error. Fallback ke simulasi pembayaran lokal.")
                self._log_transaction(
                    order_id,
                    email,
                    package_name,
                    actual_price,
                    "fallback_to_simulation_connection_error",
                     {"error_type": type(e).__name__, "error_message": str(e)}
                )
                return {
                    "status": "success", # Status ini menandakan bahwa *aplikasi lokal* berhasil membuat alur simulasi
                    "redirect_url": f"{base_url}/payment_simulation?order_id={order_id}",
                    "token": f"sim_conn_error_{timestamp_order}",
                    "order_id": order_id,
                    "message": f"Menggunakan simulasi pembayaran lokal (koneksi error: {type(e).__name__})"
                }

            # Jika bukan mode sandbox, kembalikan error koneksi
            return {"status": "error", "message": f"Connection error: {str(e)}"}

        except Exception as e:
            # Menangani error tak terduga lainnya dalam fungsi ini
            print(f"❌ ERROR TIDAK TERDUGA DALAM create_transaction: {type(e).__name__} - {str(e)}")
            self._log_transaction(order_id, email, package_name, actual_price, "error_unexpected_in_create", {"error_type": type(e).__name__, "error_message": str(e)})

            # Fallback ke simulasi jika mode sandbox aktif
            if self.sandbox:
                 print(f"⚠️ Error Tak Terduga. Fallback ke simulasi pembayaran lokal.")
                 self._log_transaction(
                    order_id,
                    email,
                    package_name,
                    actual_price,
                    "fallback_to_simulation_unexpected_error",
                     {"error_type": type(e).__name__, "error_message": str(e)}
                 )
                 return {
                    "status": "success", # Status ini menandakan bahwa *aplikasi lokal* berhasil membuat alur simulasi
                    "redirect_url": f"{base_url}/payment_simulation?order_id={order_id}",
                    "token": f"sim_error_{timestamp_order}",
                    "order_id": order_id,
                    "message": f"Menggunakan simulasi pembayaran lokal (error tidak terduga: {type(e).__name__})"
                }

            # Jika bukan mode sandbox, kembalikan error tak terduga
            return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}
   
    def process_callback(self, callback_data):
        # print(f"Received iPaymu callback data: {callback_data}")
        try:
            status_code = callback_data.get("status_code")
            status_desc = callback_data.get("status", callback_data.get("status_description", "")).lower()
            order_id = callback_data.get("reference_id", callback_data.get("referenceId"))
            
            if not order_id: # Fallback for local simulation order_id
                order_id = callback_data.get("order_id")

            if not order_id:
                self._log_transaction("UNKNOWN_ORDER", "", "", 0, "callback_failed_no_order_id", callback_data)
                return {"success": False, "message": "Order ID (reference_id) tidak ditemukan dalam callback"}

            is_success = (str(status_code) == "000" or status_desc in ["berhasil", "success", "paid", "settlement"])

            if not is_success:
                self._log_transaction(order_id, "", "", 0, f"callback_failed_status_{status_desc}_{status_code}", callback_data)
                return {"success": False, "message": f"Status transaksi tidak berhasil: {status_desc} (Code: {status_code})"}

            # PERBAIKAN: Penanganan order_id yang tepat
            parts = order_id.split('_')
            if len(parts) < 3: # email_package_timestamp
                self._log_transaction(order_id, "", "", 0, "callback_invalid_order_id_format", callback_data)
                return {"success": False, "message": "Format Order ID tidak valid dalam callback"}

            # PERBAIKAN: Cek jika ada '@' dalam order_id
            if '@' in order_id or '_gmail.com_' in order_id or '_yahoo.com_' in order_id:
                # Format: username_domain.com_package_timestamp
                if len(parts) >= 4:
                    email_raw = parts[0]
                    domain = parts[1]
                    package_name = parts[2]
                    email = f"{email_raw}@{domain}"
                else:
                    return {"success": False, "message": "Format Order ID tidak valid (domain email terdeteksi)"}
            else:
                # Format lama: username_package_timestamp
                email_raw = parts[0]
                package_name = parts[1]
                email = email_raw.replace('_', '@')

            self._log_transaction(order_id, email, package_name, 0, "callback_success_ipaymu", callback_data)
            return {
                "success": True,
                "email": email,
                "package": package_name, # Renamed from 'package' to 'package_name' for clarity
                "order_id": order_id,
                "message": "Callback pembayaran berhasil diproses"
            }
        except Exception as e:
            print(f"Error processing iPaymu callback: {e}")
            self._log_transaction(callback_data.get("reference_id", "UNKNOWN_CALLBACK_ORDER"), "", "", 0, "callback_exception", {"error": str(e), "data": callback_data})
            return {"success": False, "message": f"Internal error processing callback: {str(e)}"}

    def _log_transaction(self, order_id, email, package_name, amount, status, details=None):
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
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"Error logging iPaymu transaction: {e}")