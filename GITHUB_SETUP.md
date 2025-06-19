# Panduan Setup GitHub Repository untuk StreamMate AI

Panduan ini akan membantu Anda mengatur repositori GitHub untuk sistem update StreamMate AI.

## Langkah 1: Clone Repositori

1. Buka terminal atau command prompt
2. Clone repositori dengan perintah:

```bash
git clone https://github.com/arulbarker/streammate-releases.git
cd streammate-releases
```

## Langkah 2: Persiapkan File Dasar

1. Salin file-file berikut dari proyek utama:
   - `version.txt`
   - `CHANGELOG.md`
   - `update-info.json`
   - `README.md`
   - `LICENSE`
   - `.gitignore`

2. Buat struktur folder:
   - `releases/` - untuk menyimpan file rilis

## Langkah 3: Persiapkan File untuk Upload

1. Buat file ZIP dari aplikasi:
   - Pastikan hanya menyertakan file yang diperlukan
   - Gunakan format nama yang konsisten: `StreamMateAI_v1.0.2.zip`

2. Jalankan script prepare_release.py:
```bash
python prepare_release.py 1.0.2 dist/StreamMateAI_v1.0.2.zip --changelog "Fitur baru 1" "Perbaikan bug 2"
```

## Langkah 4: Buat GitHub Personal Access Token

1. Login ke GitHub
2. Buka Settings > Developer settings > Personal access tokens
3. Klik "Generate new token"
4. Beri nama token (misalnya "StreamMate AI Releases")
5. Pilih scope: `repo` (full control of private repositories)
6. Klik "Generate token"
7. Salin token yang dihasilkan (hanya ditampilkan sekali)

## Langkah 5: Upload ke GitHub

1. Commit perubahan:
```bash
git add .
git commit -m "Prepare release v1.0.2"
```

2. Push ke GitHub:
```bash
git push origin main
```

3. Upload release dengan script:
```bash
python upload_to_github.py --token YOUR_TOKEN --version 1.0.2 --file dist/StreamMateAI_v1.0.2.zip
```

## Langkah 6: Verifikasi Release

1. Buka halaman GitHub Releases:
   `https://github.com/arulbarker/streammate-releases/releases`

2. Pastikan release baru muncul dengan file ZIP yang dapat didownload

3. Cek URL download di update-info.json apakah sudah benar

## Langkah 7: Uji Update dari Aplikasi

1. Jalankan aplikasi StreamMate AI versi lama
2. Pilih menu "Check for Updates"
3. Pastikan update terdeteksi dan dapat didownload

## Tips Keamanan

1. **Jangan** menyertakan file sensitif seperti:
   - Kredensial database
   - API key
   - Token autentikasi
   - Data pengguna

