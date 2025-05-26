# modules_server/webhook_handler.py
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs
from modules_server.license_manager import LicenseManager
from modules_server.ipaymu_handler import IPaymuHandler

class WebhookHandler(BaseHTTPRequestHandler):
    """Handler untuk webhook payment."""
    
    def __init__(self, *args, **kwargs):
        self.license_manager = LicenseManager()
        self.ipaymu_handler = IPaymuHandler()
        super().__init__(*args, **kwargs)
    
    def _parse_json_body(self):
        """Parse JSON dari request body."""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        return json.loads(post_data.decode('utf-8'))
    
    def _send_response_json(self, data, status=200):
        """Kirim response JSON."""
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def do_POST(self):
        """Handle POST requests webhook."""
        if self.path == '/webhook/payment':
            try:
                # Parse data dari iPaymu
                data = self._parse_json_body()
                
                # Proses callback
                result = self.ipaymu_handler.process_callback(data)
                
                if result.get("success"):
                    # Update lisensi jika pembayaran berhasil
                    email = result.get("email")
                    package = result.get("package")
                    
                    if email and package:
                        # Tentukan durasi berdasarkan paket
                        days = 30  # Default
                        if package == "pro":
                            days = 30
                        elif package == "basic":
                            days = 30
                        
                        # Update atau buat lisensi baru
                        self.license_manager.create_or_update_license(email, package, days)
                
                self._send_response_json({
                    'status': 'ok',
                    'message': 'Webhook received'
                })
                
            except Exception as e:
                self._send_response_json({
                    'status': 'error',
                    'message': str(e)
                }, 500)
        else:
            self._send_response_json({
                'status': 'error',
                'message': 'Invalid endpoint'
            }, 404)