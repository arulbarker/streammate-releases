# modules_server/deepseek_ai.py

import os
import json
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DEEPSEEK_API_KEY")
ENDPOINT = "https://api.deepseek.com/v1/chat/completions"

# Setup logging
logger = logging.getLogger(__name__)

def generate_reply(prompt: str, timeout: int = 15) -> str | None:
    """
    Generate AI reply dengan timeout protection dan error handling yang lebih baik
    """
    if not API_KEY:
        logger.error("[deepseek_ai] DEEPSEEK_API_KEY not configured")
        return None
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       "deepseek-chat",
        "messages":    [{"role": "user", "content": prompt}],
        "max_tokens":  400,
        "temperature": 0.8,
        "top_p":       0.95,
    }
    
    try:
        logger.info(f"[deepseek_ai] Sending request to DeepSeek API (timeout: {timeout}s)")
        resp = requests.post(ENDPOINT, headers=headers, json=payload, timeout=timeout)
        
        if resp.status_code == 200:
            result = resp.json()
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"].strip()
                logger.info(f"[deepseek_ai] Success: {len(content)} chars")
                return content
            else:
                logger.error(f"[deepseek_ai] Invalid response format: {result}")
                return None
        else:
            logger.error(f"[deepseek_ai] API error {resp.status_code}: {resp.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error(f"[deepseek_ai] Timeout after {timeout}s")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[deepseek_ai] Connection error: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"[deepseek_ai] Request error: {e}")
        return None
    except Exception as e:
        logger.error(f"[deepseek_ai] Unexpected error: {e}")
        return None

