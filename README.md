# Proto_Travelmaker

**Travelmaker** adalah prototipe sistem rekomendasi destinasi wisata berbasis *Case-Based Reasoning* (CBR).

Proyek ini dikembangkan untuk mengeksplorasi rekomendasi destinasi wisata berdasarkan kemiripan preferensi wisatawan dan respons historis terhadap destinasi.

## Tujuan

- Merepresentasikan preferensi wisatawan sebagai kasus.
- Menghitung kemiripan antara preferensi pengguna baru dan kasus historis.
- Menghasilkan peringkat rekomendasi berdasarkan respons wisatawan terdahulu.
- Menyediakan antarmuka web untuk berinteraksi dengan sistem.

## Teknologi

- Python
- Streamlit
- Pandas
- NumPy

## Struktur Proyek

```text
Proto_Travelmaker/
├── app.py
├── requirements.txt
├── .gitignore
├── README.md
└── data/
    └── .gitkeep
```

## Persyaratan

Pastikan Python telah terinstal pada komputer.

## Instalasi

Clone repository:

```bash
git clone <URL_REPOSITORY>
cd Proto_Travelmaker
```

Buat virtual environment:

```bash
python -m venv .venv
```

Aktifkan virtual environment.

Windows:

```powershell
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Instal dependensi:

```bash
pip install -r requirements.txt
```

## Menjalankan Aplikasi

```bash
streamlit run app.py
```

Aplikasi akan berjalan pada alamat lokal yang ditampilkan oleh Streamlit di terminal.

## Status Pengembangan

Proyek masih berada pada tahap prototipe awal.

Fitur perhitungan kemiripan, pemeringkatan destinasi, integrasi dataset, dan evaluasi rekomendasi akan dikembangkan secara bertahap.

## Metode

Sistem dirancang berdasarkan siklus *Case-Based Reasoning*:

1. **Retrieve** — mencari kasus historis yang serupa.
2. **Reuse** — memanfaatkan respons dari kasus yang relevan untuk menyusun rekomendasi.
3. **Revise** — menyesuaikan rekomendasi jika mekanisme revisi diterapkan.
4. **Retain** — menyimpan kasus atau umpan balik baru jika mekanisme pembaruan kasus diterapkan.

Implementasi setiap tahap akan disesuaikan dengan rancangan sistem dan ketersediaan data.

## Catatan Data

Dataset penelitian tidak disertakan dalam repository ini. Penggunaan dan distribusi dataset harus mengikuti ketentuan sumber data yang digunakan.

## Lisensi

Lisensi proyek belum ditentukan.