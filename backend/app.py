from contextlib import asynccontextmanager
import json
import logging
import joblib
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .domain import ROOT, QUESTIONS, answer_summary, question
from .engine import Recommender, infer, POLICY_VERSION

rec = None


@asynccontextmanager
async def lifespan(app):
    global rec
    rec = None
    path = ROOT / "artifacts/model.joblib"
    if path.exists():
        rec = Recommender(joblib.load(path))
    yield
    rec = None


app = FastAPI(title="Tourguider", description="Proyek mata kuliah Sistem Berbasis Pengetahuan: rekomendasi wisata dengan forward chaining dan case-based reasoning.", lifespan=lifespan)
app.mount("/assets", StaticFiles(directory=ROOT / "frontend/assets"), name="assets")


class ConsultationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: dict[str, list[str]] = Field(default_factory=dict, max_length=8)

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, answers):
        for f, vals in answers.items():
            if f not in QUESTIONS:
                raise ValueError("Kelompok pertanyaan tidak dikenal.")
            q = QUESTIONS[f]
            if any(v not in dict(q["options"]) for v in vals) or len(set(vals)) != len(vals):
                raise ValueError("Pilihan tidak valid atau berulang.")
            if not q["multiple"] and len(vals) > 1:
                raise ValueError("Pertanyaan ini hanya menerima satu pilihan.")
        return answers


def require_model():
    if rec is None:
        raise HTTPException(503, "Model belum tersedia. Jalankan python -m backend.train terlebih dahulu.")
    return rec


def consultation(answers):
    model = require_model()
    state = infer(model.rules, answers)
    effective = {f: answers[f] for f in state["used_fields"] if f in answers}
    out = {"complete": state["leaf"] is not None, "answers": effective, "summary": answer_summary(effective), "question": question(state["next_field"]) if state["next_field"] else None, "question_number": len(effective) + (state["next_field"] is not None), "trace": state["trace"], "facts": state["facts"]}
    out["results"] = model.results(effective, state) if out["complete"] else None
    return out


@app.get("/api/health")
def health():
    return {"status": "ready" if rec else "model_missing"}


@app.post("/api/consultations/start")
def start():
    return consultation({})


@app.post("/api/consultations/answer")
def answer(body: ConsultationRequest):
    return consultation(body.answers)


@app.get("/api/project")
def project():
    require_model()
    return {"audit": json.loads((ROOT / "data/processed/audit.json").read_text()), "evaluation": current_evaluation(ROOT / "artifacts/evaluation.json"), "policy_version": POLICY_VERSION, "rule_count": len(rec.rules), "questions": [question(f) for f in QUESTIONS]}


def current_evaluation(path):
    if not path.exists():
        return None
    data=json.loads(path.read_text())
    return data if data.get("policy_version")==POLICY_VERSION else None


@app.get("/")
def index():
    return FileResponse(ROOT / "frontend/index.html")


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    from fastapi.responses import JSONResponse
    logging.exception("Consultation error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Ada kendala saat memproses konsultasi. Coba lagi sebentar."})
