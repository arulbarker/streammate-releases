#!/usr/bin/env python3
"""
Script untuk clean restart aplikasi dengan license fix
"""

import os
import sys
import json
import time
from pathlib import Path
import subprocess

def clean_license_cache():
    """Clean license cache files"""
    print("🧹 CLEANING LICENSE CACHE...")
    
    cache_files = [
        "temp/license_cache.json",
        "temp/vps_cache.json",
        "temp/license_validator_cache.json"
    ]
    
    cleaned = 0
    for cache_file in cache_files:
        file_path = Path(cache_file)
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"  ✅ Deleted: {cache_file}")
                cleaned += 1
            except Exception as e:
                print(f"  ❌ Failed to delete {cache_file}: {e}")
        else:
            print(f"  ⏭️ Not found: {cache_file}")
    
    print(f"🧹 Cleaned {cleaned} cache files")

def verify_subscription_status():
    """Verify subscription status is valid"""
    print("\n📋 VERIFYING SUBSCRIPTION STATUS...")
    
    sub_file = Path("config/subscription_status.json")
    if not sub_file.exists():
        print("❌ Subscription file not found!")
        return False
    
    try:
        with open(sub_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        is_valid = data.get("is_valid", False)
        status = data.get("status", "")
        credits = data.get("credit_balance", data.get("hours_credit", 0))
        
        print(f"  📧 Email: {data.get('email', 'N/A')}")
        print(f"  ✅ Is Valid: {is_valid}")
        print(f"  📊 Status: {status}")
        print(f"  💰 Credits: {credits}")
        
        if is_valid and status == "active" and credits > 0:
            print("✅ Subscription status VALID!")
            return True
        else:
            print("❌ Subscription status INVALID!")
            return False
            
    except Exception as e:
        print(f"❌ Error reading subscription file: {e}")
        return False

def check_main_window_fix():
    """Check if main window has been fixed"""
    print("\n🔧 CHECKING MAIN WINDOW FIX...")
    
    main_window_file = Path("ui/main_window.py")
    if not main_window_file.exists():
        print("❌ Main window file not found!")
        return False
    
    try:
        with open(main_window_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for the fix
        has_vps_format_check = 'license_data.get("data", {}).get("is_active", False)' in content
        has_fallback_check = 'sub_data.get("is_valid", False) and sub_data.get("status") == "active"' in content
        
        if has_vps_format_check and has_fallback_check:
            print("✅ Main window license fix APPLIED!")
            return True
        else:
            print("❌ Main window license fix NOT applied!")
            print(f"  VPS format check: {has_vps_format_check}")
            print(f"  Fallback check: {has_fallback_check}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking main window: {e}")
        return False

def create_app_start_script():
    """Create script to start the app"""
    print("\n📝 CREATING APP START SCRIPT...")
    
    if os.name == 'nt':  # Windows
        script_content = '''@echo off
echo Starting StreamMateAI with license fix...
python main.py
pause
'''
        script_file = "start_streammate.bat"
    else:  # Linux/Mac
        script_content = '''#!/bin/bash
echo "Starting StreamMateAI with license fix..."
python main.py
read -p "Press Enter to continue..."
'''
        script_file = "start_streammate.sh"
    
    try:
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # Make executable on Unix systems
        if os.name != 'nt':
            os.chmod(script_file, 0o755)
        
        print(f"✅ Created: {script_file}")
        return script_file
    except Exception as e:
        print(f"❌ Error creating start script: {e}")
        return None

def main():
    """Main function"""
    print("🔧 StreamMateAI Clean Restart Tool")
    print("📅 Fixing 'No valid license' display issue")
    print("=" * 60)
    
    # 1. Clean cache
    clean_license_cache()
    
    # 2. Verify subscription
    if not verify_subscription_status():
        print("\n❌ SUBSCRIPTION ISSUE DETECTED!")
        print("Please check your subscription status first.")
        return
    
    # 3. Check fix
    if not check_main_window_fix():
        print("\n❌ MAIN WINDOW FIX NOT APPLIED!")
        print("Please run: python fix_license_display.py")
        return
    
    # 4. Create start script
    start_script = create_app_start_script()
    
    # 5. Summary
    print("\n" + "=" * 60)
    print("📋 CLEAN RESTART SUMMARY")
    print("=" * 60)
    print("✅ License cache cleaned")
    print("✅ Subscription status verified")
    print("✅ Main window fix confirmed")
    print("✅ Start script created")
    
    print("\n🎉 READY TO RESTART!")
    print("=" * 60)
    print("📝 LANGKAH SELANJUTNYA:")
    if start_script:
        print(f"1. ✅ Jalankan: {start_script}")
    else:
        print("1. ✅ Jalankan: python main.py")
    print("2. ✅ Check status bar di bawah kanan")
    print("3. ✅ Seharusnya muncul: '🔑 Basic'")
    print("4. ✅ Tidak lagi 'No valid license'")
    
    print("\n💡 CATATAN:")
    print("- License Anda sudah VALID")
    print("- Masalah display sudah diperbaiki")
    print("- Aplikasi siap digunakan")
    
    # Option to start immediately
    if os.name == 'nt':  # Windows
        try:
            choice = input("\n🚀 Start aplikasi sekarang? (y/n): ").lower().strip()
            if choice in ['y', 'yes', 'ya']:
                print("🚀 Starting StreamMateAI...")
                subprocess.Popen([sys.executable, "main.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                print("✅ Aplikasi dimulai di window baru!")
        except KeyboardInterrupt:
            print("\n👋 Cancelled by user")

if __name__ == "__main__":
    main() 