import json
import logging
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .cases import load_individual
from .domain import CATEGORIES, DATA_VERSION, MIN_REVIEWERS, MODES, PRIOR_WEIGHT, QUESTIONS, REGIONS
from .engine import recommend

ROOT = Path(__file__).resolve().parents[1]
CASE_SOURCE = "https://data.mendeley.com/datasets/h58s544674/1"
CASE_PATH = ROOT / "artifacts/cbr.json"
CASE_V4_PATH = ROOT / "artifacts/cbr-cases-v4.json"
EVAL_PATH = ROOT / "docs/cbr-evaluation.json"


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


@app.get("/api/catalog")
def get_catalog():
    if not catalog:
        raise HTTPException(503, "Katalog wisata belum tersedia.")
    min_reviewers = case_index.minimum if case_index is not None else MIN_REVIEWERS
    items = []
    for place in catalog:
        place_id = place["id"]
        region_code = place["region"]
        category_code = place["category"]
        region_label = REGIONS[region_code]
        if case_index is not None:
            mode_counts = {mode: case_index.support.get((place_id, mode), 0) for mode in MODES}
            hist_mean = case_index.priors[place_id]
        else:
            groups = place.get("groups", {})
            mode_counts = {mode: groups.get(mode, {}).get("count", 0) for mode in MODES}
            hist_mean = place.get("historical_mean", 0.0)
        items.append({
            "id": place_id,
            "name": place["name"],
            "region": region_code,
            "region_label": region_label,
            "category": category_code,
            "category_label": CATEGORIES.get(category_code, category_code),
            "historical_mean": hist_mean,
            "mode_counts": mode_counts,
            "total_mode_reviewers": sum(mode_counts.values()),
            "address": "Desa Pandesari, Pujon, Kabupaten Malang" if place_id == 897 else addresses.get(place_id),
            "map_url": "https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": f"{place['name']}, {region_label}, Indonesia"}),
        })
    items.sort(key=lambda x: (-x["historical_mean"], -x["total_mode_reviewers"], x["id"]))
    return {
        "places": items,
        "min_reviewers": min_reviewers,
        "regions": REGIONS,
        "categories": {k: v for k, v in CATEGORIES.items() if k != "all"},
        "modes": MODES,
    }


@app.get("/api/overview")
def overview():
    if not catalog:
        raise HTTPException(503, "Katalog wisata belum tersedia.")
    audit = case_base.get("audit", {})
    eval_doc = {}
    if EVAL_PATH.exists():
        try:
            eval_doc = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            eval_doc = {}

    eval_audit = eval_doc.get("audit", {})
    visits_by_region = eval_audit.get("active_by_region") or audit.get("visits_by_region") or {}
    total_visits = sum(visits_by_region.values()) or audit.get("clean_visits", 0)
    places_by_region = {code: sum(1 for p in catalog if p["region"] == code) for code in REGIONS}
    regions_summary = [
        {
            "code": code,
            "label": label,
            "places": places_by_region.get(code, 0),
            "visits": visits_by_region.get(code, 0),
            "share": (visits_by_region.get(code, 0) / total_visits * 100) if total_visits else 0,
        }
        for code, label in REGIONS.items()
    ]
    rating_all = eval_doc.get("rating", {}).get("all", {})
    models = rating_all.get("models", {})
    cbr_metrics = models.get("C", {}).get("common_support", {})
    base_metrics = models.get("A", {}).get("common_support", {})
    fallback_eval = case_base.get("evaluation", {}).get("overall", {})
    cov_before = eval_doc.get("coverage_before", {})
    cov_after = eval_doc.get("coverage_after", {})
    total_cov_before = sum(v.get("supported", 0) for v in cov_before.values()) if cov_before else None
    total_cov_after = sum(v.get("supported", 0) for v in cov_after.values()) if cov_after else None
    return {
        "policy_version": case_base.get("version"),
        "evidence_type": "individual" if case_index is not None else "legacy_summary",
        "min_reviewers": case_index.minimum if case_index is not None else MIN_REVIEWERS,
        "prior_weight": case_index.prior_weight if case_index is not None else PRIOR_WEIGHT,
        "counts": {
            "raw_visits": eval_audit.get("raw_visits", audit.get("raw_visits", 0)),
            "duplicates_removed": eval_audit.get("duplicates_removed", audit.get("duplicates_removed", 0)),
            "conflicting_rows_removed": eval_audit.get("conflicting_rows_removed", audit.get("conflicting_rows_removed", 0)),
            "excluded_visits": sum(eval_audit.get("excluded_visits", {}).values()),
            "active_visits": eval_audit.get("active_visits", total_visits),
            "active_reviewers": eval_audit.get("active_reviewers", audit.get("clean_reviewers", 0)),
            "active_places": len(catalog),
            "excluded_places": len(audit.get("excluded_from_recommendations", [])),
        },
        "regions": regions_summary,
        "evaluation": {
            "cases": rating_all.get("common_cases", fallback_eval.get("cases", 0)),
            "held_out_cases": rating_all.get("held_out_cases", 0),
            "cbr_mae": cbr_metrics.get("mae", fallback_eval.get("cbr_mae")),
            "baseline_mae": base_metrics.get("mae", fallback_eval.get("baseline_mae")),
            "cbr_rmse": cbr_metrics.get("rmse"),
            "baseline_rmse": base_metrics.get("rmse"),
            "coverage_before_total": total_cov_before,
            "coverage_after_total": total_cov_after,
            "coverage_before": cov_before,
            "coverage_after": cov_after,
        },
        "source": CASE_SOURCE,
    }


@app.get("/")
@app.get("/alur-cbr")
@app.get("/basis-kasus")
@app.get("/evaluasi")
def index():
    return FileResponse(ROOT / "frontend/index.html", headers={"Cache-Control": "no-store"})
