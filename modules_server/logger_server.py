# modules_server/logger_server.py

from datetime import datetime
from pathlib import Path

LOG_FILE = Path("log_request.txt")


def log_request(endpoint: str, payload: dict, result: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"[{timestamp}] ENDPOINT: {endpoint}\n"
        f"Payload : {payload}\n"
        f"Response: {result}\n"
        f"{'-' * 50}\n"
    )
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry)


def log_error(endpoint: str, error: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"[{timestamp}] ERROR on {endpoint}\n"
        f"Message: {error}\n"
        f"{'=' * 50}\n"
    )
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
