#!/usr/bin/env python3
"""
Windows SmartScreen Fix untuk StreamMateAI
Script untuk mengatasi warning Windows Defender SmartScreen
"""

import os
import sys
import subprocess
from pathlib import Path
import shutil

def check_signing_tools():
    """Check apakah signing tools tersedia"""
    print("[CHECK] Checking code signing tools availability...")
    
    tools = {
        'signtool.exe': 'Windows SDK SignTool',
        'makecert.exe': 'Certificate creation tool',
        'pvk2pfx.exe': 'Private key to PFX converter'
    }
    
    found_tools = {}
    
    # Check di common locations
    search_paths = [
        r'C:\Program Files (x86)\Windows Kits\10\bin',
        r'C:\Program Files\Windows Kits\10\bin',
        r'C:\Program Files (x86)\Microsoft SDKs\Windows',
        r'C:\Program Files\Microsoft SDKs\Windows'
    ]
    
    for tool, description in tools.items():
        found = False
        for search_path in search_paths:
            for root, dirs, files in os.walk(search_path):
                if tool in files:
                    tool_path = os.path.join(root, tool)
                    found_tools[tool] = tool_path
                    print(f"  ✅ Found {tool}: {tool_path}")
                    found = True
                    break
            if found:
                break
        
        if not found:
            print(f"  ❌ {tool} not found ({description})")
    
    return found_tools

