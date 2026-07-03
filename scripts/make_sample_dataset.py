"""
Build the self-contained sample dataset for notebooks/methodology_walkthrough.ipynb.

Extracts a two-season slice of data/raw/PlayerStatistics.csv (306 MB) into
data/sample/PlayerStatistics_sample.csv.gz (a few MB) so the walkthrough
notebook runs without the full raw dump.

Extraction rule (documented in data/sample/README.md):
  * game dates 2023-10-01 through 2025-06-30 (the 2023-24 season as a
    warm-up / training runway plus the full 2024-25 season),
  * gameType in {Regular Season, Playoffs, Play-in Tournament} — the same
    VALID_GAME_TYPES filter nba_betting.ml.train_regression applies, so
    pre-filtering here changes nothing downstream,
  * only the columns the training pipeline reads,
  * ALL player-rows for every included game. Filtering happens at the
    game-date level, never the player level: build_opponent_defense() sums
    full team totals per (gameId, opponentteamName), so dropping any player
    row of an included game would corrupt the opponent-defense features.

Usage (from repo root):
    venv/Scripts/python.exe scripts/make_sample_dataset.py
"""

from pathlib import Path
import sys

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from nba_betting.ml.train_regression import VALID_GAME_TYPES  # noqa: E402

RAW_CSV = REPO_ROOT / "data" / "raw" / "PlayerStatistics.csv"
OUT_DIR = REPO_ROOT / "data" / "sample"
OUT_CSV = OUT_DIR / "PlayerStatistics_sample.csv.gz"

DATE_FROM = pd.Timestamp("2023-10-01")
DATE_TO = pd.Timestamp("2025-06-30")

# Exactly the columns load_and_filter_csv / build_player_features /
# build_opponent_defense consume (fieldGoalsPercentage is derived, not needed).
COLUMNS = [
    "personId", "firstName", "lastName",
    "gameId", "gameDateTimeEst", "gameType",
    "numMinutes",
    "points", "reboundsTotal", "assists",
    "fieldGoalsMade", "fieldGoalsAttempted",
    "home", "opponentteamName",
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    chunks = []
    reader = pd.read_csv(RAW_CSV, usecols=COLUMNS, chunksize=500_000, low_memory=False)
    for chunk in reader:
        # Same date parsing as load_and_filter_csv
        dates = (
            pd.to_datetime(chunk["gameDateTimeEst"], utc=True, errors="coerce")
            .dt.tz_localize(None)
            .dt.normalize()
        )
        mask = (
            dates.between(DATE_FROM, DATE_TO)
            & chunk["gameType"].isin(VALID_GAME_TYPES)
        )
        kept = chunk.loc[mask].copy()
        if not kept.empty:
            kept["_date"] = dates[mask]
            chunks.append(kept)

    df = pd.concat(chunks, ignore_index=True)
    df = df.sort_values(["_date", "gameId"]).drop(columns="_date").reset_index(drop=True)

    # Sanity: every game keeps all of its player rows (we filtered by game
    # date, which is constant within a game — assert nothing looks truncated).
    rows_per_game = df.groupby("gameId").size()
    assert rows_per_game.min() >= 10, "A game lost player rows — check the filter."

    df.to_csv(OUT_CSV, index=False, compression="gzip")

    size_mb = OUT_CSV.stat().st_size / 1e6
    print(f"Rows:    {len(df):,}")
    print(f"Games:   {df['gameId'].nunique():,}")
    print(f"Players: {df['personId'].nunique():,}")
    print(f"Dates:   {df['gameDateTimeEst'].min()} .. {df['gameDateTimeEst'].max()}")
    print(f"Output:  {OUT_CSV}  ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
