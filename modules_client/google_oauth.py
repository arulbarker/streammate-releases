# modules_client/google_oauth.py
import os
import sys
import json
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token
from googleapiclient.discovery import build
from pathlib import Path
import webbrowser
import urllib.parse
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ========== PATH HANDLING FOR FROZEN EXE ==========
def get_application_path():
    """Get the correct application path for both dev and exe modes"""
    if getattr(sys, 'frozen', False):
        # Running as executable
        application_path = Path(sys.executable).parent
    else:
        # Running as script
        application_path = Path(__file__).resolve().parent.parent
    return application_path

# Use absolute paths
ROOT_PATH = get_application_path()
TOKEN_PATH = ROOT_PATH / "config" / "google_token.json"
CREDS_PATH = ROOT_PATH / "config" / "google_oauth.json"
SCOPES = ['https://www.googleapis.com/auth/userinfo.email', 'openid']

# Server configuration - Dynamic based on settings
def get_server_url():
    """Get server URL from settings or use default - EXE SAFE"""
    try:
        # Try multiple possible locations for settings
        possible_paths = [
            ROOT_PATH / "config" / "settings.json",
            ROOT_PATH / "config" / "settings_default.json",
            ROOT_PATH / "config" / "production_config.json"
        ]
        
        for settings_path in possible_paths:
            if settings_path.exists():
                try:
                    with open(settings_path, 'r') as f:
                        settings = json.load(f)
                        # Try different possible field names
                        server_url = (settings.get("server_url") or 
                                     settings.get("vps_server_url") or
                                     settings.get("api_server_url"))
                        if server_url:
                            print(f"[DEBUG] Server URL from {settings_path.name}: {server_url}")
                            return server_url.rstrip("/")
                except Exception as e:
                    print(f"[DEBUG] Failed to read {settings_path}: {e}")
                    continue
        
        print(f"[DEBUG] No server_url found in config files, using default")
        
    except Exception as e:
        print(f"[DEBUG] Error in get_server_url: {e}")
    
    # Default fallback - PRODUCTION SERVER
    default_url = "http://69.62.79.238:8000"
    print(f"[DEBUG] Using default server URL: {default_url}")
    return default_url

# SERVER_URL will be dynamically retrieved when needed

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback from Google"""
    
    def do_GET(self):
        """Handle GET request with OAuth callback"""
        try:
            # Parse query parameters
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            if 'code' in query_params:
                # Success - got authorization code
                self.server.auth_code = query_params['code'][0]
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                success_html = """
                <html>
                <head><title>Login Successful</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h2 style="color: green;">✅ Login Berhasil!</h2>
                    <p>Anda dapat menutup tab ini dan kembali ke aplikasi StreamMate AI.</p>
                    <script>setTimeout(function(){ window.close(); }, 3000);</script>
                </body>
                </html>
                """
                self.wfile.write(success_html.encode())
            elif 'error' in query_params:
                # Error in OAuth
                error = query_params.get('error', ['unknown'])[0]
                self.server.auth_error = error
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                error_html = f"""
                <html>
                <head><title>Login Failed</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h2 style="color: red;">❌ Login Gagal</h2>
                    <p>Error: {error}</p>
                    <p>Silakan tutup tab ini dan coba lagi.</p>
                </body>
                </html>
                """
                self.wfile.write(error_html.encode())
            
        except Exception as e:
            print(f"[ERROR] OAuth callback error: {e}")
            self.send_response(500)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress log messages"""
        pass

def get_oauth_config_from_server():
    """Get OAuth configuration from server"""
    try:
        server_url = get_server_url()  # Get fresh server URL
        response = requests.post(
            f"{server_url}/api/oauth/google",
            json={"action": "get_config"},
            timeout=10
        )
        response.raise_for_status()
        
        result = response.json()
        if result.get("status") == "success":
            oauth_config = result.get("data", {}).get("oauth_config", {})
            if oauth_config and "installed" in oauth_config:
                print("[DEBUG] OAuth config retrieved from server")
                return oauth_config
        
        print(f"[ERROR] Server OAuth response: {result}")
        return None
        
    except Exception as e:
        print(f"[ERROR] Failed to get OAuth config from server: {e}")
        return None

