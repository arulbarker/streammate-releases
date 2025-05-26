# payment_server.py
from flask import Flask, request, jsonify, render_template_string, redirect
from pathlib import Path
from datetime import datetime, timedelta, timezone
import json
import os
import time
import socket
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config['TEMPLATES_AUTO_RELOAD'] = True

# TAMBAHKAN KODE INI DI SINI (setelah baris import, sebelum definisi PACKAGES)
# ========================================
# Import debug manager
try:
    from modules_client.credit_debug_manager import CreditDebugManager
    DEBUG_MANAGER = CreditDebugManager()
    CREDIT_DEBUG_ENABLED = True
    print("[DEBUG] Credit Debug Manager loaded successfully in payment_server")
except ImportError as e:
    DEBUG_MANAGER = None
    CREDIT_DEBUG_ENABLED = False
    print(f"[DEBUG] Credit Debug Manager not available in payment_server: {e}")
# ========================================

# Define packages with consistent structure: price and hours
PACKAGES = {
    "basic": {"hours": 100, "price": 100000},
    "pro": {"hours": 200, "price": 250000},
    "pro_bonus": {"hours": 200, "price": 180000}  # Special package with bonus
}

try:
    from modules_server.ipaymu_handler import IPaymuHandler
    
    # PERBAIKAN: Auto-detect development mode
    is_development = (
        os.getenv("STREAMMATE_DEV", "").lower() == "true" or
        os.path.exists("config/dev_users.json") or
        "localhost" in os.getenv("FLASK_RUN_HOST", "localhost")
    )

    # PERBAIKAN: Sandbox mode - paksa aktif untuk development
    if is_development:
        ipaymu_sandbox_mode = True
        print("🧪 DEVELOPMENT MODE - Forcing iPaymu Sandbox")
    else:
        ipaymu_sandbox_mode = os.getenv("IPAYMU_SANDBOX_MODE", "false").lower() == "true"
        print("🚀 PRODUCTION MODE - Using iPaymu Production")

    print(f"📊 Mode Summary: Development={is_development}, Sandbox={ipaymu_sandbox_mode}")
    
    if is_development:
        print("🧪 Development mode detected - Using iPaymu Sandbox")
    else:
        print("🚀 Production mode - Using iPaymu Production")
    
    ipaymu = IPaymuHandler(sandbox=ipaymu_sandbox_mode)
except ImportError as e:
    print(f"ALERT: Failed to import IPaymuHandler: {e}. Using DummyIPaymuHandler.")
    class DummyIPaymuHandler:
        def __init__(self, sandbox=False):
            self.sandbox = sandbox
            print(f"DummyIPaymuHandler initialized (sandbox: {self.sandbox})")

        def create_transaction(self, email, package_name):
            order_id_time = int(time.time())
            if package_name not in PACKAGES:
                return {"status": "error", "message": f"Dummy: Package {package_name} not found"}
            order_id = f"{email.replace('@', '_')}_{package_name}_{order_id_time}"
            return {
                "status": "success",
                "redirect_url": f"http://localhost:5005/payment_simulation?order_id={order_id}",
                "order_id": order_id
            }
            
        def process_callback(self, data):
            order_id = data.get("order_id", data.get("reference_id", ""))
            if not order_id: 
                return {"success": False, "message": "Dummy: Order ID invalid"}
            
            parts = order_id.split('_')
            if len(parts) >= 3:  # email_package_timestamp
                return {
                    "success": True, 
                    "email": parts[0].replace('_', '@'), 
                    "package": parts[1], 
                    "order_id": order_id
                }
            return {"success": False, "message": "Dummy: Order ID format invalid"}
            
    ipaymu = DummyIPaymuHandler(sandbox=False)  # Default to production for dummy

