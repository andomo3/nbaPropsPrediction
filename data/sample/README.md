# Sample dataset

`PlayerStatistics_sample.csv.gz` — a self-contained slice of the full NBA
box-score history, checked in so `notebooks/methodology_walkthrough.ipynb`
runs end-to-end without the 300+ MB raw dump, a database, or any API keys.

## Provenance

Extracted from `data/raw/PlayerStatistics.csv` (NBA API historical player
box scores; not tracked in git) by `scripts/make_sample_dataset.py`.

## Extraction rule

- **Game dates 2023-10-01 → 2025-06-30**: the 2023-24 season serves as a
  warm-up/training runway, and 2024-25 is a complete season for evaluation.
- **Game types**: Regular Season, Playoffs, Play-in Tournament — the same
  `VALID_GAME_TYPES` filter `nba_betting.ml.train_regression` applies, so
  pre-filtering changes nothing downstream.
- **Columns**: only the 14 columns the training pipeline reads.
- **All player-rows for every included game.** Filtering is done at the
  game-date level, never the player level: opponent-defense features sum
  full team totals per `(gameId, opponentteamName)`, so dropping individual
  player rows would corrupt them.

## Contents

~68k player-game rows, ~2.6k games, ~700 players (2023-10-24 → 2025-06-22).
Pandas reads the `.gz` directly: `pd.read_csv("PlayerStatistics_sample.csv.gz")`.

To regenerate (requires the raw CSV):

```bash
venv/Scripts/python.exe scripts/make_sample_dataset.py
```
