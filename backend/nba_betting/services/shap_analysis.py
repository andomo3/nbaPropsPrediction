"""
services/shap_analysis.py

SHAP (SHapley Additive exPlanations) feature attribution for the XGBoost
regression models.

For a given player + stat, this service:
  1. Loads the player's 2025-26 game log and builds the same feature matrix
     used by the backtest engine.
  2. Runs shap.TreeExplainer on the trained XGBoost model.
  3. Returns per-feature global importance (mean |SHAP|) and per-game
     local attributions (top driver each game).
  4. Auto-generates a plain-English insight paragraph.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

try:
    import shap as _shap
    SHAP_AVAILABLE = True
except ImportError:
    _shap = None
    SHAP_AVAILABLE = False

from nba_betting.constants import SEASON_DATES
from nba_betting.ml.predictor import ModelPredictor
from nba_betting.ml.train_regression import FEATURE_COLUMNS
from nba_betting.services.backtest import _add_season_features, _batch_opponent_defense
from nba_betting.services.features import (
    _add_rolling_features,
    _find_player,
    _load_player_history,
)

SEASON = 2026

# ── Human-readable feature labels ────────────────────────────────────────────

FEATURE_LABELS: dict[str, str] = {
    "is_home":              "Home game",
    "days_rest":            "Days of rest",
    "pts_L5":               "Pts avg (L5)",
    "pts_L10":              "Pts avg (L10)",
    "pts_ema_L5":           "Pts EMA (L5)",
    "pts_std_L10":          "Pts volatility (L10)",
    "reb_L5":               "Reb avg (L5)",
    "reb_L10":              "Reb avg (L10)",
    "reb_ema_L5":           "Reb EMA (L5)",
    "reb_std_L10":          "Reb volatility (L10)",
    "ast_L5":               "Ast avg (L5)",
    "ast_L10":              "Ast avg (L10)",
    "ast_ema_L5":           "Ast EMA (L5)",
    "ast_std_L10":          "Ast volatility (L10)",
    "min_L5":               "Minutes (L5)",
    "min_L10":              "Minutes (L10)",
    "fg_pct_L5":            "FG% (L5)",
    "fg_pct_L10":           "FG% (L10)",
    "season_avg_pts":       "Season avg pts",
    "season_avg_reb":       "Season avg reb",
    "season_avg_ast":       "Season avg ast",
    "hot_cold_pts":         "Hot/cold streak (pts)",
    "hot_cold_reb":         "Hot/cold streak (reb)",
    "hot_cold_ast":         "Hot/cold streak (ast)",
    "opp_pts_allowed_L10":  "Opponent pts allowed (L10)",
    "opp_reb_allowed_L10":  "Opponent reb allowed (L10)",
    "opp_ast_allowed_L10":  "Opponent ast allowed (L10)",
}

STAT_LABELS = {"pts": "points", "reb": "rebounds", "ast": "assists"}

# Group features for insight generation
_FORM_FEATURES   = {"pts_L5", "pts_L10", "pts_ema_L5", "reb_L5", "reb_L10",
                    "reb_ema_L5", "ast_L5", "ast_L10", "ast_ema_L5",
                    "hot_cold_pts", "hot_cold_reb", "hot_cold_ast"}
_OPP_FEATURES    = {"opp_pts_allowed_L10", "opp_reb_allowed_L10", "opp_ast_allowed_L10"}
_MINUTES_FEATURES = {"min_L5", "min_L10"}
_SHOOTING_FEATURES = {"fg_pct_L5", "fg_pct_L10"}
_SEASON_FEATURES = {"season_avg_pts", "season_avg_reb", "season_avg_ast"}
_CONTEXT_FEATURES = {"is_home", "days_rest"}


def compute_shap_analysis(
    player_name: str,
    stat: str,
) -> dict[str, Any]:
    """
    Compute SHAP feature attributions for player + stat over their 2025-26 games.

    Returns:
        player_name, stat, n_games, expected_value,
        feature_importance: [{feature, label, mean_abs_shap, mean_shap, direction, pct_contribution}],
        per_game: [{game_num, date, opponent, actual, projection, top_driver, shap_values}],
        group_importance: {form, opponent, minutes, shooting, season_avg, context},
        insight: str
    """
    # ── Load player history ───────────────────────────────────────────────────
    player = _find_player(player_name)
    if not player:
        raise ValueError(f"Player not found: {player_name!r}")

    history_df = _load_player_history(player)
    if history_df.empty:
        raise ValueError(f"No historical stats for {player_name!r}")

    history_df = _add_rolling_features(history_df)
    history_df = _add_season_features(history_df)
    history_df = history_df[history_df["min"] > 0].reset_index(drop=True)

    # ── Filter to 2025-26 season ──────────────────────────────────────────────
    date_from, date_to = SEASON_DATES[SEASON]
    history_df["date"] = pd.to_datetime(history_df["date"])
    mask = (
        (history_df["date"].dt.date >= date_from)
        & (history_df["date"].dt.date <= date_to)
    )
    season_df = history_df[mask].reset_index(drop=True)

    if season_df.empty:
        raise ValueError(f"No 2025-26 data for {player_name!r}")

    # ── Load XGBoost model ────────────────────────────────────────────────────
    predictor = ModelPredictor()
    model = predictor.load_model(stat, "xgb")
    if model is None:
        raise ValueError(f"XGBoost model for {stat!r} not found. Run train_models first.")

    # ── Build feature matrix (same logic as backtest engine) ─────────────────
    opp_defense  = _batch_opponent_defense()
    feats        = FEATURE_COLUMNS[stat]
    opp_defaults = {"pts": 112.0, "reb": 44.0, "ast": 26.0}

    X_rows: list[dict] = []
    meta:   list[dict] = []

    def _safe(row, col, default):
        v = row.get(col)
        return float(v) if v is not None and not pd.isna(v) else default

    for _, row in season_df.iterrows():
        game_date = row["date"].date()
        opponent  = str(row.get("opponent") or "")
        actual    = float(row[stat])

        opp_pts = opp_defense.get(("pts", opponent, game_date), opp_defaults["pts"])
        opp_reb = opp_defense.get(("reb", opponent, game_date), opp_defaults["reb"])
        opp_ast = opp_defense.get(("ast", opponent, game_date), opp_defaults["ast"])

        feature_pool = {
            "is_home":              float(row["is_home"]),
            "days_rest":            _safe(row, "days_rest", 2.0),
            "pts_L5":               _safe(row, "pts_L5", 0.0),
            "pts_L10":              _safe(row, "pts_L10", 0.0),
            "pts_ema_L5":           _safe(row, "pts_ema_L5", 0.0),
            "pts_std_L10":          _safe(row, "pts_std_L10", 5.0),
            "reb_L5":               _safe(row, "reb_L5", 0.0),
            "reb_L10":              _safe(row, "reb_L10", 0.0),
            "reb_ema_L5":           _safe(row, "reb_ema_L5", 0.0),
            "reb_std_L10":          _safe(row, "reb_std_L10", 2.0),
            "ast_L5":               _safe(row, "ast_L5", 0.0),
            "ast_L10":              _safe(row, "ast_L10", 0.0),
            "ast_ema_L5":           _safe(row, "ast_ema_L5", 0.0),
            "ast_std_L10":          _safe(row, "ast_std_L10", 1.5),
            "min_L5":               _safe(row, "min_L5", 30.0),
            "min_L10":              _safe(row, "min_L10", 30.0),
            "fg_pct_L5":            _safe(row, "fg_pct_L5", 0.45),
            "fg_pct_L10":           _safe(row, "fg_pct_L10", 0.45),
            "season_avg_pts":       _safe(row, "season_avg_pts", _safe(row, "pts_L10", 15.0)),
            "season_avg_reb":       _safe(row, "season_avg_reb", _safe(row, "reb_L10", 5.0)),
            "season_avg_ast":       _safe(row, "season_avg_ast", _safe(row, "ast_L10", 4.0)),
            "hot_cold_pts":         _safe(row, "hot_cold_pts", 0.0),
            "hot_cold_reb":         _safe(row, "hot_cold_reb", 0.0),
            "hot_cold_ast":         _safe(row, "hot_cold_ast", 0.0),
            "opp_pts_allowed_L10":  opp_pts,
            "opp_reb_allowed_L10":  opp_reb,
            "opp_ast_allowed_L10":  opp_ast,
        }

        X_rows.append({k: feature_pool[k] for k in feats})
        meta.append({
            "game_num": len(meta) + 1,
            "date":     str(game_date),
            "opponent": opponent,
            "actual":   round(actual, 1),
        })

    if not X_rows:
        raise ValueError("No valid feature rows could be built.")

    if not SHAP_AVAILABLE:
        raise RuntimeError(
            "shap is not installed. Run: pip install shap>=0.44"
        )

    X = pd.DataFrame(X_rows, columns=feats)

    # ── Compute SHAP values ───────────────────────────────────────────────────
    explainer   = _shap.TreeExplainer(model)
    shap_matrix = explainer.shap_values(X)   # (n_games, n_features)
    expected_val = float(explainer.expected_value)

    # XGBoost predictions for projection column in per_game
    dmatrix     = xgb.DMatrix(X, feature_names=feats)
    projections = model.predict(dmatrix)

    # ── Global feature importance ─────────────────────────────────────────────
    mean_abs  = np.mean(np.abs(shap_matrix), axis=0)   # (n_features,)
    mean_shap = np.mean(shap_matrix, axis=0)
    total_abs = float(mean_abs.sum()) or 1.0

    feature_importance = []
    for i, feat in enumerate(feats):
        feature_importance.append({
            "feature":           feat,
            "label":             FEATURE_LABELS.get(feat, feat),
            "mean_abs_shap":     round(float(mean_abs[i]), 4),
            "mean_shap":         round(float(mean_shap[i]), 4),
            "direction":         "positive" if mean_shap[i] >= 0 else "negative",
            "pct_contribution":  round(float(mean_abs[i]) / total_abs * 100, 1),
        })
    feature_importance.sort(key=lambda x: x["mean_abs_shap"], reverse=True)

    # ── Per-game attributions ─────────────────────────────────────────────────
    per_game = []
    for i, game in enumerate(meta):
        game_shap = shap_matrix[i]
        top_idx   = int(np.argmax(np.abs(game_shap)))

        per_game.append({
            **game,
            "projection": round(float(projections[i]), 1),
            "top_driver": {
                "feature":    feats[top_idx],
                "label":      FEATURE_LABELS.get(feats[top_idx], feats[top_idx]),
                "shap_value": round(float(game_shap[top_idx]), 3),
            },
            "shap_values": {
                feats[j]: round(float(game_shap[j]), 3)
                for j in range(len(feats))
            },
        })

    # ── Group-level importance ────────────────────────────────────────────────
    group_importance = _compute_group_importance(feats, mean_abs)

    # ── Auto-insight ──────────────────────────────────────────────────────────
    insight = _generate_insight(
        player_name, stat, feature_importance, group_importance,
        shap_matrix, X, expected_val
    )

    return {
        "player_name":       player_name,
        "stat":              stat,
        "n_games":           len(meta),
        "expected_value":    round(expected_val, 2),
        "feature_importance": feature_importance,
        "per_game":          per_game,
        "group_importance":  group_importance,
        "insight":           insight,
    }


# ── Group importance ──────────────────────────────────────────────────────────

def _compute_group_importance(
    feats: list[str],
    mean_abs: np.ndarray,
) -> dict[str, float]:
    """
    Aggregate mean |SHAP| into interpretable groups, returning % contribution each.
    """
    groups = {
        "form":       _FORM_FEATURES,
        "opponent":   _OPP_FEATURES,
        "minutes":    _MINUTES_FEATURES,
        "shooting":   _SHOOTING_FEATURES,
        "season_avg": _SEASON_FEATURES,
        "context":    _CONTEXT_FEATURES,
    }
    totals: dict[str, float] = {g: 0.0 for g in groups}
    total_all = float(mean_abs.sum()) or 1.0

    for i, feat in enumerate(feats):
        for group, members in groups.items():
            if feat in members:
                totals[group] += float(mean_abs[i])
                break

    return {g: round(v / total_all * 100, 1) for g, v in totals.items()}


# ── Auto-insight generation ───────────────────────────────────────────────────

def _generate_insight(
    player_name: str,
    stat: str,
    feature_importance: list[dict],
    group_importance: dict[str, float],
    shap_matrix: np.ndarray,
    X: pd.DataFrame,
    expected_value: float,
) -> str:
    stat_label = STAT_LABELS.get(stat, stat)
    first_name = player_name.split()[0]

    top_feat   = feature_importance[0]
    top2_feat  = feature_importance[1] if len(feature_importance) > 1 else None

    form_pct   = group_importance.get("form", 0)
    opp_pct    = group_importance.get("opponent", 0)
    shoot_pct  = group_importance.get("shooting", 0)
    min_pct    = group_importance.get("minutes", 0)

    # Predictability: coefficient of variation of |SHAP| sums per game
    per_game_total_abs = np.sum(np.abs(shap_matrix), axis=1)
    shap_cv = float(np.std(per_game_total_abs) / (np.mean(per_game_total_abs) + 1e-6))
    consistency_desc = (
        "highly consistent game-to-game" if shap_cv < 0.25
        else "moderately consistent" if shap_cv < 0.45
        else "variable — the model's confidence shifts significantly game-to-game"
    )

    # Primary driver sentence
    top_label = top_feat["label"]
    top_dir   = "increases" if top_feat["direction"] == "positive" else "decreases"
    primary = (
        f"{first_name}'s projected {stat_label} output is most sensitive to "
        f"**{top_label}** ({top_feat['pct_contribution']:.0f}% of total prediction variance), "
        f"which on average {top_dir} the projection by {top_feat['mean_abs_shap']:.2f} {stat_label}."
    )

    # Opponent sensitivity sentence
    if opp_pct >= 15:
        opp_sent = (
            f"Opponent defensive strength accounts for {opp_pct:.0f}% of the model's signal, "
            f"meaning matchup context meaningfully shifts {first_name}'s projections."
        )
    elif opp_pct >= 6:
        opp_sent = (
            f"Opponent defense has a moderate influence ({opp_pct:.0f}%), "
            f"providing some edge when {first_name} faces weaker or stronger defenses."
        )
    else:
        opp_sent = (
            f"Opponent defense contributes minimally ({opp_pct:.0f}%), suggesting "
            f"{first_name}'s {stat_label} output is largely opponent-independent."
        )

    # Shooting / form split (for pts)
    if stat == "pts" and shoot_pct >= 10:
        form_sent = (
            f"Recent shooting form (FG%) contributes {shoot_pct:.0f}% of the signal — "
            f"a signal that is inherently volatile, which limits the model's ceiling for this player."
        )
    elif form_pct >= 40:
        form_sent = (
            f"Recent performance trends (L5/L10 averages, hot-cold index) dominate "
            f"the prediction at {form_pct:.0f}%, making the model momentum-sensitive."
        )
    else:
        form_sent = (
            f"Recent form accounts for {form_pct:.0f}% of the signal, "
            f"balanced against season-level and contextual factors."
        )

    # Consistency sentence
    consistency_sent = (
        f"Overall, the model's feature attribution for {first_name} is {consistency_desc}."
    )

    return " ".join([primary, opp_sent, form_sent, consistency_sent])
