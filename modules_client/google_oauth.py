# modules_client/google_oauth.py
import os
import json
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token
from pathlib import Path

TOKEN_PATH = "config/google_token.json"
CREDS_PATH = "config/google_oauth.json"
SCOPES = ['https://www.googleapis.com/auth/userinfo.email', 'openid']

def login_google():
    """
    Proses login dengan Google OAuth.
    
    Returns:
        str: Email pengguna jika login berhasil, None jika gagal
    """
    creds = None
    
    # Pastikan direktori config ada
    Path(TOKEN_PATH).parent.mkdir(parents=True, exist_ok=True)

    # Cek apakah sudah ada token
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception as e:
            print(f"Error loading token: {e}")
            # File token mungkin corrupt, hapus dan buat baru
            os.remove(TOKEN_PATH)
            creds = None

    # Login baru jika belum ada atau token tidak valid
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    # Token tidak bisa di-refresh, mulai alur login baru
                    creds = None
                    
            if not creds:
                if not os.path.exists(CREDS_PATH):
                    raise FileNotFoundError(f"File OAuth tidak ditemukan: {CREDS_PATH}")
                
                flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
                # Set timeout yang lebih lama untuk menghindari not responding
                creds = flow.run_local_server(port=0, timeout=300)
            
            # Simpan token
            with open(TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
                
        except Exception as e:
            print(f"Error dalam proses OAuth: {e}")
            return None

    # Ambil email dari ID token
    try:
        if creds.id_token:
            info = id_token.verify_oauth2_token(creds.id_token, Request())
            if info and "email" in info:
                return info.get("email")
    except Exception as e:
        print(f"Error verifikasi id_token: {e}")

    # Jika id_token tidak tersedia, ambil dari userinfo endpoint
    try:
        headers = {'Authorization': f'Bearer {creds.token}'}
        resp = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=headers)
        if resp.status_code == 200:
            return resp.json().get("email")
        else:
            print(f"Error dari userinfo endpoint: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"Error mendapatkan info pengguna: {e}")

    return None