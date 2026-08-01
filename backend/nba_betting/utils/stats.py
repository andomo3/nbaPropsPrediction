"""Shared statistical helpers used across multiple services and views."""


def pred_components(actuals, errors, hit_rate):
    """
    Components behind the composite predictability score.

    Returns a dict with the raw inputs the score is built from, so callers can
    show the working rather than only the headline number:

        {
            "score": 0-100 composite,
            "tier":  "High" | "Moderate" | "Low",
            "r2":    variance of the actuals explained by the model,
            "cv":    coefficient of variation of the actuals,
            "hit_excess": hit rate minus the 52.4% break-even, in points,
        }

    Every value is None when there are fewer than 5 graded games.
    """
    n = len(actuals)
    if n < 5:
        return {"score": None, "tier": None, "r2": None, "cv": None, "hit_excess": None}

    mean_a = sum(actuals) / n
    var_a  = sum((a - mean_a) ** 2 for a in actuals) / n
    mean_e = sum(errors)  / n
    var_e  = sum((e - mean_e) ** 2 for e in errors)  / n

    r2    = max(0.0, 1.0 - var_e / var_a) if var_a > 0 else 0.0
    cv    = (var_a ** 0.5) / mean_a       if mean_a > 0 else 1.0

    r2_s  = max(0.0, min(1.0, r2))
    cv_s  = max(0.0, min(1.0, 1.0 - cv))
    hr_s  = min(max(0.0, hit_rate - 0.524) / 0.476, 1.0)

    score = round(r2_s * 50 + cv_s * 30 + hr_s * 20, 1)
    tier  = "High" if score >= 65 else ("Moderate" if score >= 40 else "Low")

    return {
        "score":      score,
        "tier":       tier,
        "r2":         round(r2, 3),
        "cv":         round(cv, 3),
        "hit_excess": round((hit_rate - 0.524) * 100, 1),
    }


def pred_score_tier(actuals, errors, hit_rate):
    """
    Composite predictability score (0–100) and tier label.

    Formula:
        score = R²(50%) + inverse-CV(30%) + hit-rate-excess(20%)

    Tiers:
        High     ≥ 65
        Moderate ≥ 40
        Low      < 40

    Returns (score, tier). Returns (None, None) if fewer than 5 games.
    """
    c = pred_components(actuals, errors, hit_rate)
    return c["score"], c["tier"]
