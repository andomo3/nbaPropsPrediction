from datetime import date

import numpy as np
import pandas as pd
from django.db.models import Q

from nba_betting.models import Player, PlayerStats


def get_model_inputs(player_name, opponent, is_home=True, days_rest=2):
    player = _find_player(player_name)
    if not player:
        return None, "Player not found."

    history_df = _load_player_history(player)
    if history_df.empty:
        return None, "No historical stats found."

    history_df = _add_rolling_features(history_df)
    history_df = history_df[history_df["min"] > 0]
    history_df = history_df.dropna()
    if history_df.empty:
        return None, "Not enough data to build features."

    latest = history_df.iloc[-1]
    opp_def = _get_opponent_pts_allowed(opponent, latest["date"])
    if opp_def is None or np.isnan(opp_def):
        return None, "Not enough opponent history to build features."

    feature_columns = [
        "is_home",
        "days_rest",
        "opp_pts_allowed_L10",
        "pts_L5",
        "pts_L10",
        "pts_ema_L5",
        "pts_std_L10",
        "reb_L5",
        "reb_L10",
        "reb_ema_L5",
        "ast_L5",
        "ast_L10",
        "ast_ema_L5",
        "min_L5",
        "min_L10",
        "fg_pct_L5",
        "fg_pct_L10",
    ]

    feature_row = latest[feature_columns].astype(float).to_frame().T
    feature_row["is_home"] = 1.0 if is_home else 0.0
    feature_row["days_rest"] = float(days_rest)
    feature_row["opp_pts_allowed_L10"] = float(opp_def)

    return player, feature_row


def _find_player(player_name):
    if not player_name:
        return None
    parts = [part for part in str(player_name).split(" ") if part]
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


def _load_player_history(player):
    stats_qs = (
        PlayerStats.objects.filter(player=player, period=0)
        .select_related("game", "team", "game__home_team", "game__away_team")
        .order_by("game__date")
    )

    rows = []
    for row in stats_qs:
        game = row.game
        fg_pct = (row.fgm / row.fga) if row.fga else 0.0
        rows.append(
            {
                "date": game.date,
                "game_id": game.game_id,
                "player_name": f"{player.first_name} {player.last_name}".strip(),
                "player_team": row.team.abbreviation if row.team else None,
                "home_team": game.home_team.abbreviation if game.home_team else None,
                "away_team": game.away_team.abbreviation if game.away_team else None,
                "pts": row.pts,
                "reb": row.reb,
                "ast": row.ast,
                "min": row.min,
                "fg_pct": fg_pct,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["player_name", "date"]).reset_index(drop=True)
    df["is_home"] = (df["player_team"] == df["home_team"]).astype(int)
    df["opponent"] = np.where(df["is_home"] == 1, df["away_team"], df["home_team"])
    df["days_rest"] = df.groupby("player_name")["date"].diff().dt.days
    df["days_rest"] = df["days_rest"].fillna(3)
    return df


def _add_rolling_features(df):
    calc_df = df.copy()
    mask = calc_df["min"] < 10
    calc_df.loc[mask, ["pts", "reb", "ast", "min", "fg_pct"]] = np.nan

    stats = ["pts", "reb", "ast", "min", "fg_pct"]
    windows = [5, 10]

    for stat in stats:
        for window in windows:
            df[f"{stat}_L{window}"] = calc_df.groupby("player_name")[stat].transform(
                lambda x: x.shift(1).rolling(window=window, min_periods=1).mean()
            )

    for stat in ["pts", "reb", "ast"]:
        df[f"{stat}_ema_L5"] = calc_df.groupby("player_name")[stat].transform(
            lambda x: x.shift(1).ewm(span=5, adjust=False).mean()
        )

    df["pts_std_L10"] = calc_df.groupby("player_name")["pts"].transform(
        lambda x: x.shift(1).rolling(window=10, min_periods=5).std()
    )

    return df


def _get_opponent_pts_allowed(opponent, as_of_date):
    if not opponent:
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
        if row.team.abbreviation.upper() == opponent.upper():
            continue
        rows.append(
            {
                "game_id": game.game_id,
                "date": game.date,
                "opponent": opponent.upper(),
                "pts": row.pts,
            }
        )

    if not rows:
        return None

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    if isinstance(as_of_date, date):
        as_of = pd.to_datetime(as_of_date)
        df = df[df["date"] < as_of]

    if df.empty:
        return None

    defense = (
        df.groupby(["opponent", "date", "game_id"])["pts"]
        .sum()
        .reset_index()
        .rename(columns={"pts": "total_pts_allowed"})
        .sort_values(["opponent", "date"])
    )

    defense["opp_pts_allowed_L10"] = defense.groupby("opponent")[
        "total_pts_allowed"
    ].transform(lambda x: x.shift(1).rolling(window=10, min_periods=1).mean())

    latest = defense.iloc[-1]["opp_pts_allowed_L10"]
    if pd.isna(latest):
        return None
    return float(latest)
