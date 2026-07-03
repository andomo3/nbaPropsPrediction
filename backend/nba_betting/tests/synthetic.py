"""Synthetic fixture helpers shared by the test modules.

Builds player-game rows in the raw CSV schema expected by
``nba_betting.ml.train_regression.load_and_filter_csv`` so tests exercise
the real loader (game-type filter, date parsing, minutes parsing, fg_pct
derivation) without touching ``data/raw/*.csv``.
"""

import os
import tempfile

import pandas as pd

from nba_betting.ml.train_regression import load_and_filter_csv


def game_dates(n: int, start: str = "2023-11-01", step_days: int = 2) -> list[str]:
    """n game dates (YYYY-MM-DD strings), step_days apart."""
    ts = pd.date_range(start=start, periods=n, freq=f"{step_days}D")
    return [d.strftime("%Y-%m-%d") for d in ts]


def player_game(
    person_id: str,
    game_id: str,
    date: str,
    points: float,
    minutes: float = 30.0,
    reb: float = 5,
    ast: float = 4,
    fgm: float = 8,
    fga: float = 16,
    home: int = 1,
    opponent: str = "Celtics",
    game_type: str = "Regular Season",
) -> dict:
    """One raw CSV row (PlayerStatistics.csv schema)."""
    return {
        "personId": person_id,
        "gameId": game_id,
        "gameDateTimeEst": f"{date}T19:00:00Z",
        "gameType": game_type,
        "numMinutes": minutes,
        "points": points,
        "reboundsTotal": reb,
        "assists": ast,
        "fieldGoalsMade": fgm,
        "fieldGoalsAttempted": fga,
        "home": home,
        "opponentteamName": opponent,
    }


def load_synthetic(rows: list[dict]) -> pd.DataFrame:
    """Round-trip synthetic rows through the real CSV loader."""
    df = pd.DataFrame(rows)
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "synthetic_player_statistics.csv")
        df.to_csv(path, index=False)
        return load_and_filter_csv(path)
