"""
nba_betting/constants.py

Shared configuration for the Season Report Card feature.
Imported by both the seed management command and the season-summary API view.
"""

from datetime import date

# ── Season Report Card seed players ──────────────────────────────────────────

SEASON_REPORT_PLAYERS = [
    # Kept — full/near-full 2025-26 seasons
    "Nikola Jokic",
    "Shai Gilgeous-Alexander",
    "Anthony Edwards",
    "LeBron James",
    "Luka Doncic",
    # Replacing injury-shortened players
    "De'Aaron Fox",
    "Jalen Brunson",
    "Karl-Anthony Towns",
    "Donovan Mitchell",
    "Victor Wembanyama",
    # Expansion — 70+ games, high consistency
    "Tyrese Maxey",
    "Jamal Murray",
    "Evan Mobley",
    "Jaylen Brown",
    "Kevin Durant",
    "Paolo Banchero",
    "Cade Cunningham",
    "Devin Booker",
]

# ── Season date ranges (keyed by end-year, e.g. 2024 = "2023-24") ────────────

SEASON_DATES: dict[int, tuple[date, date]] = {
    2023: (date(2022, 10, 18), date(2023, 6, 12)),
    2024: (date(2023, 10, 24), date(2024, 6, 17)),
    2025: (date(2024, 10, 22), date(2025, 6, 22)),
    2026: (date(2025, 10, 22), date(2026, 6, 20)),
}

DEFAULT_SEASON = 2026

# ── Shared serving fallbacks ──────────────────────────────────────────────────
# Single source of truth for probability derivation. services/features.py,
# services/probability.py, views.py, and generate_daily_picks.py must all use
# these — the audit found three divergent copies.

STD_DEFAULTS = {"pts": 5.0, "reb": 2.0, "ast": 1.5}   # fallback rolling stds
STD_FLOOR = 0.5                                        # guard against ~0 stds
PROB_CLAMP = (0.01, 0.99)   # reported probabilities never claim near-certainty

# ── Backtest model comparison set ─────────────────────────────────────────────

BACKTEST_MODELS = ["xgb", "rf", "lr", "naive"]

MODEL_LABELS = {
    "xgb":   "XGBoost",
    "rf":    "Random Forest",
    "lr":    "Linear Reg.",
    "naive": "Naive (Season Avg)",
}
