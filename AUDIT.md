# Validasi Tourguider

Proyek mata kuliah Sistem Berbasis Pengetahuan. Pemeriksaan terakhir dilakukan pada **29 Oktober 2026**, menggunakan kebijakan proses `tourguider-audit-2`.

## Ringkasan

- **22 pengujian backend dan 3 pengujian frontend lulus.**
- **17 pemeriksaan independen data dan perhitungan lulus.**
- Seluruh **61.130 profil bersih** menghasilkan kelompok akhir yang sama pada mesin forward chaining dan pohon sumber.
- Tidak ada pengguna maupun kasus identik yang tersebar antara data pelatihan dan pengujian.
- Perhitungan konsultasi dan evaluasi cocok persis pada **150 contoh pembanding**.
- Bukti keluaran diperiksa independen pada contoh yang mewakili seluruh **32 kelompok akhir**.

## Hal yang diperiksa

1. Hash CSV dan pemetaan 1.486 nama destinasi terhadap artefak model.
2. Jumlah data setelah penghapusan rekaman identik, swipe berulang, label bertentangan, dan rekaman tanpa interaksi bersih.
3. Pembagian 48.904 pengguna pelatihan dan 12.226 pengguna pengujian tanpa tumpang tindih.
4. Pengodean seluruh profil pelatihan dan kecocokan respons Ya, Tidak, serta Mungkin pada basis kasus dengan CSV.
5. Kesetaraan pohon dan aturan pada seluruh profil bersih, serta pemakaian kesimpulan aturan sebagai premis berikutnya.
6. Distribusi destinasi berbobot, jumlah pengguna pendukung, dan ukuran kelompok, dihitung ulang dari CSV.
7. Cosine similarity, pemilihan tetangga, suara berbobot, nama destinasi, dan bukti rekomendasi pada setiap kelompok akhir.
8. Jawaban belum tahu dikeluarkan dari kemiripan. Jika tidak ada preferensi, hasil memakai popularitas dengan penanda yang jelas.
9. Destinasi yang hanya ditolak kasus serupa tidak menjadi rekomendasi CBR, termasuk dari alternatif populer.
10. Perubahan jawaban membersihkan cabang lama. Pemulihan setelah kegagalan koneksi mempertahankan pilihan pengguna.
11. Angka evaluasi dari versi proses lain tidak ditampilkan sebagai hasil versi saat ini.

Penyaringan dukungan CBR menggunakan respons kasus **pelatihan**, bukan label pengguna uji. Skor pemeringkatan merupakan nilai internal, bukan persentase kepuasan atau akurasi keseluruhan aplikasi.

## Hasil evaluasi

Sebanyak **9.457 pengguna uji** memenuhi kriteria: minimal lima kandidat berlabel Ya/Tidak dan minimal satu Ya. Respons Mungkin serta destinasi tanpa penilaian dikeluarkan dari kandidat evaluasi.

| Metode | Ketepatan 5 hasil | Cakupan 5 hasil | Kualitas urutan 5 hasil |
|---|---:|---:|---:|
| Forward Chaining | 56.86% | 56.57% | 66.17% |
| CBR | 56.70% | 56.93% | 65.04% |
| Popularitas | 56.95% | 56.62% | 66.10% |

Forward Chaining hampir setara dengan popularitas. CBR memiliki cakupan tertinggi, sedangkan ketepatan dan kualitas urutannya sedikit lebih rendah. Belum dilakukan uji signifikansi statistik atas perbedaan tersebut.

## Pemeriksaan antarmuka

Alur yang diperiksa melalui browser meliputi konsultasi awal sampai hasil, pemilihan satu/beberapa jawaban, perpindahan tab metode dengan keyboard, perubahan cabang, validasi pilihan kosong, semua jawaban belum tahu, serta kegagalan koneksi dan percobaan ulang. Nama, urutan, dan jumlah respons pendukung pada contoh hasil sesuai dengan API yang diperiksa.

Pada lebar 320 piksel, halaman tidak meluap secara horizontal; tabel bergulir di dalam wadahnya. Tampilan desktop juga diperiksa pada lebar 1.280 piksel. Pengujian ini memakai alur perwakilan, bukan seluruh kombinasi preferensi dan perangkat.

## Mengulang pemeriksaan

Dari folder proyek dan setelah lingkungan Python aktif:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --test tests/frontend_regression.cjs
python -m backend.audit --write-evaluation
```

Bukti terstruktur disimpan pada `artifacts/process_audit.json`; berkas tersebut mencatat hash sumber, model, evaluasi, dan contoh keluaran setiap kelompok. Ringkasan metrik aktif tersedia pada `artifacts/evaluation.json`. Pengujian frontend memerlukan Node.js.

## Batas interpretasi

Keluaran yang sesuai berarti konsisten dengan aturan, perhitungan, dan label dataset yang diperiksa. Dataset tidak menyediakan atribut destinasi terverifikasi untuk menjamin kesesuaian pantai, harga, keamanan, atau kondisi terkini. Evaluasi mengukur kandidat yang telah dinilai dan belum membuktikan kualitas rekomendasi seluruh katalog atau kepuasan perjalanan nyata.

Aturan yang diekstrak menyatakan status cabang pohon dan belum divalidasi sebagai pengetahuan pakar pariwisata. Aplikasi diuji pada Python 3.14 di macOS; belum diuji langsung pada semua sistem operasi.
