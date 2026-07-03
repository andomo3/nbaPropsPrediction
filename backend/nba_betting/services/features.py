"""
Feature engineering for inference.

Builds stat-specific feature rows from the ESPN-synced database for use
with the regression models trained in nba_betting.ml.train_regression.
"""

from datetime import date

import numpy as np
import pandas as pd
from django.db.models import Q

from nba_betting.constants import STD_DEFAULTS
from nba_betting.ml.train_regression import FEATURE_COLUMNS
from nba_betting.models import Player, PlayerStats


def _num_or(value, default: float) -> float:
    """float(value) unless it's None/NaN — preserves legitimate zeros,
    which an `or`-style fallback would silently replace."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return float(default)
    return float(default) if np.isnan(f) else f


def get_model_inputs(player_name: str, opponent: str, stat: str, is_home: bool = True):
    """
    Build a stat-specific feature row for the given player.

    Returns:
        (player, feature_row)  on success
        (None, error_message)  on failure
    """
    player = _find_player(player_name)
    if not player:
        return None, "Player not found."

    history_df = _load_player_history(player)
    if history_df.empty:
        return None, "No historical stats found."

    history_df = _add_rolling_features(history_df)
    history_df = history_df[history_df["min"] > 0]
    history_df = history_df.dropna(subset=[
        "pts_L5", "pts_L10", "reb_L5", "reb_L10", "ast_L5", "ast_L10",
        "min_L5", "min_L10",
    ])
    if history_df.empty:
        return None, "Not enough data to build features."

    latest = history_df.iloc[-1]
    ref_date = latest["date"]

    # ── Opponent defense ──────────────────────────────────────────────────────
    opp_pts = _get_opponent_stat_allowed(opponent, ref_date, "pts")
    opp_reb = _get_opponent_stat_allowed(opponent, ref_date, "reb")
    opp_ast = _get_opponent_stat_allowed(opponent, ref_date, "ast")

    # Fallbacks to league averages
    if opp_pts is None or np.isnan(opp_pts):
        opp_pts = _get_league_avg_allowed(ref_date, "pts")
    if opp_reb is None or np.isnan(opp_reb):
        opp_reb = _get_league_avg_allowed(ref_date, "reb")
    if opp_ast is None or np.isnan(opp_ast):
        opp_ast = _get_league_avg_allowed(ref_date, "ast")

    # ── Season averages (from DB history) ────────────────────────────────────
    season_avg_pts = _get_season_avg(history_df, "pts", ref_date)
    season_avg_reb = _get_season_avg(history_df, "reb", ref_date)
    season_avg_ast = _get_season_avg(history_df, "ast", ref_date)

    # ── Hot / cold streaks ────────────────────────────────────────────────────
    def _hot_cold(l5_val, season_avg):
        return float((l5_val - season_avg) / (abs(season_avg) + 0.1))

    hot_cold_pts = _hot_cold(float(latest["pts_L5"]), season_avg_pts)
    hot_cold_reb = _hot_cold(float(latest["reb_L5"]), season_avg_reb)
    hot_cold_ast = _hot_cold(float(latest["ast_L5"]), season_avg_ast)

    # ── Std L10 (pts_std used for probability derivation in views.py) ─────────
    # NaN-safe: a short history yields NaN std (rolling min_periods=5), and
    # float(NaN) is truthy — an `or` fallback would pass NaN straight into the
    # probability CDF and produce a clamped prob_over of 0.99.
    pts_std  = _num_or(latest.get("pts_std_L10"), STD_DEFAULTS["pts"])
    reb_std  = _num_or(latest.get("reb_std_L10"), STD_DEFAULTS["reb"])
    ast_std  = _num_or(latest.get("ast_std_L10"), STD_DEFAULTS["ast"])

    # ── Assemble full feature pool ────────────────────────────────────────────
    all_features = {
        "is_home":             1.0 if is_home else 0.0,
        "days_rest":           _num_or(latest.get("days_rest"), 3.0),
        # pts features
        "pts_L5":              float(latest["pts_L5"]),
        "pts_L10":             float(latest["pts_L10"]),
        "pts_ema_L5":          float(latest["pts_ema_L5"]),
        "pts_std_L10":         pts_std,
        "season_avg_pts":      season_avg_pts,
        "hot_cold_pts":        hot_cold_pts,
        "opp_pts_allowed_L10": float(opp_pts),
        # reb features
        "reb_L5":              float(latest["reb_L5"]),
        "reb_L10":             float(latest["reb_L10"]),
        "reb_ema_L5":          float(latest["reb_ema_L5"]),
        "reb_std_L10":         reb_std,
        "season_avg_reb":      season_avg_reb,
        "hot_cold_reb":        hot_cold_reb,
        "opp_reb_allowed_L10": float(opp_reb),
        # ast features
        "ast_L5":              float(latest["ast_L5"]),
        "ast_L10":             float(latest["ast_L10"]),
        "ast_ema_L5":          float(latest["ast_ema_L5"]),
        "ast_std_L10":         ast_std,
        "season_avg_ast":      season_avg_ast,
        "hot_cold_ast":        hot_cold_ast,
        "opp_ast_allowed_L10": float(opp_ast),
        # shared
        "min_L5":              float(latest["min_L5"]),
        "min_L10":             float(latest["min_L10"]),
        "fg_pct_L5":           _num_or(latest.get("fg_pct_L5"), 0.45),
        "fg_pct_L10":          _num_or(latest.get("fg_pct_L10"), 0.45),
    }

    # Select only the columns for this stat's model
    stat_feats = FEATURE_COLUMNS[stat]
    feature_row = pd.DataFrame([{k: all_features[k] for k in stat_feats}])

    return player, feature_row


def get_std_for_stat(player_name: str, stat: str) -> float:
    """Return the player's rolling 10-game std dev for the given stat (for probability derivation)."""
    player = _find_player(player_name)
    if not player:
        return STD_DEFAULTS.get(stat, 3.0)

    history_df = _load_player_history(player)
    if history_df.empty:
        return STD_DEFAULTS.get(stat, 3.0)

    history_df = _add_rolling_features(history_df)
    history_df = history_df.dropna(subset=[f"{stat}_std_L10"])
    if history_df.empty:
        return STD_DEFAULTS.get(stat, 3.0)

    return float(history_df.iloc[-1][f"{stat}_std_L10"])


