#!/usr/bin/env python3
"""
Build Release Script untuk StreamMate AI
Menggunakan PyInstaller untuk create executable dan zip file untuk GitHub release
"""

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path
from datetime import datetime

# Konfigurasi build
APP_NAME = "StreamMate_AI"
VERSION_FILE = "version.txt"
BUILD_DIR = "dist"
RELEASE_DIR = "release"

def get_version():
    """Ambil versi dari version.txt"""
    try:
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip()
    except:
        return "1.0.0"

def should_exclude_file(file_path):
    """Cek apakah file harus diexclude dari build"""
    exclude_patterns = [
        # Developer files
        "config/dev_users.json",
        "config/beta_users.json", 
        "config/settings_dev_backup.json",
        ".env.dev.backup",
        
        # Development scripts
        "dev_mode.bat",
        "dev.bat", 
        "print_tree.py",
        "monitor_credit_realtime.py",
        "test_credit_system.py",
        "reset_payment.py",
        
        # Server files
        "modules_server/server.py",
        "logger_server.py",
        "run_server.py",
        
        # Log dan temp files
        "logs/",
        "temp/",
        "__pycache__/",
        ".pyc",
        ".log"
    ]
    
    return any(pattern in file_path for pattern in exclude_patterns)

def clean_build():
    """Bersihkan direktori build sebelumnya"""
    print("🧹 Cleaning previous build...")
    
    dirs_to_clean = ["build", "dist", "__pycache__", "release"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"   Removed {dir_name}/")
    
    # Clean pycache dari subdirectories
    for root, dirs, files in os.walk("."):
        for dir_name in dirs:
            if dir_name == "__pycache__":
                pycache_path = os.path.join(root, dir_name)
                shutil.rmtree(pycache_path)
                print(f"   Removed {pycache_path}")

def create_spec_file():
    """Buat file .spec untuk PyInstaller"""
    print("📝 Creating PyInstaller spec file...")
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Collect all required files
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('config', 'config', lambda x: not any(exclude in x for exclude in [
            'dev_users.json', 'beta_users.json', 'settings_dev_backup.json'
        ])),
        ('ui', 'ui'),
        ('modules_client', 'modules_client'),
        ('modules_server', 'modules_server', lambda x: 'server.py' not in x),
        ('listeners', 'listeners'),
        ('thirdparty', 'thirdparty'),
        ('templates', 'templates'),
        ('version.txt', '.'),
        ('requirements.txt', '.'),
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtWidgets',
        'PyQt6.QtGui',
        'requests',
        'sounddevice',
        'soundfile',
        'keyboard',
        'google.cloud.texttospeech',
        'pytchat',
        'transformers',
        'torch',
        'openai',
        'pydub',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/app_icon.ico' if os.path.exists('resources/app_icon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='{APP_NAME}',
)
'''
    
    with open(f"{APP_NAME}.spec", 'w') as f:
        f.write(spec_content)
    
    print(f"   Created {APP_NAME}.spec")

def build_executable():
    """Build executable menggunakan PyInstaller"""
    print("🔨 Building executable with PyInstaller...")
    
    try:
        # Install pyinstaller jika belum ada
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        
        # Build menggunakan spec file
        cmd = [
            "pyinstaller",
            "--clean",
            "--noconfirm",
            f"{APP_NAME}.spec"
        ]
        
        print(f"   Command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ PyInstaller failed:")
            print(result.stderr)
            return False
        
        print("✅ Executable built successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def create_portable_structure():
    """Buat struktur portable dengan file yang diperlukan"""
    print("📦 Creating portable structure...")
    
    version = get_version()
    portable_dir = Path(RELEASE_DIR) / f"{APP_NAME}_v{version}_Windows"
    
    # Buat direktori release
    portable_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy executable dan dependencies
    dist_dir = Path(BUILD_DIR) / APP_NAME
    if not dist_dir.exists():
        print(f"❌ Build directory not found: {dist_dir}")
        return False
    
    # Copy semua file dari dist dengan filtering
    for item in dist_dir.iterdir():
        # Skip file yang harus diexclude
        if should_exclude_file(str(item)):
            print(f"   Excluded: {item.name}")
            continue
            
        if item.is_file():
            shutil.copy2(item, portable_dir)
        else:
            # Copy directory dengan filtering
            try:
                shutil.copytree(
                    item, 
                    portable_dir / item.name, 
                    dirs_exist_ok=True,
                    ignore=lambda dir, files: [
                        f for f in files 
                        if should_exclude_file(os.path.join(dir, f))
                    ]
                )
            except Exception as e:
                print(f"   Warning: Could not copy {item.name}: {e}")
    
    # Copy file tambahan yang diperlukan
    additional_files = [
        "README.md",
        "LICENSE",
        "version.txt",
        "requirements.txt"
    ]
    
    for file_name in additional_files:
        if os.path.exists(file_name):
            shutil.copy2(file_name, portable_dir)
    
    # Buat file startup batch
    startup_batch = portable_dir / "StartStreamMate.bat"
    with open(startup_batch, 'w') as f:
        f.write(f'''@echo off
