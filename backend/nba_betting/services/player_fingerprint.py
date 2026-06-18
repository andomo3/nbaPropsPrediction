"""
Behavioral fingerprint — synthesises edge calibration, floor/ceiling, opponent
analysis, and (optionally) SHAP to produce a structured player scouting profile.
"""

import logging

from ..constants import DEFAULT_SEASON

logger = logging.getLogger(__name__)


def compute_player_fingerprint(player_name, stat, season=DEFAULT_SEASON):
    from .edge_calibration   import compute_edge_calibration
    from .floor_ceiling      import compute_floor_ceiling
    from .opponent_analysis  import compute_opponent_analysis

    shap_data = None
    shap_error = None
    try:
        from .shap_analysis import compute_shap_analysis
        shap_data = compute_shap_analysis(player_name, stat)
    except Exception as e:
        shap_error = str(e)
        logger.warning("SHAP unavailable for %s/%s: %s", player_name, stat, e)

    edge  = compute_edge_calibration(player_name, stat, season)
    fc    = compute_floor_ceiling(player_name, stat, season)
    opp   = compute_opponent_analysis(player_name, stat, season)

    # ── Dimension scores (0–100) ──────────────────────────────────────────────

    # 1. Consistency: inverse of boom-bust, scaled to 0-100
    bb = fc.get("boom_bust") or 1.5
    consistency = round(max(0, min(100, (2.0 - bb) / 1.5 * 100)), 1)

    # 2. Edge reliability: hit rate at best threshold vs break-even
    bt = edge.get("best_threshold")
    if bt:
        edge_reliability = round(min(100, (bt["hit_rate"] - 0.524) / 0.476 * 100), 1)
    else:
        # Use overall hit rate from the best edge band
        high_band = next((b for b in edge["edge_bands"] if b["bucket"] == "3+"), None)
        if high_band and high_band["n"] >= 3:
            edge_reliability = round(max(0, (high_band["hit_rate"] - 0.524) / 0.476 * 100), 1)
        else:
            edge_reliability = 0.0

    # 3. Matchup sensitivity (already 0-100 from opponent_analysis)
    matchup_sensitivity = opp["matchup_sensitivity"]

    # 4. Form dependence: gap between hot vs cold hit rates (from edge calibration)
    hot_hr  = next((f["hit_rate"] for f in edge["form_analysis"] if "Hot"  in f["label"]), None)
    cold_hr = next((f["hit_rate"] for f in edge["form_analysis"] if "Cold" in f["label"]), None)
    if hot_hr is not None and cold_hr is not None:
        form_dependence = round(min(100, abs(hot_hr - cold_hr) / 0.5 * 100), 1)
    else:
        form_dependence = 0.0

    # 5. Rest sensitivity: gap between rested vs back-to-back hit rates
    rested_hr = next((r["hit_rate"] for r in edge["rest_analysis"] if "2+" in r["label"]), None)
    bb_hr     = next((r["hit_rate"] for r in edge["rest_analysis"] if "Back" in r["label"]), None)
    if rested_hr is not None and bb_hr is not None:
        rest_sensitivity = round(min(100, abs(rested_hr - bb_hr) / 0.5 * 100), 1)
    else:
        rest_sensitivity = 0.0

    # 6. SHAP: dominant driver group
    dominant_group = None
    shap_group_importance = {}
    if shap_data and shap_data.get("group_importance"):
        gi = shap_data["group_importance"]
        shap_group_importance = gi
        dominant_group = max(gi, key=gi.get)

    # ── Archetype label ───────────────────────────────────────────────────────
    archetype = _archetype(consistency, matchup_sensitivity, form_dependence,
                           rest_sensitivity, edge_reliability, dominant_group)

    # ── Strengths & vulnerabilities ───────────────────────────────────────────
    strengths, vulnerabilities = _swot(
        player_name, stat, consistency, edge_reliability, matchup_sensitivity,
        form_dependence, rest_sensitivity, fc, opp, edge
    )

    # ── Betting profile ───────────────────────────────────────────────────────
    betting_profile = _betting_profile(
        player_name, stat, archetype, bt, fc, opp, edge, rested_hr, bb_hr
    )

    dimensions = {
        "consistency":         consistency,
        "edge_reliability":    edge_reliability,
        "matchup_sensitivity": matchup_sensitivity,
        "form_dependence":     form_dependence,
        "rest_sensitivity":    rest_sensitivity,
    }

    radar = [
        {"dimension": "Consistency",    "value": consistency},
        {"dimension": "Edge Reliability", "value": edge_reliability},
        {"dimension": "Matchup Sens.",  "value": matchup_sensitivity},
        {"dimension": "Form Dep.",      "value": form_dependence},
        {"dimension": "Rest Sens.",     "value": rest_sensitivity},
    ]

    insight = _insight(
        player_name, stat, archetype, dimensions,
        dominant_group, shap_group_importance, fc, opp, edge
    )

    return {
        "player_name":            player_name,
        "stat":                   stat,
        "archetype":              archetype,
        "dimensions":             dimensions,
        "radar":                  radar,
        "dominant_shap_group":    dominant_group,
        "shap_group_importance":  shap_group_importance,
        "shap_available":         shap_data is not None,
        "shap_error":             shap_error,
        "strengths":              strengths,
        "vulnerabilities":        vulnerabilities,
        "betting_profile":        betting_profile,
        "insight":                insight,
        "floor":                  fc["floor"],
        "ceiling":                fc["ceiling"],
        "best_edge_threshold":    bt,
        "top_favorable_opponent": opp["favorable"][0]["opponent"] if opp["favorable"] else None,
        "top_unfavorable_opponent": opp["unfavorable"][-1]["opponent"] if opp["unfavorable"] else None,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _archetype(consistency, matchup_sensitivity, form_dependence,
               rest_sensitivity, edge_reliability, dominant_group):
    if consistency >= 70 and matchup_sensitivity < 15:
        return "Consistent Workhorse"
    if matchup_sensitivity >= 25:
        return "Matchup-Driven Player"
    if form_dependence >= 40:
        return "Momentum Rider"
    if rest_sensitivity >= 40:
        return "Load-Sensitive Performer"
    if consistency < 35:
        return "Boom/Bust Gamble"
    if edge_reliability >= 60:
        return "Model-Friendly Pick"
    return "Balanced All-Rounder"


def _swot(player_name, stat, consistency, edge_reliability, matchup_sensitivity,
          form_dependence, rest_sensitivity, fc, opp, edge):
    s = {"pts": "points", "reb": "rebounds", "ast": "assists"}.get(stat, stat)
    strengths = []
    vulnerabilities = []

    if consistency >= 65:
        strengths.append(f"High output consistency — floor of {fc['floor']} is reliable")
    if edge_reliability >= 50:
        bt = edge.get("best_threshold")
        strengths.append(
            f"Model edges are profitable (>{bt['threshold']} pts edge hits {bt['hit_rate']*100:.0f}%)"
            if bt else "Strong model alignment when edge is present"
        )
    if matchup_sensitivity < 12:
        strengths.append("Output is largely opponent-agnostic — context-proof")
    if opp["favorable"]:
        best = opp["favorable"][0]
        strengths.append(f"Exploitable matchup vs {best['opponent']} ({best['delta']:+.1f} vs avg)")

    if consistency < 40:
        vulnerabilities.append(f"High boom-bust ratio — median {fc['percentiles']['p50']} masks extreme variance")
    if matchup_sensitivity >= 25:
        worst = opp["unfavorable"][-1] if opp["unfavorable"] else None
        vulnerabilities.append(
            f"Matchup-sensitive: significant output drop vs {worst['opponent']}" if worst
            else "Opponent matchup is a key risk factor"
        )
    if form_dependence >= 40:
        cold_hr = next((f["hit_rate"] for f in edge["form_analysis"] if "Cold" in f["label"]), None)
        vulnerabilities.append(
            f"Cold streaks hurt model accuracy ({cold_hr*100:.0f}% hit rate when below form)"
            if cold_hr else "Performance heavily form-dependent"
        )
    if rest_sensitivity >= 40:
        bb_hr = next((r["hit_rate"] for r in edge["rest_analysis"] if "Back" in r["label"]), None)
        vulnerabilities.append(
            f"Back-to-backs are a risk ({bb_hr*100:.0f}% hit rate)"
            if bb_hr else "Performance degrades on back-to-backs"
        )

    return strengths[:3], vulnerabilities[:3]


def _insight(player_name, stat, archetype, dimensions, dominant_group,
             shap_group_importance, fc, opp, edge):
    first = player_name.split()[0]
    s = {"pts": "points", "reb": "rebounds", "ast": "assists"}.get(stat, stat)

    cons  = dimensions["consistency"]
    er    = dimensions["edge_reliability"]
    ms    = dimensions["matchup_sensitivity"]
    fd    = dimensions["form_dependence"]
    rs    = dimensions["rest_sensitivity"]

    parts = [f"**{first}** is classified as a **{archetype}**."]

    if cons >= 65:
        parts.append(f"Output consistency is high ({cons:.0f}/100) — the floor is reliable.")
    elif cons < 35:
        parts.append(f"Output is volatile ({cons:.0f}/100) — expect wide swings around the median.")

    if er >= 50:
        parts.append(f"Model edges convert to profit ({er:.0f}/100 edge reliability).")
    else:
        parts.append(f"Model edges are weak predictors ({er:.0f}/100) — bet selectively.")

    if ms >= 25:
        best = opp["favorable"][0]["opponent"] if opp["favorable"] else None
        parts.append(
            f"Matchup is a key lever ({ms:.0f}/100 sensitivity)"
            + (f" — {best} is a prime target." if best else ".")
        )

    if fd >= 40:
        parts.append(f"Recent form strongly influences output ({fd:.0f}/100) — avoid cold streaks.")

    if rs >= 40:
        parts.append(f"Rest matters significantly ({rs:.0f}/100) — back-to-backs carry risk.")

    if dominant_group and shap_group_importance:
        pct = shap_group_importance.get(dominant_group, 0)
        label_map = {
            "form": "recent form", "opponent": "opponent strength",
            "minutes": "minutes load", "shooting": "shooting efficiency",
            "season_avg": "season averages", "context": "game context",
        }
        parts.append(
            f"The XGBoost model is primarily driven by **{label_map.get(dominant_group, dominant_group)}** "
            f"({pct:.0f}% of prediction variance)."
        )

    return " ".join(parts)


def _betting_profile(player_name, stat, archetype, bt, fc, opp, edge, rested_hr, bb_hr):
    s = {"pts": "points", "reb": "rebounds", "ast": "assists"}.get(stat, stat)
    lines = []

    if bt:
        lines.append(
            f"**When to bet:** Look for edges of {bt['threshold']}+ pts — "
            f"historically {bt['hit_rate']*100:.0f}% accurate ({bt['n']} games)."
        )
    else:
        lines.append("**Edge signal:** No clear profitable edge threshold — bet selectively.")

    if opp["favorable"]:
        favs = ", ".join(o["opponent"] for o in opp["favorable"][:3])
        lines.append(f"**Favorable matchups:** {favs} — output reliably above season average.")

    if opp["unfavorable"]:
        bads = ", ".join(o["opponent"] for o in opp["unfavorable"][-3:])
        lines.append(f"**Avoid:** {bads} — historically suppressive matchups.")

    if rested_hr is not None and bb_hr is not None and abs(rested_hr - bb_hr) > 0.08:
        if rested_hr > bb_hr:
            lines.append(f"**Rest filter:** Skip back-to-backs ({bb_hr*100:.0f}% vs {rested_hr*100:.0f}% rested).")
        else:
            lines.append(f"**Back-to-back OK:** Accuracy is similar regardless of rest.")

    lines.append(
        f"**Distribution:** Floor {fc['floor']} / Ceiling {fc['ceiling']} — "
        f"{'wide range, median line bets are risky' if fc.get('boom_bust', 0) >= 1.5 else 'tight range, median line bets are reliable'}."
    )

    return " ".join(lines)
