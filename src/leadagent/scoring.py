"""Step 3 - deterministic, explainable lead score. No AI involved."""


def score_lead(facts, icp):
    """facts: output of facts.verify_facts. Returns score, confidence, tier and a breakdown."""
    breakdown = []
    score = 0
    known_weight = 0
    upside = 0   # extra points possible if unknown facts turned out best-case
    for c in icp["criteria"]:
        fact = facts.get(c["field"], {})
        if fact.get("status") == "verified":
            points = c["points"].get(fact["value"], 0)
            score += points
            known_weight += c["weight"]
            note = f'{fact["value"]} -> {points}/{c["weight"]} pts'
            if fact["evidence"]:
                note += f' (evidence: "{fact["evidence"]}")'
            status = "verified"
        else:
            points = 0
            upside += max(c["points"].values())
            note = f'not verified -> 0/{c["weight"]} pts ({fact.get("reason", "no data")})'
            status = "unknown"
        breakdown.append({
            "id": c["id"], "label": c["label"], "weight": c["weight"], "points": points,
            "value": fact.get("value"), "status": status, "note": note,
            "source_url": fact.get("source_url", ""),
        })

    # Business-rule caps (config/icp.yaml): a verified disqualifying fact limits the score.
    caps_applied = []
    max_possible = score + upside
    for cap in icp.get("caps", []):
        fact = facts.get(cap["field"], {})
        if fact.get("status") == "verified" and fact["value"] == cap["value"]:
            max_possible = min(max_possible, cap["max_score"])
            if score > cap["max_score"]:
                caps_applied.append(
                    f'Score capped at {cap["max_score"]} (was {score}): {cap["field"]} = {cap["value"]}, {cap["reason"]}')
                score = cap["max_score"]

    confidence = known_weight / 100
    tiers = icp["tiers"]
    if score >= tiers["high"]:
        tier = "High priority"
    elif score >= tiers["medium"]:
        tier = "Medium"
    else:
        tier = "Low / not a fit"
    return {
        "score": score,
        "max_possible": max(max_possible, score),
        "caps_applied": caps_applied,
        "confidence": round(confidence, 2),
        "low_confidence": confidence < icp["min_confidence"],
        "tier": tier,
        "breakdown": breakdown,
    }