title StreamMate AI v{version}
echo Starting StreamMate AI...
echo.
"{APP_NAME}.exe"
if errorlevel 1 (
    echo.
    echo Error occurred! Press any key to exit...
    pause >nul
)
''')
    
    # Buat file README untuk portable
    readme_portable = portable_dir / "README_PORTABLE.txt"
    with open(readme_portable, 'w', encoding='utf-8') as f:
        f.write(f'''StreamMate AI v{version} - Portable Edition

CARA MENJALANKAN:
1. Dobel klik "StartStreamMate.bat" ATAU
2. Dobel klik "{APP_NAME}.exe" langsung

SYSTEM REQUIREMENTS:
- Windows 10/11 (64-bit)
- RAM: Minimal 4GB (Disarankan 8GB)
- Storage: 500MB ruang kosong
- Koneksi internet untuk fitur AI

FITUR:
- Voice Translation Real-time
- Auto-Reply Chat Streaming
- Integrasi Avatar & Animasi
- Virtual Microphone (Pro)
- Multi-Platform Support

DUKUNGAN:
- Website: https://streammateai.com
- Email: support@streammateai.com
- Tutorial: https://youtube.com/@StreamMateID

© 2025 StreamMate AI. All rights reserved.
''')
    
    print(f"✅ Portable structure created: {portable_dir}")
    return portable_dir

def create_installer():
    """Buat installer menggunakan NSIS (opsional)"""
    print("🔧 Creating installer...")
    
    # Cek apakah NSIS tersedia
    nsis_path = shutil.which("makensis")
    if not nsis_path:
        print("⚠️  NSIS not found, skipping installer creation")
        return None
    
    version = get_version()
    nsis_script = f'''
!include "MUI2.nsh"

Name "StreamMate AI"
OutFile "{RELEASE_DIR}\\StreamMate_AI_v{version}_Setup.exe"
InstallDir "$PROGRAMFILES\\StreamMate AI"
RequestExecutionLevel admin

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "Install"
    SetOutPath "$INSTDIR"
    File /r "{BUILD_DIR}\\{APP_NAME}\\*"
    
    CreateDirectory "$SMPROGRAMS\\StreamMate AI"
    CreateShortCut "$SMPROGRAMS\\StreamMate AI\\StreamMate AI.lnk" "$INSTDIR\\{APP_NAME}.exe"
    CreateShortCut "$DESKTOP\\StreamMate AI.lnk" "$INSTDIR\\{APP_NAME}.exe"
    
    WriteUninstaller "$INSTDIR\\Uninstall.exe"
    
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\StreamMate AI" "DisplayName" "StreamMate AI"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\StreamMate AI" "UninstallString" "$INSTDIR\\Uninstall.exe"
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\\*"
    RMDir /r "$INSTDIR"
    Delete "$SMPROGRAMS\\StreamMate AI\\*"
    RMDir "$SMPROGRAMS\\StreamMate AI"
    Delete "$DESKTOP\\StreamMate AI.lnk"
    
    DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\StreamMate AI"
SectionEnd
'''



    nsis_file = f"{APP_NAME}_installer.nsi"
    with open(nsis_file, 'w') as f:
        f.write(nsis_script)
    
    try:
        subprocess.run([nsis_path, nsis_file], check=True)
        print(f"✅ Installer created: StreamMate_AI_v{version}_Setup.exe")
        os.remove(nsis_file)  # Cleanup
        return f"StreamMate_AI_v{version}_Setup.exe"
    except subprocess.CalledProcessError:
        print("❌ Failed to create installer")
        return None

def create_release_zip(portable_dir):
    """Buat file ZIP untuk release"""
    print("📦 Creating release ZIP...")
    
    version = get_version()
    zip_name = f"{APP_NAME}_v{version}_Windows.zip"
    zip_path = Path(RELEASE_DIR) / zip_name
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(portable_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, portable_dir.parent)
                zipf.write(file_path, arcname)
    
    print(f"✅ Release ZIP created: {zip_path}")
    return zip_path

def create_checksums(files):
    """Buat file checksum untuk verifikasi"""
    print("🔐 Creating checksums...")
    
    import hashlib
    
    checksums = {}
    for file_path in files:
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                sha256_hash = hashlib.sha256(f.read()).hexdigest()
                checksums[os.path.basename(file_path)] = sha256_hash
    
    # Simpan checksums
    checksum_file = Path(RELEASE_DIR) / "checksums.txt"
    with open(checksum_file, 'w') as f:
        f.write(f"StreamMate AI v{get_version()} - File Checksums (SHA256)\n")
        f.write("=" * 60 + "\n\n")
        for filename, checksum in checksums.items():
            f.write(f"{filename}:\n{checksum}\n\n")
    
    print(f"✅ Checksums created: {checksum_file}")

def create_release_notes():
    """Buat file release notes"""
    print("📝 Creating release notes...")
    
    version = get_version()
    release_notes = f'''# StreamMate AI v{version} Release Notes