def server_based_oauth():
    """Perform OAuth using server backend"""
    try:
        server_url = get_server_url()  # Get fresh server URL
        print(f"[DEBUG] Starting server-based OAuth flow...")
        print(f"[DEBUG] Using server URL: {server_url}")
        print(f"[DEBUG] Running in frozen mode: {getattr(sys, 'frozen', False)}")
        
        # Test server connectivity first
        try:
            health_response = requests.get(f"{server_url}/api/health", timeout=5)
            print(f"[DEBUG] Server health check: {health_response.status_code}")
        except Exception as e:
            print(f"[DEBUG] Server health check failed: {e}")
        
        # Get OAuth URL from server
        print(f"[DEBUG] Requesting OAuth URL from: {server_url}/api/oauth/google")
        response = requests.post(
            f"{server_url}/api/oauth/google",
            json={"action": "get_auth_url"},
            timeout=10
        )
        print(f"[DEBUG] OAuth URL request status: {response.status_code}")
        response.raise_for_status()
        
        result = response.json()
        if result.get("status") != "success":
            raise Exception(f"Failed to get auth URL: {result.get('message', 'Unknown error')}")
        
        auth_url = result.get("data", {}).get("auth_url")
        redirect_uri = result.get("data", {}).get("redirect_uri", "http://localhost:50700")
        
        if not auth_url:
            raise Exception("No auth URL received from server")
        
        print(f"[DEBUG] Got auth URL from server: {auth_url[:50]}...")
        
        # Start local server to handle callback
        from urllib.parse import urlparse
        parsed_redirect = urlparse(redirect_uri)
        callback_port = parsed_redirect.port or 50700
        
        server = HTTPServer(('localhost', callback_port), OAuthCallbackHandler)
        server.auth_code = None
        server.auth_error = None
        
        # Start server in background
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        
        print(f"[DEBUG] Callback server started on port {callback_port}")
        
        # Open browser for OAuth
        print("[DEBUG] Opening browser for OAuth...")
        webbrowser.open(auth_url)
        
        # Wait for callback (max 5 minutes)
        timeout = 300  # 5 minutes
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if server.auth_code:
                print("[DEBUG] Authorization code received!")
                break
            elif server.auth_error:
                raise Exception(f"OAuth error: {server.auth_error}")
            time.sleep(1)
        
        server.shutdown()
        
        if not server.auth_code:
            raise Exception("OAuth timeout - no authorization code received")
        
        # Exchange code for tokens via server
        print("[DEBUG] Exchanging authorization code for tokens...")
        response = requests.post(
            f"{server_url}/api/oauth/google",
            json={
                "action": "exchange_code",
                "code": server.auth_code
            },
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        if result.get("status") != "success":
            raise Exception(f"Token exchange failed: {result.get('message', 'Unknown error')}")
        
        token_data = result.get("data", {})
        print("[DEBUG] Token exchange successful!")
        
        return token_data
        
    except Exception as e:
        print(f"[ERROR] Server-based OAuth failed: {e}")
        return None

def local_oauth():
    """Perform OAuth using local credentials file"""
    try:
        if not CREDS_PATH.exists():
            print(f"[DEBUG] Local credentials not found: {CREDS_PATH}")
            return None
        
        print(f"[DEBUG] Starting local OAuth flow with credentials from: {CREDS_PATH}")
        
        # For executable, we need to handle SSL certificates properly
        import ssl
        import certifi
        
        # Set CA bundle for SSL verification
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
        os.environ['SSL_CERT_FILE'] = certifi.where()
        
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
        # Set timeout yang lebih lama untuk menghindari not responding
        creds = flow.run_local_server(port=0, timeout=300)
        print("[DEBUG] Local OAuth flow completed successfully")
        
        return creds
        
    except Exception as e:
        print(f"[ERROR] Local OAuth failed: {e}")
        return None

def login_google():
    """
    Proses login dengan Google OAuth - HYBRID MODE
    Coba local dulu, fallback ke server jika gagal
    
    Returns:
        str: Email pengguna jika login berhasil, None jika gagal
    """
    creds = None
    
    # Pastikan direktori config ada
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Production mode - minimal logging
    if not getattr(sys, 'frozen', False):
        print(f"[DEBUG] Looking for credentials at: {CREDS_PATH}")
        print(f"[DEBUG] Token will be saved to: {TOKEN_PATH}")
        print(f"[DEBUG] Current working directory: {os.getcwd()}")
        print(f"[DEBUG] Application path: {ROOT_PATH}")
        print(f"[DEBUG] Server URL: {get_server_url()}")
        print(f"[DEBUG] Frozen mode: {getattr(sys, 'frozen', False)}")

    # Cek apakah sudah ada token
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
            print("[DEBUG] Token loaded from file")
            
            # Check if token has required components
            if not creds.refresh_token:
                print("[DEBUG] Token missing refresh_token - deleting and recreating")
                TOKEN_PATH.unlink()
                creds = None
            elif creds.expired:
                print("[DEBUG] Token is expired - attempting refresh")
                try:
                    creds.refresh(Request())
                    print("[DEBUG] Token refreshed successfully")
                except Exception as e:
                    print(f"[DEBUG] Token refresh failed: {e}")
                    print("[DEBUG] Deleting expired token, will create new one")
                    TOKEN_PATH.unlink()
                    creds = None
            
            # IMMEDIATE VALIDATION: Test token dengan userinfo endpoint
            if creds and creds.valid:
                try:
                    print("[DEBUG] Testing token validity with userinfo...")
                    test_service = build('oauth2', 'v2', credentials=creds)
                    userinfo = test_service.userinfo().get().execute()
                    email = userinfo.get('email')
                    if email:
                        print(f"[DEBUG] Token is VALID - email: {email}")
                        # Token valid, langsung return email
                        return email
                    else:
                        print("[DEBUG] Token valid but no email - forcing refresh")
                        creds = None
                except Exception as e:
                    print(f"[DEBUG] Token validation failed: {e}")
                    print("[DEBUG] Token exists but invalid - will refresh/recreate")
                    creds = None
            
        except Exception as e:
            print(f"[DEBUG] Error loading token file: {e}")
            # File token mungkin corrupt, hapus dan buat baru
            try:
                TOKEN_PATH.unlink()
                print("[DEBUG] Corrupted token file deleted")
            except:
                pass
            creds = None

    # Login baru jika belum ada atau token tidak valid
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                try:
                    print("[DEBUG] Attempting to refresh expired token...")
                    creds.refresh(Request())
                    print("[DEBUG] Token refreshed successfully")
                    
                    # Validate refreshed token
                    try:
                        test_service = build('oauth2', 'v2', credentials=creds)
                        userinfo = test_service.userinfo().get().execute()
                        email = userinfo.get('email')
                        if email:
                            print(f"[DEBUG] Refreshed token valid - email: {email}")
                        else:
                            print("[DEBUG] Refreshed token has no email - creating new")
                            creds = None
                    except Exception as e:
                        print(f"[DEBUG] Refreshed token validation failed: {e}")
                        creds = None
                        
                except Exception as e:
                    print(f"[DEBUG] Token refresh failed: {e}")
                    # Token tidak bisa di-refresh, mulai alur login baru
                    creds = None
                    
            if not creds:
                # HYBRID APPROACH: Try local first, then server
                print("[DEBUG] Starting new OAuth flow...")
                
                # Try local OAuth first (for development)
                creds = local_oauth()
                
                # If local fails, try server-based OAuth (for production EXE)
                if not creds:
                    print("[DEBUG] Local OAuth failed, trying server-based OAuth...")
                    token_data = server_based_oauth()
                    
                    if token_data:
                        # Create credentials from server response
                        creds_info = {
                            'token': token_data.get('access_token'),
                            'refresh_token': token_data.get('refresh_token'),
                            'token_uri': 'https://oauth2.googleapis.com/token',
                            'client_id': token_data.get('client_id', ''),
                            'client_secret': '',  # Don't store client secret locally
                            'scopes': SCOPES
                        }
                        
                        # Add ID token if available
                        if 'id_token' in token_data:
                            creds_info['id_token'] = token_data['id_token']
                        
                        # Debug token data (development only)
                        if not getattr(sys, 'frozen', False):
                            print(f"[DEBUG] Token data received:")
                            print(f"  - Access token: {'✅ Present' if token_data.get('access_token') else '❌ Missing'}")
                            print(f"  - Refresh token: {'✅ Present' if token_data.get('refresh_token') else '❌ Missing'}")
                            print(f"  - ID token: {'✅ Present' if token_data.get('id_token') else '❌ Missing'}")
                            print(f"  - Client ID: {'✅ Present' if token_data.get('client_id') else '❌ Missing'}")
                            
                            if not token_data.get('refresh_token'):
                                print("[WARNING] No refresh token received - token cannot be refreshed!")
                                print("[WARNING] This may cause issues when token expires")
                        
                        creds = Credentials.from_authorized_user_info(creds_info, SCOPES)
                        print("[DEBUG] Server-based OAuth completed successfully")
                
                if not creds:
                    # Last resort: Try to guide user to manual setup
                    print("[ERROR] Both local and server-based OAuth failed!")
                    print("[ERROR] Possible solutions:")
                    print("1. Check internet connection")
                    print("2. Check server status at http://69.62.79.238:8000/api/health")
                    print("3. Ensure port 50700 is not blocked by firewall")
                    print("4. Try running as administrator")
                    raise Exception("OAuth authentication failed - please check connection and try again")
            
            # Simpan token
            with open(TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
            print(f"[DEBUG] Token saved to: {TOKEN_PATH}")
                
        except Exception as e:
            print(f"Error dalam proses OAuth: {e}")
            import traceback
            print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
            return None

    # FINAL EMAIL EXTRACTION - PRIORITIZE ID TOKEN (No Client ID needed)
    try:
        print("[DEBUG] Extracting email using multiple methods...")
        
        # Method 1: Try ID token first (BEST - no client ID needed)
        if hasattr(creds, 'id_token') and creds.id_token:
            try:
                print("[DEBUG] Attempting ID token verification...")
                # Try without verification first (faster)
                import base64
                import json as json_lib
                
                # Decode ID token payload (JWT format)
                parts = creds.id_token.split('.')
                if len(parts) >= 2:
                    # Add padding if needed
                    payload = parts[1]
                    payload += '=' * (4 - len(payload) % 4)
                    
                    try:
                        decoded = base64.urlsafe_b64decode(payload)
                        token_info = json_lib.loads(decoded)
                        email = token_info.get('email')
                        if email:
                            print(f"[DEBUG] Email from ID token payload: {email}")
                            return email
                    except Exception as e:
                        print(f"[DEBUG] ID token manual decode failed: {e}")
                
                # Fallback to proper verification
                try:
                    info = id_token.verify_oauth2_token(creds.id_token, Request())
                    if info and "email" in info:
                        email = info.get("email")
                        print(f"[DEBUG] Email from verified ID token: {email}")
                        return email
                except Exception as e:
                    print(f"[DEBUG] ID token verification failed: {e}")
                    
            except Exception as e:
                print(f"[DEBUG] ID token processing failed: {e}")

        # Method 2: Direct REST call with fresh token (bypass Google API client)
        try:
            print("[DEBUG] Attempting direct userinfo call...")
            # Ensure token is fresh
            if creds.expired and creds.refresh_token:
                print("[DEBUG] Token expired, refreshing...")
                try:
                    creds.refresh(Request())
                    print("[DEBUG] Token refreshed successfully")
                except Exception as e:
                    print(f"[DEBUG] Token refresh failed: {e}")
                    # Continue with expired token, might still work
                
            headers = {'Authorization': f'Bearer {creds.token}'}
            resp = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=headers, verify=True)
            
            print(f"[DEBUG] Userinfo response status: {resp.status_code}")
            if resp.status_code == 200:
                email = resp.json().get("email")
                print(f"[DEBUG] Email from direct REST call: {email}")
                return email
            else:
                print(f"[DEBUG] Userinfo error: {resp.status_code} - {resp.text}")
                
        except Exception as e:
            print(f"[DEBUG] Direct userinfo call failed: {e}")

        # Method 3: Try Google API client (if client ID issue is resolved)
        try:
            print("[DEBUG] Attempting Google API client (last resort)...")
            service = build('oauth2', 'v2', credentials=creds)
            userinfo = service.userinfo().get().execute()
            email = userinfo.get('email')
            if email:
                print(f"[DEBUG] Email from Google API client: {email}")
                return email
            else:
                print("[DEBUG] No email in Google API client response")
        except Exception as e:
            print(f"[DEBUG] Google API client failed: {e}")

        # If all methods fail, delete token and suggest retry
        print("[ERROR] All email extraction methods failed!")
        print("[ERROR] Token info:")
        print(f"  - Valid: {creds.valid if creds else 'No creds'}")
        print(f"  - Expired: {creds.expired if creds else 'No creds'}")
        print(f"  - Has refresh token: {bool(creds.refresh_token) if creds else 'No creds'}")
        
        # Delete invalid token file to force fresh OAuth next time
        if TOKEN_PATH.exists():
            try:
                TOKEN_PATH.unlink()
                print("[DEBUG] Invalid token file deleted - fresh OAuth required next time")
            except Exception as e:
                print(f"[DEBUG] Could not delete token file: {e}")
        
        print("[ERROR] Please try logging in again - token has been reset")
        return None
        
    except Exception as e:
        print(f"[ERROR] Critical error in email extraction: {e}")
        import traceback
        print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
        return None
