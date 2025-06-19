#!/usr/bin/env python3
"""
StreamMate AI Development Server
Server untuk development dan testing fitur baru
"""

import os
import sys
import json
import uvicorn
from pathlib import Path

# Set development environment
os.environ["STREAMMATE_ENV"] = "development"
os.environ["STREAMMATE_DEBUG"] = "true"

def load_dev_config():
    """Load development configuration"""
    config_path = Path("config/development_config.json")
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}

def setup_dev_environment():
    """Setup development environment variables"""
    config = load_dev_config()
    
    # Set environment variables from config
    if 'security' in config:
        os.environ["STREAMMATE_ADMIN_KEY"] = config['security'].get('admin_key', 'dev_admin_2025')
    
    if 'payment' in config:
        os.environ["IPAYMU_MODE"] = config['payment'].get('mode', 'sandbox')
    
    if 'database' in config:
        os.environ["DEV_DB_PATH"] = config['database'].get('path', 'data/license_data_dev.db')
    
    print("🔧 Development environment configured")
    print(f"📊 Admin Key: {os.environ.get('STREAMMATE_ADMIN_KEY', 'default')}")
    print(f"💳 Payment Mode: {os.environ.get('IPAYMU_MODE', 'sandbox')}")
    print(f"🗄️ Database: {os.environ.get('DEV_DB_PATH', 'default')}")

def main():
    """Main development server function"""
    print("🚀 Starting StreamMate AI Development Server")
    print("=" * 50)
    
    # Setup development environment
    setup_dev_environment()
    
    # Load configuration
    config = load_dev_config()
    server_config = config.get('server', {})
    
    host = server_config.get('host', 'localhost')
    port = server_config.get('port', 8001)
    debug = server_config.get('debug', True)
    auto_reload = server_config.get('auto_reload', True)
    
    print(f"🌐 Server URL: http://{host}:{port}")
    print(f"🔧 Debug Mode: {debug}")
    print(f"🔄 Auto Reload: {auto_reload}")
    print("=" * 50)
    
    # Import and run the server
    try:
        # Import server_inti after environment setup
        from server_inti import app
        
        # Run development server
        uvicorn.run(
            "server_inti:app",
            host=host,
            port=port,
            reload=auto_reload,
            log_level="debug" if debug else "info",
            access_log=True
        )
        
    except ImportError as e:
        print(f"❌ Error importing server: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting development server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 