"""
services/backtest.py

Backtest engine: applies the trained XGBoost model to a player's historical
game log and simulates a -110 odds betting record.

"Line" = pts_L5 rolling average (what the model was trained to predict over/under).

Usage:
    from nba_betting.services.backtest import run_backtest
    result = run_backtest("LeBron James", "pts", date(2023,1,1), date(2023,6,30))
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from nba_betting.ml.predictor import ModelPredictor
from nba_betting.models import BacktestResult, BacktestRun, PlayerStats
from nba_betting.services.features import (
    _add_rolling_features,
    _find_player,
    _load_player_history,
)

# Simulates standard -110 juice: win 1.0 unit, lose 1.1 units
WIN_UNIT = 1.0
LOSS_UNIT = -1.1

FEATURE_COLUMNS = [
    "is_home", "days_rest",
    "pts_L5", "pts_L10", "pts_ema_L5", "pts_std_L10",
    "reb_L5", "reb_L10", "reb_ema_L5",
    "ast_L5", "ast_L10", "ast_ema_L5",
    "min_L5", "min_L10",
    "fg_pct_L5", "fg_pct_L10",
    "opp_pts_allowed_L10",
]

_predictor = None


def _get_predictor() -> ModelPredictor:
    global _predictor
    if _predictor is None:
        _predictor = ModelPredictor()
    return _predictor


def run_backtest(
    player_name: str,
    stat: str,
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    """
    Run a per-game backtest for one player + stat over a date range.

    Returns a dict with:
        run_id, player_name, stat, date_from, date_to,
        aggregate: {total_bets, wins, accuracy, total_pnl, roi},
        per_game: [{date, opponent, actual, line, prob_over,
                    predicted_over, correct, pnl, cumulative_pnl}, ...]
    """
    # --- Cache check -------------------------------------------------
    cached = BacktestRun.objects.filter(
        player_name=player_name,
        stat=stat,
        date_from=date_from,
        date_to=date_to,
        total_bets__gt=0,
    ).first()

    if cached:
        return _serialize_run(cached)

    # --- Find player -------------------------------------------------
    player = _find_player(player_name)
    if not player:
        raise ValueError(f"Player not found: {player_name!r}")

    # --- Build rolling features on FULL history ----------------------
    full_df = _load_player_history(player)
    if full_df.empty:
        raise ValueError(f"No historical stats for {player_name!r}")

    full_df = _add_rolling_features(full_df)
    full_df = full_df[full_df["min"] > 0].dropna().reset_index(drop=True)

    # --- Filter to date range ----------------------------------------
    full_df["date"] = pd.to_datetime(full_df["date"])
    mask = (full_df["date"].dt.date >= date_from) & (full_df["date"].dt.date <= date_to)
    window_df = full_df[mask].reset_index(drop=True)

    if window_df.empty:
        raise ValueError(
            f"No data for {player_name!r} between {date_from} and {date_to}"
        )

    # --- Pre-compute opponent defense --------------------------------
    opp_defense = _batch_opponent_defense(full_df)

    # --- Per-game prediction loop ------------------------------------
    per_game_rows = []
    cumulative_pnl = 0.0

    for _, row in window_df.iterrows():
        game_date = row["date"].date()
        opponent = str(row.get("opponent", row.get("away_team", "")))
        actual = float(row[stat])
        line = float(row[f"{stat}_L5"])

        opp_def = opp_defense.get((opponent, game_date), 112.0)

        feature_row = pd.DataFrame(
            [{
                "is_home": float(row["is_home"]),
                "days_rest": float(row.get("days_rest", 2) or 2),
                "pts_L5": float(row["pts_L5"]),
                "pts_L10": float(row["pts_L10"]),
                "pts_ema_L5": float(row["pts_ema_L5"]),
                "pts_std_L10": float(row["pts_std_L10"]) if not pd.isna(row["pts_std_L10"]) else 4.0,
                "reb_L5": float(row["reb_L5"]),
                "reb_L10": float(row["reb_L10"]),
                "reb_ema_L5": float(row["reb_ema_L5"]),
                "ast_L5": float(row["ast_L5"]),
                "ast_L10": float(row["ast_L10"]),
                "ast_ema_L5": float(row["ast_ema_L5"]),
                "min_L5": float(row["min_L5"]),
                "min_L10": float(row["min_L10"]),
                "fg_pct_L5": float(row["fg_pct_L5"]),
                "fg_pct_L10": float(row["fg_pct_L10"]),
                "opp_pts_allowed_L10": float(opp_def),
            }]
        )

        prob_over = _get_predictor().predict_probability(feature_row, stat, "xgb")
        if prob_over is None:
            continue

        prob_over = float(prob_over)
        predicted_over = prob_over >= 0.5
        actual_over = actual > line
        correct = predicted_over == actual_over
        pnl = WIN_UNIT if correct else LOSS_UNIT
        cumulative_pnl += pnl

        per_game_rows.append({
            "date": str(game_date),
            "opponent": opponent,
            "actual": round(actual, 1),
            "line": round(line, 2),
            "prob_over": round(prob_over, 4),
            "predicted_over": predicted_over,
            "correct": correct,
            "pnl": pnl,
            "cumulative_pnl": round(cumulative_pnl, 2),
        })

    if not per_game_rows:
        raise ValueError("No valid predictions could be generated for this range.")

    # --- Aggregate stats ---------------------------------------------
    total_bets = len(per_game_rows)
    wins = sum(1 for r in per_game_rows if r["correct"])
    accuracy = wins / total_bets
    total_pnl = per_game_rows[-1]["cumulative_pnl"]
    roi = (total_pnl / (total_bets * abs(LOSS_UNIT))) * 100

    # --- Persist results ---------------------------------------------
    run = BacktestRun.objects.create(
        player_name=player_name,
        stat=stat,
        date_from=date_from,
        date_to=date_to,
        total_bets=total_bets,
        wins=wins,
        accuracy=round(accuracy, 4),
        total_pnl=round(total_pnl, 2),
        roi=round(roi, 2),
    )

    BacktestResult.objects.bulk_create([
        BacktestResult(
            run=run,
            game_date=r["date"],
            opponent=r["opponent"],
            actual=r["actual"],
            line=r["line"],
            prob_over=r["prob_over"],
            predicted_over=r["predicted_over"],
            correct=r["correct"],
            pnl=r["pnl"],
        )
        for r in per_game_rows
    ])

    return {
        "run_id": run.pk,
        "player_name": player_name,
        "stat": stat,
        "date_from": str(date_from),
        "date_to": str(date_to),
        "aggregate": {
            "total_bets": total_bets,
            "wins": wins,
            "accuracy": round(accuracy, 4),
            "total_pnl": round(total_pnl, 2),
            "roi": round(roi, 2),
        },
        "per_game": per_game_rows,
    }


def _serialize_run(run: BacktestRun) -> dict[str, Any]:
    """Serialize a cached BacktestRun + its BacktestResult rows."""
    per_game = []
    cumulative = 0.0
    for r in run.results.all():
        cumulative += r.pnl
        per_game.append({
            "date": str(r.game_date),
            "opponent": r.opponent,
            "actual": r.actual,
            "line": r.line,
            "prob_over": r.prob_over,
            "predicted_over": r.predicted_over,
            "correct": r.correct,
            "pnl": r.pnl,
            "cumulative_pnl": round(cumulative, 2),
        })

    return {
        "run_id": run.pk,
        "player_name": run.player_name,
        "stat": run.stat,
        "date_from": str(run.date_from),
        "date_to": str(run.date_to),
        "aggregate": {
            "total_bets": run.total_bets,
            "wins": run.wins,
            "accuracy": run.accuracy,
            "total_pnl": run.total_pnl,
            "roi": run.roi,
        },
        "per_game": per_game,
    }


def _batch_opponent_defense(full_df: pd.DataFrame) -> dict[tuple[str, date], float]:
    """
    Pre-compute a lookup dict: {(opponent_abbr, game_date): opp_pts_allowed_L10}
    from the full PlayerStats table in a single query, avoiding N+1 queries
    in the prediction loop.

    This replicates the rolling L10 opponent defense logic from features.py
    but in batch form.
    """
    try:
        qs = (
            PlayerStats.objects.filter(period=0)
            .select_related("game", "game__home_team", "game__away_team", "team")
            .values(
                "game__game_id",
                "game__date",
                "game__home_team__abbreviation",
                "game__away_team__abbreviation",
                "team__abbreviation",
                "pts",
            )
        )
        rows = list(qs)
        if not rows:
            return {}

        df = pd.DataFrame(rows)
        df.columns = ["game_id", "date", "home_abbr", "away_abbr", "player_team", "pts"]
        df["date"] = pd.to_datetime(df["date"])

        # Determine opponent for each player row
        df["opponent"] = df.apply(
            lambda r: r["away_abbr"] if r["player_team"] == r["home_abbr"] else r["home_abbr"],
            axis=1,
        )

        # Filter out the opponent's own players
        opponent_allowed = df[df["player_team"] != df["opponent"]]

        # Group by opponent + game
        opp_game = (
            opponent_allowed.groupby(["opponent", "game_id", "date"])["pts"]
            .sum()
            .reset_index()
            .sort_values(["opponent", "date"])
        )

        # Rolling L10 with shift(1)
        opp_game["opp_pts_l10"] = opp_game.groupby("opponent")["pts"].transform(
            lambda x: x.shift(1).rolling(10, min_periods=1).mean()
        )

        # Fill NaN with league average
        league_avg = float(opp_game["pts"].mean()) if not opp_game.empty else 112.0

        result: dict[tuple[str, date], float] = {}
        for _, row in opp_game.iterrows():
            val = row["opp_pts_l10"]
            opp_def = float(val) if not pd.isna(val) else league_avg
            result[(str(row["opponent"]), row["date"].date())] = opp_def

        return result

    except Exception:
        return {}
