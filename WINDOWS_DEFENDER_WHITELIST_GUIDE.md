# Windows Defender Whitelist Guide - StreamMate AI v1.0.9

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
