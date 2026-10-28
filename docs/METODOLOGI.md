# Metodologi Tourguider

Pakai delapan kelompok `form_a/b/c/f/g/h/i/j`, representasi multi-hot ditambah penanda kosong. `form_b` dan `form_j` mempertahankan pilihan banyak yang memang muncul pada data, termasuk pilihan semua kategori. Label anggaran mengikuti README asli; rentang US$250–299 tidak ditambahkan karena tidak didefinisikan sumber. Nilai kosong tidak disamakan dengan jawaban negatif.

Gabungkan rekaman identik selain ID terlebih dahulu. Dalam tiap rekaman, hitung suatu swipe sekali dan keluarkan seluruh label untuk pasangan pengguna–destinasi yang bertentangan. Rekaman tanpa interaksi bersih tidak masuk basis kasus. `form_k`, preferensi wilayah yang mayoritas kosong, informasi algoritma lama, rekomendasi lama, dan rating lama tidak dipakai sebagai fitur. Makna rating `0` tidak dijelaskan di README.

Pembagian pengguna 80:20, seed 42, dilakukan sebelum ekspansi pasangan. Setiap pasangan profil–destinasi Yes menjadi sampel untuk `DecisionTreeClassifier(max_depth=5, min_samples_leaf=200)`. Total bobot sampel setiap pengguna yang memiliki Yes adalah 1. Target adalah destinasi yang disukai, bukan satu destinasi favorit atau perjalanan yang benar-benar dilakukan. No dan Maybe tidak melatih pohon ini; keduanya tetap menjadi bagian CBR.

Mesin forward chaining tidak memanggil `tree.predict`: memori kerja dimulai dari `node:0`, aturan aktif memeriksa fakta jawaban, menambah kesimpulan cabang, dan melanjutkan sampai kesimpulan daun. Pengatur pertanyaan meminta fakta yang belum diketahui pada cabang aktif. Setiap pertanyaan kelompok ditampilkan sekali. Daun menyimpan distribusi berbobot destinasi Yes dan jumlah pengguna pendukung yang berbeda untuk setiap destinasi.

CBR menghitung cosine similarity hanya pada kelompok preferensi yang sudah ditanyakan dan memiliki jawaban yang ditentukan. Jawaban “belum tahu” dikeluarkan dari perhitungan kemiripan. Maksimal 20 tetangga dengan kemiripan positif dipilih, ikatan diputus dengan urutan kasus yang tetap. Untuk setiap destinasi:

```text
skor = (1 + Σ kemiripan × nilai_respons) / (2 + Σ kemiripan_pada_respons_teramati)
nilai_respons: Yes = 1, Maybe = 0.5, No = 0
```

Kecocokan CBR memerlukan minimal satu respons Yes dari tetangga. Destinasi yang hanya mendapat No tanpa Yes dari tetangga diblokir, termasuk dari alternatif populer. Maybe tetap berkontribusi pada skor untuk destinasi yang memiliki dukungan Yes. Jika hasil yang didukung kurang dari lima, daftar dilengkapi dari popularitas Yes di data pelatihan, dengan penanda alternatif populer. Bila semua jawaban belum tahu, kedua tab menampilkan alternatif populer secara eksplisit, tanpa klaim personalisasi atau pengguna serupa. Angka kemiripan bukan probabilitas kecocokan. Rekomendasi kedua metode tidak digabung menjadi satu skor.

### Evaluasi

Semua pengguna uji dengan minimal lima kandidat Yes/No dan minimal satu Yes dinilai; Maybe dan destinasi tanpa penilaian dikeluarkan dari kandidat evaluasi. Forward chaining, CBR, dan popularitas memakai kandidat yang sama. Jawaban untuk CBR terbatas pada jalur pohon masing-masing pengguna, sama seperti konsultasi. Precision@5, Recall@5, dan NDCG@5 dirata-ratakan per pengguna. Pemilihan kasus memakai irisan fitur biner dan aritmetika yang sama pada konsultasi maupun evaluasi; selisih pembulatan float32 tidak memecah ikatan tetangga secara berbeda. Kebijakan dukungan dan alternatif populer juga memakai fungsi yang sama. Jumlah yang masuk dan dikeluarkan dilaporkan dalam `artifacts/evaluation.json`.

