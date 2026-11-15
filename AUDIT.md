# Audit sumber dan arsip Tourguider Indonesia

**Versi aktif:** 46.989 kunjungan individual dari 32.915 pengulas pada 27 tempat. Rincian verifikasi dan hasil terbaru ada di [metodologi](docs/METODOLOGI.md).

## Arsip katalog kurasi

Pemeriksaan sumber pada 4 November 2026. Versi kurasi saat itu berisi **75 tempat dan 162 skenario kurasi dari delapan provinsi**. Setiap tempat memiliki lokasi, titik peta, rujukan, dan tanggal pemeriksaan. Versi kurasi memakai skenario dan bukti dari sumber pengelola.

## Pemeriksaan sumber dan cakupan

- [Jadesta](https://jadesta.kemenpar.go.id/desa) menyediakan profil desa, label administrasi, pin peta, dan jenis atraksi. Terima profil dengan tanda verifikasi, pin, dan kegiatan tercatat. Dedup berdasarkan nama/wilayah dan pin yang sama. Singkirkan pin nol dan koordinat di luar rentang geografis wajar wilayah. Contoh yang disisihkan adalah Sembalun Lawang dan Prenggan dengan pin di Jakarta, serta profil Borobudur dengan nilai bujur tanpa titik desimal. Pemeriksaan ini mencocokkan pin dengan sumber dan rentang wilayah, dengan keterbatasan bahwa batas administrasi presisi belum diperiksa melalui poligon.
- [Sisparnas](https://sisparnas.kemenpar.go.id/p/14632), [Dinas Pariwisata Jawa Tengah](https://visitjawatengah.jatengprov.go.id/id/regency/kabupaten-banjarnegara/destinasi-wisata/kawah-sikidang), [BIG](https://sinar.big.go.id/pencarian/detail/3577), [Disparpora Subang](https://wisata.subang.go.id/view-gunung-tangkuban-parahu.jsp), dan [Sembalun Destination](https://www.sembalundestination.or.id/pendakian) mendukung lokasi atau aktivitas gunung. Pendakian Gunung Rinjani juga merujuk [Balai TN Gunung Rinjani](https://www.rinjaninationalpark.id). Status buka dan izin diperiksa melalui pengelola saat pengguna berencana berangkat.
- Pemeriksaan data menghasilkan 58 skenario alam, 55 budaya, 41 rekreasi, dan 8 gunung. Hanya 4 dari 162 skenario punya durasi yang dapat dipakai sebagai batas dan 6 punya bukti tipe rombongan khusus. Pilihan durasi dapat membatasi hasil secara signifikan. Kecocokan rombongan pada kasus lainnya masih netral.

Matriks berikut menghitung tipe rombongan (dari 5) yang menghasilkan tempat dengan durasi tanpa batas. Pada kategori gunung, satu kombinasi dihitung berhasil jika kunjungan wisata atau pendakian punya kandidat. Kategori “semua” dikecualikan agar tidak menggandakan hasil.

| Provinsi | Tempat | Alam | Budaya | Rekreasi | Gunung |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bali | 9 | 5 | 5 | 5 | 5 |
| DI Yogyakarta | 11 | 5 | 5 | 5 | 5 |
| Jawa Barat | 9 | 5 | 5 | 5 | 5 |
| Jawa Tengah | 10 | 5 | 5 | 5 | 5 |
| Jawa Timur | 7 | 5 | 5 | 5 | 0 |
| Nusa Tenggara Barat | 12 | 5 | 5 | 5 | 5 |
| Sumatera Barat | 9 | 5 | 5 | 5 | 0 |
| Sulawesi Selatan | 8 | 5 | 5 | 5 | 0 |
| **Total** | **75** | **40** | **40** | **40** | **25** |

Total **145 dari 160 kombinasi**. Cakupan ini mengukur ketersediaan kandidat, bukan penilaian wisatawan atau kualitas pengalaman di lapangan.

## Validasi

- Seluruh 26 skenario dengan kandidat yang diperkirakan layak memenuhi batas wajib dan, untuk skenario dengan ekspektasi nama, menghasilkan tempat yang diharapkan. Dua skenario tanpa kandidat menawarkan perubahan pilihan yang berhasil. Ini adalah uji penerimaan berdasarkan katalog, belum merupakan evaluasi independen oleh wisatawan. Total 34 tes otomatis lulus, termasuk validasi katalog, API, dan arsip Mendeley.
- Browser pada 1280 × 800 menampilkan Gunung Tangkuban Parahu untuk kunjungan keluarga di Jawa Barat, dengan pin dan tautan pengelola. Pada 390 × 844, perubahan jawaban tetap terisi dan Bali + pendakian + maksimal 4 jam menawarkan perluasan wilayah yang menghasilkan Bukit Pergasingan. Tidak ada luapan horizontal pada layar revisi dan hasil yang diperiksa.

## Arsip audit Mendeley


Sumber: [Tourism Dataset v1, Choirul Huda](https://doi.org/10.17632/h58s544674.1) dan [publikasi dataset](https://pmc.ncbi.nlm.nih.gov/articles/PMC10788210/).

## Pembersihan dan cakupan

Dari 52.930 transaksi, 3.722 baris identik selain ID transaksi dikeluarkan. Setelah itu 2.052 baris dikeluarkan karena pengulas, tempat, tahun, bulan, dan tipe rombongan sama tetapi rating berbeda. Tersisa 47.156 baris dari 33.009 pengulas. Kunjungan berbeda waktu dapat tetap tercatat. Untuk skor, kunjungan berulang digabung sesuai unit pengulas.

| Kelompok katalog | Kode asli | Kasus bersih | Cakupan aplikasi |
| --- | ---: | ---: | --- |
| Bali | 1 | 43.014 | Aktif |
| Malang | 2 | 827 | Kandidat perluasan |
| Yogyakarta | 3 | 3.315 | Aktif |

Kode wilayah pada katalog dipetakan dari nama dan alamat, karena penggabungan langsung dengan tabel kota menghasilkan lokasi berbeda (Douala, South Region, N’Djamena). Wilayah di aplikasi mengikuti kelompok katalog sumber. Daftar lengkap 30 tempat, alamat, kategori, kode sumber, dan checksum berkas yang dipakai tersedia di bagian `audit` pada `artifacts/cbr.json`. Kategori gunung berasal dari tipe sumber `Volcanos`. Cakupan aktif berisi 20 tempat, termasuk satu gunung, Gunung Merapi.

## Evaluasi

Uji pada wilayah aktif memakai pembagian 80:20 menurut pengulas dengan seed 42. Ada 25.994 pengulas latih dan 6.499 pengulas uji. Unit evaluasi adalah rating rata-rata per pengulas, tempat, dan tipe rombongan. Kedua metode dinilai pada 8.966 dari 8.967 kasus uji yang mempunyai dukungan latih cukup untuk CBR. Nilai MAE lebih kecil berarti prediksi rating lebih dekat dengan rating yang tercatat.

| Wilayah | Rombongan | Kasus uji | MAE CBR | MAE historis | Cakupan pilihan |
| --- | --- | ---: | ---: | ---: | ---: |
| Bali | Bisnis | 55 | 0,6247 | 0,6288 | 4/5 |
| Bali | Pasangan | 3.676 | 0,7530 | 0,7513 | 4/5 |
| Bali | Keluarga | 2.384 | 0,6971 | 0,6986 | 4/5 |
| Bali | Teman | 1.593 | 0,7251 | 0,7238 | 4/5 |
| Bali | Solo | 627 | 0,7341 | 0,7319 | 4/5 |
| Yogyakarta | Bisnis | 26 | 0,4716 | 0,5110 | 4/5 |
| Yogyakarta | Pasangan | 170 | 0,8578 | 0,8476 | 5/5 |
| Yogyakarta | Keluarga | 147 | 0,6985 | 0,7006 | 5/5 |
| Yogyakarta | Teman | 201 | 0,7366 | 0,7387 | 5/5 |
| Yogyakarta | Solo | 87 | 0,8811 | 0,9091 | 5/5 |
| **Total** | | **8.966** | **0,7322** | **0,7318** | **44/50** |

Cakupan menghitung berapa pilihan minat yang menghasilkan minimal satu tempat dengan dukungan cukup per wilayah dan tipe rombongan. Hasil cakupan sama pada basis latih dan basis untuk demo. CBR belum mengungguli baseline secara keseluruhan. Uji ini mengukur prediksi rating historis yang tersedia. Relevansi tempat yang tidak dikunjungi tetap tidak diketahui. Rating berasal dari kunjungan 2013–2022 dan mayoritas dari 2013–2019.

## Perluasan Malang

Basis rekomendasi sekarang memuat 27 tempat, termasuk tujuh tempat dari kelompok Malang. Coban Rondo tersedia untuk keluarga (20 pengguna berbeda) dan teman (21). Kategori Air terjun memakai kode 93 dari katalog Mendeley dan tetap tercakup pada pilihan Alam. Semeru ditahan sampai akses pendakian terkini dikonfirmasi. Pulau Sempu merupakan cagar alam dan Museum Malang Tempo Doeloe dilaporkan tutup permanen. Ketiga tempat tetap tercatat pada audit sumber.

Evaluasi ulang 80:20 berdasarkan pengguna, seed 42, pada katalog aktif menghasilkan MAE CBR 0,7250 dan baseline 0,7240 dari 9.201 kasus yang memenuhi ambang. Angka arsip di atas memakai cakupan versi sebelumnya.