@app.route("/create_transaction", methods=["POST"])
def create_transaction_route():
    try:
        data = request.json
        email = data.get("email")
        package_name = data.get("package")

        if not email or not package_name:
            return jsonify({"status": "error", "message": "Email dan nama paket diperlukan"}), 400

        if package_name not in PACKAGES:
            return jsonify({"status": "error", "message": f"Paket tidak valid: {package_name}"}), 400

        # Try using iPaymu first
        try:
            response_ipaymu = ipaymu.create_transaction(email, package_name)
            
            # If successful from iPaymu, use that
            if response_ipaymu.get("status") == "success" and response_ipaymu.get("order_id"):
                filepath = Path("config/subscription_status.json")
                status_data = {
                    "email": email,
                    "package": package_name,
                    "status": "pending",
                    "hours_credit": 0,
                    "hours_used": 0,
                    "start_date": datetime.now(timezone.utc).isoformat(),
                    "expire_date": None,
                    "order_id": response_ipaymu.get("order_id"),
                    "transaction_id_gateway": response_ipaymu.get("token", ""),
                    "transaction_status": "pending_gateway",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "gateway": "ipaymu_sandbox" if ipaymu.sandbox else "ipaymu_production"
                }
                filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(status_data, f, indent=2)
                
                return jsonify(response_ipaymu)
            
            # Add return here if iPaymu response is invalid
            return jsonify({"status": "error", "message": "Respon iPaymu tidak valid"}), 400
            
        except Exception as e:
            print(f"iPaymu processing failed, falling back to simulation: {e}")
            # Fallback to local simulation if iPaymu fails
            timestamp = int(time.time())
            order_id = f"{email.replace('@', '_')}_{package_name}_{timestamp}"
            
            # Save transaction status
            filepath = Path("config/subscription_status.json")
            status_data = {
                "email": email,
                "package": package_name,
                "status": "pending",
                "hours_credit": 0,
                "hours_used": 0,
                "start_date": datetime.now(timezone.utc).isoformat(),
                "expire_date": None,
                "order_id": order_id,
                "transaction_id_gateway": f"sim_{timestamp}",
                "transaction_status": "pending_simulation",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "gateway": "simulation"
            }
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(status_data, f, indent=2)
            
            # Return simulation URL
            return jsonify({
                "status": "success",
                "redirect_url": f"http://localhost:5005/payment_simulation?order_id={order_id}",
                "order_id": order_id,
                "message": "Menggunakan simulasi pembayaran lokal"
            })

    except Exception as e:
        error_msg = str(e)
        print(f"Error in /create_transaction route: {error_msg}")
        return jsonify({
            "status": "error",
            "message": "Terjadi kesalahan internal server saat membuat transaksi.",
            "detail": error_msg
        }), 500

@app.route('/payment_simulation', methods=['GET'])
def payment_simulation():
    order_id = request.args.get('order_id', '')
    filepath = Path("config/subscription_status.json")
    if filepath.exists() and order_id:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("order_id") == order_id:
                package_name = data.get("package", "basic")
                hours = PACKAGES.get(package_name, {}).get("hours", 0)
                amount = PACKAGES.get(package_name, {}).get("price", 0)
                return render_template_string(SIMULATION_TEMPLATE,
                                            order_id=order_id,
                                            email=data.get("email", ""),
                                            package=package_name,
                                            amount=amount,
                                            hours=hours)
        except Exception as e: 
            return f"Error loading simulation data: {str(e)}"
    return "Transaksi simulasi tidak ditemukan atau file status tidak ada.", 404

