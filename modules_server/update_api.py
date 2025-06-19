#!/usr/bin/env python3
"""
StreamMate AI Update API Server
Simple API untuk melayani informasi update dari website
"""

import json
import os
from datetime import datetime
from flask import Flask, jsonify, request
from pathlib import Path

app = Flask(__name__)

# Configuration
UPDATE_CONFIG_FILE = Path("config/update_config.json")
DOWNLOAD_BASE_URL = "https://drive.google.com/uc?export=download&id="  # Google Drive Business

# Default update configuration
DEFAULT_UPDATE_CONFIG = {
    "latest_version": "1.0.1",
    "download_info": {
        "google_drive_id": "YOUR_GOOGLE_DRIVE_FILE_ID",  # Replace dengan ID file di Google Drive
        "file_size": 52428800,  # 50MB in bytes
        "checksum": "sha256_hash_of_file"
    },
    "changelog": [
        "• Perbaikan sistem update otomatis",
        "• Peningkatan performa download",
        "• Bug fixes pada authentication system",
        "• UI improvements dan optimasi"
    ],
    "release_date": "2025-01-01T12:00:00Z",
    "minimum_version": "1.0.0",  # Minimum version yang masih supported
    "force_update": False,  # Apakah update ini wajib
    "beta_versions": {
        "1.0.2-beta": {
            "download_id": "BETA_FILE_ID",
            "changelog": ["• Beta features", "• Experimental improvements"],
            "release_date": "2025-01-02T12:00:00Z"
        }
    }
}

def load_update_config():
    """Load update configuration"""
    try:
        if UPDATE_CONFIG_FILE.exists():
            with open(UPDATE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Create default config
            UPDATE_CONFIG_FILE.parent.mkdir(exist_ok=True)
            save_update_config(DEFAULT_UPDATE_CONFIG)
            return DEFAULT_UPDATE_CONFIG
    except Exception as e:
        print(f"[UPDATE_API] Error loading config: {e}")
        return DEFAULT_UPDATE_CONFIG

def save_update_config(config):
    """Save update configuration"""
    try:
        UPDATE_CONFIG_FILE.parent.mkdir(exist_ok=True)
        with open(UPDATE_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[UPDATE_API] Error saving config: {e}")

@app.route('/api/version/latest', methods=['GET'])
def get_latest_version():
    """Get latest version information"""
    try:
        config = load_update_config()
        channel = request.args.get('channel', 'stable').lower()
        
        if channel == 'beta' and 'beta_versions' in config:
            # Return latest beta version
            beta_versions = config['beta_versions']
            if beta_versions:
                latest_beta = max(beta_versions.keys())
                beta_info = beta_versions[latest_beta]
                
                return jsonify({
                    "version": latest_beta,
                    "download_url": f"{DOWNLOAD_BASE_URL}{beta_info['download_id']}",
                    "changelog": "\n".join(beta_info.get('changelog', [])),
                    "release_date": beta_info.get('release_date'),
                    "file_size": config['download_info'].get('file_size', 0),
                    "channel": "beta",
                    "force_update": False
                })
        
        # Return stable version
        download_info = config.get('download_info', {})
        return jsonify({
            "version": config.get('latest_version', '1.0.1'),
            "download_url": f"{DOWNLOAD_BASE_URL}{download_info.get('google_drive_id', '')}",
            "changelog": "\n".join(config.get('changelog', [])),
            "release_date": config.get('release_date'),
            "file_size": download_info.get('file_size', 0),
            "checksum": download_info.get('checksum', ''),
            "minimum_version": config.get('minimum_version', '1.0.0'),
            "force_update": config.get('force_update', False),
            "channel": "stable"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/version/check', methods=['POST'])
def check_version():
    """Check if update is available for specific version"""
    try:
        data = request.get_json()
        current_version = data.get('current_version', '1.0.0')
        channel = data.get('channel', 'stable').lower()
        
        config = load_update_config()
        
        if channel == 'beta' and 'beta_versions' in config:
            latest_version = max(config['beta_versions'].keys())
        else:
            latest_version = config.get('latest_version', '1.0.1')
        
        # Simple version comparison (you might want to use proper semver)
        update_available = _is_newer_version(current_version, latest_version)
        
        response = {
            "update_available": update_available,
            "current_version": current_version,
            "latest_version": latest_version,
            "force_update": config.get('force_update', False) and update_available
        }
        
        if update_available:
            # Include download info
            response.update({
                "download_url": f"{DOWNLOAD_BASE_URL}{config['download_info']['google_drive_id']}",
                "changelog": "\n".join(config.get('changelog', [])),
                "file_size": config['download_info'].get('file_size', 0)
            })
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/update', methods=['POST'])
def admin_update_version():
    """Admin endpoint untuk update version info (protected)"""
    try:
        # Basic auth check (implement proper authentication in production)
        auth_token = request.headers.get('Authorization')
        if auth_token != 'Bearer YOUR_ADMIN_SECRET_TOKEN':
            return jsonify({"error": "Unauthorized"}), 401
        
        data = request.get_json()
        config = load_update_config()
        
        # Update version info
        if 'latest_version' in data:
            config['latest_version'] = data['latest_version']
        
        if 'download_info' in data:
            config['download_info'].update(data['download_info'])
        
        if 'changelog' in data:
            config['changelog'] = data['changelog']
        
        if 'release_date' in data:
            config['release_date'] = data['release_date']
        else:
            config['release_date'] = datetime.now().isoformat() + 'Z'
        
        if 'force_update' in data:
            config['force_update'] = data['force_update']
        
        save_update_config(config)
        
        return jsonify({
            "success": True,
            "message": "Update configuration saved",
            "config": config
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats/download', methods=['POST'])
def log_download():
    """Log download statistics"""
    try:
        data = request.get_json()
        
        # Log download info (implement proper logging/analytics)
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "version": data.get('version'),
            "ip": request.remote_addr,
            "user_agent": request.headers.get('User-Agent', ''),
            "client_version": data.get('client_version')
        }
        
        # Save to download log file
        log_file = Path("logs/download_stats.jsonl")
        log_file.parent.mkdir(exist_ok=True)
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        return jsonify({"success": True})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "StreamMate AI Update API"
    })

def _is_newer_version(current, latest):
    """Simple version comparison"""
    try:
        # Remove any non-numeric prefixes/suffixes for comparison
        def parse_version(v):
            return [int(x) for x in v.replace('v', '').split('-')[0].split('.')]
        
        current_parts = parse_version(current)
        latest_parts = parse_version(latest)
        
        # Pad with zeros if lengths differ
        max_len = max(len(current_parts), len(latest_parts))
        current_parts += [0] * (max_len - len(current_parts))
        latest_parts += [0] * (max_len - len(latest_parts))
        
        return latest_parts > current_parts
        
    except Exception:
        # Fallback to string comparison
        return latest > current

if __name__ == '__main__':
    print("[UPDATE_API] Starting StreamMate AI Update API Server...")
    print(f"[UPDATE_API] Config file: {UPDATE_CONFIG_FILE}")
    
    # Create default config if not exists
    if not UPDATE_CONFIG_FILE.exists():
        print("[UPDATE_API] Creating default update configuration...")
        save_update_config(DEFAULT_UPDATE_CONFIG)
    
    # Run server
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('DEBUG', 'False').lower() == 'true'
    ) 