def create_self_signed_certificate():
    """Create self-signed certificate for code signing"""
    print("[CERT] Creating self-signed certificate...")
    
    cert_name = "StreamMateAI"
    cert_path = f"{cert_name}.pfx"
    
    if Path(cert_path).exists():
        print(f"  ✅ Certificate {cert_path} already exists")
        return cert_path
    
    # PowerShell command untuk membuat self-signed certificate
    powershell_cmd = f'''
$cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN={cert_name}" -KeyUsage DigitalSignature -FriendlyName "{cert_name}" -CertStoreLocation "Cert:\\CurrentUser\\My" -TextExtension @("2.5.29.37={{text}}1.3.6.1.5.5.7.3.3", "2.5.29.19={{text}}")
$password = ConvertTo-SecureString -String "{cert_name}123" -Force -AsPlainText
Export-PfxCertificate -cert "Cert:\\CurrentUser\\My\\$($cert.Thumbprint)" -FilePath "{cert_path}" -Password $password
'''
    
    try:
        # Run PowerShell command
        result = subprocess.run([
            'powershell', '-ExecutionPolicy', 'Bypass', '-Command', powershell_cmd
        ], capture_output=True, text=True, shell=True)
        
        if result.returncode == 0 and Path(cert_path).exists():
            print(f"  ✅ Self-signed certificate created: {cert_path}")
            print(f"  🔑 Certificate password: {cert_name}123")
            return cert_path
        else:
            print(f"  ❌ Failed to create certificate: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"  ❌ Error creating certificate: {e}")
        return None

def sign_exe_file(exe_path, cert_path):
    """Sign EXE file with certificate"""
    print(f"[SIGN] Signing {exe_path}...")
    
    # Find signtool.exe
    tools = check_signing_tools()
    signtool = tools.get('signtool.exe')
    
    if not signtool:
        print("  ❌ SignTool not found. Please install Windows SDK")
        return False
    
    if not Path(exe_path).exists():
        print(f"  ❌ EXE file not found: {exe_path}")
        return False
    
    if not Path(cert_path).exists():
        print(f"  ❌ Certificate file not found: {cert_path}")
        return False
    
    # Sign command
    cert_password = "StreamMateAI123"  # Default password
    sign_cmd = [
        signtool, 'sign',
        '/f', cert_path,
        '/p', cert_password,
        '/t', 'http://timestamp.sectigo.com',  # Timestamp server
        '/v',  # Verbose
        exe_path
    ]
    
    try:
        result = subprocess.run(sign_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"  ✅ Successfully signed: {exe_path}")
            print("  📋 Signature details:")
            print(result.stdout)
            return True
        else:
            print(f"  ❌ Signing failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"  ❌ Error during signing: {e}")
        return False

def verify_exe_signature(exe_path):
    """Verify EXE signature"""
    print(f"[VERIFY] Verifying signature for {exe_path}...")
    
    tools = check_signing_tools()
    signtool = tools.get('signtool.exe')
    
    if not signtool:
        print("  ❌ SignTool not found")
        return False
    
    verify_cmd = [signtool, 'verify', '/pa', '/v', exe_path]
    
    try:
        result = subprocess.run(verify_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("  ✅ Signature verification successful")
            print(result.stdout)
            return True
        else:
            print("  ⚠️ Signature verification failed or warnings:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"  ❌ Error during verification: {e}")
        return False

def update_build_spec_for_signing():
    """Update .spec file untuk mendukung signing"""
    print("[UPDATE] Updating build spec for signing...")
    
    spec_file = "StreamMateAI_Production.spec"
    if not Path(spec_file).exists():
        print(f"  ❌ Spec file not found: {spec_file}")
        return False
    
    # Read current spec
    with open(spec_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Update codesign_identity
    if 'codesign_identity=None' in content:
        content = content.replace('codesign_identity=None', 'codesign_identity="StreamMateAI"')
        print("  ✅ Updated codesign_identity")
    
    # Add version info if not present
    version_info = '''
version_info = {
    'version': '1.0.0.0',
    'company_name': 'StreamMateAI',
    'file_description': 'StreamMateAI - AI-powered streaming assistant',
    'internal_name': 'StreamMateAI',
    'legal_copyright': 'Copyright © 2024 StreamMateAI',
    'original_filename': 'StreamMateAI_Production.exe',
    'product_name': 'StreamMateAI',
    'product_version': '1.0.0.0',
}
'''
    
    if 'version_info' not in content:
        # Add version info before exe = EXE
        exe_pos = content.find('exe = EXE(')
        if exe_pos != -1:
            content = content[:exe_pos] + version_info + '\n' + content[exe_pos:]
            
            # Add version_info parameter to EXE
            content = content.replace(
                'icon=\'icon.ico\',',
                'icon=\'icon.ico\',\n    version=version_info,'
            )
            print("  ✅ Added version information")
    
    # Write updated spec
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  ✅ Updated {spec_file}")
    return True

def create_smartscreen_bypass_guide():
    """Create guide untuk bypass SmartScreen"""
    guide_content = '''# Windows SmartScreen Bypass Guide

## Untuk Developer (Anda):

### 1. Code Signing (Recommended)
- Beli certificate dari CA terpercaya (Sectigo, DigiCert, dll) - $200-500/tahun
- Atau gunakan self-signed certificate (untuk testing)
- Run: python fix_smartscreen_issue.py

### 2. Build Reputation
- Upload exe ke VirusTotal
- Distribute ke beberapa user untuk build reputation
- Microsoft akan mengurangi warning setelah cukup user download

### 3. Alternative Distribution
- Compress dalam ZIP/RAR
- Upload ke GitHub Releases
- Provide clear installation instructions

## Untuk End User:

### Cara 1: Click "More info" → "Run anyway"
1. Saat muncul SmartScreen warning
2. Click "More info"
3. Click "Run anyway"

### Cara 2: Add to Windows Defender Exclusion
1. Windows Security → Virus & threat protection
2. Manage settings → Add or remove exclusions
3. Add folder atau file exe

### Cara 3: Disable SmartScreen (Not recommended)
1. Windows Settings → Privacy & Security → Windows Security
2. App & browser control → Reputation-based protection
3. Turn off SmartScreen

### Cara 4: Properties → Unblock
1. Right-click exe file → Properties
2. Check "Unblock" di bagian bawah
3. Click OK

## Notes:
- SmartScreen warning normal untuk aplikasi baru/tidak dikenal
- Signing dengan certificate terpercaya adalah solusi terbaik
- Self-signed certificate masih akan show warning tapi lebih mudah dibypass
'''
    
    with open('SMARTSCREEN_BYPASS_GUIDE.md', 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    print("  ✅ Created SMARTSCREEN_BYPASS_GUIDE.md")

def main():
    """Main function untuk fix SmartScreen issue"""
    print("=" * 60)
    print("🛡️  Windows SmartScreen Fix untuk StreamMateAI")
    print("=" * 60)
    
    # Check if running as admin
    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    
    if not is_admin:
        print("⚠️  Recommended to run as Administrator for certificate creation")
    
    # 1. Check tools
    tools = check_signing_tools()
    
    # 2. Update build spec
    update_build_spec_for_signing()
    
    # 3. Create certificate
    cert_path = create_self_signed_certificate()
    
    # 4. Find and sign exe if exists
    exe_candidates = [
        "dist/StreamMateAI_Production.exe",
        "StreamMateAI_Production.exe",
        "dist/main.exe",
        "main.exe"
    ]
    
    signed_any = False
    for exe_path in exe_candidates:
        if Path(exe_path).exists():
            if cert_path and tools.get('signtool.exe'):
                if sign_exe_file(exe_path, cert_path):
                    verify_exe_signature(exe_path)
                    signed_any = True
            else:
                print(f"  ⚠️  Found {exe_path} but cannot sign (missing tools or certificate)")
    
    if not signed_any:
        print("  ℹ️  No existing exe found to sign. Build exe first, then run this script again.")
    
    # 5. Create user guide
    create_smartscreen_bypass_guide()
    
    print("\n" + "=" * 60)
    print("📋 SUMMARY:")
    print("=" * 60)
    
    if cert_path:
        print(f"✅ Certificate created: {cert_path}")
    if signed_any:
        print("✅ EXE files signed successfully")
    print("✅ Build spec updated for signing")
    print("✅ User guide created: SMARTSCREEN_BYPASS_GUIDE.md")
    
    print("\n🔧 NEXT STEPS:")
    print("1. Rebuild exe: python build_production_exe_fixed.py")
    print("2. Sign exe: python fix_smartscreen_issue.py")
    print("3. Test on different machines")
    print("4. Consider purchasing real certificate for production")
    
    print("\n💡 USER INSTRUCTIONS:")
    print("Tell your users to click 'More info' → 'Run anyway' when SmartScreen appears")
    print("Or refer them to SMARTSCREEN_BYPASS_GUIDE.md")

if __name__ == "__main__":
    main() 