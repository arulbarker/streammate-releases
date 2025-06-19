@echo off
echo ===================================================
echo StreamMate AI - GitHub Repository Setup
echo ===================================================
echo.

REM Check if Git is installed
where git >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Git tidak ditemukan. Silakan install Git dari https://git-scm.com/downloads
    pause
    exit /b 1
)

REM Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Python tidak ditemukan. Silakan install Python dari https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Checking required files...

if not exist "version.txt" (
    echo ERROR: version.txt tidak ditemukan!
    pause
    exit /b 1
)

if not exist "CHANGELOG.md" (
    echo ERROR: CHANGELOG.md tidak ditemukan!
    pause
    exit /b 1
)

if not exist "prepare_release.py" (
    echo ERROR: prepare_release.py tidak ditemukan!
    pause
    exit /b 1
)

if not exist "upload_to_github.py" (
    echo ERROR: upload_to_github.py tidak ditemukan!
    pause
    exit /b 1
)

echo.
echo Semua file yang diperlukan ditemukan.
echo.

REM Ask for GitHub repository details
set /p repo_owner=Masukkan nama pemilik repositori GitHub (default: arulbarker): 
if "%repo_owner%"=="" set repo_owner=arulbarker

set /p repo_name=Masukkan nama repositori GitHub (default: streammate-releases): 
if "%repo_name%"=="" set repo_name=streammate-releases

echo.
echo Membuat folder releases...
mkdir releases 2>nul

echo.
echo Membuat .gitignore...
echo # Byte-compiled / optimized / DLL files > .gitignore
echo __pycache__/ >> .gitignore
echo *.py[cod] >> .gitignore
echo *$py.class >> .gitignore
echo. >> .gitignore
echo # Distribution / packaging >> .gitignore
echo dist/ >> .gitignore
echo build/ >> .gitignore
echo *.egg-info/ >> .gitignore
echo. >> .gitignore
echo # Virtual environments >> .gitignore
echo venv*/ >> .gitignore
echo env/ >> .gitignore
echo ENV/ >> .gitignore
echo. >> .gitignore
echo # Local development settings >> .gitignore
echo .env >> .gitignore
echo .venv >> .gitignore
echo .idea/ >> .gitignore
echo .vscode/ >> .gitignore
echo. >> .gitignore
echo # Logs and databases >> .gitignore
echo logs/ >> .gitignore
echo *.log >> .gitignore
echo *.db >> .gitignore
echo *.sqlite3 >> .gitignore
echo billing_security.db >> .gitignore
echo license_data.db >> .gitignore
echo. >> .gitignore
echo # Temporary files >> .gitignore
echo temp/ >> .gitignore
echo .temp/ >> .gitignore
echo *.tmp >> .gitignore
echo. >> .gitignore
echo # Credentials and sensitive information >> .gitignore
echo *credentials* >> .gitignore
echo *secret* >> .gitignore
echo *api_key* >> .gitignore
echo *password* >> .gitignore
echo *token* >> .gitignore
echo backup_credentials/ >> .gitignore
echo. >> .gitignore
echo # User data >> .gitignore
echo data/ >> .gitignore
echo knowledge/ >> .gitignore
echo knowledge_bases/ >> .gitignore
echo. >> .gitignore
echo # Cache files >> .gitignore
echo .cache/ >> .gitignore
echo __pycache__/ >> .gitignore
echo .pytest_cache/ >> .gitignore
echo. >> .gitignore
echo # System files >> .gitignore
echo .DS_Store >> .gitignore
echo Thumbs.db >> .gitignore

echo.
echo Menginstal dependensi Python...
pip install requests

echo.
echo Apakah Anda ingin menginisialisasi repositori Git? (y/n)
set /p init_git=
if /i "%init_git%"=="y" (
    echo Menginisialisasi repositori Git...
    git init
    git add .
    git commit -m "Initial commit"
    
    echo.
    echo Apakah Anda ingin menambahkan remote GitHub? (y/n)
    set /p add_remote=
    if /i "%add_remote%"=="y" (
        git remote add origin https://github.com/%repo_owner%/%repo_name%.git
        echo Remote ditambahkan: https://github.com/%repo_owner%/%repo_name%.git
        
        echo.
        echo Apakah Anda ingin push ke GitHub? (y/n)
        set /p push_git=
        if /i "%push_git%"=="y" (
            git push -u origin main
        )
    )
)

echo.
echo ===================================================
echo Setup selesai!
echo ===================================================
echo.
echo Langkah selanjutnya:
echo 1. Buat file ZIP aplikasi
echo 2. Jalankan prepare_release.py untuk mempersiapkan rilis
echo 3. Jalankan upload_to_github.py untuk mengupload ke GitHub
echo.
echo Contoh:
echo python prepare_release.py 1.0.2 dist/StreamMateAI_v1.0.2.zip --changelog "Fitur baru" "Perbaikan bug"
echo python upload_to_github.py --token YOUR_TOKEN --version 1.0.2 --file dist/StreamMateAI_v1.0.2.zip
echo.

pause 