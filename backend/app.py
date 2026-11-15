import json
import logging
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .cases import load_individual
from .domain import CATEGORIES, DATA_VERSION, MODES, QUESTIONS, REGIONS
from .engine import recommend

ROOT = Path(__file__).resolve().parents[1]
CASE_SOURCE = "https://data.mendeley.com/datasets/h58s544674/1"
CASE_PATH = ROOT / "artifacts/cbr.json"
CASE_V4_PATH = ROOT / "artifacts/cbr-cases-v4.json"


def load_case_base():
    try:
        return load_individual(CASE_V4_PATH)
    except FileNotFoundError:
        pass
    except (OSError, ValueError, KeyError, TypeError):
        logging.getLogger(__name__).warning("Basis individual tidak valid. Mencoba ringkasan lama.")
    try:
        legacy = json.loads(CASE_PATH.read_text(encoding="utf-8"))
        if isinstance(legacy, dict) and legacy.get("version") == DATA_VERSION and legacy.get("places"):
            return legacy, None
    except (OSError, ValueError):
        pass
    return {}, None


case_base, case_index = load_case_base()
catalog = case_base.get("places", [])
addresses = {place["AttractionId"]: place["AttractionAddress"] for place in case_base.get("audit", {}).get("catalog", [])}
REGION_CHOICES = {"all": "Semua wilayah", **REGIONS}


app = FastAPI(title="Tourguider", description="Rekomendasi objek wisata dengan Case-Based Reasoning.")
app.mount("/assets", StaticFiles(directory=ROOT / "frontend/assets"), name="assets")


class ConsultationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: dict[str, list[str]] = Field(default_factory=dict, max_length=5)


def consultation(answers):
    if not catalog:
        raise HTTPException(503, "Katalog wisata belum tersedia.")
    valid = {"region": REGION_CHOICES, "mode": MODES, "category": CATEGORIES}
    for key, values in answers.items():
        if key not in valid or len(values) != 1 or values[0] not in valid[key]:
            raise HTTPException(422, "Pilihan konsultasi tidak valid.")

    def available(preferences):
        if case_index is not None:
            return case_index.has_match(preferences)
        return recommend(catalog, preferences)[0] is not None

    def has_match(prefix):
        return any(
            available({"region": region, "mode": mode, "category": category})
            for region in (prefix.get("region", "all"),)
            for mode in ([prefix["mode"]] if "mode" in prefix else MODES)
            for category in ([prefix["category"]] if "category" in prefix else ["all"])
        )

    accepted = {}
    summary = []
    for key, (label, prompt, _) in QUESTIONS.items():
        choices = valid[key]
        if key not in answers:
            return {
                "status": "question", "answers": accepted, "summary": summary,
                "question_number": len(accepted) + 1,
                "question": {
                    "id": key, "label": label, "prompt": prompt, "options": choices,
                    "unavailable": [value for value in choices if not has_match(
                        {**{k: v[0] for k, v in accepted.items()}, key: value}
                    )],
                },
            }
        value = answers[key][0]
        accepted[key] = [value]
        summary.append({"label": label, "value": choices[value]})

    preferences = {key: values[0] for key, values in accepted.items()}
    if case_index is not None:
        result, trace = case_index.recommend(preferences)
    else:
        result, trace = recommend(catalog, preferences)
        trace.update(policy_version=DATA_VERSION, evidence_type="legacy_summary")
    alternatives = []
    if result:
        region = REGIONS[result["region"]]
        name = result["name"]
        access = "Gunakan nama tempat di peta, lalu konfirmasikan titik masuk dan jam kunjungan sebelum berangkat."
        operator_url = None
        if result["id"] == 841:
            access = "Pintu masuk di Jl. Kartika Plaza, Kuta. Cek jam dan ketentuan kunjungan di situs Waterbom."
            operator_url = "https://www.waterbom-bali.com/contact-us"
        if result["id"] == 897:
            access = "Coban Rondo berada di Desa Pandesari, Kecamatan Pujon. Cek kondisi akses dan jam kunjungan sebelum berangkat."
            operator_url = "https://kamasuta.malangkab.go.id/data-nilai-public?id=9555"
        if result["id"] == 1171:
            access = "Tentukan lokasi kunjungan di lereng Merapi dan konfirmasikan akses dengan pengelola. Hasil ini tidak menilai kelayakan pendakian."
        result.update(
            region=region,
            map_url="https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": f"{name}, {region}, Indonesia"}),
            recorded_location="Desa Pandesari, Pujon, Kabupaten Malang" if result["id"] == 897 else addresses.get(result["id"]),
            access=access,
            source=CASE_SOURCE,
            operator_url=operator_url,
            reason=f"Ada {trace['reviewer_count']} pengguna berbeda dengan tipe perjalanan yang sama. Skor akhir {trace['score']:.2f} dari 5.",
        )
    else:
        for key, label in (("category", "Cari semua jenis wisata"), ("region", "Cari di semua wilayah")):
            revised = {**preferences, key: "all"}
            if revised != preferences and has_match(revised):
                alternatives.append({"label": label, "answers": {k: [v] for k, v in revised.items()}})
        if not alternatives:
            for mode, label in MODES.items():
                revised = {**preferences, "mode": mode}
                if mode != preferences["mode"] and has_match(revised):
                    alternatives.append({
                        "label": f"Ubah rombongan ke {label}",
                        "answers": {key: [value] for key, value in revised.items()},
                    })
    return {
        "status": "recommended" if result else "insufficient_support",
        "answers": accepted, "summary": summary, "recommendation": result,
        "trace": trace, "alternatives": alternatives,
    }


@app.get("/api/health")
def health():
    return {"status": "ready" if catalog else "model_missing",
            "version": case_base.get("version"),
            "evidence_type": "individual" if case_index is not None else "legacy_summary" if catalog else None}


@app.post("/api/consultations/start")
def start():
    return consultation({})


@app.post("/api/consultations/answer")
def answer(body: ConsultationRequest):
    return consultation(body.answers)


@app.get("/api/project")
def project():
    return {
        "policy_version": case_base.get("version"),
        "catalog_count": len(catalog),
        "evaluation": case_base.get("evaluation"),
        "regions": REGION_CHOICES,
    }


@app.get("/")
@app.get("/alur-cbr")
def index():
    return FileResponse(ROOT / "frontend/index.html", headers={"Cache-Control": "no-store"})
