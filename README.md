# Tourguider

Tourguider adalah proyek mata kuliah **Sistem Berbasis Pengetahuan** yang menerapkan **Case-Based Reasoning (CBR)** untuk merekomendasikan satu objek wisata. Pengguna memilih wilayah, tipe rombongan, dan minat. Hasil disertai alasan, kasus kunjungan terdahulu, rating, peta, dan informasi akses.

## Coba Tourguider

Gunakan Python 3.11 atau lebih baru.

Di macOS, buka folder proyek lalu jalankan:

```sh
./run.command
```

Atau jalankan manual di macOS atau Linux:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
```

Di Windows PowerShell, aktifkan lingkungan dengan `.venv\Scripts\Activate.ps1` setelah membuatnya, lalu jalankan dua perintah pemasangan dan server di atas.

Buka [http://127.0.0.1:8765](http://127.0.0.1:8765) setelah server berjalan. Untuk menghentikannya, tekan `Ctrl+C` di terminal.

Repo menyertakan ringkasan kasus agregat agar aplikasi dapat langsung dicoba. Untuk menampilkan jejak rinci dari kasus individual, bangun artefak v4 dari berkas sumber Mendeley seperti dijelaskan di bagian [membangun basis kasus individual](#membangun-basis-kasus-individual). Status basis yang sedang aktif tersedia di `/api/health`.

## Metode dan data

Tourguider memakai **Tourism Dataset Mendeley v1** dengan cakupan Bali, Yogyakarta, dan Malang. Satu kasus menggambarkan satu kunjungan dan rating setelah berkunjung. Pencarian membatasi wilayah dan minat, lalu mencocokkan tipe rombongan yang sama. Rating kasus serupa digabung dengan rata-rata historis tempat untuk menghasilkan satu rekomendasi.

Alur CBR di situs menjelaskan kasus yang mendukung hasil, rating yang dihitung, jumlah pengulas unik, dan rumus skor. Peta membantu menemukan tempat. Informasi akses dapat berubah, jadi periksa sumber pengelola sebelum berangkat.

## Berkas proyek

- [Metodologi dan evaluasi](docs/METODOLOGI.md) menjelaskan definisi kasus, tahapan CBR, metrik, hasil sebelum dan sesudah, serta keterbatasan evaluasi.
- [Panduan demo](docs/PANDUAN-DEMO.md) berisi urutan konsultasi, contoh perhitungan, dan penjelasan yang dapat dipakai saat presentasi.
- [Audit sumber dan data](AUDIT.md) merangkum asal data, pembersihan, dan cakupan katalog.
- [Dataset Mendeley](https://data.mendeley.com/datasets/h58s544674/1) adalah sumber utama rating kunjungan.

## Membangun basis kasus individual

Dataset mentah dan artefak kasus individual tidak disertakan dalam repo. Unduh dan ekstrak berkas Excel dari Mendeley, lalu siapkan Python 3.11 atau lebih baru.

```sh
python -m pip install -r requirements-dev.txt
python -m backend.evaluate_cbr --source /lokasi/folder/dataset --output docs/cbr-evaluation.json --artifact artifacts/cbr-cases-v4.json
```

Ganti `/lokasi/folder/dataset` dengan folder berisi berkas Excel hasil ekstraksi. Artefak kasus individual disimpan lokal dan diabaikan Git karena menyimpan referensi internal untuk menautkan kunjungan pengulas secara konsisten. Setelah artefak dibuat, mulai ulang server. Pemeriksaan tes tersedia dengan `python -m pytest -q`.

## Teknologi

- Antarmuka: HTML, CSS, JavaScript
- API: Python dan FastAPI
- Pengujian: Pytest