2. Pastikan .gitignore sudah diatur dengan benar untuk mengecualikan:
   - File database (*.db)
   - File log (logs/*)
   - File kredensial (*.key, *.pem)
   - Folder data pengguna (data/*)

3. Gunakan GitHub Secrets untuk menyimpan token API dan kredensial lainnya

## Otomatisasi dengan GitHub Actions

Untuk otomatisasi proses rilis, Anda dapat membuat workflow GitHub Actions:

1. Buat file `.github/workflows/release.yml`:

```yaml
name: Release StreamMate AI

on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Version number (e.g., 1.0.2)'
        required: true
      changelog:
        description: 'Changelog items (comma separated)'
        required: true

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
          
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests
          
      - name: Prepare release
        run: |
          python prepare_release.py ${{ github.event.inputs.version }} releases/StreamMateAI_v${{ github.event.inputs.version }}.zip --changelog ${{ github.event.inputs.changelog }}
          
      - name: Create GitHub Release
        run: |
          python upload_to_github.py --token ${{ secrets.GITHUB_TOKEN }} --version ${{ github.event.inputs.version }} --file releases/StreamMateAI_v${{ github.event.inputs.version }}.zip
          
      - name: Commit changes
        run: |
          git config --global user.name 'GitHub Actions'
          git config --global user.email 'actions@github.com'
          git add version.txt CHANGELOG.md update-info.json
          git commit -m "Release v${{ github.event.inputs.version }}"
          git push
```

2. Tambahkan secret `GITHUB_TOKEN` di repository settings

3. Gunakan workflow ini untuk merilis versi baru dengan mengklik "Run workflow" di tab Actions 







ini yang gampang

Saya akan memberikan panduan langkah demi langkah yang lebih sederhana untuk mengupdate aplikasi StreamMate AI ke versi 1.0.3:

## Tutorial Update StreamMate AI ke v1.0.3 (Langkah Mudah)

### Langkah 1: Persiapkan File ZIP Aplikasi
1. Buat folder `releases` jika belum ada:
```
mkdir releases
```
2. Salin file aplikasi yang sudah di-build ke folder `releases` dengan nama `StreamMateAI_v1.0.3.zip`

### Langkah 2: Perbarui Versi dan Changelog
1. Jalankan script prepare_release.py:
```
python prepare_release.py 1.0.3 releases/StreamMateAI_v1.0.3.zip --changelog "Fitur baru: TikTok integration" "Perbaikan bug notifikasi" "Peningkatan performa"
```

Script ini akan otomatis:
- Memperbarui version.txt menjadi V.1.0.3
- Memperbarui CHANGELOG.md dengan fitur baru
- Memperbarui update-info.json dengan informasi versi baru

### Langkah 3: Buat GitHub Personal Access Token (Jika Belum Punya)
1. Buka https://github.com/settings/tokens
2. Klik "Generate new token"
3. Beri nama token (misalnya "StreamMate AI Releases")
4. Pilih scope "repo"
5. Klik "Generate token"
6. Salin token yang dihasilkan

### Langkah 4: Upload ke GitHub
1. Jalankan script upload_to_github.py:
```
python upload_to_github.py --token YOUR_GITHUB_TOKEN --version 1.0.3 --file releases/StreamMateAI_v1.0.3.zip
```
(Ganti YOUR_GITHUB_TOKEN dengan token yang Anda salin tadi)

### Langkah 5: Commit dan Push Perubahan
1. Tambahkan file yang diperbarui ke Git:
```
git add version.txt CHANGELOG.md update-info.json
```

2. Commit perubahan:
```
git commit -m "Release v1.0.3"
```

3. Push ke GitHub:
```
git push origin main
```

### Langkah 6: Verifikasi
1. Buka repositori GitHub Anda: https://github.com/arulbarker/streammate-releases
2. Periksa bagian "Releases" untuk memastikan rilis v1.0.3 muncul
3. Pastikan file ZIP dapat didownload

### Langkah 7: Uji Update
1. Jalankan aplikasi StreamMate AI versi lama
2. Pilih menu "Check for Updates"
3. Verifikasi bahwa update v1.0.3 terdeteksi dan dapat didownload

## Jika Anda Belum Terhubung ke GitHub

Jika Anda belum terhubung ke GitHub, ikuti langkah tambahan ini sebelum Langkah 4:

1. Buat repositori baru di GitHub dengan nama "streammate-releases"

2. Inisialisasi Git di folder proyek Anda:
```
git init
```

3. Tambahkan remote GitHub:
```
git remote add origin https://github.com/arulbarker/streammate-releases.git
```

4. Tambahkan semua file ke Git:
```
git add .
```

5. Commit pertama:
```
git commit -m "Initial commit"
```

6. Push ke GitHub:
```
git push -u origin main
```

Setelah itu, lanjutkan dengan Langkah 4 di atas.

## Cara Paling Mudah (Jika Masih Bingung)

Jika Anda masih bingung, gunakan file batch yang sudah dibuat:

1. Jalankan `setup_github_repo.bat` dan ikuti instruksinya
2. Salin file aplikasi ke folder `releases` dengan nama `StreamMateAI_v1.0.3.zip`
3. Jalankan perintah:
```
python prepare_release.py 1.0.3 releases/StreamMateAI_v1.0.3.zip --changelog "Fitur baru" "Perbaikan bug"
python upload_to_github.py --token YOUR_GITHUB_TOKEN --version 1.0.3 --file releases/StreamMateAI_v1.0.3.zip
```

Setelah itu, pengguna aplikasi StreamMate AI akan menerima notifikasi update saat mereka menjalankan aplikasi.





lebih full


# Tutorial Lengkap Update StreamMate AI ke v1.0.4

Berikut panduan langkah demi langkah yang sangat detail untuk update ke versi 1.0.4 dengan penambahan fitur Trakteer Tab:

## Persiapan Awal

### Langkah 1: Pastikan Folder Releases Ada
```bash
mkdir -p releases
```
Mari kita mulai dengan membuat folder releases jika belum ada:

```
mkdir -p releases
```

### Langkah 2: Siapkan File ZIP Aplikasi

1. Setelah Anda selesai mengembangkan fitur Trakteer Tab, build aplikasi Anda menjadi file ZIP
2. Beri nama file ZIP dengan format: `StreamMateAI_v1.0.4.zip`
3. Letakkan file ZIP tersebut di folder `releases/`

## Update Versi dan Changelog

### Langkah 3: Jalankan Script Prepare Release

Jalankan perintah berikut untuk memperbarui semua file yang diperlukan:

```
python prepare_release.py 1.0.4 releases/StreamMateAI_v1.0.4.zip --changelog "Penambahan fitur Trakteer Tab" "Perbaikan UI pada halaman utama" "Optimasi performa"
```

Script ini akan otomatis:
- Memperbarui `version.txt` menjadi V.1.0.4
- Menambahkan entri baru di `CHANGELOG.md`
- Memperbarui `update-info.json` dengan informasi versi baru
- Menghitung checksum dan ukuran file

## Upload ke GitHub

### Langkah 4: Upload Release ke GitHub

Jalankan perintah berikut untuk mengupload rilis ke GitHub:

```
python upload_to_github.py --token GITHUB_TOKEN_ANDA --version 1.0.4 --file releases/StreamMateAI_v1.0.4.zip
```

Ganti `GITHUB_TOKEN_ANDA` dengan token GitHub Anda yang sudah dibuat sebelumnya.

Script ini akan:
- Membuat rilis baru di GitHub dengan tag v1.0.4
- Mengupload file ZIP ke rilis tersebut
- Memperbarui `update-info.json` dengan URL download yang benar

## Update Repository Git

### Langkah 5: Tambahkan File yang Diperbarui ke Git

```
git add version.txt CHANGELOG.md update-info.json
```

### Langkah 6: Commit Perubahan

```
git commit -m "Release v1.0.4 dengan fitur Trakteer Tab"
```

### Langkah 7: Push ke GitHub

```
git push origin master
```

### Langkah 8: Tambahkan Tag

```
git tag v1.0.4
git push origin v1.0.4
```

## Verifikasi Update

### Langkah 9: Periksa GitHub Releases

1. Buka browser dan kunjungi: `https://github.com/arulbarker/streammate-releases/releases`
2. Pastikan rilis v1.0.4 muncul dengan deskripsi yang benar
3. Pastikan file ZIP dapat didownload

### Langkah 10: Uji Update dari Aplikasi

1. Jalankan aplikasi StreamMate AI versi lama (v1.0.3)
2. Pilih menu "Check for Updates" atau tunggu notifikasi otomatis
3. Verifikasi bahwa update v1.0.4 terdeteksi dan dapat didownload
4. Uji proses download dan instalasi

## Panduan Lengkap dalam Satu Script

Untuk memudahkan, Anda bisa menyimpan semua langkah di atas dalam satu file batch. Buat file `update_v1.0.4.bat` dengan isi:

```batch
@echo off
echo ===================================================
echo StreamMate AI - Update ke v1.0.4
echo ===================================================
echo.

REM Pastikan folder releases ada
mkdir -p releases 2>nul

echo.
echo Pastikan file StreamMateAI_v1.0.4.zip sudah ada di folder releases
echo.
pause

REM Perbarui versi dan changelog
echo.
echo Memperbarui versi dan changelog...
python prepare_release.py 1.0.4 releases/StreamMateAI_v1.0.4.zip --changelog "Penambahan fitur Trakteer Tab" "Perbaikan UI pada halaman utama" "Optimasi performa"

REM Upload ke GitHub
echo.
echo Mengupload ke GitHub...
set /p token=Masukkan GitHub Token Anda: 
python upload_to_github.py --token %token% --version 1.0.4 --file releases/StreamMateAI_v1.0.4.zip

REM Update repository Git
echo.
echo Memperbarui repository Git...
git add version.txt CHANGELOG.md update-info.json
git commit -m "Release v1.0.4 dengan fitur Trakteer Tab"
git push origin master
git tag v1.0.4
git push origin v1.0.4

echo.
echo ===================================================
echo Update v1.0.4 selesai!
echo ===================================================
echo.
echo Silakan periksa GitHub Releases:
echo https://github.com/arulbarker/streammate-releases/releases
echo.
pause
```

## Troubleshooting

### Jika File ZIP Tidak Ditemukan

Pastikan file `StreamMateAI_v1.0.4.zip` sudah ada di folder `releases/` sebelum menjalankan script prepare_release.py.

### Jika Token GitHub Invalid

Buat token GitHub baru:
1. Buka https://github.com/settings/tokens
2. Klik "Generate new token (classic)"
3. Beri nama token, misalnya "StreamMate AI Releases"
4. Pilih scope "repo" (full control of private repositories)
5. Klik "Generate token"
6. Salin token yang dihasilkan

### Jika Tag Sudah Ada

Jika tag v1.0.4 sudah ada, Anda bisa menghapusnya terlebih dahulu:
```
git tag -d v1.0.4
git push origin :refs/tags/v1.0.4
```

### Jika Push Ditolak

Jika push ditolak karena perubahan di remote, lakukan pull terlebih dahulu:
```
git pull origin master
```

## Ringkasan Singkat

1. Siapkan file ZIP aplikasi di folder `releases/`
2. Jalankan `prepare_release.py` untuk memperbarui versi dan changelog
3. Jalankan `upload_to_github.py` untuk mengupload ke GitHub
4. Commit dan push perubahan ke repository Git
5. Tambahkan tag versi dan push ke GitHub
6. Verifikasi rilis di GitHub dan uji update dari aplikasi

Dengan mengikuti langkah-langkah di atas, Anda akan berhasil mengupdate StreamMate AI ke versi 1.0.4 dengan fitur Trakteer Tab yang baru.