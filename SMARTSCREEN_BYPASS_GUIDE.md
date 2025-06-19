# Windows SmartScreen Bypass Guide

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
