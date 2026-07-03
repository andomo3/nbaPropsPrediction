"""Leakage regression tests — the publication-protecting suite.

The repo's core methodological claim is that every feature a model sees for
game *t* is built exclusively from games strictly before *t* (``shift(1)``
discipline), and that evaluation splits are strictly chronological.

These tests poison a single synthetic game's box score and assert that the
poison CANNOT reach that game's own features, while it MUST reach the next
game's — i.e. the information genuinely flows, just one game late.
"""

import numpy as np
import pandas as pd
from django.test import SimpleTestCase

from nba_betting.ml.train_regression import (
    MIN_MINUTES,
    build_opponent_defense,
    build_player_features,
    eligible_rows,
    time_split,
    walk_forward_splits,
)

from .synthetic import game_dates, load_synthetic, player_game

# Rolling features of game t that must be blind to game t's own box score.
OWN_GAME_FEATURES = ["pts_L5", "pts_ema_L5", "pts_std_L10", "season_avg_pts"]


def _player_pipeline(points, minutes=None):
    """Synthetic single-player season -> loader -> build_player_features."""
    n = len(points)
    minutes = minutes or [30.0] * n
    rows = [
        player_game("p1", f"G{i}", d, pts, minutes=m)
        for i, (d, pts, m) in enumerate(zip(game_dates(n), points, minutes))
    ]
    return build_player_features(load_synthetic(rows))


class PoisonTests(SimpleTestCase):
    """Poison game t's target; its own features must not move."""

    POINTS = [10, 20, 14, 18, 22, 16, 12, 24, 20, 18, 15, 21]
    T = 6  # poisoned game index (enough history for std_L10's min_periods=5)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base = _player_pipeline(cls.POINTS)
        poisoned_points = list(cls.POINTS)
        poisoned_points[cls.T] = 300  # extreme outlier
        cls.poisoned = _player_pipeline(poisoned_points)

    def test_own_game_features_unaffected_by_own_target(self):
        """shift(1): game t's rolling features must ignore game t's value."""
        for col in OWN_GAME_FEATURES:
            self.assertAlmostEqual(
                float(self.base.loc[self.T, col]),
                float(self.poisoned.loc[self.T, col]),
                places=9,
                msg=f"{col} at row t leaked the poisoned target of game t",
            )

    def test_next_game_features_do_see_the_poisoned_game(self):
        """Sanity check the poison flows: game t+1's features must move."""
        for col in OWN_GAME_FEATURES:
            self.assertNotAlmostEqual(
                float(self.base.loc[self.T + 1, col]),
                float(self.poisoned.loc[self.T + 1, col]),
                places=6,
                msg=f"{col} at row t+1 did not react — the fixture is inert",
            )


class OpponentDefenseTests(SimpleTestCase):
    """A game's own totals must not appear in its opp_*_allowed_L10."""

    @staticmethod
    def _frame(poison_game_index=None):
        """5 games where 'Celtics' defend; two attacking rows per game.

        Baseline per-game totals allowed: 30, 40, 50, 60, 60.
        Poisoning adds +50 to each attacker (=+100 to the game total).
        """
        scores = [(10, 20), (15, 25), (20, 30), (25, 35), (30, 30)]
        rows = []
        for i, pair in enumerate(scores):
            d = pd.Timestamp("2023-11-01") + pd.Timedelta(days=2 * i)
            for pts in pair:
                if i == poison_game_index:
                    pts += 50
                rows.append({
                    "gameId": f"G{i}",
                    "opponentteamName": "Celtics",
                    "date": d,
                    "points": pts,
                    "reboundsTotal": 5,
                    "assists": 4,
                })
        return pd.DataFrame(rows)

    def test_rolling_allowed_excludes_current_game(self):
        out = build_opponent_defense(self._frame())
        # First defended game: no history yet -> NaN, never the game's own 30.
        self.assertTrue(out.loc[out["gameId"] == "G0", "opp_pts_allowed_L10"]
                        .isna().all())
        # G3's value = mean of G0..G2 totals (30, 40, 50) = 40; its own
        # 60-point total must be excluded.
        g3 = out.loc[out["gameId"] == "G3", "opp_pts_allowed_L10"]
        self.assertTrue(np.allclose(g3.to_numpy(), 40.0))

    def test_poisoned_game_totals_only_reach_later_games(self):
        base = build_opponent_defense(self._frame())
        pois = build_opponent_defense(self._frame(poison_game_index=2))
        # G2's own opp feature is untouched by G2's poisoned total ...
        for gid in ("G0", "G1", "G2"):
            b = base.loc[base["gameId"] == gid, "opp_pts_allowed_L10"].to_numpy()
            p = pois.loc[pois["gameId"] == gid, "opp_pts_allowed_L10"].to_numpy()
            np.testing.assert_allclose(b, p, equal_nan=True)
        # ... but the next defended game (G3) must see it:
        # baseline mean(30,40,50)=40 vs poisoned mean(30,40,150)=73.33.
        g3 = pois.loc[pois["gameId"] == "G3", "opp_pts_allowed_L10"].to_numpy()
        np.testing.assert_allclose(g3, 220.0 / 3.0)