## 🚀 New Features
- Auto-update system dengan GitHub integration
- Improved voice translation dengan caching
- Enhanced chat overlay dengan customizable themes
- Better error handling dan logging system

## 🐛 Bug Fixes
- Fixed TTS delay issues
- Resolved hotkey conflicts
- Improved memory management
- Fixed avatar animation sync

## 🔧 Improvements
- Optimized startup time
- Better resource management
- Enhanced UI responsiveness
- Improved stability

## 📋 System Requirements
- Windows 10/11 (64-bit)
- RAM: Minimal 4GB (Disarankan 8GB)
- Storage: 500MB ruang kosong
- Koneksi internet untuk fitur AI

## 📥 Installation
1. Download file ZIP dari GitHub releases
2. Extract ke folder pilihan Anda
3. Jalankan `StartStreamMate.bat` atau `{APP_NAME}.exe`
4. Login dengan akun Google
5. Pilih paket Basic atau Pro

## 🆘 Support
- Website: https://streammateai.com
- Email: support@streammateai.com
- Tutorial: https://youtube.com/@StreamMateID
- Discord: https://discord.gg/streammateai

## 🔄 Auto-Update
Aplikasi akan otomatis check update setiap 24 jam. Anda juga bisa manual check di Profile > Settings > Check for Updates.

Terima kasih telah menggunakan StreamMate AI! 🎉
'''
    
    notes_file = Path(RELEASE_DIR) / "RELEASE_NOTES.md"
    with open(notes_file, 'w', encoding='utf-8') as f:
        f.write(release_notes)
    
    print(f"✅ Release notes created: {notes_file}")

def main():
    """Main build process"""
    print("🔥 StreamMate AI Release Builder")
    print("=" * 40)
    
    version = get_version()
    print(f"📦 Building version: {version}")
    print(f"🕐 Build started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Step 1: Clean
    clean_build()
    
    # Step 2: Create spec file
    create_spec_file()
    
    # Step 3: Build executable
    if not build_executable():
        print("❌ Build failed!")
        return False
    
    # Step 4: Create portable structure
    portable_dir = create_portable_structure()
    if not portable_dir:
        print("❌ Failed to create portable structure!")
        return False
    
    # Step 4.5: Security check - SEKARANG portable_dir SUDAH ADA
    print("🔒 Running security check...")
    
    security_violations = []
    for root, dirs, files in os.walk(portable_dir):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, portable_dir)
            
            if should_exclude_file(rel_path):
                security_violations.append(rel_path)
    
    if security_violations:
        print("❌ SECURITY VIOLATIONS FOUND:")
        for violation in security_violations:
            print(f"   - {violation}")
        print("Build stopped for security reasons!")
        return False
    else:
        print("✅ Security check passed - no sensitive files found")
    
    # Step 5: Create installer (optional)
    installer_file = create_installer()
    
    # Step 6: Create release ZIP
    zip_file = create_release_zip(portable_dir)
    
    # Step 7: Create checksums
    release_files = [zip_file]
    if installer_file:
        release_files.append(Path(RELEASE_DIR) / installer_file)
    create_checksums(release_files)
    
    # Step 8: Create release notes
    create_release_notes()
    
    # Summary
    print("\n🎉 BUILD COMPLETE!")
    print("=" * 40)
    print(f"📦 Version: {version}")
    print(f"📁 Release directory: {RELEASE_DIR}/")
    print(f"📦 ZIP file: {zip_file.name}")
    if installer_file:
        print(f"🔧 Installer: {installer_file}")
    print(f"🔐 Checksums: checksums.txt")
    print(f"📝 Release notes: RELEASE_NOTES.md")
    print()
    print("🚀 Ready to upload to GitHub Releases!")
    print("Upload files:")
    for file_path in release_files:
        print(f"   - {file_path.name}")
    print("   - checksums.txt")
    print("   - RELEASE_NOTES.md")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n✅ Build process completed successfully!")
        else:
            print("\n❌ Build process failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Build cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)