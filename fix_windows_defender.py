#!/usr/bin/env python3
"""
Fix Windows Defender Issues - StreamMateAI v1.0.9
Multiple approaches to reduce false positive detection
"""

import os
import sys
import subprocess
import shutil
import hashlib
from pathlib import Path
import json
import time

def check_admin():
    """Check if running as administrator"""
    try:
        return os.getuid() == 0
    except AttributeError:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0

def create_enhanced_certificate():
    """Create enhanced self-signed certificate with better attributes"""
    print("[CERT] Creating enhanced certificate for better Windows trust...")
    
    # Enhanced PowerShell script for certificate creation
    cert_script = '''
# Enhanced Certificate Creation for StreamMateAI
$ErrorActionPreference = "Stop"

try {
    # Create enhanced certificate with better attributes
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject "CN=StreamMate AI, O=StreamMate AI Technologies, C=US" `
        -KeyUsage DigitalSignature `
        -FriendlyName "StreamMate AI Code Signing Certificate" `
        -CertStoreLocation "Cert:\\CurrentUser\\My" `
        -KeyLength 2048 `
        -KeyAlgorithm RSA `
        -HashAlgorithm SHA256 `
        -NotAfter (Get-Date).AddYears(3) `
        -KeyExportPolicy Exportable
    
    # Export to PFX with strong password
    $password = ConvertTo-SecureString -String "StreamMateAI2024!" -Force -AsPlainText
    $pfxPath = "StreamMateAI_Enhanced.pfx"
    
    Export-PfxCertificate -cert "Cert:\\CurrentUser\\My\\$($cert.Thumbprint)" -FilePath $pfxPath -Password $password
    
    Write-Host "✅ Enhanced certificate created successfully"
    Write-Host "📁 File: $pfxPath"
    Write-Host "🔑 Password: StreamMateAI2024!"
    Write-Host "👤 Thumbprint: $($cert.Thumbprint)"
    
    # Try to install to trusted root (requires admin)
    try {
        $store = New-Object System.Security.Cryptography.X509Certificates.X509Store([System.Security.Cryptography.X509Certificates.StoreName]::Root, [System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine)
        $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
        $store.Add($cert)
        $store.Close()
        Write-Host "✅ Certificate installed to Trusted Root (Admin mode)"
    } catch {
        Write-Host "⚠️ Could not install to Trusted Root (need admin): $($_.Exception.Message)"
    }
    
} catch {
    Write-Host "❌ Certificate creation failed: $($_.Exception.Message)"
    exit 1
}
'''
    
    # Write and execute PowerShell script
    script_path = Path("create_enhanced_cert.ps1")
    script_path.write_text(cert_script, encoding='utf-8')
    
    try:
        result = subprocess.run([
            "powershell", "-ExecutionPolicy", "Bypass", "-File", str(script_path)
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ Enhanced certificate created successfully")
            print(result.stdout)
            return True
        else:
            print(f"❌ Certificate creation failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating certificate: {e}")
        return False
    finally:
        # Cleanup script file
        if script_path.exists():
            script_path.unlink()

def sign_executable_enhanced():
    """Sign executable with enhanced certificate"""
    print("[SIGN] Signing executable with enhanced certificate...")
    
    exe_path = Path("dist/StreamMateAI_Production.exe")
    cert_path = Path("StreamMateAI_Enhanced.pfx")
    
    if not exe_path.exists():
        print(f"❌ EXE not found: {exe_path}")
        return False
    
    if not cert_path.exists():
        print(f"❌ Certificate not found: {cert_path}")
        return False
    
    # Try multiple signtool locations
    signtool_paths = [
        "signtool.exe",  # If in PATH
        "C:\\Program Files (x86)\\Windows Kits\\10\\bin\\10.0.22621.0\\x64\\signtool.exe",
        "C:\\Program Files (x86)\\Windows Kits\\10\\bin\\10.0.19041.0\\x64\\signtool.exe",
        "C:\\Program Files (x86)\\Microsoft SDKs\\Windows\\v10.0A\\bin\\NETFX 4.8 Tools\\signtool.exe"
    ]
    
    signtool_path = None
    for path in signtool_paths:
        if Path(path).exists():
            signtool_path = path
            break
        try:
            subprocess.run([path, "/?"], capture_output=True, timeout=5)
            signtool_path = path
            break
        except:
            continue
    
    if not signtool_path:
        print("❌ signtool.exe not found. Please install Windows SDK")
        print("💡 Download from: https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/")
        return False
    
    print(f"✅ Found signtool: {signtool_path}")
    
    # Sign with enhanced parameters
    sign_cmd = [
        signtool_path, "sign",
        "/f", str(cert_path),
        "/p", "StreamMateAI2024!",
        "/t", "http://timestamp.sectigo.com",  # Timestamp server
        "/fd", "SHA256",  # File digest algorithm
        "/tr", "http://timestamp.sectigo.com",  # RFC3161 timestamp server
        "/td", "SHA256",  # Timestamp digest algorithm
        "/d", "StreamMate AI - Live Stream Assistant",  # Description
        "/du", "https://github.com/arulbarker/streammate-releases",  # URL
        "/v",  # Verbose
        str(exe_path)
    ]
    
    try:
        result = subprocess.run(sign_cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print("✅ Executable signed successfully!")
            print("✅ Enhanced signing with SHA256 and RFC3161 timestamp")
            return True
        else:
            print(f"❌ Signing failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error signing executable: {e}")
        return False

def create_reputation_builder():
    """Create files to help build Windows reputation"""
    print("[REP] Creating reputation building files...")
    
    # Create VirusTotal submission info
    vt_info = {
        "name": "StreamMateAI_Production.exe",
        "version": "1.0.9",
        "publisher": "StreamMate AI Technologies",
        "description": "Live Stream Assistant for YouTube and TikTok",
        "website": "https://github.com/arulbarker/streammate-releases",
        "submission_notes": "Legitimate application for live streaming assistance. Self-signed certificate due to indie development."
    }
    
    Path("virustotal_submission.json").write_text(
        json.dumps(vt_info, indent=2), encoding='utf-8'
    )
    
    # Create Windows Defender submission template
    defender_template = """
Windows Defender False Positive Submission Template:

Application Name: StreamMate AI
Version: 1.0.9
File Name: StreamMateAI_Production.exe
File Hash (SHA256): [Will be calculated]
Publisher: StreamMate AI Technologies
Website: https://github.com/arulbarker/streammate-releases

Description:
StreamMate AI is a legitimate live streaming assistant application for YouTube and TikTok content creators. 
It provides features like:
- Speech-to-text transcription
- AI-powered chat responses  
- Text-to-speech functionality
- Live chat monitoring

The application is built with Python and PyInstaller, which may trigger heuristic detection.
It uses self-signed certificate as it's an independent developer project.

The application does NOT:
- Access sensitive system files
- Modify system settings without permission
- Communicate with malicious servers
- Contain any malware or viruses

Please whitelist this application as it's a false positive detection.
"""
    
    Path("defender_submission_template.txt").write_text(defender_template, encoding='utf-8')
    
    print("✅ Created reputation building files")
    print("  📁 virustotal_submission.json")
    print("  📁 defender_submission_template.txt")

def create_user_whitelist_guide():
    """Create guide for users to whitelist the application"""
    print("[GUIDE] Creating user whitelist guide...")
    
    guide_content = """# Windows Defender Whitelist Guide - StreamMate AI v1.0.9

## 🛡️ Why is Windows Defender blocking StreamMateAI?

Windows Defender may flag StreamMateAI as potentially unwanted software because:
1. **New Application**: Not yet established in Microsoft's reputation database
2. **Self-Signed Certificate**: Uses self-signed certificate (common for indie developers)
3. **PyInstaller Detection**: Built with PyInstaller, which some antivirus flag heuristically

**StreamMateAI is 100% SAFE and LEGITIMATE software.**

## ✅ How to Whitelist StreamMateAI

### Method 1: Windows Security Exclusion (Recommended)

1. **Open Windows Security**
   - Press `Windows + I` → Go to "Update & Security" → "Windows Security"
   - Or search "Windows Security" in Start menu

2. **Add Exclusion**
   - Click "Virus & threat protection"
   - Click "Manage settings" under "Virus & threat protection settings"
   - Scroll down to "Exclusions" and click "Add or remove exclusions"
   - Click "Add an exclusion" → "Folder"
   - Browse and select your StreamMateAI folder

3. **Verify Exclusion**
   - The folder should appear in exclusions list
   - StreamMateAI will no longer be scanned

### Method 2: Allow Through SmartScreen

When you first run StreamMateAI.exe:

1. **SmartScreen Warning Appears**
   - Click "More info" link
   - Click "Run anyway" button
   - Windows will remember this choice

### Method 3: Temporarily Disable Real-time Protection

**⚠️ Only if other methods don't work:**

1. Open Windows Security → Virus & threat protection
2. Turn OFF "Real-time protection" temporarily
3. Run StreamMateAI.exe
4. Turn ON "Real-time protection" again
5. Add exclusion using Method 1

## 🔒 Certificate Information

- **Publisher**: StreamMate AI Technologies
- **Certificate Type**: Self-signed (Enhanced SHA256)
- **Valid Until**: 3 years from issue date
- **Thumbprint**: [Check certificate properties]

## 📋 Application Safety Verification

You can verify StreamMateAI safety by:

1. **Check File Hash**:
   ```
   certutil -hashfile StreamMateAI.exe SHA256
   ```
   Expected: [Hash from release notes]

2. **Scan with Multiple Engines**:
   - Upload to VirusTotal.com
   - Use Malwarebytes
   - Use other trusted scanners

3. **Check Network Activity**:
   - Only connects to legitimate services:
     - Google Cloud APIs (STT/TTS)
     - YouTube/TikTok APIs
     - License validation server

## 🆘 Still Having Issues?

1. **Contact Support**: Report issues on GitHub
2. **Alternative**: Use portable version (if available)
3. **Enterprise**: Contact for commercial certificate options

## 💡 For IT Administrators

Add these exclusions to your enterprise antivirus:
- **Process**: StreamMateAI.exe
- **Folder**: [Installation directory]
- **Publisher**: StreamMate AI Technologies
- **Certificate Thumbprint**: [From certificate]

---

**This guide helps ensure StreamMateAI runs smoothly on your system while maintaining security.**
"""
    
    Path("WINDOWS_DEFENDER_WHITELIST_GUIDE.md").write_text(guide_content, encoding='utf-8')
    print("✅ Created user whitelist guide: WINDOWS_DEFENDER_WHITELIST_GUIDE.md")

def calculate_file_hash(file_path):
    """Calculate SHA256 hash of file"""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"Error calculating hash: {e}")
        return None

def update_submission_files():
    """Update submission files with actual file hash"""
    print("[UPDATE] Updating submission files with file hash...")
    
    exe_path = Path("dist/StreamMateAI_Production.exe")
    if not exe_path.exists():
        print("❌ EXE file not found for hash calculation")
        return
    
    file_hash = calculate_file_hash(exe_path)
    if not file_hash:
        return
    
    print(f"📊 File Hash (SHA256): {file_hash}")
    
    # Update VirusTotal submission
    vt_file = Path("virustotal_submission.json")
    if vt_file.exists():
        data = json.loads(vt_file.read_text())
        data["file_hash_sha256"] = file_hash
        data["file_size"] = exe_path.stat().st_size
        vt_file.write_text(json.dumps(data, indent=2))
    
    # Update Defender template
    defender_file = Path("defender_submission_template.txt")
    if defender_file.exists():
        content = defender_file.read_text()
        content = content.replace("[Will be calculated]", file_hash)
        defender_file.write_text(content)
    
    print("✅ Submission files updated with file hash")

def main():
    print("🛡️ Windows Defender Fix Tool - StreamMateAI v1.0.9")
    print("=" * 60)
    
    is_admin = check_admin()
    if is_admin:
        print("✅ Running as Administrator - Full features available")
    else:
        print("⚠️ Not running as Administrator - Some features limited")
        print("💡 Run as Administrator for best results")
    
    print("\n[1/5] Creating enhanced certificate...")
    cert_success = create_enhanced_certificate()
    
    print("\n[2/5] Signing executable...")
    if cert_success:
        sign_success = sign_executable_enhanced()
    else:
        print("⏭️ Skipping signing due to certificate issues")
        sign_success = False
    
    print("\n[3/5] Creating reputation building files...")
    create_reputation_builder()
    
    print("\n[4/5] Creating user whitelist guide...")
    create_user_whitelist_guide()
    
    print("\n[5/5] Updating submission files...")
    update_submission_files()
    
    print("\n" + "=" * 60)
    print("📋 WINDOWS DEFENDER FIX SUMMARY")
    print("=" * 60)
    
    if cert_success:
        print("✅ Enhanced certificate created")
    else:
        print("❌ Certificate creation failed")
    
    if sign_success:
        print("✅ Executable signed successfully")
    else:
        print("❌ Executable signing failed")
    
    print("✅ User guides created")
    print("✅ Submission templates ready")
    
    print("\n📝 NEXT STEPS:")
    print("1. ✅ Test signed EXE on clean Windows machine")
    print("2. ✅ Submit to VirusTotal for reputation building")
    print("3. ✅ Submit false positive report to Microsoft")
    print("4. ✅ Distribute whitelist guide to users")
    print("5. ✅ Consider purchasing commercial certificate for future releases")
    
    print("\n💡 USER INSTRUCTIONS:")
    print("- Share WINDOWS_DEFENDER_WHITELIST_GUIDE.md with users")
    print("- Most users can whitelist by adding folder exclusion")
    print("- SmartScreen warnings will decrease over time with usage")
    
    if not sign_success:
        print("\n⚠️ IMPORTANT:")
        print("- Install Windows SDK for signtool.exe")
        print("- Or manually sign using certificate tools")
        print("- Self-signed certificates still trigger some warnings")

if __name__ == "__main__":
    main() 