@app.route('/payment_success', methods=['POST'])
def payment_success_simulation():
    order_id = request.form.get('order_id', '')
    email = request.form.get('email', '')
    package_name = request.form.get('package', '')
    filepath = Path("config/subscription_status.json")

    if not order_id: 
        print(f"Order ID tidak ada dari form simulasi. Form data: {request.form}")
        return "Order ID tidak ada dari form simulasi.", 400
    
    if not filepath.exists(): 
        filepath.parent.mkdir(parents=True, exist_ok=True)
        # If file doesn't exist, create new with form data
        if email and package_name:
            data = {
                "email": email,
                "package": package_name,
                "status": "pending",
                "hours_credit": 0,
                "hours_used": 0,
                "order_id": order_id,
                "transaction_status": "pending_simulation",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        else:
            return "File status transaksi tidak ditemukan dan data form tidak lengkap.", 404

    try:
        with open(filepath, "r+", encoding="utf-8") as f:
            data = json.load(f)
            file_order_id = data.get("order_id")
            
            if file_order_id == order_id:
                # Order ID matches, normal process
                package_name = data.get("package")
            elif email and package_name:
                # Order ID doesn't match, but form data is complete
                # Update data with form data
                print(f"Order ID mismatch. File: {file_order_id}, Form: {order_id}. Using form data.")
                data["email"] = email
                data["package"] = package_name
                data["order_id"] = order_id
            else:
                return "Order ID tidak cocok dan data form tidak lengkap.", 400

            if package_name not in PACKAGES:
                return f"Paket '{package_name}' tidak dikenal dalam sistem.", 400

            # Update data
            now = datetime.now(timezone.utc)
            expire_date = now + timedelta(days=30)
            
            data["status"] = "paid"
            data["transaction_status"] = "settlement_simulation"
            data["hours_credit"] = PACKAGES[package_name]["hours"]
            data["start_date"] = now.isoformat()
            data["expire_date"] = expire_date.isoformat()
            data["updated_at"] = now.isoformat()

            # Write back to file
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()

            # Log transaction
            _log_transaction_server(
                order_id, 
                data.get("email", email), 
                package_name, 
                "success_simulation_completed",
                PACKAGES[package_name]["price"]
            )
            
            return redirect(f'/payment_completed?status=success&order_id={order_id}')
    except Exception as e:
        _log_transaction_server(
            order_id, 
            email or "unknown", 
            package_name or "unknown", 
            f"error_simulation_success_update: {str(e)}", 
            0
        )
        return f"Error updating transaction for simulation: {str(e)}", 500

@app.route('/payment_callback', methods=['POST'])
def payment_callback_ipaymu():
    """Handler for callback from iPaymu."""
    try:
        # Get data from body
        if request.is_json:
            data = request.json
        else:
            # If not JSON, get from form data
            data = request.form.to_dict()
            
            # If still empty, try reading from raw data
            if not data:
                data_str = request.get_data(as_text=True)
                try:
                    data = json.loads(data_str)
                except:
                    data = {}
        
        # Log callback data for debugging
        print(f"========== IPAYMU CALLBACK DATA ==========")
        print(f"Headers: {dict(request.headers)}")
        print(f"Data: {data}")
        print(f"==========================================")
        
        # Extract important information
        reference_id = data.get("reference_id", data.get("referenceId"))
        status = data.get("status", "").lower()
        status_code = data.get("status_code", data.get("statusCode"))
        trx_id = data.get("trx_id", data.get("trxId"))
        
        if not reference_id:
            print("Callback missing reference_id")
            return jsonify({"status": "error", "message": "Reference ID not found"}), 400
        
        # Validate payment status
        is_success = ((status in ["berhasil", "success", "paid", "settlement"]) and 
                      (str(status_code) in ["1", "000"]))
        
        if not is_success:
            print(f"Payment status not success: {status}, code: {status_code}")
            return jsonify({"status": "success", "message": "Notification received but status not success"}), 200
        
        # Update subscription status directly from here
        success = update_subscription_status(reference_id, "success", trx_id)
        
        # Log update subscription result
        print(f"Subscription update from callback result: {success}")
        
        if success:
            return jsonify({
                "status": "success", 
                "message": "Subscription updated successfully",
                "order_id": reference_id,
                "transaction_id": trx_id
            }), 200
        else:
            # Log detailed failure
            print(f"Failed to update subscription for order_id: {reference_id}")
            return jsonify({"status": "error", "message": "Failed to update subscription"}), 500
            
    except Exception as e:
        print(f"Error in payment callback: {str(e)}")
        # Log stack trace for more detailed debugging
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error processing callback: {str(e)}"}), 500

@app.route("/payment_completed", methods=["GET"])
def payment_completed_page():
    """
    Page after payment is complete, either successful or canceled.
    Also updates subscription status if successful.
    """
    status = request.args.get("status", "")
    order_id = request.args.get("order_id", "")
    trx_id = request.args.get("trx_id", "")
    
    # Log for debugging
    print(f"Payment completed page accessed: status={status}, order_id={order_id}, trx_id={trx_id}")
    
    transaction_details = {
        "order_id": order_id, 
        "gateway_status": status, 
        "email": "N/A", 
        "package_name": "N/A", 
        "hours": "N/A", 
        "price": 0, 
        "current_status_from_file": "N/A"
    }
    
    # Try to update subscription status if payment is successful
    if status == "success" and order_id:
        try:
            # Call update_subscription_status with trx_id
            update_result = update_subscription_status(order_id, "success", trx_id)
            
            # Get transaction details from subscription file
            filepath = Path("config/subscription_status.json")
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    subscription_data = json.load(f)
                    email = subscription_data.get("email", "N/A")
                    package = subscription_data.get("package", "N/A")
                    hours = subscription_data.get("hours_credit", 0)
                    
                    # Update transaction details
                    transaction_details.update({
                        "email": email,
                        "package_name": package,
                        "hours": hours,
                        "current_status_from_file": subscription_data.get("status", "N/A")
                    })
                    
                    # Find package information
                    if package in PACKAGES:
                        transaction_details["price"] = PACKAGES[package]["price"]
                    
            # Render success page
            return render_template_string(
                SUCCESS_TEMPLATE,
                order_id=order_id,
                email=transaction_details["email"],
                package_name=transaction_details["package_name"],
                hours=transaction_details["hours"],
                price=transaction_details["price"],
                gateway_status=status,
                current_status_from_file=transaction_details["current_status_from_file"]
            )
        except Exception as e:
            print(f"Error in payment_completed_page (success): {e}")
            # Fallback to simple rendering if error
            return f"""
            <html>
                <head><title>Pembayaran Diproses</title></head>
                <body>
                    <h1>Pembayaran Berhasil Diproses</h1>
                    <p>Order ID: {order_id}</p>
                    <p>Error processing details: {str(e)}</p>
                    <a href="#">Tutup Halaman</a>
                </body>
            </html>
            """
    
    elif status == "canceled":
        # If payment is canceled
        return render_template_string(
            CANCELED_TEMPLATE,
            order_id=order_id
        )
    
    else:
        # Other status or unknown
        return f"""
        <html>
            <head><title>Status Pembayaran</title></head>
            <body>
                <h1>Status Pembayaran: {status}</h1>
                <p>Order ID: {order_id}</p>
                <a href="#">Tutup Halaman</a>
            </body>
        </html>
        """

def _log_transaction_server(order_id, email, package_name, status, amount, details=None):
    """Log transaction to file for auditing purposes."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "payment_server_transactions.jsonl"
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "order_id": order_id,
        "email": email,
        "package": package_name,
        "status": status,
        "amount": amount,
        "details": details or {},
        "source": "payment_server"
    }
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"Error logging payment_server transaction: {e}")

def check_ipaymu_status():
    """Check connection status to iPaymu and validate credentials."""
    try:
        from modules_server.ipaymu_handler import IPaymuHandler
        # Create instance for test
        handler = IPaymuHandler(sandbox=os.getenv("IPAYMU_SANDBOX_MODE", "false").lower() == "true")
        # Try to call test_connection
        return handler._test_connection()
    except Exception as e:
        print(f"Error checking iPaymu status: {e}")
        return False

def check_server_running(port=5005):
    """Check if payment server is already running."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', port))
    sock.close()
    return result == 0

# Temukan fungsi update_subscription_status() di payment_server.py 
# dan ubah bagian berikut (sekitar baris 490-560)

def update_subscription_status(order_id, payment_status="success", transaction_id=None):
    try:
        # Parse order_id to get email and package
        parts = order_id.split('_')
        if len(parts) < 3:
            print(f"Invalid order_id format: {order_id}")
            return False
        
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

        # Find package information
        if package_name in PACKAGES:
            hours = PACKAGES[package_name]["hours"]
            price = PACKAGES[package_name]["price"]
        else:
            # Fallback if package not found
            print(f"Warning: Package {package_name} not found in PACKAGES, using defaults")
            hours = 100 if package_name == "basic" else 200
            price = 100000 if package_name == "basic" else 250000
        
        # TAMBAHAN: Debug logging sebelum update
        if CREDIT_DEBUG_ENABLED and DEBUG_MANAGER:
            payment_data = {
                "order_id": order_id,
                "payment_status": payment_status,
                "transaction_id": transaction_id,
                "package_name": package_name,
                "hours": hours,
                "price": price
            }
            DEBUG_MANAGER.log_payment_completion(payment_data)
            print(f"[PAYMENT_DEBUG] Payment completion logged: {order_id}")

        # Update subscription status file
        filepath = Path("config/subscription_status.json")
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Read file if exists
        status_data = {}
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    status_data = json.load(f)
            except Exception as e:
                print(f"Error reading subscription file: {e}")
        
        # PERBAIKAN: Set time format (hanya gunakan satu format konsisten - timezone naive)
        # Gunakan timezone naive (tanpa timezone info) untuk semua tanggal
        # Ini membantu menghindari masalah perbandingan timezone
        now = datetime.now()
        expire_date = now + timedelta(days=30)
        
        # Format ISO konsisten tanpa timezone info
        now_str = now.isoformat()
        expire_str = expire_date.isoformat()
        
        # Update status
        status = "paid" if payment_status.lower() in ["success", "berhasil"] else "pending"
        
        # PERBAIKAN UTAMA: Tambahkan kredit yang sudah ada jika status pembayaran sukses
        current_hours = 0
        if status == "paid" and status_data.get("status") == "paid":
            try:
                current_hours = float(status_data.get("hours_credit", 0))
                print(f"[DEBUG] Kredit saat ini: {current_hours}, menambahkan {hours} jam baru")
            except (ValueError, TypeError):
                current_hours = 0
                print(f"[DEBUG] Error membaca kredit saat ini, menggunakan 0")
        
        # Total jam = jam yang sudah ada + jam baru
        total_hours = current_hours + (hours if status == "paid" else 0)
        
        # Update data
        status_data.update({
            "email": email,
            "package": package_name,
            "status": status,
            "hours_credit": total_hours,  # PERBAIKAN: Gunakan total jam
            "hours_used": status_data.get("hours_used", 0),
            "start_date": now_str,
            "expire_date": expire_str,
            "order_id": order_id,
            "transaction_id_gateway": transaction_id or status_data.get("transaction_id_gateway", ""),
            "transaction_status": "success" if status == "paid" else payment_status,
            "updated_at": now_str,
            "gateway": status_data.get("gateway", "ipaymu_sandbox")
        })
        
        # PERBAIKAN: Tambahkan logging untuk debug
        print(f"[DEBUG] Updating subscription: {email}, {package_name}")
        print(f"[DEBUG] Hours credit: {total_hours if status == 'paid' else 0}")
        print(f"[DEBUG] Status: {status}")
        print(f"[DEBUG] Transaction status: {'success' if status == 'paid' else payment_status}")
        
        # PERBAIKAN: Pastikan semua nilai angka disimpan sebagai angka, bukan string
        try:
            status_data["hours_credit"] = float(status_data["hours_credit"])
            status_data["hours_used"] = float(status_data["hours_used"])
        except (ValueError, TypeError):
            pass
        
        # Save data
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2)

        # TAMBAHAN: Debug logging SETELAH update berhasil
        # ===============================================
        if CREDIT_DEBUG_ENABLED and DEBUG_MANAGER:
            DEBUG_MANAGER._log_debug("payment_update_complete", {
                "order_id": order_id,
                "email": email,
                "package_name": package_name,
                "hours_added": hours,
                "total_hours_credit": total_hours,
                "previous_hours": current_hours,
                "status": status,
                "update_successful": True,
                "timestamp": now_str,
                "file_path": str(filepath)
            })
            print(f"[PAYMENT_DEBUG] Credit update completed: {email} - {total_hours}h total")
        # ===============================================
        
        print(f"Subscription updated: {email}, {package_name}, status={status}, hours={total_hours}")
        return True
    
    except Exception as e:
        print(f"Error updating subscription status: {e}")

        # TAMBAHAN: Debug logging untuk error
        # ==================================
        if CREDIT_DEBUG_ENABLED and DEBUG_MANAGER:
            DEBUG_MANAGER._log_debug("payment_update_error", {
                "order_id": order_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            print(f"[PAYMENT_DEBUG] Payment update error logged: {e}")
        # ==================================

        # PERBAIKAN: Log stack trace untuk debugging
        import traceback
        traceback.print_exc()
        return False

# --- HTML Templates ---
SIMULATION_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>StreamMate AI - Simulasi Pembayaran</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }
        .container { border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin-top: 20px; }
        h1, h2 { color: #1877F2; text-align: center; }
        .header { text-align: center; margin-bottom: 30px; }
        .logo { font-size: 24px; font-weight: bold; color: #1877F2; }
        .info { background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .btn { display: block; width: 100%; padding: 10px; text-align: center; background-color: #1877F2; color: white; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; margin-top: 20px; text-decoration: none; box-sizing: border-box;}
        .btn-cancel { background-color: #f44336; }
        .row { display: flex; justify-content: space-between; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="header"> <div class="logo">StreamMate AI</div> <p>Simulasi Pembayaran (Development Mode)</p> </div>
    <div class="container">
        <h2>Detail Pesanan</h2>
        <div class="info">
            <div class="row"><div>Order ID:</div><div>{{ order_id }}</div></div>
            <div class="row"><div>Email:</div><div>{{ email }}</div></div>
            <div class="row"><div>Paket:</div><div>{{ package.upper() }}</div></div>
            <div class="row"><div>Jumlah Jam:</div><div>{{ hours }} jam</div></div>
            <div class="row"><div>Total Pembayaran:</div><div><strong>Rp {{ '{:,.0f}'.format(amount) }}</strong></div></div>
        </div>
        <h2>Metode Pembayaran</h2>
        <form action="/payment_success" method="post">
            <input type="hidden" name="order_id" value="{{ order_id }}">
            <input type="hidden" name="email" value="{{ email }}">
            <input type="hidden" name="package" value="{{ package }}">
            <input type="hidden" name="amount" value="{{ amount }}">
            <button type="submit" class="btn">Bayar Sekarang (Simulasi)</button>
        </form>
        <a href="/payment_completed?status=canceled&order_id={{ order_id }}" class="btn btn-cancel">Batal (Simulasi)</a>
        <p style="text-align: center; margin-top: 20px; color: #666;"> Ini adalah halaman simulasi. Tidak ada transaksi nyata. </p>
    </div>
</body>
</html>
"""

SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>StreamMate AI - Pembayaran Diproses</title>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; text-align: center; }
        .container { border: 1px solid #4CAF50; border-radius: 8px; padding: 20px; margin-top: 20px; background-color: #f1f8e9; }
        h1 { color: #4CAF50; }
        .logo { font-size: 24px; font-weight: bold; color: #1877F2; margin-bottom: 20px; }
        .info { margin: 30px 0; text-align: left; padding: 15px; border-radius: 5px; background-color: white; border: 1px solid #ddd; }
        .btn { display: inline-block; padding: 10px 20px; text-align: center; background-color: #1877F2; color: white; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; margin-top: 20px; text-decoration: none; }
        .row { display: flex; justify-content: space-between; margin-bottom: 10px; }
        .highlight { background-color: #FFEB3B; padding: 5px; border-radius: 3px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="logo">StreamMate AI</div>
    <div class="container">
        <h1>✅ Pembayaran Anda Sedang Diproses</h1>
        <p>Terima kasih! Info pembayaran Anda telah diterima. Paket akan aktif setelah konfirmasi (biasanya beberapa menit).</p>
        <div class="info">
            <div class="row"><div>Order ID:</div><div>{{ order_id }}</div></div>
            <div class="row"><div>Email:</div><div>{{ email }}</div></div>
            <div class="row"><div>Paket:</div><div>{{ package_name }}</div></div>
            <div class="row"><div>Jam Kredit:</div><div><span class="highlight">+{{ hours }} jam</span> ke akun Anda</div></div>
            <div class="row"><div>Harga:</div><div>Rp {{ '{:,.0f}'.format(price) }}</div></div>
            <div class="row"><div>Status Redirect:</div><div style="color: #4CAF50; font-weight: bold;">{{ gateway_status }}</div></div>
            <div class="row"><div>Status Aktual (dari file):</div><div>{{ current_status_from_file }}</div></div>
        </div>
        <p>Silakan kembali ke aplikasi StreamMate AI dan klik 'Refresh Status' untuk mengaktifkan paket Anda.</p>
        <a href="#" onclick="window.close(); return false;" class="btn">Tutup Halaman</a>
    </div>
</body>
</html>
"""

CANCELED_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>StreamMate AI - Pembayaran Dibatalkan</title>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; text-align: center; }
        .container { border: 1px solid #f44336; border-radius: 8px; padding: 20px; margin-top: 20px; background-color: #ffebee; }
        h1 { color: #f44336; }
        .logo { font-size: 24px; font-weight: bold; color: #1877F2; margin-bottom: 20px; }
        .btn { display: inline-block; padding: 10px 20px; text-align: center; background-color: #1877F2; color: white; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; margin-top: 20px; text-decoration: none; }
    </style>
</head>
<body>
    <div class="logo">StreamMate AI</div>
    <div class="container">
        <h1>❌ Pembayaran Dibatalkan</h1>
        <p>Transaksi (Order ID: {{ order_id }}) telah dibatalkan.</p>
        <p>Silakan kembali ke aplikasi StreamMate AI untuk mencoba proses pembayaran lagi.</p>
        <a href="#" onclick="window.close(); return false;" class="btn">Tutup Halaman</a>
    </div>
</body>
</html>
"""

@app.route("/test_callback", methods=["GET"])
def test_callback_form():
    """Form page for testing iPaymu callback simulation."""
    return """
    <html>
        <head>
            <title>Test Callback iPaymu</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                form { background-color: #f5f5f5; padding: 20px; border-radius: 5px; }
                label { display: block; margin-bottom: 5px; }
                input, select { margin-bottom: 15px; padding: 5px; width: 100%; }
                button { padding: 10px; background-color: #4CAF50; color: white; border: none; cursor: pointer; }
            </style>
        </head>
        <body>
            <h1>Simulasi Callback iPaymu</h1>
            <form action="/test_send_callback" method="post">
                <label>Reference ID (Order ID):</label>
                <input type="text" name="reference_id" required>
                
                <label>Status:</label>
                <select name="status">
                    <option value="berhasil">berhasil</option>
                    <option value="pending">pending</option>
                    <option value="failed">failed</option>
                </select>
                
                <label>Status Code:</label>
                <select name="status_code">
                    <option value="000">000 (Success)</option>
                    <option value="001">001 (Pending)</option>
                    <option value="002">002 (Failed)</option>
                </select>
                
                <label>Transaction ID:</label>
                <input type="text" name="trx_id" value="12345">
                
                <button type="submit">Send Callback</button>
            </form>
        </body>
    </html>
    """

@app.route("/test_send_callback", methods=["POST"])
def test_send_callback():
    """Endpoint for simulating callback submission."""
    # Get data from form
    reference_id = request.form.get("reference_id")
    status = request.form.get("status")
    status_code = request.form.get("status_code")
    trx_id = request.form.get("trx_id")
    
    # Create simulated callback payload
    callback_data = {
        "reference_id": reference_id,
        "status": status,
        "status_code": status_code,
        "trx_id": trx_id,
        "payment_method": "simulation",
        "payment_channel": "test"
    }
    
    # Call callback function directly
    try:
        # Save original request
        original_request = request
        
        # Create a custom request context
        class CustomRequest:
            def __init__(self, data):
                self.is_json = True
                self.json_data = data
                
            def get_json(self):
                return self.json_data
        
        # Modify request
        request.__class__ = type('ModifiedRequest', (request.__class__,), {})
        request.is_json = True
        request.json = callback_data
        
        # Call callback handler
        response = payment_callback_ipaymu()
        
        # Restore original request
        request.__class__ = original_request.__class__
        
        # Get current subscription status
        subscription_status = "Unknown"
        filepath = Path("config/subscription_status.json")
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                subscription_status = data.get("status", "Unknown")
        
        return f"""
        <html>
            <head>
                <title>Callback Test Result</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .result {{ background-color: #f5f5f5; padding: 20px; border-radius: 5px; }}
                    .success {{ color: green; }}
                    .error {{ color: red; }}
                </style>
            </head>
            <body>
                <h1>Callback Test Result</h1>
                <div class="result">
                    <h2>Callback Response:</h2>
                    <pre>{json.dumps(callback_data, indent=2)}</pre>
                    
                    <h2>Current Subscription Status:</h2>
                    <p class="{'success' if subscription_status == 'paid' else 'error'}">
                        {subscription_status}
                    </p>
                    
                    <a href="/test_callback">Test Another Callback</a>
                </div>
            </body>
        </html>
        """
    except Exception as e:
        return f"""
        <html>
            <head><title>Error</title></head>
            <body>
                <h1>Error Processing Result</h1>
                <p>{str(e)}</p>
                <a href="/test_callback">Back to Test Form</a>
            </body>
        </html>
        """

@app.route("/check_subscription/<email>", methods=["GET"])
def check_subscription(email):
    """View subscription status for specific user."""
    try:
        # Sanitize email for security
        email = email.replace("<", "").replace(">", "")
        
        filepath = Path("config/subscription_status.json")
        if not filepath.exists():
            return jsonify({
                "status": "error",
                "message": "Subscription file not found"
            }), 404
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if data.get("email") != email:
            return jsonify({
                "status": "error",
                "message": f"Subscription not found for email: {email}"
            }), 404
            
        # Return status
        return jsonify({
            "status": "success",
            "data": {
                "email": data.get("email"),
                "package": data.get("package"),
                "status": data.get("status"),
                "hours_credit": data.get("hours_credit"),
                "hours_used": data.get("hours_used"),
                "expire_date": data.get("expire_date"),
                "updated_at": data.get("updated_at")
            }
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error checking subscription: {str(e)}"
        }), 500

@app.route("/test_subscription", methods=["GET"])
def test_subscription():
    """Endpoint for testing and debugging subscription status."""
    try:
        filepath = Path("config/subscription_status.json")
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
            try:
                json_data = json.loads(content)
                order_id = json_data.get('order_id', '')
                transaction_id = json_data.get('transaction_id_gateway', '')
            except:
                order_id = ""
                transaction_id = ""
                
            return f"""
            <html>
                <head>
                    <title>Subscription Status</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; }}
                        pre {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; }}
                        .actions {{ margin-top: 20px; }}
                        button {{ padding: 10px; margin-right: 10px; cursor: pointer; }}
                    </style>
                </head>
                <body>
                    <h1>Subscription Status</h1>
                    <pre>{content}</pre>
                    
                    <div class="actions">
                        <h2>Debug Actions</h2>
                        <form action="/test_update_subscription" method="post">
                            <label>Order ID: <input type="text" name="order_id" value="{order_id}" required></label><br>
                            <label>Status: 
                                <select name="status">
                                    <option value="paid">paid</option>
                                    <option value="pending">pending</option>
                                </select>
                            </label><br>
                            <label>Transaction ID: <input type="text" name="transaction_id" value="{transaction_id}"></label><br>
                            <input type="submit" value="Update Subscription">
                        </form>
                    </div>
                </body>
            </html>
            """
        else:
            return "File subscription_status.json not found"
    except Exception as e:
        return f"Error reading file: {str(e)}"

@app.route("/test_update_subscription", methods=["POST"])
def test_update_subscription():
    """Endpoint for updating subscription status directly from form."""
    order_id = request.form.get("order_id")
    status = request.form.get("status", "paid")
    transaction_id = request.form.get("transaction_id", "")
    
    if not order_id:
        return "Order ID is required", 400
    
    result = update_subscription_status(order_id, status, transaction_id)
    if result:
        return redirect("/test_subscription")
    else:
        return "Error updating subscription", 500

if __name__ == "__main__":
    # Ensure port is an integer
    flask_port = int(os.getenv("FLASK_PORT", os.getenv("PORT", 5005)))
    # Ensure debug mode is boolean or integer 0/1
    flask_debug = os.getenv("FLASK_DEBUG", "1").lower() in ["true", "1", "yes"]

    app.run(host=os.getenv("FLASK_RUN_HOST", "0.0.0.0"),
            port=flask_port,
            debug=flask_debug)