Ini evaluasi pemeringkatan kandidat yang sudah dinilai, bukan top-5 seluruh katalog. Paparan destinasi pada situs asal, ketimpangan popularitas, profil tanpa Yes, dan interaksi yang jarang membatasi interpretasi. Hasil yang lebih rendah dari popularitas tetap dilaporkan; tidak ada klaim bahwa metode yang lebih kompleks pasti unggul.

### Melatih dan memeriksa ulang

```sh
python -m backend.train
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --test tests/frontend_regression.cjs
python -m backend.audit --write-evaluation
```

Pelatihan membangun ulang seluruh artefak dan membuktikan kesetaraan aturan terhadap pohon pada setiap profil bersih, baik pelatihan maupun pengujian. Setelah melatih ulang, mulai ulang server agar model baru dimuat. Model disimpan dengan joblib dan terikat versi scikit-learn di `requirements.txt`; muat hanya artefak proyek ini yang dipercaya. Untuk versi library lain, latih ulang dari CSV.

## Antarmuka API

Dokumentasi interaktif: [API docs](http://127.0.0.1:8765/docs).

- `POST /api/consultations/start`: tubuh `{}`; mulai ulang tanpa jawaban.
- `POST /api/consultations/answer`: tubuh `{"answers":{"form_a":["1"]}}`. Kirim jawaban kumulatif; daftar kosong berarti pengguna memilih belum tahu. Jawaban cabang yang tidak aktif diabaikan pada keluaran dan CBR.
- `GET /api/project`: ringkasan audit dan evaluasi.
- `GET /api/health`: kesiapan model.

Konsultasi tidak memakai sesi server, cookie, akun, atau basis data. Jawaban hanya disimpan pada memori halaman; memuat ulang halaman mengawali konsultasi baru. Respons konsultasi memuat `complete`, `answers`, `summary`, `question`, `trace`, dan `results`. Masukan di luar kamus atau format salah menghasilkan 422; model yang belum tersedia menghasilkan 503.

## Sumber dan batasan

- Dataset: [Stravl/Stravl-Data](https://github.com/Stravl/Stravl-Data). README pemilik mengizinkan penggunaan akademik dan komersial; tidak ada lisensi terpisah pada repositori saat diperiksa. CSV SHA-256: `16dd0d5e83c4c2952f073c4bbdd94f25678f5a537753cee4994bb2d6f0484792`.
- Acuan metode: Mustafa, Saad, dan Rizkallah (2023), [Building an enhanced case-based reasoning and rule-based systems for medical diagnosis](https://doi.org/10.1186/s44147-023-00315-4). Ini adaptasi domain dan metode yang disederhanakan, bukan replikasi hasil atau implementasi Stravl asli.
- Desain: [Swap — Refero Styles](https://styles.refero.design/style/15d10d6c-1844-46c6-ae69-c99a56e6ad41). Gaya visual diadaptasi; merek dan halaman sumber tidak disalin.
- Font: Cormorant Garamond dan Inter dari Google Fonts, SIL Open Font License. Teks lisensi disertakan di `frontend/assets/`.

Data hanya menunjukkan ketertarikan. Tidak tersedia atribut harga, keamanan, foto, kondisi terkini, atau kepuasan perjalanan. Anggaran dan perhatian terhadap keamanan adalah preferensi pengguna, bukan jaminan kondisi destinasi. Mayoritas pertanyaan yang tidak membantu pohon membedakan kelompok mungkin tidak muncul; itulah perilaku alur berbasis data. Proyek ini untuk pembelajaran dan demo lokal.

## Audit proses

Lihat [laporan validasi](../AUDIT.md) untuk pemeriksaan independen terhadap CSV, regresi frontend/backend, dan pengujian browser. `artifacts/process_audit.json` memuat 17 pemeriksaan data/perhitungan, hash sumber/model/evaluasi, serta contoh keluaran dari seluruh 32 daun. Website hanya menampilkan evaluasi dengan versi kebijakan yang sesuai.

API hasil menyertakan `evidence_scope`, `evidence`, `ranking_score`, `fallback`, dan status personalisasi agar rekomendasi dapat ditelusuri. Skor pemeringkatan merupakan nilai internal dan bukan persentase akurasi atau peluang kepuasan.
