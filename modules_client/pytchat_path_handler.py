"""Auto-import pytchat for frozen exe"""
import sys
from pathlib import Path

# Get correct path
if getattr(sys, 'frozen', False):
    app_path = Path(sys.executable).parent
else:
    app_path = Path(__file__).resolve().parent.parent

# Add all possible pytchat paths
pytchat_paths = [
    app_path / "thirdparty" / "pytchat_ng",
    app_path / "thirdparty" / "pytchat",
    app_path / "_internal" / "pytchat",
]

for p in pytchat_paths:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
