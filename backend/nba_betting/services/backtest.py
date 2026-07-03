"""
services/backtest.py

Backtest engine: applies the trained XGBoost regression model to a player's
historical game log and simulates a -110 odds betting record.

"Line" used in backtesting = player's L5 rolling average (the natural baseline
available from historical data; real sportsbook lines aren't stored).

Usage:
    from nba_betting.services.backtest import run_backtest
    result = run_backtest("LeBron James", "pts", date(2024,1,1), date(2024,6,30))
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from django.db.models import Count, Max

from nba_betting.ml.predictor import ModelPredictor
from nba_betting.ml.train_regression import FEATURE_COLUMNS, _default_model_dir
from nba_betting.models import BacktestResult, BacktestRun, PlayerStats
from nba_betting.services.features import (
    _add_rolling_features,
    _find_player,
    _load_player_history,
)

# Simulates standard -110 juice: win 1.0 unit, lose 1.1 units
WIN_UNIT  =  1.0
LOSS_UNIT = -1.1

_predictor = None


def _get_predictor() -> ModelPredictor:
    global _predictor
    if _predictor is None:
        _predictor = ModelPredictor()
    return _predictor


def _sample_regime(date_from: date, date_to: date) -> str:
    """
    Classify a backtest window against the deployed model's split dates so
    accuracy is never silently presented as out-of-sample when it isn't.
    Classified by the window's EARLIEST date (worst case for a mixed window).

      out-of-sample     — entirely within the held-out test partition
      selection-overlap — overlaps the early-stopping validation window
      training-overlap  — overlaps the model's fit window
    """
    try:
        meta = json.loads((_default_model_dir() / "model_metadata.json").read_text())
        val_start = date.fromisoformat(meta["val_split_date"])
        test_start = date.fromisoformat(meta["split_date"])
    except Exception:
        return "unknown"
    if date_from >= test_start:
        return "out-of-sample"
    if date_from >= val_start:
        return "selection-overlap"
    return "training-overlap"


def run_backtest(
    player_name: str,
    stat: str,
    date_from: date,
    date_to: date,
    model: str = "xgb",
) -> dict[str, Any]:
    """
    Run a per-game backtest for one player + stat + model over a date range.

    model: 'xgb' | 'rf' | 'lr' | 'naive'
      - xgb/rf/lr use ModelPredictor with the corresponding saved model file
      - naive uses the player's season average as the projection (no ML model)

    Returns a dict with:
        run_id, player_name, stat, model, date_from, date_to,
        aggregate: {total_bets, wins, accuracy, total_pnl, roi},
        per_game: [{date, opponent, actual, line, projection, error,
                    predicted_over, correct, pnl, cumulative_pnl}, ...]
    """
    # ── Cache check ───────────────────────────────────────────────────────────
    cached = BacktestRun.objects.filter(
        player_name=player_name,
        stat=stat,
        model=model,
        date_from=date_from,
        date_to=date_to,
        total_bets__gt=0,
    ).first()
    if cached:
        return _serialize_run(cached)

    # ── Find player ───────────────────────────────────────────────────────────
    player = _find_player(player_name)
    if not player:
        raise ValueError(f"Player not found: {player_name!r}")

    # ── Build rolling features on FULL history ────────────────────────────────
    full_df = _load_player_history(player)
    if full_df.empty:
        raise ValueError(f"No historical stats for {player_name!r}")

    full_df = _add_rolling_features(full_df)
    full_df = _add_season_features(full_df)
    # Score only games the model was trained to predict (>= 10 minutes,
    # matching MIN_MINUTES target eligibility in ml/train_regression.py)
    full_df = full_df[full_df["min"] >= 10].reset_index(drop=True)

    # Drop rows that are still NaN in the stat-specific features we need
    required_cols = FEATURE_COLUMNS[stat]
    full_df = full_df.dropna(subset=[
        c for c in required_cols
        if c not in ("season_avg_pts", "season_avg_reb", "season_avg_ast",
                     "hot_cold_pts", "hot_cold_reb", "hot_cold_ast",
                     "opp_pts_allowed_L10", "opp_reb_allowed_L10", "opp_ast_allowed_L10")
    ])

    # ── Filter to date range ──────────────────────────────────────────────────
    full_df["date"] = pd.to_datetime(full_df["date"])
    mask = (full_df["date"].dt.date >= date_from) & (full_df["date"].dt.date <= date_to)
    window_df = full_df[mask].reset_index(drop=True)

    if window_df.empty:
        raise ValueError(
            f"No data for {player_name!r} between {date_from} and {date_to}"
        )

    # ── Pre-compute opponent defense (batch, no N+1) ──────────────────────────
    opp_defense = _batch_opponent_defense()

    # ── Per-game prediction loop ──────────────────────────────────────────────
    per_game_rows = []
    cumulative_pnl = 0.0
    feats = FEATURE_COLUMNS[stat]
    opp_defaults = {"pts": 112.0, "reb": 44.0, "ast": 26.0}

    for _, row in window_df.iterrows():
        game_date = row["date"].date()
        opponent  = str(row.get("opponent") or row.get("away_team") or "")
        actual    = float(row[stat])
        line      = float(row[f"{stat}_L5"])   # rolling avg as the backtest line

        # Push (actual exactly on the line): a sportsbook voids the bet, so
        # scoring it as a decided outcome would distort the hit rate.
        if actual == line:
            continue

        # Opponent defense lookup
        opp_pts = opp_defense.get(("pts", opponent, game_date), opp_defaults["pts"])
        opp_reb = opp_defense.get(("reb", opponent, game_date), opp_defaults["reb"])
        opp_ast = opp_defense.get(("ast", opponent, game_date), opp_defaults["ast"])

        # Std devs (with safe fallbacks)
        def _safe(col, default):
            v = row.get(col)
            return float(v) if v is not None and not pd.isna(v) else default

        # Build the full feature pool for this row
        feature_pool = {
            "is_home":             float(row["is_home"]),
            "days_rest":           _safe("days_rest", 3.0),
            "pts_L5":              _safe("pts_L5", 0.0),
            "pts_L10":             _safe("pts_L10", 0.0),
            "pts_ema_L5":          _safe("pts_ema_L5", 0.0),
            "pts_std_L10":         _safe("pts_std_L10", 5.0),
            "reb_L5":              _safe("reb_L5", 0.0),
            "reb_L10":             _safe("reb_L10", 0.0),
            "reb_ema_L5":          _safe("reb_ema_L5", 0.0),
            "reb_std_L10":         _safe("reb_std_L10", 2.0),
            "ast_L5":              _safe("ast_L5", 0.0),
            "ast_L10":             _safe("ast_L10", 0.0),
            "ast_ema_L5":          _safe("ast_ema_L5", 0.0),
            "ast_std_L10":         _safe("ast_std_L10", 1.5),
            "min_L5":              _safe("min_L5", 30.0),
            "min_L10":             _safe("min_L10", 30.0),
            "fg_pct_L5":           _safe("fg_pct_L5", 0.45),
            "fg_pct_L10":          _safe("fg_pct_L10", 0.45),
            "season_avg_pts":      _safe("season_avg_pts", _safe("pts_L10", 15.0)),
            "season_avg_reb":      _safe("season_avg_reb", _safe("reb_L10", 5.0)),
            "season_avg_ast":      _safe("season_avg_ast", _safe("ast_L10", 4.0)),
            "hot_cold_pts":        _safe("hot_cold_pts", 0.0),
            "hot_cold_reb":        _safe("hot_cold_reb", 0.0),
            "hot_cold_ast":        _safe("hot_cold_ast", 0.0),
            "opp_pts_allowed_L10": opp_pts,
            "opp_reb_allowed_L10": opp_reb,
            "opp_ast_allowed_L10": opp_ast,
        }

        # Select only the stat-specific features
        feature_row = pd.DataFrame([{k: feature_pool[k] for k in feats}])

        if model == "naive":
            # Naive baseline: predict the player's season average (no ML)
            season_avg_col = f"season_avg_{stat}"
            naive_val = row.get(season_avg_col)
            projection = float(naive_val) if naive_val is not None and not pd.isna(naive_val) else line
        else:
            projection = _get_predictor().predict_projection(feature_row, stat, model)
        if projection is None:
            continue

        projection    = float(projection)
        predicted_over = projection > line
        actual_over    = actual > line
        correct        = predicted_over == actual_over
        pnl            = WIN_UNIT if correct else LOSS_UNIT
        cumulative_pnl += pnl

        error = round(actual - projection, 2)

        # Store projection in prob_over field (repurposed for regression output)
        per_game_rows.append({
            "date":           str(game_date),
            "opponent":       opponent,
            "actual":         round(actual, 1),
            "line":           round(line, 2),
            "projection":     round(projection, 1),
            "prob_over":      round(projection, 4),   # stored for backward compat
            "predicted_over": predicted_over,
            "correct":        correct,
            "pnl":            pnl,
            "error":          error,
            "cumulative_pnl": round(cumulative_pnl, 2),
        })

    if not per_game_rows:
        raise ValueError("No valid predictions could be generated for this range.")

    # ── Aggregate stats ───────────────────────────────────────────────────────
    total_bets  = len(per_game_rows)
    wins        = sum(1 for r in per_game_rows if r["correct"])
    accuracy    = wins / total_bets
    total_pnl   = per_game_rows[-1]["cumulative_pnl"]
    roi         = (total_pnl / (total_bets * abs(LOSS_UNIT))) * 100

    # ── Persist results ───────────────────────────────────────────────────────
    run = BacktestRun.objects.create(
        player_name=player_name,
        stat=stat,
        model=model,
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
            error=r["error"],
        )
        for r in per_game_rows
    ])

    return {
        "run_id":      run.pk,
        "player_name": player_name,
        "stat":        stat,
        "model":       model,
        "date_from":   str(date_from),
        "date_to":     str(date_to),
        "sample_regime": _sample_regime(date_from, date_to),
        "aggregate": {
            "total_bets": total_bets,
            "wins":       wins,
            "accuracy":   round(accuracy, 4),
            "total_pnl":  round(total_pnl, 2),
            "roi":        round(roi, 2),
        },
        "per_game": per_game_rows,
    }


# ── Season-level features ─────────────────────────────────────────────────────

def _add_season_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add season_avg and hot_cold features to a player history dataframe.
    Season = NBA year (Oct start), derived from game date.
    Uses expanding mean shifted by 1 (no leakage).
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    # Determine NBA season start year from date
    df["_season_year"] = df["date"].apply(
        lambda d: d.year if d.month >= 10 else d.year - 1
    )

    grp = df.groupby(["player_name", "_season_year"], sort=False)
    for stat in ["pts", "reb", "ast"]:
        if stat not in df.columns:
            df[f"season_avg_{stat}"] = np.nan
            df[f"hot_cold_{stat}"]   = 0.0
            continue
        df[f"season_avg_{stat}"] = grp[stat].transform(
            lambda x: x.shift(1).expanding(min_periods=1).mean()
        )

    df = df.drop(columns=["_season_year"])

    for stat in ["pts", "reb", "ast"]:
        avg_col = f"season_avg_{stat}"
        l5_col  = f"{stat}_L5"
        if avg_col in df.columns and l5_col in df.columns:
            df[f"hot_cold_{stat}"] = (
                (df[l5_col] - df[avg_col]) / (df[avg_col].abs() + 0.1)
            )
        else:
            df[f"hot_cold_{stat}"] = 0.0

    return df


# ── Opponent defense batch ────────────────────────────────────────────────────

_OPP_DEFENSE_CACHE: dict[str, Any] = {"key": None, "value": {}}


def _batch_opponent_defense() -> dict[tuple[str, str, date], float]:
    """
    Pre-compute a lookup dict:
        {("pts"|"reb"|"ast", opponent_abbr, game_date): rolling_allowed}

    Fetches all PlayerStats in one query, avoids N+1 in the prediction loop.
    Memoized on (row count, latest game date) so repeated backtests — e.g.
    the season seeder's hundreds of runs — rebuild it only when new games
    have been synced.
    """
    try:
        agg = PlayerStats.objects.filter(period=0).aggregate(
            n=Count("id"), latest=Max("game__date")
        )
        cache_key = (agg["n"], str(agg["latest"]))
        if _OPP_DEFENSE_CACHE["key"] == cache_key:
            return _OPP_DEFENSE_CACHE["value"]

        qs = (
            PlayerStats.objects.filter(period=0)
            .select_related("game", "game__home_team", "game__away_team", "team")
            .values(
                "game__game_id",
                "game__date",
                "game__home_team__abbreviation",
                "game__away_team__abbreviation",
                "team__abbreviation",
                "pts", "reb", "ast",
            )
        )
        rows = list(qs)
        if not rows:
            return {}

        df = pd.DataFrame(rows)
        df.columns = ["game_id", "date", "home_abbr", "away_abbr", "player_team",
                      "pts", "reb", "ast"]
        df["date"] = pd.to_datetime(df["date"])

        # Determine opponent for each player row
        df["opponent"] = df.apply(
            lambda r: r["away_abbr"] if r["player_team"] == r["home_abbr"]
                      else r["home_abbr"],
            axis=1,
        )

        # Keep only the attacking team's rows (what the opponent ALLOWED)
        attacking = df[df["player_team"] != df["opponent"]]

        # Group by opponent + game
        per_game = (
            attacking.groupby(["opponent", "game_id", "date"])[["pts", "reb", "ast"]]
            .sum()
            .reset_index()
            .sort_values(["opponent", "date"])
        )

        # Rolling L10 shifted by 1 per opponent
        defaults = {"pts": 112.0, "reb": 44.0, "ast": 26.0}
        result: dict[tuple[str, str, date], float] = {}

        grp = per_game.groupby("opponent", sort=False)
        for stat in ("pts", "reb", "ast"):
            per_game[f"{stat}_l10"] = grp[stat].transform(
                lambda x: x.shift(1).rolling(10, min_periods=1).mean()
            )

        for _, row in per_game.iterrows():
            opp  = str(row["opponent"])
            gd   = row["date"].date()
            for stat in ("pts", "reb", "ast"):
                val = row[f"{stat}_l10"]
                result[(stat, opp, gd)] = float(val) if not pd.isna(val) else defaults[stat]

        _OPP_DEFENSE_CACHE["key"] = cache_key
        _OPP_DEFENSE_CACHE["value"] = result
        return result

    except Exception:
        return {}


# ── Serialize cached run ──────────────────────────────────────────────────────

def _serialize_run(run: BacktestRun) -> dict[str, Any]:
    per_game = []
    cumulative = 0.0
    for r in run.results.all():
        cumulative += r.pnl
        per_game.append({
            "date":           str(r.game_date),
            "opponent":       r.opponent,
            "actual":         r.actual,
            "line":           r.line,
            "projection":     r.prob_over,   # stored as projection value
            "prob_over":      r.prob_over,
            "predicted_over": r.predicted_over,
            "correct":        r.correct,
            "pnl":            r.pnl,
            "error":          r.error,
            "cumulative_pnl": round(cumulative, 2),
        })

    return {
        "run_id":      run.pk,
        "player_name": run.player_name,
        "stat":        run.stat,
        "model":       run.model,
        "date_from":   str(run.date_from),
        "date_to":     str(run.date_to),
        "sample_regime": _sample_regime(run.date_from, run.date_to),
        "aggregate": {
            "total_bets": run.total_bets,
            "wins":       run.wins,
            "accuracy":   run.accuracy,
            "total_pnl":  run.total_pnl,
            "roi":        run.roi,
        },
        "per_game": per_game,
    }
