# ISB LKPP → Google Sheets — Data Automation

Panduan lengkap untuk menyiapkan dan menjalankan integrasi otomatisasi pengambilan data dari ISB LKPP ke Google Sheets.

## Ringkasan proyek

Proyek ini berisi script Python yang otomatis mengambil data dari API/halaman ISB LKPP, memproses data menggunakan pandas, lalu mengunggah hasilnya ke Google Sheets menggunakan service account.

File utama:

- `isb_lkpp_integration.py` — script utama (login via Selenium, ambil data, proses, upload ke Google Sheets, scheduling).
- `config_template.json` — template konfigurasi yang harus Anda salin dan isi menjadi `config.json`.
- `requirements.txt` — daftar dependensi Python.


## Kontrak singkat

- Input: `config.json` (ISB credentials, Google Sheets credentials file, spreadsheet id), Chrome terpasang.
- Output: Worksheet di Google Sheets per-endpoint (nama: `<endpoint>_YYYYMMDD`), file log `isb_integration.log`, cache `cache_<endpoint>.pkl`.
- Kegagalan umum: kredensial Google salah, Selenium/Chrome tidak cocok, endpoint API berubah.


## Persiapan lingkungan (Windows / PowerShell)

1. Buka PowerShell di folder proyek (contoh: `C:\Aldiva\CPNS\Data automation`).

2. Buat dan aktifkan virtual environment (direkomendasikan):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

3. Install dependensi:

```powershell
pip install -r .\requirements.txt
```


## Menyiapkan konfigurasi

1. Salin file template menjadi `config.json`:

```powershell
copy .\config_template.json .\config.json
```

2. Edit `config.json` dan isi:
- `isb_credentials.username` / `password`
- `google_sheets.credentials_file` → path ke file service account JSON
- `google_sheets.spreadsheet_id` → ID dari URL spreadsheet
- Atur `automation.update_interval_minutes`, `timeout_seconds` sesuai kebutuhan

Contoh singkat `config.json` (sesuaikan nilai):

```json
{
  "isb_credentials": {
    "username": "my_user",
    "password": "my_pass",
    "login_url": "https://isb.lkpp.go.id/isb-2/login",
    "api_base_url": "https://isb.lkpp.go.id/isb-2/api"
  },
  "google_sheets": {
    "credentials_file": "C:/Aldiva/CPNS/Data automation/service-account-key.json",
    "spreadsheet_id": "1AbcDEfGhIJKLmnopQRsTuvWXyZ",
    "worksheet_name": "Sheet1"
  },
  "automation": {
    "update_interval_minutes": 30,
    "max_retries": 3,
    "timeout_seconds": 30
  },
  "api_endpoints": {
    "ecat_penyedia": "/b2231dd9-cf41-43cb-8a1a-26922abec2e3/json/1814/Ecat-PenyediaDetail/tipe/4/parameter/",
    "ecat_paket": "/b2231dd9-cf41-43cb-8a1a-26922abec2e3/json/1814/Ecat-PaketEPurchasing/",
    "tender_data": "/b2231dd9-cf41-43cb-8a1a-26922abec2e3/json/1814/Bela-TokoDaringRealisasi/"
  }
}
```


## Google Sheets (service account) — langkah penting

1. Buat project di Google Cloud Console.
2. Aktifkan Google Sheets API dan Google Drive API.
3. Buat service account dan download key JSON.
4. Letakkan file JSON di path sesuai `config.json` (`google_sheets.credentials_file`).
5. Buka spreadsheet yang akan digunakan, klik Share → tambahkan email service account (mis. `service-account@...gserviceaccount.com`) → beri peran Editor.


## Chrome & Selenium

- Pastikan Google Chrome terpasang.
- Selenium 4 memiliki Selenium Manager yang biasanya mengatur driver secara otomatis. Jika WebDriver gagal diinisialisasi, opsi:
  - Pasang `chromedriver` yang sesuai versi Chrome dan letakkan `chromedriver.exe` di PATH.
  - Atau adaptasikan script untuk menunjuk `executable_path` ke driver.
- Script menjalankan Chrome headless. Jika Anda butuh melihat browser saat debugging, hapus atau ubah opsi `--headless` di `isb_lkpp_integration.py`.


## Menjalankan (uji satu kali)

Jalankan script untuk satu siklus update (script akan mencoba meng-login, mengambil, memproses, dan meng-upload):

```powershell
# pastikan venv aktif
python .\isb_lkpp_integration.py
```

Periksa `isb_integration.log` untuk hasil atau error.


## Menjalankan sebagai proses terjadwal / service

Script sudah memiliki loop scheduler internal (`schedule`). Untuk produksi di Windows:
- Buat Task Scheduler task yang menjalankan Python script pada startup/user login.
- Atau gunakan NSSM untuk menjalankan script sebagai service.

Contoh singkat Task Scheduler (PowerShell) — jalankan dengan hak yg sesuai:

```powershell
# contoh cara manual: jalankan background dengan Start-Process
Start-Process -FilePath .\.venv\Scripts\python.exe -ArgumentList '.\\isb_lkpp_integration.py' -WindowStyle Hidden
```


## Troubleshooting cepat

- "Gagal setup Google Sheets" → periksa path service account JSON, dan bahwa spreadsheet dibagikan ke service account.
- "Gagal menginisialisasi WebDriver" → periksa versi Chrome dan chromedriver; coba jalankan tanpa `--headless` untuk melihat error.
- API mengembalikan JSON berbeda → periksa struktur response dan sesuaikan `process_data` di script.


## Rekomendasi perbaikan (opsional)

- Pindahkan kredensial sensitif ke environment variables (`python-dotenv`) dan jangan commit ke repo.
- Tambahkan retry exponential/backoff untuk panggilan API berat.
- Tambahkan unit tests (mock requests & gspread) untuk logic pemrosesan.
- Buat skrip PowerShell yang membuat Task Scheduler entry otomatis.


## File & path penting

- `config_template.json` — template (jangan edit langsung, salin ke `config.json`).
- `config.json` — (harus dibuat oleh Anda) konfigurasi runtime.
- `service-account-key.json` — file kunci Google service account (tidak disertakan di repo).


## Next steps (saya bisa bantu)

- Saya dapat membuat `config.json` dari template dan menandai nilai yang perlu Anda isi.
- Saya dapat menambahkan `.env` support dan memperbarui script untuk memakai environment variables.
- Saya dapat membuat `install_and_run.ps1` untuk otomatisasi setup & Task Scheduler.

Jika Anda ingin saya membuat salah satu di atas, katakan pilihan Anda (contoh: "Buat config.json" atau "Tambah .env support").

---

Dokumentasi dibuat otomatis berdasarkan isi repo saat ini. Periksa dan sesuaikan nilai sensitif sebelum menjalankan.
