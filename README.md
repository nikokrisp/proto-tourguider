# Tourguider Indonesia

Proyek mata kuliah Sistem Berbasis Pengetahuan. Tourguider memakai **Case-Based Reasoning (CBR)** untuk memilih satu tempat dari riwayat kunjungan di Bali, Yogyakarta, dan Malang, berdasarkan wilayah, tipe rombongan, dan minat. Halaman **Alur CBR** menunjukkan kasus pendukung dan cara skor dihitung.

## Jalankan di komputer

Gunakan Python 3.11 atau lebih baru. Di macOS, jalankan `./run.command`. Untuk menjalankan secara manual:

```sh
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
```

Buka [Tourguider](http://127.0.0.1:8765/) dan pilih **Yogyakarta → Keluarga → Gunung dan vulkanologi**. Hasilnya **Gunung Merapi**. Halaman **Alur CBR** menampilkan contoh kunjungan anonim, rating, dan perhitungan skor.

Basis kasus aktif adalah [Tourism Dataset Mendeley v1](https://data.mendeley.com/datasets/h58s544674/1) dengan cakupan Bali, Yogyakarta, dan Malang. Pemeringkatan memakai rata-rata rating pengulas serupa dan rata-rata historis tempat. Kartu hasil menyertakan lokasi yang tercatat dan pencarian tempat di peta. Informasi akses perlu dikonfirmasi sebelum kunjungan.

Untuk mengaktifkan basis kasus individual, unduh dan ekstrak Excel Mendeley, lalu jalankan:

```sh
python -m pip install -r requirements-dev.txt
python -m backend.evaluate_cbr --source /lokasi/folder/dataset --output docs/cbr-evaluation.json --artifact artifacts/cbr-cases-v4.json
python -m pytest -q
```

Mulai ulang server setelah membangun artefak. `/api/health` menampilkan versi aktif. Saat basis individual belum tersedia, Tourguider dapat memakai ringkasan lama `artifacts/cbr.json`, yang dibangun dengan `python -m backend.train --source /lokasi/folder/dataset`.

Lihat [metodologi, evaluasi, dan panduan demo](docs/METODOLOGI.md) untuk definisi kasus, perhitungan, serta hasil sebelum dan sesudah.
