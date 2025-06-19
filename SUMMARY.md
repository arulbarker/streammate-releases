# StreamMate AI - Sistem Update

## Ringkasan File yang Dibuat

1. **version.txt**
   - File yang berisi versi aplikasi saat ini
   - Format: `V.1.0.2`

2. **update-info.json**
   - File konfigurasi untuk informasi update
   - Berisi versi terbaru, changelog, URL download, dll.

3. **CHANGELOG.md**
   - File yang berisi riwayat perubahan aplikasi
   - Diperbarui setiap kali merilis versi baru

4. **README.md**
   - File informasi utama untuk repositori GitHub
   - Berisi informasi tentang aplikasi, cara install, dll.

5. **LICENSE**
   - File lisensi MIT untuk aplikasi

6. **.gitignore**
   - File untuk mengecualikan file sensitif dari repositori Git

7. **prepare_release.py**
   - Script untuk mempersiapkan rilis baru
   - Memperbarui version.txt, CHANGELOG.md, dan update-info.json

8. **upload_to_github.py**
   - Script untuk mengupload rilis ke GitHub
   - Membuat GitHub release dan mengupload file ZIP

9. **setup_github_repo.bat**
   - File batch untuk membantu setup repositori GitHub
   - Memeriksa file yang diperlukan dan membuat struktur repositori

10. **UPDATE_GUIDE.md**
    - Panduan lengkap untuk proses update aplikasi
    - Menjelaskan struktur sistem update, proses rilis, dll.

11. **GITHUB_SETUP.md**
    - Panduan langkah demi langkah untuk memperbarui repositori GitHub
    - Menjelaskan cara clone repositori, persiapan file, dll.

## Perubahan pada Kode Aplikasi

1. **modules_client/update_manager.py**
   - Diperbarui untuk menggunakan repositori GitHub
   - Menambahkan dukungan untuk file ZIP
   - Menambahkan metode untuk ekstraksi otomatis

## Langkah-langkah Penggunaan

### Persiapan Awal

1. Jalankan `setup_github_repo.bat` untuk mempersiapkan repositori GitHub
2. Ikuti instruksi di `GITHUB_SETUP.md` untuk mengatur repositori

### Setiap Kali Merilis Versi Baru

1. Build aplikasi menjadi file ZIP
2. Jalankan `prepare_release.py` untuk mempersiapkan rilis
3. Jalankan `upload_to_github.py` untuk mengupload ke GitHub

### Pengujian Update

1. Jalankan aplikasi versi lama
2. Pilih menu "Check for Updates"
3. Verifikasi bahwa update terdeteksi dan dapat didownload

## Struktur Folder

```
streammate-releases/
├── releases/                # Folder untuk file rilis
├── .github/                 # Konfigurasi GitHub Actions
│   └── workflows/
│       └── release.yml      # Workflow untuk otomatisasi rilis
├── version.txt              # Versi aplikasi saat ini
├── update-info.json         # Informasi update
├── CHANGELOG.md             # Riwayat perubahan
├── README.md                # Informasi utama
├── LICENSE                  # Lisensi MIT
├── .gitignore               # Pengecualian Git
├── prepare_release.py       # Script persiapan rilis
├── upload_to_github.py      # Script upload ke GitHub
├── setup_github_repo.bat    # Setup repositori
├── UPDATE_GUIDE.md          # Panduan update
├── GITHUB_SETUP.md          # Panduan setup GitHub
└── SUMMARY.md               # File ini
``` 