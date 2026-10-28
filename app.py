```python
import streamlit as st

st.set_page_config(
    page_title="Travelmaker",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 Travelmaker")
st.subheader("Sistem Rekomendasi Destinasi Wisata Berbasis CBR")

st.markdown("""
Selamat datang di **Travelmaker**, sebuah prototipe sistem rekomendasi
destinasi wisata berdasarkan preferensi wisatawan menggunakan
pendekatan **Case-Based Reasoning (CBR)**.

### Tujuan Proyek

Aplikasi ini dikembangkan untuk mengeksplorasi penerapan CBR dalam
merekomendasikan destinasi wisata berdasarkan kemiripan preferensi
pengguna dan respons wisatawan terdahulu.

### Rencana Fitur

- Input preferensi wisatawan.
- Perhitungan kemiripan antar kasus.
- Pemeringkatan destinasi berdasarkan respons historis.
- Tampilan hasil rekomendasi.
- Dashboard analisis dan evaluasi.

### Status Pengembangan

Prototipe tahap awal — pengembangan antarmuka dan algoritma CBR
akan dilakukan secara bertahap.
""")

st.info(
    "Versi ini merupakan kerangka awal aplikasi. "
    "Fitur rekomendasi belum diimplementasikan."
)
```