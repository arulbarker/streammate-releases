#!/usr/bin/env python3
"""
API Bridge untuk StreamMate AI Client
Menghubungkan aplikasi client dengan server VPS untuk AI processing
"""

import json
import requests
import logging
import os
from modules_client.config_manager import ConfigManager
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class APIClient:
    def __init__(self):
        self.cfg = ConfigManager()
        # Debug environment
        print(f"[DEBUG] Environment STREAMMATE_DEV: {os.getenv('STREAMMATE_DEV', 'not set')}")
        print(f"[DEBUG] Environment STREAMMATE_SERVER_URL: {os.getenv('STREAMMATE_SERVER_URL', 'not set')}")
        
        # Base URL dengan prioritas environment variable - PERBAIKAN: Port 8000 untuk VPS
        env_url = os.getenv("STREAMMATE_SERVER_URL")
        if env_url:
            self.base_url = env_url
            print(f"[API] Using server URL from environment: {env_url}")
        else:
            self.base_url = "http://69.62.79.238:8000"  # PERBAIKAN: VPS di port 8000
            print(f"[API] Using default server URL: {self.base_url}")
        
        self.timeout = 30
        
    def _get_server_url(self):
        """Tentukan server URL berdasarkan mode"""
        # 1. Cek environment variable dari .env
        env_url = self.cfg.get_env('API_BASE_URL')
        if env_url:
            return env_url
            
        # 2. Cek environment variable dulu (developer override) - PERBAIKAN: Port 8000
        if os.getenv("STREAMMATE_DEV", "").lower() == "true":
            return "http://localhost:8888"  # Dev mode gunakan localhost
    
    def _make_request(self, endpoint, data, timeout=None):
        """Make request dengan error handling"""
        if timeout is None:
            timeout = self.timeout
            
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.post(url, json=data, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.ConnectionError:
            if self.base_url == "https://api.streammateai.com":
                # Production server down, fallback ke localhost
                logger.warning("Production server unavailable, trying localhost...")
                self.base_url = "http://69.62.79.238:8000"
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

class APIBridge:
    """Bridge untuk komunikasi dengan VPS server"""
    
    def __init__(self):
        # Server endpoints - PERBAIKAN: VPS di port 8000, local tetap 8888
        self.vps_server = "http://69.62.79.238:8000"  # VPS di port 8000
        self.local_server = "http://localhost:8888"  # Local dev di port 8888
        
        # Test koneksi dan tentukan server aktif
        self.active_server = self._get_active_server()
        
    def _get_active_server(self):
        """Test koneksi server dan return yang aktif"""
        # Test VPS server dulu
        try:
            response = requests.get(f"{self.vps_server}/api/health", timeout=3)
            if response.status_code == 200:
                print(f"[API] VPS server active: {self.vps_server}")
                return self.vps_server
        except Exception:
            pass
        
        # Test local server
        try:
            response = requests.get(f"{self.local_server}/api/health", timeout=10)
            if response.status_code == 200:
                print(f"[API] Local server active: {self.local_server}")
                return self.local_server
        except Exception:
            pass
        
        # Default ke VPS jika keduanya gagal
        print(f"[API] No server responded, defaulting to VPS: {self.vps_server}")
        return self.vps_server

# Global API bridge instance
api_bridge = APIBridge()

def generate_reply(prompt: str, timeout: int = 30) -> str:
    """
    Generate AI reply using VPS DeepSeek API with local fallback
    
    Args:
        prompt: User prompt for AI
        timeout: Request timeout in seconds
        
    Returns:
        AI generated reply string, or fallback response if failed
    """
    print(f"[API] generate_reply called with prompt length: {len(prompt)}")
    
    # Method 1: Try VPS API endpoint (preferred)
    try:
        print(f"[API] Trying VPS API endpoint...")
        
        response = requests.post(
            f"{api_bridge.active_server}/api/ai/generate",
            json={"prompt": prompt},
            timeout=timeout,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Handle FastAPI response format
            if result.get("status") == "success" and "data" in result:
                reply = result["data"].get("reply", "").strip()
                if reply:
                    print(f"[API] VPS API success: {len(reply)} chars")
                    return reply
            
            # Handle old format (fallback)
            elif "reply" in result:
                reply = result.get("reply", "").strip()
                if reply:
                    print(f"[API] VPS API success (old format): {len(reply)} chars")
                    return reply
            
            print(f"[API] VPS API returned empty reply")
            
        else:
            print(f"[API] VPS API error: {response.status_code}")
            if response.status_code == 404:
                print(f"[API] Endpoint /api/ai/generate not found on server")
            try:
                error_detail = response.json()
                print(f"[API] Error detail: {error_detail}")
            except:
                print(f"[API] Error response: {response.text[:200]}")
            
    except requests.exceptions.RequestException as e:
        print(f"[API] VPS API request failed: {e}")
    except Exception as e:
        print(f"[API] VPS API unexpected error: {e}")
    
    # Method 1.5: Try existing /api/ai/reply endpoint as fallback
    try:
        print(f"[API] Trying existing /api/ai/reply endpoint...")
        
        response = requests.post(
            f"{api_bridge.active_server}/api/ai/reply",
            json={"text": prompt},  # Different format for existing endpoint
            timeout=timeout,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Handle various response formats
            reply = ""
            if "data" in result and isinstance(result["data"], dict):
                reply = result["data"].get("reply", "").strip()
            elif "reply" in result:
                reply = result.get("reply", "").strip()
            elif "data" in result and isinstance(result["data"], str):
                reply = result["data"].strip()
            
            if reply:
                print(f"[API] Existing endpoint success: {len(reply)} chars")
                return reply
            else:
                print(f"[API] Existing endpoint returned empty reply")
                
        else:
            print(f"[API] Existing endpoint error: {response.status_code}")
            
    except Exception as e:
        print(f"[API] Existing endpoint error: {e}")
    
    # Method 2: Try direct DeepSeek API if local API key available
    try:
        print(f"[API] Trying direct DeepSeek API...")
        
        # Check if we have local API key
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key and len(deepseek_key) > 10:
            print(f"[API] Using local DeepSeek API key...")
            
            headers = {
                "Authorization": f"Bearer {deepseek_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 400,
                "temperature": 0.8,
                "top_p": 0.95,
            }
            
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                reply = result["choices"][0]["message"]["content"].strip()
                if reply:
                    print(f"[API] Direct DeepSeek success: {len(reply)} chars")
                    return reply
            else:
                print(f"[API] Direct DeepSeek error: {response.status_code}")
                
        else:
            print(f"[API] No local DeepSeek API key found")
            
    except Exception as e:
        print(f"[API] Direct DeepSeek API error: {e}")
    
    # Method 3: Fallback response
    print(f"[API] All methods failed, using fallback response")
    return _get_fallback_response(prompt)

def _get_fallback_response(prompt: str) -> str:
    """Generate fallback response when AI API fails"""
    prompt_lower = prompt.lower()
    
    # Extract author name from prompt if possible
    author = "teman"
    if "penonton" in prompt and "bertanya" in prompt:
        # Try to extract author name from typical prompt format
        import re
        author_match = re.search(r'Penonton (\w+) bertanya', prompt)
        if author_match:
            author = author_match.group(1)
    
    # Simple rule-based responses
    if any(word in prompt_lower for word in ["halo", "hai", "hello"]):
        return f"Hai {author}! Maaf lagi ada gangguan koneksi AI"
    elif any(word in prompt_lower for word in ["kabar", "apa kabar"]):
        return f"Baik {author}, lagi streaming nih meski ada sedikit lag AI"
    elif any(word in prompt_lower for word in ["makan", "udah makan"]):
        return f"Udah makan {author}, sekarang lagi fokus main"
    elif any(word in prompt_lower for word in ["khodam", "cek"]):
        return f"{author} khodammu lagi offline kayak AI-nya hehe"
    else:
        return f"Hai {author} sorry AI lagi bermasalah, coba tanya lagi nanti ya"

def test_api_connection():
    """Test API connection and return status"""
    results = {
        "vps_server": False,
        "local_server": False,
        "deepseek_direct": False,
        "active_server": None
    }
    
    # Test VPS server
    try:
        response = requests.get(f"{api_bridge.vps_server}/api/health", timeout=3)
        results["vps_server"] = response.status_code == 200
    except:
        pass
    
    # Test local server  
    try:
        response = requests.get(f"{api_bridge.local_server}/api/health", timeout=10)
        results["local_server"] = response.status_code == 200
    except:
        pass
    
    # Test direct DeepSeek
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if deepseek_key and len(deepseek_key) > 10:
        try:
            headers = {"Authorization": f"Bearer {deepseek_key}"}
            response = requests.get("https://api.deepseek.com/v1/models", headers=headers, timeout=5)
            results["deepseek_direct"] = response.status_code == 200
        except:
            pass
    
    results["active_server"] = api_bridge.active_server
    return results

if __name__ == "__main__":
    # Test script
    print("Testing API connections...")
    status = test_api_connection()
    
    print("\n=== API Connection Status ===")
    print(f"VPS Server (69.62.79.238): {'✅' if status['vps_server'] else '❌'}")
    print(f"Local Server (localhost:8888): {'✅' if status['local_server'] else '❌'}")
    print(f"Direct DeepSeek API: {'✅' if status['deepseek_direct'] else '❌'}")
    print(f"Active Server: {status['active_server']}")
    
    # Test generate_reply
    print("\n=== Testing AI Generation ===")
    test_prompt = "Penonton TestUser bertanya: halo bang apa kabar?"
    result = generate_reply(test_prompt)
    print(f"Test Result: {result}")
