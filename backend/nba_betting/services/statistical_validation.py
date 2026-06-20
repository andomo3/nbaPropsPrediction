"""
Statistical validation service.

For a given player + stat + season, answers four questions:

1. Hit-rate significance   — is the model's hit rate meaningfully above the
                             52.4% break-even, or is it plausible noise?
                             (one-sided binomial test)

2. Edge-hit correlation    — does a larger projected edge actually predict
                             a higher hit rate?
                             (Spearman rank correlation, edge vs correct)

3. Calibration / bias      — does the model systematically over- or
                             under-project?
                             (one-sample t-test of signed errors vs 0)

4. Sample adequacy         — is there enough data to trust any of the above?
                             (minimum n thresholds with plain-English warnings)

Returns a dict ready for JSON serialisation.
"""

from __future__ import annotations

from scipy.stats import binomtest, spearmanr, ttest_1samp

from ..models import BacktestRun
from ..constants import DEFAULT_SEASON, SEASON_DATES

BREAK_EVEN = 0.524
MIN_N_RELIABLE = 30   # below this, flag results as low-confidence
MIN_N_EDGE     = 15   # minimum for edge correlation to be meaningful


def compute_statistical_validation(
    player_name: str,
    stat: str,
    season: int = DEFAULT_SEASON,
) -> dict:
    date_from, date_to = SEASON_DATES[season]

    run = (
        BacktestRun.objects
        .filter(
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
    if run is None:
        raise ValueError(f"No backtest data for {player_name} / {stat}")

    results = list(run.results.all())
    n = len(results)

    actuals     = [r.actual    for r in results]
    errors      = [r.error     for r in results]       # actual - projection
    corrects    = [int(r.correct) for r in results]    # 1/0
    edges       = [abs(r.prob_over - r.line) for r in results]

    hits = sum(corrects)
    hit_rate = hits / n if n else 0.0

    # ── 1. Hit-rate significance (one-sided: is hit_rate > break-even?) ──────
    binom   = binomtest(hits, n, BREAK_EVEN, alternative="greater")
    hr_pval = float(binom.pvalue)
    hr_sig  = hr_pval < 0.05

    # ── 2. Edge–hit correlation ───────────────────────────────────────────────
    if n >= MIN_N_EDGE:
        rho, edge_pval = spearmanr(edges, corrects)
        rho       = float(rho)
        edge_pval = float(edge_pval)
        edge_sig  = edge_pval < 0.05 and rho > 0
    else:
        rho = edge_pval = None
        edge_sig = False

    # ── 3. Calibration / bias (signed error mean vs 0) ───────────────────────
    tstat, bias_pval = ttest_1samp(errors, popmean=0.0)
    mean_error = sum(errors) / n if n else 0.0
    bias_pval  = float(bias_pval)
    bias_sig   = bias_pval < 0.05   # significantly non-zero → systematic bias

    # Direction: positive = model under-projects, negative = over-projects
    if abs(mean_error) < 0.3:
        bias_direction = "negligible"
    elif mean_error > 0:
        bias_direction = "under-projects"
    else:
        bias_direction = "over-projects"

    # ── 4. Sample adequacy ────────────────────────────────────────────────────
    warnings = _sample_warnings(n, hits, edges)

    # ── Overall verdict ───────────────────────────────────────────────────────
    verdict, verdict_color = _overall_verdict(
        n, hr_sig, hit_rate, edge_sig, rho, bias_sig, mean_error
    )

    # ── Insight narrative ─────────────────────────────────────────────────────
    insight = _insight(
        player_name, stat, n, hit_rate, hr_sig, hr_pval,
        rho, edge_pval, edge_sig,
        mean_error, bias_pval, bias_sig, bias_direction,
        verdict
    )

    return {
        "player_name": player_name,
        "stat":        stat,
        "season":      season,
        "n_games":     n,
        "verdict":     verdict,
        "verdict_color": verdict_color,
        "hit_rate": {
            "value":     round(hit_rate, 4),
            "hits":      hits,
            "n":         n,
            "p_value":   round(hr_pval, 4),
            "significant": hr_sig,
            "label":     "Significant" if hr_sig else "Not significant",
        },
        "edge_correlation": {
            "rho":       round(rho, 4) if rho is not None else None,
            "p_value":   round(edge_pval, 4) if edge_pval is not None else None,
            "significant": edge_sig,
            "label":     (
                "Positive & significant" if edge_sig
                else "Not significant" if rho is not None
                else "Insufficient data"
            ),
            "n":         n,
        },
        "calibration": {
            "mean_error":    round(mean_error, 3),
            "p_value":       round(bias_pval, 4),
            "significant":   bias_sig,
            "direction":     bias_direction,
            "label":         (
                f"Significant bias ({bias_direction})" if bias_sig
                else "Well-calibrated"
            ),
        },
        "sample_adequacy": {
            "n":        n,
            "adequate": n >= MIN_N_RELIABLE,
            "warnings": warnings,
        },
        "insight": insight,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sample_warnings(n: int, hits: int, edges: list[float]) -> list[str]:
    warnings = []
    if n < MIN_N_RELIABLE:
        warnings.append(
            f"Only {n} games — results are low-confidence. "
            f"Minimum {MIN_N_RELIABLE} recommended for reliable inference."
        )
    if n >= MIN_N_RELIABLE and hits < 10:
        warnings.append(
            f"Only {hits} correct predictions — binomial test has low power."
        )
    if n < MIN_N_EDGE:
        warnings.append(
            f"Edge correlation skipped — fewer than {MIN_N_EDGE} games available."
        )
    high_edge_n = sum(1 for e in edges if e >= 2.0)
    if high_edge_n < 5:
        warnings.append(
            f"Only {high_edge_n} games with edge ≥ 2 pts — "
            "high-edge bucket conclusions are unreliable."
        )
    return warnings


def _overall_verdict(
    n: int, hr_sig: bool, hit_rate: float,
    edge_sig: bool, rho,
    bias_sig: bool, mean_error: float,
) -> tuple[str, str]:
    if n < MIN_N_RELIABLE:
        return "Insufficient data", "slate"
    positives = sum([
        hr_sig and hit_rate > BREAK_EVEN,
        edge_sig and rho is not None and rho > 0,
        not bias_sig or abs(mean_error) < 0.5,
    ])
    if positives == 3:
        return "Strong signal", "green"
    if positives == 2:
        return "Moderate signal", "amber"
    if positives == 1:
        return "Weak signal", "red"
    return "No reliable signal", "red"


def _insight(
    player_name, stat, n, hit_rate, hr_sig, hr_pval,
    rho, edge_pval, edge_sig,
    mean_error, bias_pval, bias_sig, bias_direction,
    verdict,
) -> str:
    s = {"pts": "points", "reb": "rebounds", "ast": "assists"}.get(stat, stat)
    first = player_name.split()[0]
    parts = []

    # Hit rate sentence
    if hr_sig:
        parts.append(
            f"**{first}'s** {s} model hits at **{hit_rate*100:.1f}%** across {n} games — "
            f"statistically above the 52.4% break-even (p={hr_pval:.3f})."
        )
    else:
        parts.append(
            f"**{first}'s** {s} hit rate of **{hit_rate*100:.1f}%** ({n} games) "
            f"is not significantly above break-even (p={hr_pval:.3f}) — "
            "could be noise."
        )

    # Edge correlation sentence
    if rho is not None:
        if edge_sig:
            parts.append(
                f"Edge size is a **meaningful predictor** of outcomes "
                f"(Spearman ρ={rho:.2f}, p={edge_pval:.3f}) — "
                "larger model edges do translate to higher hit rates."
            )
        else:
            parts.append(
                f"Edge size does **not** reliably predict outcomes "
                f"(ρ={rho:.2f}, p={edge_pval:.3f}) — "
                "the edge signal should be treated with caution."
            )

    # Bias sentence
    if bias_sig:
        parts.append(
            f"The model has a **systematic {bias_direction}** bias "
            f"(mean error {mean_error:+.2f} {s}, p={bias_pval:.3f}). "
            "Lines derived from its projections inherit this offset."
        )
    else:
        parts.append(
            f"Projection bias is **negligible** (mean error {mean_error:+.2f}, "
            f"p={bias_pval:.3f}) — the model is well-calibrated on average."
        )

    parts.append(f"Overall verdict: **{verdict}**.")
    return " ".join(parts)
