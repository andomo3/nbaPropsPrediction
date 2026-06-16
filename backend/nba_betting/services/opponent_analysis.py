from ..models import BacktestRun
from ..constants import DEFAULT_SEASON, SEASON_DATES


def compute_opponent_analysis(player_name, stat, season=DEFAULT_SEASON):
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
    n_total  = len(results)
    mean_all = sum(r.actual for r in results) / n_total

    # ── Per-opponent stats ────────────────────────────────────────────────────
    opp_map = {}
    for r in results:
        opp = r.opponent
        if opp not in opp_map:
            opp_map[opp] = []
        opp_map[opp].append(r)

    per_opponent = []
    for opp, games in opp_map.items():
        ng       = len(games)
        avg_act  = sum(g.actual for g in games) / ng
        avg_err  = sum(g.error  for g in games) / ng   # positive = model under-projected
        avg_edge = sum(abs(g.prob_over - g.line) for g in games) / ng
        hits     = sum(1 for g in games if g.correct)
        hr       = hits / ng
        roi      = round((hr * 1.0 - (1 - hr) * 1.1) * 100, 1)
        delta    = round(avg_act - mean_all, 2)   # vs season avg

        per_opponent.append({
            "opponent":   opp,
            "n":          ng,
            "avg_actual": round(avg_act, 2),
            "delta":      delta,           # +ve = player outperforms avg
            "avg_error":  round(avg_err, 2),  # model bias vs this opponent
            "avg_edge":   round(avg_edge, 2),
            "hit_rate":   round(hr, 4),
            "roi":        roi,
        })

    per_opponent.sort(key=lambda x: x["delta"], reverse=True)

    # ── Tier classification ───────────────────────────────────────────────────
    # Use delta threshold: top/bottom 25% of opponents by avg_actual delta
    deltas = sorted(o["delta"] for o in per_opponent)
    if len(deltas) >= 4:
        q75 = deltas[int(len(deltas) * 0.75)]
        q25 = deltas[int(len(deltas) * 0.25)]
    else:
        q75, q25 = mean_all * 0.1, -mean_all * 0.1

    favorable   = [o for o in per_opponent if o["delta"] >= q75 and o["n"] >= 1]
    neutral     = [o for o in per_opponent if q25 < o["delta"] < q75]
    unfavorable = [o for o in per_opponent if o["delta"] <= q25 and o["n"] >= 1]

    # ── Matchup sensitivity score ─────────────────────────────────────────────
    # How much does opponent change output? Std dev of per-opp avg_actuals
    opp_avgs = [o["avg_actual"] for o in per_opponent]
    opp_mean = sum(opp_avgs) / len(opp_avgs)
    opp_std  = (sum((a - opp_mean) ** 2 for a in opp_avgs) / len(opp_avgs)) ** 0.5
    matchup_sensitivity = round(opp_std / mean_all * 100, 1) if mean_all > 0 else 0.0

    # ── Model bias by opponent tier ───────────────────────────────────────────
    def _tier_bias(group):
        if not group:
            return None
        return round(sum(o["avg_error"] for o in group) / len(group), 2)

    bias_by_tier = {
        "favorable":   _tier_bias(favorable),
        "neutral":     _tier_bias(neutral),
        "unfavorable": _tier_bias(unfavorable),
    }

    insight = _insight(player_name, stat, per_opponent, favorable, unfavorable,
                       matchup_sensitivity, mean_all)

    return {
        "player_name":          player_name,
        "stat":                 stat,
        "n_games":              n_total,
        "season_avg":           round(mean_all, 2),
        "per_opponent":         per_opponent,
        "favorable":            favorable,
        "unfavorable":          unfavorable,
        "neutral_count":        len(neutral),
        "matchup_sensitivity":  matchup_sensitivity,
        "bias_by_tier":         bias_by_tier,
        "insight":              insight,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _insight(player_name, stat, per_opponent, favorable, unfavorable,
             sensitivity, mean_all):
    s = {"pts": "points", "reb": "rebounds", "ast": "assists"}.get(stat, stat)
    parts = []

    if sensitivity >= 20:
        parts.append(
            f"**Matchup-sensitive.** Opponent accounts for ~{sensitivity:.0f}% relative variance "
            f"in {player_name}'s {s} — who they play matters significantly."
        )
    elif sensitivity <= 8:
        parts.append(
            f"**Matchup-resistant.** Only {sensitivity:.0f}% output variance explained by opponent — "
            f"{player_name}'s {s} are largely opponent-agnostic."
        )
    else:
        parts.append(
            f"**Moderate matchup sensitivity** ({sensitivity:.0f}%) — some opponents move the needle "
            "but it's not the dominant factor."
        )

    if favorable:
        best = favorable[0]
        parts.append(
            f"**Best matchup:** {best['opponent']} ({best['avg_actual']} avg, "
            f"{best['delta']:+.1f} vs season avg, {best['hit_rate']*100:.0f}% model hit rate)."
        )

    if unfavorable:
        worst = unfavorable[-1]
        parts.append(
            f"**Worst matchup:** {worst['opponent']} ({worst['avg_actual']} avg, "
            f"{worst['delta']:+.1f} vs season avg)."
        )

    return " ".join(parts)
