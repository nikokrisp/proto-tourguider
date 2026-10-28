"""Documented Stravl fields and shared, deterministic feature encoding."""
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SEED = 42
QUESTIONS = {
    "form_a": {"title": "Siapa yang ikut dalam perjalananmu?", "label": "Usia rombongan", "hint": "Pilih semua kelompok usia yang ikut.", "multiple": True, "options": [("0", "0–19 tahun"), ("1", "20–39 tahun"), ("2", "40–59 tahun"), ("3", "60 tahun ke atas")]},
    "form_b": {"title": "Berapa anggaran perjalananmu?", "label": "Anggaran", "hint": "Per orang, per malam, dalam dolar AS. Ini preferensi anggaran, bukan harga destinasi.", "multiple": True, "options": [("0", "US$0–49"), ("1", "US$50–99"), ("2", "US$100–249"), ("3", "US$300+")]},
    "form_c": {"title": "Pada musim apa kamu ingin bepergian?", "label": "Musim", "hint": "Mengikuti empat kategori musim pada dataset Stravl.", "multiple": False, "options": [("0", "Musim dingin"), ("1", "Musim semi"), ("2", "Musim panas"), ("3", "Musim gugur")]},
    "form_f": {"title": "Pengalaman seperti apa yang kamu cari?", "label": "Pengalaman", "hint": "Boleh pilih lebih dari satu. Apa yang paling ingin kamu temukan?", "multiple": True, "options": [("0", "Pantai"), ("1", "Petualangan"), ("2", "Alam"), ("3", "Budaya"), ("4", "Kehidupan malam"), ("5", "Sejarah"), ("6", "Belanja"), ("7", "Kuliner")]},
    "form_g": {"title": "Pemandangan apa yang ingin kamu nikmati?", "label": "Pemandangan", "hint": "Pilih semua suasana yang menarik buatmu.", "multiple": True, "options": [("0", "Perkotaan"), ("1", "Pedesaan"), ("2", "Laut"), ("3", "Pegunungan"), ("4", "Danau"), ("5", "Gurun"), ("6", "Dataran"), ("7", "Hutan tropis")]},
    "form_h": {"title": "Bagaimana ritme liburan idealmu?", "label": "Aktivitas", "hint": "Tidak ada jawaban yang salah. Pilih ritme yang paling nyaman.", "multiple": False, "options": [("0", "Santai dan rileks"), ("1", "Seimbang"), ("2", "Aktif dan penuh kegiatan")]},
    "form_i": {"title": "Seberapa besar perhatianmu pada keamanan?", "label": "Preferensi keamanan", "hint": "Jawaban ini menggambarkan preferensimu, bukan penilaian keamanan suatu tempat.", "multiple": False, "options": [("0", "Sangat memperhatikan"), ("1", "Seimbang"), ("2", "Siap menghadapi tantangan")]},
    "form_j": {"title": "Seberapa populer tempat yang ingin kamu kunjungi?", "label": "Popularitas", "hint": "Boleh memilih beberapa tipe destinasi.", "multiple": True, "options": [("0", "Jarang dikunjungi"), ("1", "Destinasi klasik"), ("2", "Populer dan sedang tren")]},
}
FEATURES = [(field, value) for field, q in QUESTIONS.items() for value in [v for v, _ in q["options"]] + ["__missing__"]]
FIELD_COLUMNS = {field: [i for i, (f, _) in enumerate(FEATURES) if f == field] for field in QUESTIONS}


def encode(answers):
    x = np.zeros(len(FEATURES), dtype=np.float32)
    for i, (field, value) in enumerate(FEATURES):
        values = answers.get(field, [])
        x[i] = (not values) if value == "__missing__" else value in values
    return x


def question(field):
    q = QUESTIONS[field]
    return {"field": field, **{k: v for k, v in q.items() if k != "options"}, "options": [{"value": v, "label": label} for v, label in q["options"]]}


def answer_summary(answers):
    return [{"field": f, "label": QUESTIONS[f]["label"], "values": v, "text": ", ".join(dict(QUESTIONS[f]["options"])[a] for a in v) if v else "Belum tahu"} for f, v in answers.items()]


def feature_description(index):
    field, value = FEATURES[index]
    option = "jawaban belum diketahui" if value == "__missing__" else dict(QUESTIONS[field]["options"])[value]
    return f"{QUESTIONS[field]['label']}: {option}"
