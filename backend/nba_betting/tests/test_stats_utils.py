"""utils/stats.py — predictability score and tier boundaries."""

from django.test import SimpleTestCase

from nba_betting.utils.stats import pred_score_tier


class PredScoreTierTests(SimpleTestCase):
    def test_fewer_than_five_games_returns_none(self):
        self.assertEqual(pred_score_tier([20, 21, 19, 22], [1, -1, 0, 1], 0.6),
                         (None, None))

    def test_hand_computed_score(self):
        """actuals mean 20, population var 8; errors mean 0, var 2.

        r2   = 1 - 2/8 = 0.75            -> 37.5 pts
        cv   = sqrt(8)/20 = 0.141421...  -> cv_s = 0.858579 -> 25.757 pts
        hr_s = (0.7 - 0.524)/0.476       -> 0.369748 -> 7.395 pts
        score = 70.652... -> 70.7, tier High
        """
        actuals = [20, 22, 18, 24, 16]
        errors = [1, -1, 2, -2, 0]
        score, tier = pred_score_tier(actuals, errors, 0.7)
        self.assertEqual(score, 70.7)
        self.assertEqual(tier, "High")

    def test_high_tier_boundary_at_65_is_inclusive(self):
        """Constructed to score exactly 65.0:
        constant errors -> var_e = 0 -> r2 = 1 (50 pts);
        actuals mean 20, var 100 -> cv 0.5 -> cv_s 0.5 (15 pts);
        hit_rate 0.524 -> hr_s 0 (0 pts)."""
        actuals = [35, 5, 25, 15, 20]
        errors = [2, 2, 2, 2, 2]
        score, tier = pred_score_tier(actuals, errors, 0.524)
        self.assertEqual(score, 65.0)
        self.assertEqual(tier, "High")

    def test_moderate_tier_boundary_at_40_is_inclusive(self):
        """Same actuals (cv_s 0.5 -> 15 pts); errors var 50 with var_a 100
        -> r2 0.5 (25 pts); hit_rate at break-even (0 pts) -> exactly 40.0."""
        actuals = [35, 5, 25, 15, 20]
        errors = [10, -10, 5, -5, 0]
        score, tier = pred_score_tier(actuals, errors, 0.524)
        self.assertEqual(score, 40.0)
        self.assertEqual(tier, "Moderate")

    def test_low_tier_below_40(self):
        """Errors as variable as the actuals (r2 floored at 0), hit rate at
        break-even: only the inverse-CV component contributes.

        actuals mean 20, var 80 -> cv 0.4472 -> cv_s 0.5528 -> 16.6 pts."""
        actuals = [10, 30, 10, 30, 20]
        errors = [20, -20, 10, -10, 0]
        score, tier = pred_score_tier(actuals, errors, 0.5)
        self.assertEqual(score, 16.6)
        self.assertEqual(tier, "Low")

    def test_hit_rate_component_is_capped_at_one(self):
        """A perfect hit rate cannot push its component above 20 points."""
        actuals = [35, 5, 25, 15, 20]     # r2 = 1, cv_s = 0.5 -> 65 base
        errors = [2, 2, 2, 2, 2]
        score, tier = pred_score_tier(actuals, errors, 1.0)
        self.assertEqual(score, 85.0)     # 50 + 15 + 20
        self.assertEqual(tier, "High")
