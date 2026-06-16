from ..models import BacktestRun
from ..constants import DEFAULT_SEASON, SEASON_DATES


def compute_edge_calibration(player_name, stat, season=DEFAULT_SEASON):
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
    season_avg = sum(r.actual for r in results) / n

    # ── Enrich each game row ──────────────────────────────────────────────────
    enriched = []
    for i, r in enumerate(results):
        # Absolute edge: how far projection is from the line
        edge = abs(r.prob_over - r.line)

        # Rest days (days between games minus 1 travel day, floored at 0)
        if i == 0:
            rest = 2
        else:
            gap = (r.game_date - results[i - 1].game_date).days
            rest = max(0, gap - 1)

        # Form: L5 rolling avg of actuals vs season avg up to this game
        past = results[max(0, i - 5):i]
        season_so_far = results[:i]
        l5_avg = sum(g.actual for g in past) / len(past) if past else r.actual
        s_avg  = sum(g.actual for g in season_so_far) / len(season_so_far) if season_so_far else season_avg
        form_delta = l5_avg - s_avg

        enriched.append({
            "r":          r,
            "edge":       round(edge, 3),
            "rest":       rest,
            "form_delta": round(form_delta, 3),
        })

    # ── Edge bands ────────────────────────────────────────────────────────────
    edge_bands = []
    thresholds = [(0, 1.0, "0–1"), (1.0, 2.0, "1–2"), (2.0, 3.0, "2–3"), (3.0, 99, "3+")]
    for lo, hi, label in thresholds:
        grp = [e for e in enriched if lo <= e["edge"] < hi]
        if grp:
            edge_bands.append({"bucket": label, **_stats(grp)})

    # ── Rest analysis ─────────────────────────────────────────────────────────
    rest_groups = [
        ("Back-to-back",  [e for e in enriched if e["rest"] == 0]),
        ("1 day rest",    [e for e in enriched if e["rest"] == 1]),
        ("2+ days rest",  [e for e in enriched if e["rest"] >= 2]),
    ]
    rest_analysis = [
        {"label": lbl, **_stats(grp)}
        for lbl, grp in rest_groups if grp
    ]

    # ── Form analysis ─────────────────────────────────────────────────────────
    threshold = max(1.5, season_avg * 0.07)  # ~7% of season avg or 1.5, whichever larger
    form_groups = [
        ("Hot (L5 > avg)",     [e for e in enriched if e["form_delta"] >= threshold]),
        ("Neutral",            [e for e in enriched if abs(e["form_delta"]) < threshold]),
        ("Cold (L5 < avg)",    [e for e in enriched if e["form_delta"] <= -threshold]),
    ]
    form_analysis = [
        {"label": lbl, **_stats(grp)}
        for lbl, grp in form_groups if grp
    ]

    # ── Cross-tab: edge × rest ────────────────────────────────────────────────
    cross_tab = []
    for edge_lbl, e_lo, e_hi in [("Low edge (<2)", 0, 2.0), ("High edge (2+)", 2.0, 99)]:
        for rest_lbl, r_lo, r_hi in [("Fatigued (≤1 day)", 0, 2), ("Rested (2+ days)", 2, 99)]:
            grp = [e for e in enriched if e_lo <= e["edge"] < e_hi and r_lo <= e["rest"] < r_hi]
            if grp:
                cross_tab.append({
                    "label":     f"{edge_lbl} · {rest_lbl}",
                    "edge_cat":  edge_lbl,
                    "rest_cat":  rest_lbl,
                    **_stats(grp),
                })

    # ── Best profitable threshold ─────────────────────────────────────────────
    best_threshold = None
    for thresh in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]:
        grp = [e for e in enriched if e["edge"] >= thresh]
        if len(grp) >= 5:
            hr = sum(1 for e in grp if e["r"].correct) / len(grp)
            if hr >= 0.55:
                best_threshold = {
                    "threshold": thresh,
                    "hit_rate":  round(hr, 4),
                    "n":         len(grp),
                    "roi":       round((hr * 1.0 - (1 - hr) * 1.1) * 100, 1),
                }
                break

    insight = _insight(edge_bands, rest_analysis, form_analysis, best_threshold, player_name, stat)

    return {
        "player_name":    player_name,
        "stat":           stat,
        "n_games":        n,
        "season_avg":     round(season_avg, 2),
        "edge_bands":     edge_bands,
        "rest_analysis":  rest_analysis,
        "form_analysis":  form_analysis,
        "cross_tab":      cross_tab,
        "best_threshold": best_threshold,
        "insight":        insight,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stats(group):
    n    = len(group)
    hits = sum(1 for e in group if e["r"].correct)
    hr   = hits / n
    return {
        "n":          n,
        "hit_rate":   round(hr, 4),
        "avg_edge":   round(sum(e["edge"] for e in group) / n, 2),
        "avg_actual": round(sum(e["r"].actual for e in group) / n, 2),
        "roi":        round((hr * 1.0 - (1 - hr) * 1.1) * 100, 1),
    }


def _insight(edge_bands, rest_analysis, form_analysis, best_threshold, player_name, stat):
    s = {"pts": "points", "reb": "rebounds", "ast": "assists"}.get(stat, stat)
    parts = []

    if best_threshold:
        parts.append(
            f"**Edge threshold:** Edges of {best_threshold['threshold']}+ pts hit "
            f"{best_threshold['hit_rate']*100:.0f}% of the time "
            f"({best_threshold['n']} games, {best_threshold['roi']:+.1f}% ROI)."
        )
    else:
        top = next((b for b in edge_bands if b["bucket"] == "3+"), None)
        if top and top["n"] >= 3:
            parts.append(
                f"**Weak edge signal:** Even 3+ pt edges only hit {top['hit_rate']*100:.0f}% — "
                f"the market prices {player_name}'s {s} efficiently."
            )

    rested = next((r for r in rest_analysis if "2+" in r["label"]), None)
    bb     = next((r for r in rest_analysis if "Back" in r["label"]), None)
    if rested and bb and rested["n"] >= 3 and bb["n"] >= 3:
        delta = rested["hit_rate"] - bb["hit_rate"]
        if abs(delta) > 0.07:
            word = "drops" if delta > 0 else "holds"
            parts.append(
                f"**Rest matters:** Accuracy {word} to {bb['hit_rate']*100:.0f}% on back-to-backs "
                f"vs {rested['hit_rate']*100:.0f}% rested."
            )

    hot  = next((f for f in form_analysis if "Hot"  in f["label"]), None)
    cold = next((f for f in form_analysis if "Cold" in f["label"]), None)
    if hot and cold and hot["n"] >= 3 and cold["n"] >= 3:
        parts.append(
            f"**Form effect:** Model hits {hot['hit_rate']*100:.0f}% when {player_name} is hot "
            f"vs {cold['hit_rate']*100:.0f}% when cold."
        )

    return " ".join(parts) if parts else (
        f"No strong conditional patterns detected for {player_name}'s {s} props — "
        "all edge/rest/form buckets perform similarly."
    )
