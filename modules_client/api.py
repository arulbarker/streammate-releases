import requests
import logging
import os
from modules_client.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self):
        self.cfg = ConfigManager()
        self.base_url = self._get_server_url()
        
    def _get_server_url(self):
        """Tentukan server URL berdasarkan mode"""
        # 1. Cek environment variable dulu (developer override)
        if os.getenv("STREAMMATE_DEV", "").lower() == "true":
            return "http://localhost:8000"
        
        # 2. Cek apakah ada dev_users.json (developer mode)
        try:
            import json
            from pathlib import Path
            dev_file = Path("config/dev_users.json")
            if dev_file.exists():
                return "http://localhost:8000"
        except:
            pass
        
        # 3. Cek debug_mode di settings
        if self.cfg.get("debug_mode", False):
            return "http://localhost:8000"
        
        # 4. Default: Production server
        return "https://api.streammateai.com"
    
    def _make_request(self, endpoint, data, timeout=10):
        """Make request dengan error handling"""
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.post(url, json=data, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.ConnectionError:
            if self.base_url == "https://api.streammateai.com":
                # Production server down, fallback ke localhost
                logger.warning("Production server unavailable, trying localhost...")
                self.base_url = "http://localhost:8000"
                return self._make_request(endpoint, data, timeout)
            else:
                raise
    
    def generate_reply(self, prompt: str) -> str:
        """Generate AI reply melalui server"""
        try:
            response = self._make_request("ai_reply", {"text": prompt})
            return response.json().get("reply", "")
        except Exception as e:
            logger.error(f"AI API failed: {e}")
            # Fallback untuk developer mode saja
            if "localhost" in self.base_url:
                try:
                    from modules_server.deepseek_ai import generate_reply as local_gen
                    logger.info("Using local DeepSeek fallback")
                    return local_gen(prompt)
                except Exception as local_error:
                    logger.error(f"Local fallback failed: {local_error}")
            
            return "Maaf, sistem AI sedang dalam maintenance"

# Global instance
_api_client = APIClient()

# Export functions
def generate_reply(prompt: str) -> str:
    return _api_client.generate_reply(prompt)

def get_server_info():
    """Info server yang sedang digunakan (untuk debugging)"""
    return {
        "server_url": _api_client.base_url,
        "mode": "development" if "localhost" in _api_client.base_url else "production"
    }