"""Train/serve feature parity.

Training features come from the CSV pipeline
(``ml.train_regression.build_player_features``); serving features come from
the DB pipeline (``services.features._add_rolling_features``). The system's
claim is that the shared rolling features are computed identically. Feed the
same game sequence — including a sub-10-minute game and a boundary
exactly-10-minute game — through both builders and require agreement to 1e-6.
"""

import numpy as np
import pandas as pd
from django.test import SimpleTestCase

from nba_betting.ml.train_regression import build_player_features
from nba_betting.services.features import _add_rolling_features, _num_or

from .synthetic import game_dates, load_synthetic, player_game

# One shared game sequence. Index 6 is a 5-minute game (masked in rolling
# windows); index 8 is exactly 10 minutes (boundary: included by both sides).
PTS = [12, 25, 8, 30, 22, 40, 55, 18, 27, 10, 33, 21, 16, 29]
REB = [5, 8, 4, 10, 7, 12, 2, 6, 9, 3, 11, 7, 5, 8]
AST = [3, 7, 2, 9, 5, 11, 1, 4, 8, 2, 10, 6, 3, 7]
MIN = [30, 32, 28, 35, 31, 33, 5, 30, 10, 29, 36, 30, 31, 34]
FGM = [5, 10, 3, 12, 9, 15, 2, 7, 11, 4, 13, 8, 6, 12]
FGA = 20
LOW_MIN_IDX = 6

SHARED_FEATURES = [
    "pts_L5", "pts_L10", "reb_L5", "reb_L10", "ast_L5", "ast_L10",
    "min_L5", "min_L10", "fg_pct_L5", "fg_pct_L10",
    "pts_ema_L5", "reb_ema_L5", "ast_ema_L5",
    "pts_std_L10", "reb_std_L10", "ast_std_L10",
]


def _training_frame() -> pd.DataFrame:
    rows = [
        player_game(
            "p1", f"G{i}", d,
            points=PTS[i], minutes=float(MIN[i]),
            reb=REB[i], ast=AST[i], fgm=FGM[i], fga=FGA,
        )
        for i, d in enumerate(game_dates(len(PTS)))
    ]
    return build_player_features(load_synthetic(rows))


def _serving_frame() -> pd.DataFrame:
    df = pd.DataFrame({
        "player_name": "Test Player",
        "date": pd.to_datetime(game_dates(len(PTS))),
        "pts": PTS,
        "reb": REB,
        "ast": AST,
        "min": [float(m) for m in MIN],
        "fg_pct": [m / FGA for m in FGM],
    })
    return _add_rolling_features(df)


class FeatureParityTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.train = _training_frame()
        cls.serve = _serving_frame()

    def test_same_number_of_rows(self):
        self.assertEqual(len(self.train), len(PTS))
        self.assertEqual(len(self.serve), len(PTS))

    def test_shared_rolling_features_match_to_1e6(self):
        for col in SHARED_FEATURES:
            np.testing.assert_allclose(
                self.train[col].to_numpy(dtype=float),
                self.serve[col].to_numpy(dtype=float),
                rtol=0.0, atol=1e-6, equal_nan=True,
                err_msg=f"train/serve divergence in {col}",
            )

    def test_parity_holds_around_the_sub_10_minute_game(self):
        """The game after the 5-minute game is the highest-skew-risk row:
        both builders must mask it identically."""
        i = LOW_MIN_IDX + 1
        for col in ("pts_L5", "pts_ema_L5", "min_L5", "fg_pct_L5"):
            self.assertAlmostEqual(
                float(self.train.loc[i, col]),
                float(self.serve.loc[i, col]),
                places=6, msg=col,
            )
        # And both must have actually masked it: an unmasked L5 window
        # (games 2..6) would include the 55-point outlier.
        unmasked = np.mean([PTS[j] for j in range(2, 7)])
        self.assertNotAlmostEqual(float(self.train.loc[i, "pts_L5"]),
                                  float(unmasked), places=6)

    def test_exactly_10_minutes_is_included_by_both(self):
        """Boundary convention: min == 10 counts (>= 10 eligible)."""
        i = 9  # game after the exactly-10-minute game (index 8)
        # window rows 5..8 contribute: row 6 masked; rows 5, 7, 8 count.
        # If either side dropped the 10-minute game, its 27 points vanish.
        expected = np.mean([PTS[5], PTS[7], PTS[8], PTS[4]])  # rows 4,5,7,8
        self.assertAlmostEqual(float(self.train.loc[i, "pts_L5"]),
                               float(expected), places=6)
        self.assertAlmostEqual(float(self.serve.loc[i, "pts_L5"]),
                               float(expected), places=6)


class NumOrTests(SimpleTestCase):
    """_num_or: the NaN-aware fallback that preserves legitimate zeros."""

    def test_nan_falls_back_to_default(self):
        self.assertEqual(_num_or(float("nan"), 5.0), 5.0)

    def test_none_falls_back_to_default(self):
        self.assertEqual(_num_or(None, 3.0), 3.0)

    def test_zero_is_preserved(self):
        self.assertEqual(_num_or(0.0, 5.0), 0.0)

    def test_unparseable_falls_back_and_numbers_pass_through(self):
        self.assertEqual(_num_or("not-a-number", 2.5), 2.5)
        self.assertEqual(_num_or("7.5", 2.5), 7.5)
        self.assertEqual(_num_or(4, 2.5), 4.0)
