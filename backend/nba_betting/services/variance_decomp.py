"""
services/variance_decomp.py

Research-grade variance decomposition for player stat predictability.

Uses already-cached BacktestResult rows to partition total observed variance
into four interpretable components:

    Var(y) = Model-explained  +  Opponent effect  +  Situational  +  Residual

Method:
  1. Model R²     — standard coefficient of determination on XGBoost residuals.
  2. Opponent η²  — one-way ANOVA eta-squared: fraction of total SS explained
                    by opponent identity (marginal, not incremental).
  3. Opponent Δ   — partial R² of opponent dummies on the MODEL residuals
                    (incremental information above what the model already captured).
  4. Residual     — 1 - R² - opponent_delta (irreducible noise floor).

Additional distributional stats:
  - CV  (coefficient of variation): σ / μ  — raw volatility of the stat.
  - MAD (median absolute deviation): robust spread measure.
  - Skewness / excess kurtosis of the error distribution.
  - Normality test (Shapiro-Wilk for n < 50, D'Agostino-Pearson otherwise).
  - ICC across opponents (intraclass correlation).
  - Per-model comparison if multiple models seeded.

Composite predictability score (0–100):
  Weighted combination of R², inverse CV, and hit-rate calibration,
  normalised so higher = more predictable.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats as scipy_stats

from nba_betting.constants import (
    BACKTEST_MODELS,
    DEFAULT_SEASON,
    MODEL_LABELS,
    SEASON_DATES,
)
from nba_betting.models import BacktestResult, BacktestRun

# ── Public entry point ────────────────────────────────────────────────────────

def compute_variance_decomposition(
    player_name: str,
    stat: str,
    season: int = DEFAULT_SEASON,
) -> dict[str, Any]:
    """
    Compute full variance decomposition for player + stat over a season.

    Reads from already-cached BacktestResult rows (no recomputation).
    Primary model for decomposition: XGBoost (most interpretable baseline).
    Multi-model comparison table included if RF/LR/Naive rows exist.

    Returns:
        player_name, stat, season, n_games,
        distributional:  {mean, std, cv, mad, skewness, kurtosis, normality_p}
        variance_components: {model_r2, opponent_eta2, opponent_delta, residual}
        icc:  float  — intraclass correlation across opponents
        model_comparison: [{model, label, mae, r2, bias, hit_rate, roi}]
        predictability_score: float  (0–100)
        predictability_tier: str    ("High" | "Moderate" | "Low")
        insight: str
    """
    if season not in SEASON_DATES:
        raise ValueError(f"Season {season} not in SEASON_DATES.")

    date_from, date_to = SEASON_DATES[season]

    # ── Load XGBoost run (anchor) ─────────────────────────────────────────────
    xgb_run = (
        BacktestRun.objects.filter(
            player_name=player_name,
            stat=stat,
            model="xgb",
            date_from=date_from,
            date_to=date_to,
            total_bets__gt=0,
        )
        .prefetch_related("results")
        .first()
    )

    if xgb_run is None:
        raise ValueError(
            f"No seeded XGBoost backtest found for {player_name!r} / {stat} / "
            f"{season - 1}-{season % 100:02d}. Run seed_season_backtest first."
        )

    results = list(xgb_run.results.all())
    n = len(results)
    if n < 5:
        raise ValueError(f"Too few games ({n}) for meaningful decomposition (need ≥ 5).")

    actuals      = np.array([r.actual     for r in results], dtype=float)
    projections  = np.array([r.prob_over  for r in results], dtype=float)  # stored as projection
    errors       = np.array([r.error      for r in results], dtype=float)
    opponents    = [r.opponent for r in results]

    # ── 1. Distributional stats ───────────────────────────────────────────────
    distributional = _distributional_stats(actuals, errors)

    # ── 2. Variance components ────────────────────────────────────────────────
    variance_components = _decompose_variance(actuals, projections, errors, opponents)

    # ── 3. ICC across opponents ───────────────────────────────────────────────
    icc = _compute_icc(actuals, opponents)

    # ── 4. Multi-model comparison ─────────────────────────────────────────────
    model_comparison = _model_comparison(
        player_name, stat, date_from, date_to, actuals
    )

    # ── 5. Composite predictability score ─────────────────────────────────────
    r2         = variance_components["model_r2"]
    cv         = distributional["cv"]
    hit_rate   = xgb_run.accuracy

    score, tier = _predictability_score(r2, cv, hit_rate)

    # ── 6. Auto-insight ───────────────────────────────────────────────────────
    season_label = f"{season - 1}-{season % 100:02d}"
    insight = _generate_insight(
        player_name, stat, season_label,
        distributional, variance_components, icc, score, tier
    )

    return {
        "player_name":         player_name,
        "stat":                stat,
        "season":              season_label,
        "n_games":             n,
        "distributional":      distributional,
        "variance_components": variance_components,
        "icc":                 round(icc, 4),
        "model_comparison":    model_comparison,
        "predictability_score": round(score, 1),
        "predictability_tier": tier,
        "insight":             insight,
    }


# ── Distributional stats ──────────────────────────────────────────────────────

def _distributional_stats(actuals: np.ndarray, errors: np.ndarray) -> dict:
    mean  = float(np.mean(actuals))
    std   = float(np.std(actuals, ddof=1))
    cv    = std / mean if mean > 0 else 0.0
    mad   = float(np.median(np.abs(actuals - np.median(actuals))))
    skew  = float(scipy_stats.skew(errors))
    kurt  = float(scipy_stats.kurtosis(errors))  # excess kurtosis

    # Normality test on errors
    n = len(errors)
    if n >= 8:
        if n < 50:
            stat_val, p_val = scipy_stats.shapiro(errors)
            normality_test = "shapiro-wilk"
        else:
            stat_val, p_val = scipy_stats.normaltest(errors)
            normality_test = "dagostino-pearson"
        normality_p = round(float(p_val), 4)
    else:
        normality_test = "insufficient-data"
        normality_p    = None

    return {
        "mean":          round(mean, 3),
        "std":           round(std, 3),
        "cv":            round(cv, 4),
        "mad":           round(mad, 3),
        "skewness":      round(skew, 4),
        "excess_kurtosis": round(kurt, 4),
        "normality_test":  normality_test,
        "normality_p":     normality_p,
        "errors_normal":   (normality_p > 0.05) if normality_p is not None else None,
    }


# ── Variance decomposition ────────────────────────────────────────────────────

def _decompose_variance(
    actuals: np.ndarray,
    projections: np.ndarray,
    errors: np.ndarray,
    opponents: list[str],
) -> dict:
    n         = len(actuals)
    grand_mean = float(np.mean(actuals))
    ss_total  = float(np.sum((actuals - grand_mean) ** 2))

    if ss_total < 1e-8:
        return {
            "model_r2":       0.0,
            "opponent_eta2":  0.0,
            "opponent_delta": 0.0,
            "residual":       1.0,
        }

    # Model R² (XGBoost)
    ss_res  = float(np.sum(errors ** 2))
    model_r2 = max(0.0, 1.0 - ss_res / ss_total)

    # Opponent η² — one-way ANOVA on raw actuals
    opp_series = pd.Series(opponents)
    unique_opps = opp_series.unique()
    if len(unique_opps) > 1:
        ss_between = float(sum(
            (opp_series == opp).sum() * (actuals[opp_series == opp].mean() - grand_mean) ** 2
            for opp in unique_opps
        ))
        opponent_eta2 = min(ss_between / ss_total, 1.0)
    else:
        opponent_eta2 = 0.0

    # Opponent Δ — partial R² of opponent dummies on MODEL RESIDUALS
    # How much additional variance can opponents explain above the model?
    if len(unique_opps) > 1 and len(unique_opps) < n:
        opp_dummies = pd.get_dummies(opp_series, drop_first=True).astype(float)
        X_opp = sm.add_constant(opp_dummies, has_constant="add")
        try:
            ols_result     = sm.OLS(errors, X_opp).fit()
            opponent_delta = max(0.0, float(ols_result.rsquared))
        except Exception:
            opponent_delta = 0.0
    else:
        opponent_delta = 0.0

    # Residual = unexplained by model OR opponent
    residual = max(0.0, 1.0 - model_r2 - opponent_delta)

    return {
        "model_r2":        round(model_r2, 4),
        "opponent_eta2":   round(opponent_eta2, 4),
        "opponent_delta":  round(opponent_delta, 4),
        "residual":        round(residual, 4),
    }


# ── ICC ───────────────────────────────────────────────────────────────────────

def _compute_icc(actuals: np.ndarray, opponents: list[str]) -> float:
    """
    One-way random-effects ICC: how consistent is each opponent's effect
    across visits?  Range [-1, 1]; > 0.1 suggests opponent identity matters.

    ICC(1,1) = (MS_between - MS_within) / (MS_between + (k-1)*MS_within)
    where k = average group size.
    """
    opp_series = pd.Series(opponents)
    unique_opps = opp_series.unique()
    g = len(unique_opps)
    n = len(actuals)

    if g < 2 or g == n:
        return 0.0

    grand_mean = float(np.mean(actuals))
    group_sizes = [int((opp_series == opp).sum()) for opp in unique_opps]
    group_means = [float(actuals[opp_series == opp].mean()) for opp in unique_opps]

    ss_between = sum(
        group_sizes[i] * (group_means[i] - grand_mean) ** 2
        for i in range(g)
    )
    ss_within = sum(
        float(np.sum((actuals[opp_series == opp] - group_means[i]) ** 2))
        for i, opp in enumerate(unique_opps)
    )

    df_between = g - 1
    df_within  = n - g

    if df_between <= 0 or df_within <= 0:
        return 0.0

    ms_between = ss_between / df_between
    ms_within  = ss_within / df_within

    k = (n - sum(s ** 2 / n for s in group_sizes)) / (g - 1)  # effective k

    denom = ms_between + (k - 1) * ms_within
    if denom < 1e-8:
        return 0.0

    icc = (ms_between - ms_within) / denom
    return float(np.clip(icc, -1.0, 1.0))


# ── Multi-model comparison ────────────────────────────────────────────────────

def _model_comparison(
    player_name: str,
    stat: str,
    date_from,
    date_to,
    actuals: np.ndarray,
) -> list[dict]:
    runs = {
        run.model: run
        for run in BacktestRun.objects.filter(
            player_name=player_name,
            stat=stat,
            date_from=date_from,
            date_to=date_to,
            total_bets__gt=0,
        ).prefetch_related("results")
    }

    ss_total   = float(np.sum((actuals - np.mean(actuals)) ** 2))
    comparison = []

    for model_key in BACKTEST_MODELS:
        run = runs.get(model_key)
        if run is None:
            comparison.append({
                "model":     model_key,
                "label":     MODEL_LABELS.get(model_key, model_key),
                "available": False,
            })
            continue

        res    = list(run.results.all())
        errs   = np.array([r.error for r in res], dtype=float)
        n      = len(res)
        mae    = float(np.mean(np.abs(errs)))
        bias   = float(np.mean(errs))
        r2     = max(0.0, 1.0 - float(np.sum(errs ** 2)) / ss_total) if ss_total > 0 else 0.0

        comparison.append({
            "model":     model_key,
            "label":     MODEL_LABELS.get(model_key, model_key),
            "available": True,
            "n_games":   n,
            "mae":       round(mae, 3),
            "r2":        round(r2, 4),
            "bias":      round(bias, 3),
            "hit_rate":  round(run.accuracy, 4),
            "roi":       round(run.roi, 2),
        })

    return comparison


# ── Predictability score ──────────────────────────────────────────────────────

def _predictability_score(r2: float, cv: float, hit_rate: float) -> tuple[float, str]:
    """
    Composite score 0–100. Higher = more predictable.

    Components:
      R²  (50%) — model explains this fraction of variance
      CV  (30%) — lower spread relative to mean = more predictable
      HR  (20%) — hit-rate above break-even signals exploitable signal
    """
    # R² component: 0 → 0 pts, 0.5 → 50 pts, 1.0 → 100 pts
    r2_score = np.clip(r2, 0, 1) * 100

    # CV component: CV=0 → 100 pts, CV=0.5 → 50 pts, CV≥1 → 0 pts
    cv_score = np.clip((1.0 - cv) * 100, 0, 100)

    # Hit rate component: 0.5 → 0 pts, 0.65 → 75 pts, 1.0 → 100 pts
    hr_excess = max(0.0, hit_rate - 0.5) / 0.5   # 0–1
    hr_score  = hr_excess * 100

    score = 0.50 * r2_score + 0.30 * cv_score + 0.20 * hr_score

    if score >= 65:
        tier = "High"
    elif score >= 40:
        tier = "Moderate"
    else:
        tier = "Low"

    return float(score), tier


# ── Auto-insight ──────────────────────────────────────────────────────────────

def _generate_insight(
    player_name: str,
    stat: str,
    season_label: str,
    dist: dict,
    vc: dict,
    icc: float,
    score: float,
    tier: str,
) -> str:
    stat_labels = {"pts": "points", "reb": "rebounds", "ast": "assists"}
    stat_label  = stat_labels.get(stat, stat)
    first_name  = player_name.split()[0]

    r2      = vc["model_r2"]
    opp_d   = vc["opponent_delta"]
    resid   = vc["residual"]
    cv      = dist["cv"]
    skew    = dist["skewness"]
    kurt    = dist["excess_kurtosis"]

    # Tier sentence
    tier_sent = (
        f"{first_name}'s {stat_label} output is **{tier.lower()} predictability** "
        f"(composite score: {score:.0f}/100) in the {season_label} season."
    )

    # R² sentence
    r2_sent = (
        f"The XGBoost model explains {r2 * 100:.0f}% of the variance in {first_name}'s "
        f"{stat_label} (R²={r2:.3f}), "
        + (
            "indicating strong signal in the rolling features."
            if r2 >= 0.35 else
            "indicating moderate signal — game-to-game noise is substantial."
            if r2 >= 0.15 else
            "suggesting the stat is largely noise-driven and difficult to forecast reliably."
        )
    )

    # Volatility sentence
    cv_desc = "low" if cv < 0.25 else "moderate" if cv < 0.40 else "high"
    vol_sent = (
        f"{first_name}'s raw {stat_label} volatility is {cv_desc} "
        f"(CV={cv:.2f}, MAD={dist['mad']:.1f})."
    )

    # Opponent sensitivity sentence
    if opp_d >= 0.08:
        opp_sent = (
            f"Opponent identity explains an additional {opp_d * 100:.0f}% of variance "
            f"beyond the model (ICC={icc:.3f}), suggesting meaningful matchup sensitivity."
        )
    elif opp_d >= 0.03:
        opp_sent = (
            f"Opponent effects contribute modestly ({opp_d * 100:.0f}% incremental, "
            f"ICC={icc:.3f}) — some opponents shift outcomes but the effect is small."
        )
    else:
        opp_sent = (
            f"Opponent identity adds little beyond model features ({opp_d * 100:.0f}% "
            f"incremental, ICC={icc:.3f}), suggesting the model already captures matchup context."
        )

    # Error distribution sentence
    if abs(skew) > 1.0:
        direction = "positively" if skew > 0 else "negatively"
        dist_sent = (
            f"Prediction errors are {direction} skewed (skewness={skew:.2f}), "
            f"meaning the model is more likely to be wrong in one direction."
        )
    elif abs(kurt) > 1.5:
        dist_sent = (
            f"Error distribution has heavy tails (excess kurtosis={kurt:.2f}), "
            f"indicating occasional large misses even when median accuracy is good."
        )
    else:
        dist_sent = (
            f"Prediction errors are approximately normal (skewness={skew:.2f}, "
            f"kurtosis={kurt:.2f}), consistent with well-calibrated residuals."
        )

    # Residual sentence
    resid_sent = (
        f"The irreducible noise floor is {resid * 100:.0f}% of total variance — "
        + (
            "the model has captured most of the available signal."
            if resid < 0.50 else
            "a substantial portion of game-to-game variation remains unexplainable by available features."
            if resid < 0.75 else
            "most variation is structurally unpredictable with current features."
        )
    )

    return " ".join([tier_sent, r2_sent, vol_sent, opp_sent, dist_sent, resid_sent])
