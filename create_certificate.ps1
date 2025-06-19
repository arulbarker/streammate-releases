# Create Self-Signed Certificate for StreamMateAI
Write-Host "Creating self-signed certificate for StreamMateAI..." -ForegroundColor Green

try {
    # Create the certificate
    $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=StreamMateAI" -KeyUsage DigitalSignature -FriendlyName "StreamMateAI" -CertStoreLocation "Cert:\CurrentUser\My" -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
    
    Write-Host "Certificate created with thumbprint: $($cert.Thumbprint)" -ForegroundColor Yellow
    
    # Set password
    $password = ConvertTo-SecureString -String "StreamMateAI123" -Force -AsPlainText
    
    # Export to PFX file
    $pfxPath = "StreamMateAI.pfx"
    Export-PfxCertificate -cert "Cert:\CurrentUser\My\$($cert.Thumbprint)" -FilePath $pfxPath -Password $password
    
    Write-Host "Certificate exported to: $pfxPath" -ForegroundColor Green
    Write-Host "Certificate password: StreamMateAI123" -ForegroundColor Yellow
    
    # Verify the certificate file
    if (Test-Path $pfxPath) {
        $fileSize = (Get-Item $pfxPath).Length
        Write-Host "Certificate file size: $fileSize bytes" -ForegroundColor Cyan
        Write-Host "Certificate creation successful!" -ForegroundColor Green
        
        # Instructions
        Write-Host ""
        Write-Host "Next Steps:" -ForegroundColor Magenta
        Write-Host "1. Build your exe: python build_production_exe_fixed.py" -ForegroundColor White
        Write-Host "2. Sign your exe: python fix_smartscreen_issue.py" -ForegroundColor White
        Write-Host "3. Or manually sign with:" -ForegroundColor White
        Write-Host '   signtool.exe sign /f "StreamMateAI.pfx" /p "StreamMateAI123" /t "http://timestamp.sectigo.com" /v "your_app.exe"' -ForegroundColor Gray
    } else {
        Write-Host "Certificate file not created" -ForegroundColor Red
    }
    
} catch {
    Write-Host "Error creating certificate: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Try running PowerShell as Administrator" -ForegroundColor Yellow
} 