# ── Player lookup ─────────────────────────────────────────────────────────────

def _find_player(player_name: str) -> Player | None:
    if not player_name:
        return None
    parts = [p for p in str(player_name).split(" ") if p]
    if len(parts) >= 2:
        player = Player.objects.filter(
            first_name__iexact=parts[0],
            last_name__iexact=" ".join(parts[1:]),
        ).first()
        if player:
            return player
    return Player.objects.filter(
        Q(first_name__icontains=player_name) | Q(last_name__icontains=player_name)
    ).first()


# ── History loading ───────────────────────────────────────────────────────────

def _load_player_history(player: Player) -> pd.DataFrame:
    stats_qs = (
        PlayerStats.objects.filter(player=player, period=0)
        .select_related("game", "team", "game__home_team", "game__away_team")
        .order_by("game__date")
    )

    rows = []
    for row in stats_qs:
        game = row.game
        fg_pct = (row.fgm / row.fga) if row.fga else 0.0
        rows.append({
            "date":        game.date,
            "game_id":     game.game_id,
            "player_name": f"{player.first_name} {player.last_name}".strip(),
            "player_team": row.team.abbreviation if row.team else None,
            "home_team":   game.home_team.abbreviation if game.home_team else None,
            "away_team":   game.away_team.abbreviation if game.away_team else None,
            "pts":         row.pts,
            "reb":         row.reb,
            "ast":         row.ast,
            "min":         row.min,
            "fg_pct":      fg_pct,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["player_name", "date"]).reset_index(drop=True)
    df["is_home"] = (df["player_team"] == df["home_team"]).astype(int)
    df["opponent"] = np.where(df["is_home"] == 1, df["away_team"], df["home_team"])
    # fillna(3) + clip(10) mirrors training (ml/train_regression.py days_rest)
    df["days_rest"] = (
        df.groupby("player_name")["date"].diff().dt.days.fillna(3).clip(upper=10)
    )
    return df


# ── Rolling feature computation ───────────────────────────────────────────────

def _add_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    calc_df = df.copy()
    # Mask games with < 10 minutes (injury/DNP) so they don't pollute rolling averages
    mask = calc_df["min"] < 10
    calc_df.loc[mask, ["pts", "reb", "ast", "min", "fg_pct"]] = np.nan

    for stat in ["pts", "reb", "ast", "min", "fg_pct"]:
        for window in (5, 10):
            df[f"{stat}_L{window}"] = calc_df.groupby("player_name")[stat].transform(
                lambda x, w=window: x.shift(1).rolling(w, min_periods=1).mean()
            )

    for stat in ["pts", "reb", "ast"]:
        df[f"{stat}_ema_L5"] = calc_df.groupby("player_name")[stat].transform(
            lambda x: x.shift(1).ewm(span=5, adjust=False).mean()
        )

    for stat in ["pts", "reb", "ast"]:
        df[f"{stat}_std_L10"] = calc_df.groupby("player_name")[stat].transform(
            lambda x: x.shift(1).rolling(10, min_periods=5).std()
        )

    return df


# ── Season average ────────────────────────────────────────────────────────────

def _get_season_avg(history_df: pd.DataFrame, stat: str, ref_date) -> float:
    """
    Current-season average for the player up to (but not including) ref_date.
    Season = calendar year of ref_date (games Oct–Jun straddle two years;
    approximate using the calendar year of the ref_date's season start).
    """
    _defaults = {"pts": 15.0, "reb": 5.0, "ast": 4.0}
    ref = pd.to_datetime(ref_date)

    # Determine the season start year (NBA season starts in October)
    season_start_year = ref.year if ref.month >= 10 else ref.year - 1
    season_start = pd.Timestamp(f"{season_start_year}-10-01")

    season_rows = history_df[
        (history_df["date"] >= season_start) & (history_df["date"] < ref)
    ]
    if season_rows.empty or stat not in season_rows.columns:
        return _defaults.get(stat, 10.0)

    vals = pd.to_numeric(season_rows[stat], errors="coerce").dropna()
    if vals.empty:
        return _defaults.get(stat, 10.0)
    return float(vals.mean())


# ── Opponent defensive averages ───────────────────────────────────────────────

def _get_opponent_stat_allowed(
    opponent: str,
    as_of_date,
    stat: str,
) -> float | None:
    """
    Rolling 10-game average of total {stat} allowed by the opponent team.

    Queries PlayerStats where the player was NOT on the opponent team
    (i.e. the opposing players' stats = what the opponent allowed).
    """
    if not opponent:
        return None

    stat_field = {"pts": "pts", "reb": "reb", "ast": "ast"}.get(stat)
    if not stat_field:
        return None

    qs = (
        PlayerStats.objects.filter(period=0)
        .select_related("game", "team", "game__home_team", "game__away_team")
        .filter(
            Q(game__home_team__abbreviation__iexact=opponent)
            | Q(game__away_team__abbreviation__iexact=opponent)
        )
    )

    rows = []
    for row in qs:
        game = row.game
        if not game or not row.team:
            continue
        # Skip rows from the opponent's own players; keep the attacking team's players
        if row.team.abbreviation.upper() == opponent.upper():
            continue
        rows.append({
            "game_id": game.game_id,
            "date":    game.date,
            "stat":    getattr(row, stat_field),
        })

    if not rows:
        return None

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])

    if isinstance(as_of_date, date):
        as_of = pd.to_datetime(as_of_date)
        df = df[df["date"] < as_of]

    if df.empty:
        return None

    per_game = (
        df.groupby(["game_id", "date"])["stat"]
        .sum()
        .reset_index()
        .sort_values("date")
    )
    per_game["rolling"] = (
        per_game["stat"].shift(1).rolling(10, min_periods=1).mean()
    )

    latest = per_game.iloc[-1]["rolling"]
    return float(latest) if not pd.isna(latest) else None


def _get_league_avg_allowed(as_of_date=None, stat: str = "pts") -> float:
    """League-wide average per game for the given stat (fallback)."""
    defaults = {"pts": 112.0, "reb": 44.0, "ast": 26.0}
    stat_field = {"pts": "pts", "reb": "reb", "ast": "ast"}.get(stat, "pts")

    try:
        qs = (
            PlayerStats.objects.filter(period=0)
            .select_related("game")
            .values("game__game_id", "game__date", stat_field)
        )
        rows = list(qs)
        if not rows:
            return defaults[stat]

        df = pd.DataFrame(rows)
        df.columns = ["game_id", "date", "val"]
        df["date"] = pd.to_datetime(df["date"])

        if as_of_date is not None:
            df = df[df["date"] < pd.to_datetime(as_of_date)]

        if df.empty:
            return defaults[stat]

        per_game = df.groupby("game_id")["val"].sum()
        avg = float(per_game.mean())
        return avg if not np.isnan(avg) else defaults[stat]

    except Exception:
        return defaults[stat]
