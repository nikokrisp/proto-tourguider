"""Retrieve and rank sourced visit scenarios, with one result per consultation."""
from collections import Counter
from itertools import combinations
from urllib.parse import urlencode

from .domain import MODES

PROVINCES = {
    "bali": "Bali", "yogyakarta": "DI Yogyakarta", "jawa-barat": "Jawa Barat",
    "jawa-tengah": "Jawa Tengah", "jawa-timur": "Jawa Timur", "ntb": "Nusa Tenggara Barat",
    "sumatera-barat": "Sumatera Barat", "sulawesi-selatan": "Sulawesi Selatan",
}
CATEGORIES = {
    "all": "Semua jenis wisata", "nature": "Alam", "culture": "Budaya dan sejarah",
    "recreation": "Rekreasi", "volcano": "Gunung dan vulkanologi",
}
ACTIVITIES = {"visit": "Kunjungan wisata", "hike": "Pendakian"}
DURATIONS = {"any": "Tanpa batas", "half-day": "Maksimal 4 jam", "day": "Maksimal 8 jam"}
MINUTES = {"half-day": 240, "day": 480}
VERSION = "curated-indonesia-1"


def options(catalog):
    counts = Counter(place["region"] for place in catalog)
    return {"all": f"Semua wilayah ({len(catalog)} tempat)", **{
        key: f"{name} ({counts[key]} tempat)" for key, name in PROVINCES.items() if counts[key]
    }}


def questions(catalog, answers):
    result = [
        ("region", "Wilayah", "Mau berwisata ke mana?", options(catalog)),
        ("category", "Minat wisata", "Jenis wisata apa yang kamu cari?", CATEGORIES),
    ]
    if answers.get("category") == ["volcano"]:
        result.append(("activity", "Aktivitas gunung", "Ingin berwisata atau mendaki?", ACTIVITIES))
    return result + [
        ("mode", "Tipe rombongan", "Kamu pergi dengan siapa?", MODES),
        ("duration", "Durasi", "Berapa waktu yang kamu punya di lokasi?", DURATIONS),
    ]


def retrieve(catalog, answers):
    for place in catalog:
        if answers["region"] not in ("all", place["region"]):
            continue
        for case in place["cases"]:
            if answers["category"] not in ("all", case["category"]):
                continue
            # Hiking is opt-in even when the user chooses all categories.
            if case.get("activity") == "hike" and answers.get("activity") != "hike":
                continue
            if answers.get("activity") and case.get("activity") != answers["activity"]:
                continue
            if case.get("allowed_modes") and answers["mode"] not in case["allowed_modes"]:
                continue
            limit = MINUTES.get(answers["duration"])
            if limit and (case.get("minutes") is None or case["minutes"] > limit):
                continue
            yield place, case


def unavailable_options(catalog, accepted, field, choices):
    """Check whether each choice can lead to a result with the answers so far."""
    prefix = {key: values[0] for key, values in accepted.items()}

    def supported(answer):
        if answer.get("category") == "volcano" and "activity" not in answer:
            return any(supported({**answer, "activity": activity}) for activity in ACTIVITIES)
        if "mode" not in answer:
            return any(supported({**answer, "mode": mode}) for mode in MODES)
        return next(retrieve(catalog, {"category": "all", "duration": "any", **answer}), None) is not None

    return [value for value in choices if not supported({**prefix, field: value})]


def rank(entry, mode):
    place, case = entry
    return (
        -(mode in case.get("modes", {})),
        -sum(bool(value) for value in (
            case.get("minutes"), case.get("access"), case.get("facilities"), case.get("price"),
        )),
        place["id"], case["id"],
    )


def suggestions(catalog, answers):
    changes = [
        (field, value, label) for field, value, label in (
            ("duration", "any", "Lepas batas durasi"),
            ("region", "all", "Cari di semua wilayah"),
            ("category", "all", "Cari semua jenis wisata"),
        ) if answers[field] != value
    ]
    for size in range(1, len(changes) + 1):
        alternatives = []
        for batch in combinations(changes, size):
            revised = {**answers, **{field: value for field, value, _ in batch}}
            if revised["category"] == "all":
                revised.pop("activity", None)
            if next(retrieve(catalog, revised), None):
                alternatives.append({
                    "label": " + ".join(label for _, _, label in batch),
                    "answers": {key: [val] for key, val in revised.items()},
                })
        if alternatives:
            return alternatives
    return []



def recommend(catalog, answers):
    retrieved = sorted(retrieve(catalog, answers), key=lambda entry: rank(entry, answers["mode"]))
    trace = {"eligible_places": len({place["id"] for place, _ in retrieved}), "case_count": len(retrieved)}
    if not retrieved:
        return None, trace, suggestions(catalog, answers)

    place, case = retrieved[0]
    mode_evidence = case.get("modes", {}).get(answers["mode"])
    trace.update(case={
        "title": case["title"], "evidence": case["evidence"], "source": case["source"],
        "mode_match": bool(mode_evidence), "mode_evidence": mode_evidence,
        "criteria": [
            f"Wilayah · {PROVINCES[place['region']]}",
            f"Minat · {CATEGORIES[case['category']]}",
            *([f"Aktivitas · {ACTIVITIES[case['activity']]}"] if case.get("activity") else []),
            *([f"Durasi · {case['minutes']} menit"] if case.get("minutes") else []),
        ],
    })
    map_query = urlencode({"api": 1, "query": f"{place['lat']},{place['lon']}"})
    return {
        "id": place["id"], "name": place["name"], "region": PROVINCES[place["region"]],
        "district": place["district"], "category": CATEGORIES[case["category"]],
        "activity": ACTIVITIES.get(case.get("activity")), "route": case.get("route"),
        "coordinate_source": place["coordinate_source"],
        "map_url": "https://www.google.com/maps/search/?" + map_query,
        "source": place["source"], "checked": place["checked"],
        "reason": case["evidence"], "mode_evidence": mode_evidence,
        **{key: case[key] for key in ("minutes", "access", "facilities", "price") if case.get(key)},
    }, trace, []
