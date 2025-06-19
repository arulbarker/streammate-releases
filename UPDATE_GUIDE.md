# Panduan Update StreamMate AI

Dokumen ini berisi panduan lengkap untuk proses update aplikasi StreamMate AI.

## Struktur Sistem Update

Sistem update StreamMate AI menggunakan beberapa komponen:

1. **GitHub Repository**: `https://github.com/arulbarker/streammate-releases`
2. **Website API**: `https://api.streammate-ai.com/api/version/latest`
3. **File Konfigurasi**: `update-info.json`
4. **Update Manager**: Kelas dalam aplikasi yang mengelola proses update

## Proses Update dari Sisi Pengguna

1. Aplikasi secara otomatis memeriksa update setiap 6 jam
2. Jika update tersedia, notifikasi muncul
3. Pengguna dapat memilih:
   - Download dan install sekarang
   - Ingatkan nanti (24 jam)
   - Skip versi ini
4. Setelah download selesai, aplikasi akan ditutup dan update diinstal
5. Aplikasi akan dibuka kembali secara otomatis setelah update selesai

## Proses Rilis Versi Baru

### 1. Persiapan Rilis

1. Selesaikan pengembangan fitur baru
2. Perbarui versi di `version.txt`
3. Perbarui changelog di `CHANGELOG.md`
4. Build aplikasi menjadi file ZIP atau EXE

### 2. Gunakan Script Prepare Release

Script `prepare_release.py` akan membantu mempersiapkan rilis:

```bash
python prepare_release.py 1.0.2 dist/StreamMateAI_v1.0.2.zip --changelog "Fitur baru 1" "Perbaikan bug 2" "Peningkatan performa"
```

Script ini akan:
- Memperbarui `version.txt`
- Memperbarui `CHANGELOG.md`
- Memperbarui `update-info.json` dengan:
  - Versi terbaru
  - Tanggal rilis
  - Changelog
  - Ukuran file
  - Checksum SHA-256
  - URL download

### 3. Upload ke GitHub

1. Commit perubahan ke Git:
```bash
git add version.txt CHANGELOG.md update-info.json
git commit -m "Release v1.0.2"
```

2. Buat tag untuk versi baru:
```bash
git tag v1.0.2
```

3. Push ke GitHub:
```bash
git push origin main
git push origin v1.0.2
```

4. Buat GitHub Release:
   - Buka `https://github.com/arulbarker/streammate-releases/releases`
   - Klik "Draft a new release"
   - Pilih tag `v1.0.2`
   - Isi judul dan deskripsi
   - Upload file ZIP atau EXE
   - Klik "Publish release"

### 4. Verifikasi Update

1. Jalankan aplikasi StreamMate AI versi lama
2. Pilih menu "Check for Updates"
3. Verifikasi bahwa update terdeteksi
4. Uji proses download dan instalasi

## Troubleshooting

### Update Tidak Terdeteksi

1. Periksa koneksi internet
2. Pastikan `update-info.json` sudah diperbarui
3. Verifikasi bahwa versi di `update-info.json` lebih tinggi dari versi aplikasi

### Download Gagal

1. Pastikan URL download di `update-info.json` benar
2. Verifikasi file ada di GitHub Releases
3. Periksa permission file download

### Instalasi Gagal

1. Verifikasi checksum file yang didownload
2. Pastikan script update memiliki permission yang cukup
3. Periksa log error di `logs/system.log`

## Konfigurasi Lanjutan

### Force Update

Jika ada update kritis yang harus diinstal, atur `force_update` menjadi `true` di `update-info.json`:

```json
{
  "latest_version": "1.0.2",
  "force_update": true,
  ...
}
```

### Minimum Version

Jika versi baru memerlukan versi minimum tertentu, atur `minimum_version` di `update-info.json`:

```json
{
  "latest_version": "1.0.2",
  "minimum_version": "1.0.0",
  ...
}
```

### Beta Versions

Untuk merilis versi beta, tambahkan ke bagian `beta_versions` di `update-info.json`:

```json
{
  "beta_versions": {
    "1.1.0-beta": {
      "download_id": "https://github.com/arulbarker/streammate-releases/releases/download/v1.1.0-beta/StreamMateAI_v1.1.0-beta.zip",
      "changelog": [
        "Beta: Fitur AI baru",
        "Beta: Antarmuka pengguna yang diperbarui"
      ],
      "release_date": "2025-11-15"
    }
  }
}
```

## Referensi API

### Website API Endpoint

```
GET https://api.streammate-ai.com/api/version/latest
```

Response:
```json
{
  "version": "1.0.2",
  "download_url": "https://github.com/arulbarker/streammate-releases/releases/download/v1.0.2/StreamMateAI_v1.0.2.zip",
  "changelog": ["Fitur 1", "Fitur 2"],
  "release_date": "2025-06-15",
  "file_size": 52428800,
  "checksum": "sha256:abc123...",
  "minimum_version": "1.0.0",
  "force_update": false
}
``` 