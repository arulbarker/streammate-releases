# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

# Collect all pytchat files
pytchat_path = Path('thirdparty/pytchat_ng')
pytchat_datas = []
if pytchat_path.exists():
    for item in pytchat_path.rglob('*'):
        if item.is_file() and not item.suffix in ['.pyc', '.pyo']:
            relative = item.relative_to('thirdparty/pytchat_ng')
            pytchat_datas.append((str(item), f'pytchat/{relative.parent}'))

a = Analysis(
    ['main.py'],
    pathex=['.', 'thirdparty', 'thirdparty/pytchat_ng'],
    binaries=[],
    datas=[
        # SAFE CONFIG FILES ONLY - NO SENSITIVE DATA
        ('config/settings_default.json', 'config'),
        ('config/packages.json', 'config'),
        ('config/voices.json', 'config'),
        ('config/production_config.json', 'config'),
        # NOTE: ALL OAuth files EXCLUDED for security - will use server backend
        # - google_oauth.json (contains client_secret - EXCLUDED)
        # - google_token.json (contains OAuth tokens - EXCLUDED)
        # - gcloud_tts_credentials.json (contains private keys - EXCLUDED)
        # - development_config.json (contains admin keys - EXCLUDED)
        # - settings.json (user-specific data - will be created as template)
        # - credit_config.json (may contain sensitive data - EXCLUDED)
        ('ui', 'ui'),
        ('modules_client', 'modules_client'),
        ('modules_server', 'modules_server'),
        ('listeners', 'listeners'),
        ('test_build_oauth.py', '.'),  # Include test script for debugging
        ('icon.ico', '.'),
    ] + pytchat_datas,
    hiddenimports=[
        # --- PYTCHAT CORE ---
        'pytchat',
        'pytchat.core',
        'pytchat.core.pytchat',
        'pytchat.config',
        'pytchat.parser',
        'pytchat.parser.live',
        'pytchat.processors',
        'pytchat.processors.default',
        'pytchat.exceptions',
        'pytchat.paramgen',
        'pytchat.paramgen.liveparam',
        'pytchat.util',
        
        # --- PYTCHAT DEPENDENCIES - EXPANDED ---
        'requests',
        'urllib3',
        'certifi',
        'httpx',
        'httpcore',
        'h11',
        'websockets','websockets.client','websockets.server','websockets.protocol',
        'aiohttp', 'aiohttp.client', 'aiohttp.client_ws',
        'async_timeout',
        'multidict',
        'yarl',
        
        # --- SUPER DIRECT GOOGLE STT (No Whisper) ---
        'google.cloud',
        'google.cloud.speech',
        'google.auth',
        'google.auth.transport',
        'google.auth.transport.requests',
        'sounddevice',
        'soundfile',
        'numpy',
        
        # --- OAUTH HYBRID SUPPORT ---
        'webbrowser',
        'urllib.parse',
        'http.server',
        'threading',
        'googleapiclient',
        'googleapiclient.discovery',
        'googleapiclient.errors',
        
        # --- UI & CORE ---
        'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtWidgets', 'PyQt6.QtGui',
        'keyboard', 'psutil',
        'customtkinter', 'packaging',
        
        # --- AI & TTS ---
        'deepseek',
        'gtts',
        'pydub',
        
        # --- Handler ---
        'modules_client.pytchat_path_handler',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['modules_client/pytchat_path_handler.py'],
    excludes=[
        # Exclude Whisper-related modules (no longer needed)
        'whisper',
        'torch',
        'transformers',
        'speech_recognition',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='StreamMateAI_Production',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Production mode - no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
    version='version_info.txt'  # Add version info for signing
)
