"""
nba_betting/constants.py

Shared configuration for the Season Report Card feature.
Imported by both the seed management command and the season-summary API view.
"""

from datetime import date

# ── Season Report Card seed players ──────────────────────────────────────────

SEASON_REPORT_PLAYERS = [
    "Nikola Jokic",
    "Shai Gilgeous-Alexander",
    "Anthony Edwards",
    "Jayson Tatum",
    "LeBron James",
    "Stephen Curry",
    "Giannis Antetokounmpo",
    "Luka Doncic",
    "Tyrese Haliburton",
    "Joel Embiid",
]

# ── Season date ranges (keyed by end-year, e.g. 2024 = "2023-24") ────────────

SEASON_DATES: dict[int, tuple[date, date]] = {
    2023: (date(2022, 10, 18), date(2023, 6, 12)),
    2024: (date(2023, 10, 24), date(2024, 6, 17)),
    2025: (date(2024, 10, 22), date(2025, 6, 22)),
    2026: (date(2025, 10, 22), date(2026, 6, 20)),
}

DEFAULT_SEASON = 2026

# ── Backtest model comparison set ─────────────────────────────────────────────

BACKTEST_MODELS = ["xgb", "rf", "lr", "naive"]

MODEL_LABELS = {
    "xgb":   "XGBoost",
    "rf":    "Random Forest",
    "lr":    "Linear Reg.",
    "naive": "Naive (Season Avg)",
}
