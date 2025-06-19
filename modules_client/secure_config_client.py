"""
Secure Config Client - Fetch sensitive configurations from server
All sensitive files are now stored on server, client fetches via API
"""

import requests
import json
import base64
import io
from pathlib import Path
from typing import Dict, Any, Optional
import tempfile
import os

class SecureConfigClient:
    def __init__(self, server_url: str = "http://69.62.79.238:8000"):
        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = 30
        
    def get_packages_config(self) -> Dict[str, Any]:
        """Get packages configuration from server"""
        try:
            response = self.session.get(f"{self.server_url}/api/config/packages")
            response.raise_for_status()
            
            result = response.json()
            if result.get("status") == "success":
                return result.get("data", {})
            else:
                raise Exception(f"Server error: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Failed to get packages config: {e}")
            # Fallback ke default packages
            return {
                "basic": {
                    "price": 100000,
                    "credits": 100000,
                    "description": "Paket Basic - 100.000 Kredit"
                },
                "pro": {
                    "price": 250000,
                    "credits": 250000,
                    "description": "Paket Pro - 250.000 Kredit"
                }
            }
    
    def get_production_config(self) -> Dict[str, Any]:
        """Get production configuration from server"""
        try:
            response = self.session.get(f"{self.server_url}/api/config/production")
            response.raise_for_status()
            
            result = response.json()
            if result.get("status") == "success":
                return result.get("data", {})
            else:
                raise Exception(f"Server error: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Failed to get production config: {e}")
            # Fallback ke default config
            return {
                "mode": "production",
                "server_only": True,
                "vps_server_url": self.server_url
            }
    
    def synthesize_tts(self, text: str, voice: str = "id-ID-Standard-A") -> Optional[bytes]:
        """Synthesize TTS via server proxy"""
        try:
            payload = {
                "text": text,
                "voice": voice
            }
            
            response = self.session.post(
                f"{self.server_url}/api/tts/synthesize",
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get("status") == "success":
                audio_base64 = result.get("data", {}).get("audio_base64")
                if audio_base64:
                    return base64.b64decode(audio_base64)
            
            raise Exception(f"TTS synthesis failed: {result.get('message', 'Unknown error')}")
            
        except Exception as e:
            print(f"❌ TTS synthesis failed: {e}")
            return None
    
    def get_google_oauth_url(self) -> Optional[str]:
        """Get Google OAuth URL from server"""
        try:
            payload = {"action": "get_auth_url"}
            
            response = self.session.post(
                f"{self.server_url}/api/oauth/google",
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get("status") == "success":
                return result.get("data", {}).get("auth_url")
            
            raise Exception(f"OAuth URL generation failed: {result.get('message', 'Unknown error')}")
            
        except Exception as e:
            print(f"❌ Failed to get OAuth URL: {e}")
            return None
    
    def exchange_oauth_code(self, auth_code: str) -> Optional[Dict[str, Any]]:
        """Exchange OAuth authorization code for tokens via server"""
        try:
            payload = {
                "action": "exchange_code",
                "code": auth_code
            }
            
            response = self.session.post(
                f"{self.server_url}/api/oauth/google",
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get("status") == "success":
                return result.get("data", {})
            
            raise Exception(f"OAuth token exchange failed: {result.get('message', 'Unknown error')}")
            
        except Exception as e:
            print(f"❌ OAuth token exchange failed: {e}")
            return None
    
    def create_temp_credentials_file(self, credentials_data: Dict[str, Any]) -> str:
        """Create temporary credentials file for Google APIs"""
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.json',
                delete=False
            )
            
            json.dump(credentials_data, temp_file, indent=2)
            temp_file.close()
            
            return temp_file.name
            
        except Exception as e:
            print(f"❌ Failed to create temp credentials file: {e}")
            return None
    
    def cleanup_temp_file(self, file_path: str):
        """Clean up temporary file"""
        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"⚠️ Failed to cleanup temp file: {e}")

# Global instance
secure_config = SecureConfigClient()

# Helper functions untuk backward compatibility
def get_packages_from_server():
    """Get packages configuration from server"""
    return secure_config.get_packages_config()

def get_production_config_from_server():
    """Get production configuration from server"""
    return secure_config.get_production_config()

def synthesize_tts_from_server(text: str, voice: str = "id-ID-Standard-A"):
    """Synthesize TTS via server"""
    return secure_config.synthesize_tts(text, voice)

def get_google_oauth_url_from_server():
    """Get Google OAuth URL from server"""
    return secure_config.get_google_oauth_url()

def exchange_oauth_code_from_server(auth_code: str):
    """Exchange OAuth code via server"""
    return secure_config.exchange_oauth_code(auth_code)

if __name__ == "__main__":
    # Test the secure config client
    client = SecureConfigClient()
    
    print("🧪 Testing Secure Config Client...")
    
    # Test packages config
    packages = client.get_packages_config()
    print(f"📦 Packages: {packages}")
    
    # Test production config
    config = client.get_production_config()
    print(f"⚙️ Production Config: {config}")
    
    # Test TTS
    audio = client.synthesize_tts("Halo, ini adalah tes TTS dari server")
    print(f"🔊 TTS Audio Length: {len(audio) if audio else 0} bytes")
    
    # Test OAuth URL
    oauth_url = client.get_google_oauth_url()
    print(f"🔐 OAuth URL: {oauth_url}")
    
    print("✅ Secure Config Client tests completed!") 