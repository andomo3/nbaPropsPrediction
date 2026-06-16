from ..models import BacktestRun
from ..constants import DEFAULT_SEASON, SEASON_DATES, SEASON_REPORT_PLAYERS


def compute_floor_ceiling(player_name, stat, season=DEFAULT_SEASON):
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
    actuals = sorted(r.actual for r in results)
    n = len(actuals)

    # ── Percentile distribution ───────────────────────────────────────────────
    def pct(p):
        idx = (p / 100) * (n - 1)
        lo, hi = int(idx), min(int(idx) + 1, n - 1)
        frac = idx - lo
        return round(actuals[lo] * (1 - frac) + actuals[hi] * frac, 1)

    p5, p10, p25, p50, p75, p90, p95 = (pct(v) for v in (5, 10, 25, 50, 75, 90, 95))
    floor   = p10
    ceiling = p90
    mean    = round(sum(actuals) / n, 2)
    std     = round((sum((a - mean) ** 2 for a in actuals) / n) ** 0.5, 2)

    # Boom-bust ratio: normalised interquartile range relative to median
    boom_bust = round((p90 - p10) / p50, 3) if p50 > 0 else None
    archetype = _archetype(boom_bust, std / mean if mean > 0 else 1)

    # ── Distribution histogram (10 equal-width bins) ──────────────────────────
    lo_val, hi_val = actuals[0], actuals[-1]
    bin_width = (hi_val - lo_val) / 10 if hi_val > lo_val else 1
    histogram = []
    for i in range(10):
        bin_lo = lo_val + i * bin_width
        bin_hi = bin_lo + bin_width
        count  = sum(1 for a in actuals if bin_lo <= a < bin_hi)
        histogram.append({
            "bin_lo": round(bin_lo, 1),
            "bin_hi": round(bin_hi, 1),
            "count":  count,
        })
    # include upper edge in last bin
    histogram[-1]["count"] += sum(1 for a in actuals if a == hi_val)

    # ── Condition splits ──────────────────────────────────────────────────────
    # Rest days
    enriched = []
    unsorted_results = list(run.results.all())  # re-fetch ordered by game_date
    for i, r in enumerate(unsorted_results):
        rest = max(0, (r.game_date - unsorted_results[i - 1].game_date).days - 1) if i > 0 else 2
        past = unsorted_results[max(0, i - 5):i]
        s_past = unsorted_results[:i]
        l5    = sum(g.actual for g in past) / len(past) if past else r.actual
        s_avg = sum(g.actual for g in s_past) / len(s_past) if s_past else mean
        enriched.append({"r": r, "rest": rest, "form_delta": l5 - s_avg})

    form_threshold = max(1.5, mean * 0.07)

    condition_splits = []
    groups = [
        ("Rested (2+ days)",  [e for e in enriched if e["rest"] >= 2]),
        ("Back-to-back",      [e for e in enriched if e["rest"] == 0]),
        ("Hot form (L5>avg)", [e for e in enriched if e["form_delta"] >= form_threshold]),
        ("Cold form (L5<avg)",[e for e in enriched if e["form_delta"] <= -form_threshold]),
    ]
    for label, grp in groups:
        if len(grp) >= 5:
            vals = sorted(g["r"].actual for g in grp)
            gn = len(vals)
            condition_splits.append({
                "label":        label,
                "n":            gn,
                "floor":        _pct_from_sorted(vals, 10),
                "median":       _pct_from_sorted(vals, 50),
                "ceiling":      _pct_from_sorted(vals, 90),
                "floor_rate":   round(sum(1 for v in vals if v <= p25) / gn, 4),
                "ceiling_rate": round(sum(1 for v in vals if v >= p75) / gn, 4),
            })

    # ── Cross-player comparison (boom-bust ranking) ───────────────────────────
    roster_scores = _roster_boom_bust(stat, season, date_from, date_to)
    my_rank = None
    for i, row in enumerate(roster_scores):
        if row["player_name"] == player_name:
            my_rank = i + 1
            break

    insight = _insight(player_name, stat, floor, ceiling, mean, boom_bust, archetype,
                       condition_splits, my_rank, len(roster_scores))

    return {
        "player_name": player_name,
        "stat":        stat,
        "n_games":     n,
        "percentiles": {
            "p5": p5, "p10": p10, "p25": p25, "p50": p50,
            "p75": p75, "p90": p90, "p95": p95,
        },
        "floor":        floor,
        "ceiling":      ceiling,
        "mean":         mean,
        "std":          std,
        "boom_bust":    boom_bust,
        "archetype":    archetype,
        "histogram":    histogram,
        "condition_splits": condition_splits,
        "roster_comparison": roster_scores,
        "my_rank_boom_bust": my_rank,
        "insight":     insight,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pct_from_sorted(vals, p):
    n = len(vals)
    idx = (p / 100) * (n - 1)
    lo, hi = int(idx), min(int(idx) + 1, n - 1)
    return round(vals[lo] * (1 - (idx - lo)) + vals[hi] * (idx - lo), 1)


def _archetype(boom_bust, cv):
    if boom_bust is None:
        return "Unknown"
    if cv < 0.15:
        return "Consistent Workhorse"
    if cv < 0.25 and boom_bust < 1.2:
        return "Reliable Contributor"
    if boom_bust >= 1.8:
        return "Boom/Bust Gamble"
    if boom_bust >= 1.4:
        return "Volatile Scorer"
    return "Steady Performer"


def _roster_boom_bust(stat, season, date_from, date_to):
    from ..models import BacktestRun
    runs = (
        BacktestRun.objects
        .filter(
            stat=stat,
            model="xgb",
            date_from=date_from,
            date_to=date_to,
            total_bets__gt=0,
            player_name__in=SEASON_REPORT_PLAYERS,
        )
        .prefetch_related("results")
    )
    rows = []
    for run in runs:
        vals = sorted(r.actual for r in run.results.all())
        if len(vals) < 10:
            continue
        p10  = _pct_from_sorted(vals, 10)
        p50  = _pct_from_sorted(vals, 50)
        p90  = _pct_from_sorted(vals, 90)
        bb   = round((p90 - p10) / p50, 3) if p50 > 0 else None
        mean = round(sum(vals) / len(vals), 2)
        rows.append({
            "player_name": run.player_name,
            "floor":       p10,
            "ceiling":     p90,
            "median":      p50,
            "mean":        mean,
            "boom_bust":   bb,
        })
    rows.sort(key=lambda r: r["boom_bust"] if r["boom_bust"] is not None else 0, reverse=True)
    return rows


def _insight(player_name, stat, floor, ceiling, mean, boom_bust, archetype,
             condition_splits, my_rank, roster_size):
    s = {"pts": "points", "reb": "rebounds", "ast": "assists"}.get(stat, stat)
    parts = [
        f"**{archetype}.** {player_name}'s {s} range from a floor of {floor} (p10) "
        f"to a ceiling of {ceiling} (p90), with a median of {mean}."
    ]

    if boom_bust is not None:
        if boom_bust >= 1.8:
            parts.append(
                f"A boom-bust ratio of {boom_bust:.2f} makes lines around the median "
                f"unreliable — the tails are where the value lies."
            )
        elif boom_bust < 1.2:
            parts.append(
                f"Low boom-bust ratio ({boom_bust:.2f}) means the median is representative "
                "— this player's output is unusually consistent."
            )

    if my_rank:
        parts.append(
            f"Ranks #{my_rank} of {roster_size} players for boom-bust volatility in {s}."
        )

    rested = next((c for c in condition_splits if "Rested" in c["label"]), None)
    hot    = next((c for c in condition_splits if "Hot" in c["label"]), None)
    if rested and hot:
        if hot["ceiling"] > rested["ceiling"] * 1.1:
            parts.append(
                f"Ceiling jumps to {hot['ceiling']} when in hot form vs {rested['ceiling']} rested — "
                "form is the better ceiling predictor than rest."
            )

    return " ".join(parts)