class SplitTests(SimpleTestCase):
    def test_time_split_is_strictly_chronological(self):
        df = pd.DataFrame({
            "date": pd.date_range("2020-01-01", periods=50, freq="D"),
            "v": range(50),
        })
        train, test = time_split(df, test_frac=0.20)
        self.assertEqual(len(train) + len(test), 50)
        self.assertEqual(len(train), 40)
        self.assertLess(train["date"].max(), test["date"].min())

    def test_walk_forward_folds_train_strictly_before_test_season(self):
        # Two games per NBA season: a November game and the following
        # January game (same season, later calendar year).
        dates = []
        for season in range(2016, 2025):
            dates.append(f"{season}-11-15")
            dates.append(f"{season + 1}-01-15")
        df = pd.DataFrame({"date": pd.to_datetime(dates), "v": range(len(dates))})

        folds = list(walk_forward_splits(df))
        self.assertEqual([ty for _, _, ty in folds], [2021, 2022, 2023, 2024])

        for train, test, test_year in folds:
            self.assertLess(int(train["year"].max()), test_year)
            self.assertEqual(set(test["year"].unique()), {test_year})
            self.assertLess(train["date"].max(), test["date"].min())

        # Season-start-year convention: the Jan 2022 game belongs to the
        # 2021-22 season, so it must sit in the 2021 TEST fold, not 2022 train.
        _, test_2021, _ = folds[0]
        self.assertIn(pd.Timestamp("2022-01-15"), set(test_2021["date"]))


class SubTenMinuteMaskingTests(SimpleTestCase):
    """5-minute games occupy a rolling-window slot but contribute no value;
    season averages (by documented convention) still include them; and they
    are never used as training targets."""

    POINTS_A = [10, 20, 10, 20, 15, 40, 18]   # game 5: 40 pts in 5 minutes
    POINTS_B = [10, 20, 10, 20, 15, 0, 18]    # same, but the 5-min game scores 0
    MINUTES = [30, 30, 30, 30, 30, 5, 30]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.a = _player_pipeline(cls.POINTS_A, cls.MINUTES)
        cls.b = _player_pipeline(cls.POINTS_B, cls.MINUTES)

    def test_low_minute_game_does_not_move_next_pts_l5(self):
        # Rows 1-5 feed row 6's L5 window; row 5 is masked, so 40 vs 0 points
        # in that game must make no difference.
        self.assertAlmostEqual(
            float(self.a.loc[6, "pts_L5"]), float(self.b.loc[6, "pts_L5"]), places=9
        )
        # mean(20, 10, 20, 15) with the masked slot skipped
        self.assertAlmostEqual(float(self.a.loc[6, "pts_L5"]), 16.25, places=9)
        # and NOT the unmasked mean(20, 10, 20, 15, 40) = 21
        self.assertNotAlmostEqual(float(self.a.loc[6, "pts_L5"]), 21.0, places=6)

    def test_low_minute_game_does_move_season_average(self):
        # Documented convention: season_avg_* uses raw, unmasked values.
        self.assertAlmostEqual(
            float(self.a.loc[6, "season_avg_pts"]), 115.0 / 6.0, places=9
        )
        self.assertNotAlmostEqual(
            float(self.a.loc[6, "season_avg_pts"]),
            float(self.b.loc[6, "season_avg_pts"]),
            places=6,
        )

    def test_low_minute_game_excluded_as_training_target(self):
        elig = eligible_rows(self.a)
        self.assertEqual(len(elig), len(self.a) - 1)
        self.assertTrue((elig["numMinutes"] >= MIN_MINUTES).all())
        self.assertNotIn(5.0, elig["numMinutes"].tolist())
