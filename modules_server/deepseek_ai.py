# modules_server/deepseek_ai.py

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DEEPSEEK_API_KEY")
ENDPOINT = "https://api.deepseek.com/v1/chat/completions"

def generate_reply(prompt: str) -> str | None:
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
        resp = requests.post(ENDPOINT, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[deepseek_ai] ERROR calling {ENDPOINT!r}: {e}")
        return None
