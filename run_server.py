# run_server.py
import sys
import os

# Tambahkan root folder ke Python path
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# Import dan jalankan server
if __name__ == "__main__":
    from modules_server.server import app
    import uvicorn
    
    print("🚀 Starting StreamMate AI Server...")
    print(f"📁 Root directory: {ROOT}")
    print("🌐 Server will be available at: http://localhost:8000")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
    