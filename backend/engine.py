from .domain import CATEGORIES, MIN_REVIEWERS, MODES, PRIOR_WEIGHT


def score(count, similar_mean, historical_mean):
    return (count * similar_mean + PRIOR_WEIGHT * historical_mean) / (count + PRIOR_WEIGHT)


def recommend(places, answers):
    region, mode, category = (answers[key] for key in ("region", "mode", "category"))
    candidates = [
        place for place in places
        if region in ("all", place["region"]) and (category == "all" or place["category"] == category
            or (category == "nature" and place["category"] == "waterfall"))
    ]
    eligible = []
    for place in candidates:
        group = place["groups"].get(mode)
        if group and group["count"] >= MIN_REVIEWERS:
            rating = score(group["count"], group["mean"], place["historical_mean"])
            eligible.append((rating, group["count"], -place["id"], place, group))

    trace = {
        "matching_places": len(candidates),
        "eligible_places": len(eligible),
        "min_reviewers": MIN_REVIEWERS,
        "prior_weight": PRIOR_WEIGHT,
    }
    if not eligible:
        return None, trace

    rating, count, _, place, group = max(eligible, key=lambda row: row[:3])
    trace.update(
        reviewer_count=count,
        similar_mean=group["mean"],
        historical_mean=place["historical_mean"],
        score=rating,
        examples=[{"mode": MODES[mode], **visit} for visit in group["examples"]],
        ranking=[{"name": candidate["name"], "score": value, "count": support}
                 for value, support, _, candidate, _ in sorted(eligible, key=lambda row: row[:3], reverse=True)],
    )
    return {
        "id": place["id"],
        "name": place["name"],
        "region": place["region"],
        "category": CATEGORIES[place["category"]],
        "reviewer_count": count,
    }, trace
