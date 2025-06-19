"""
Runtime hook for pytchat initialization in EXE mode
"""
import os
import sys
from pathlib import Path

# Set environment variables for pytchat
os.environ['PYTCHAT_NO_BROWSER'] = '1'
os.environ['PYTCHAT_BROWSER'] = 'no_browser'
os.environ['PYTCHAT_QUIET'] = '1'
os.environ['HTTPX_DISABLE_HTTP2'] = '1'

print("[RUNTIME] PyTchat environment configured")

# Add pytchat paths for EXE mode
if getattr(sys, 'frozen', False):
    app_dir = Path(sys.executable).parent
    
    pytchat_paths = [
        app_dir / "_internal" / "pytchat",
        app_dir / "_internal" / "pytchat_ng", 
        app_dir / "thirdparty" / "pytchat_ng",
        app_dir / "thirdparty" / "pytchat",
    ]
    
    for path in pytchat_paths:
        if path.exists() and str(path) not in sys.path:
            sys.path.insert(0, str(path))
            print(f"[RUNTIME] Added pytchat path: {path}")
