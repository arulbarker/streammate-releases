#!/usr/bin/env python3
"""
Debug script untuk memeriksa status license validation
Gunakan untuk troubleshoot "No valid license" issue
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

# Add current directory to path
sys.path.insert(0, os.getcwd())

def check_subscription_file():
    """Check subscription status file"""
    print("=" * 60)
    print("🔍 CHECKING SUBSCRIPTION STATUS FILE")
    print("=" * 60)
    
    sub_file = Path("config/subscription_status.json")
    if not sub_file.exists():
        print("❌ File config/subscription_status.json TIDAK DITEMUKAN!")
        return None
        
    try:
        with open(sub_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        print(f"✅ File ditemukan dan berhasil dibaca")
        print(f"📧 Email: {data.get('email', 'N/A')}")
        print(f"📊 Status: {data.get('status', 'N/A')}")
        print(f"📦 Package: {data.get('package', 'N/A')}")
        print(f"💰 Credit Balance: {data.get('credit_balance', data.get('hours_credit', 'N/A'))}")
        print(f"📈 Credit Used: {data.get('credit_used', data.get('hours_used', 'N/A'))}")
        print(f"🎯 Tier: {data.get('tier', 'N/A')}")
        print(f"✅ Is Valid: {data.get('is_valid', 'N/A')}")
        print(f"📅 Expire Date: {data.get('expire_date', 'N/A')}")
        print(f"🔄 Last Sync: {data.get('last_sync', 'N/A')}")
        
        return data
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return None

def test_license_validator():
    """Test license validator directly"""
    print("\n" + "=" * 60)
    print("🔍 TESTING LICENSE VALIDATOR")
    print("=" * 60)
    
    try:
        from modules_server.license_validator import LicenseValidator
        
        validator = LicenseValidator()
        print("✅ LicenseValidator imported successfully")
        
        # Test validation
        print("🔄 Running license validation...")
        result = validator.validate(force_refresh=False)
        
        print(f"📋 Validation Result:")
        for key, value in result.items():
            print(f"  {key}: {value}")
            
        return result
        
    except Exception as e:
        print(f"❌ Error testing license validator: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_main_window_status():
    """Test main window license status update"""
    print("\n" + "=" * 60)
    print("🔍 TESTING MAIN WINDOW LICENSE STATUS")
    print("=" * 60)
    
    try:
        # Test if we can import and run the license status code
        from modules_client.config_manager import ConfigManager
        from modules_server.license_validator import LicenseValidator
        from datetime import datetime
        
        cfg = ConfigManager("config/settings.json")
        validator = LicenseValidator()
        
        print("✅ Components imported successfully")
        
        # Simulate the license check from main window
        print("🔄 Simulating main window license check...")
        
        try:
            license_data = validator.validate(force_refresh=True)
            print(f"📋 License Data: {license_data}")
        except Exception as e:
            print(f"❌ License validation failed: {e}")
            # Fallback mode
            license_data = {
                "is_valid": True,
                "tier": "basic",
                "expire_date": "2025-12-31",
                "offline_mode": True
            }
            print(f"🔄 Using fallback data: {license_data}")

        # 🔧 PERBAIKAN: Use the same logic as fixed main window
        is_license_valid = False
        tier = "Basic"
        expire_date = None
        
        # Format 1: Direct is_valid field (fallback mode)
        if license_data.get("is_valid", False):
            is_license_valid = True
            tier = license_data.get("tier", "basic").title()
            expire_date = license_data.get("expire_date", "Unknown")
            print(f"✅ License valid (Direct format)")
        
        # Format 2: VPS server response dengan data.is_active
        elif license_data.get("status") == "success" and license_data.get("data", {}).get("is_active", False):
            is_license_valid = True
            vps_data = license_data.get("data", {})
            tier = vps_data.get("tier", "basic").title()
            expire_date = vps_data.get("expire_date", "Unknown")
            print(f"✅ License valid (VPS server format)")
        
        # Format 3: Check subscription file directly sebagai fallback
        elif not is_license_valid:
            try:
                from pathlib import Path
                import json
                sub_file = Path("config/subscription_status.json")
                if sub_file.exists():
                    with open(sub_file, 'r', encoding='utf-8') as f:
                        sub_data = json.load(f)
                    if sub_data.get("is_valid", False) and sub_data.get("status") == "active":
                        is_license_valid = True
                        tier = sub_data.get("tier", "basic").title()
                        expire_date = sub_data.get("expire_date")
                        print(f"✅ License valid (Subscription file fallback)")
            except Exception as fallback_error:
                print(f"❌ Fallback check failed: {fallback_error}")

        if is_license_valid:
            print(f"✅ License IS VALID")
            print(f"🎯 Tier: {tier}")
            print(f"📅 Expire Date: {expire_date}")
            
            if expire_date and expire_date != "Unknown" and expire_date:
                try:
                    expire_dt = datetime.fromisoformat(expire_date)
                    days_left = (expire_dt - datetime.now()).days
                    print(f"⏰ Days left: {days_left}")
                    
                    status_text = f"🔑 {tier} - {days_left} days"
                    if license_data.get("offline_mode"):
                        status_text += " (Offline)"
                    
                    print(f"📺 Status Text: {status_text}")
                    
                except Exception as e:
                    print(f"❌ Error parsing expire date: {e}")
                    status_text = f"🔑 {tier} - Expires: {expire_date}"
                    print(f"📺 Status Text: {status_text}")
            else:
                # Credit-based license tanpa expire date
                status_text = f"🔑 {tier}"
                if license_data.get("offline_mode"):
                    status_text += " (Offline)"
                print(f"📺 Status Text: {status_text}")
        else:
            print(f"❌ License IS NOT VALID")
            print(f"📺 Status Text: ❌ No valid license")
            
    except Exception as e:
        print(f"❌ Error testing main window status: {e}")
        import traceback
        traceback.print_exc()

def check_config_files():
    """Check other config files that might affect license"""
    print("\n" + "=" * 60)
    print("🔍 CHECKING OTHER CONFIG FILES")
    print("=" * 60)
    
    config_files = [
        "config/settings.json",
        "config/google_token.json",
        "config/live_state.json"
    ]
    
    for config_file in config_files:
        file_path = Path(config_file)
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"✅ {config_file}: OK (size: {len(str(data))} chars)")
                
                # Check specific fields for settings.json
                if config_file == "config/settings.json":
                    user_data = data.get("user_data", {})
                    email = user_data.get("email", "")
                    print(f"  📧 Email in settings: {email}")
                    
            except Exception as e:
                print(f"❌ {config_file}: Error - {e}")
        else:
            print(f"⚠️ {config_file}: Not found")

def main():
    """Main debug function"""
    print("🔧 StreamMateAI License Debug Tool")
    print("📅 " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # 1. Check subscription file
    sub_data = check_subscription_file()
    
    # 2. Check config files
    check_config_files()
    
    # 3. Test license validator
    license_result = test_license_validator()
    
    # 4. Test main window status
    test_main_window_status()
    
    # 5. Summary
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    
    if sub_data and sub_data.get("is_valid", False):
        print("✅ Subscription file shows VALID license")
    else:
        print("❌ Subscription file shows INVALID license")
        
    if license_result and license_result.get("is_valid", False):
        print("✅ License validator returns VALID")
    else:
        print("❌ License validator returns INVALID")
        
    print("\n🔧 RECOMMENDED ACTIONS:")
    print("1. Restart aplikasi StreamMateAI")
    print("2. Jika masih muncul 'No valid license', jalankan:")
    print("   python fix_license_display.py")
    print("3. Check log console saat aplikasi startup")

if __name__ == "__main__":
    main() 