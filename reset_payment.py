#!/usr/bin/env python3
# reset_payment.py
from pathlib import Path
import json
import os
import time

def reset_payment_state():
    """Reset status pembayaran untuk testing."""
    sub_status_path = Path("config/subscription_status.json")
    
    # Backup file lama jika ada
    if sub_status_path.exists():
        backup_path = Path(f"config/subscription_status.backup_{int(time.time())}.json")
        import shutil
        shutil.copy2(sub_status_path, backup_path)
        print(f"Backup created: {backup_path}")
        
        # Reset ke status pending
        try:
            with open(sub_status_path, "r+") as f:
                data = json.load(f)
                data["status"] = "pending"
                data["transaction_status"] = "pending"
                data["hours_credit"] = 0
                data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
                
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
            
            print("Reset subscription status to pending")
        except Exception as e:
            print(f"Error resetting subscription status: {e}")
    else:
        print("No subscription status file found")
    
    # Check if payment server is running
    import socket
    server_running = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            server_running = s.connect_ex(('localhost', 5005)) == 0
        
        if server_running:
            print("Payment server is running")
        else:
            print("Payment server is not running")
            
            # Ask to start server
            answer = input("Start payment server? (y/n): ")
            if answer.lower() == 'y':
                import subprocess, sys
                server_path = Path("payment_server.py")
                if server_path.exists():
                    if os.name == 'nt':  # Windows
                        subprocess.Popen([sys.executable, str(server_path)], 
                                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
                    else:  # Unix
                        subprocess.Popen([sys.executable, str(server_path)], 
                                         start_new_session=True)
                    print("Server started")
                else:
                    print("Server file not found")
                    
    except Exception as e:
        print(f"Error checking server status: {e}")

if __name__ == "__main__":
    reset_payment_state()
    print("Done!")