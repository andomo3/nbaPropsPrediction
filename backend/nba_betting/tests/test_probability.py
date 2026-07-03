"""calculate_probability — the single source of truth for prob_over."""

import math

from django.test import SimpleTestCase
from scipy.stats import norm, poisson

from nba_betting.constants import PROB_CLAMP, STD_DEFAULTS, STD_FLOOR
from nba_betting.services.probability import calculate_probability


class NormalBranchTests(SimpleTestCase):
    def test_monotonic_in_projection(self):
        line, std = 20.0, 5.0
        probs = [calculate_probability("pts", proj, line, std)
                 for proj in (14.0, 18.0, 20.0, 24.0, 30.0)]
        for lo, hi in zip(probs, probs[1:]):
            self.assertLess(lo, hi)

    def test_symmetric_at_the_line(self):
        """projection == line -> exactly 0.5 (inside the clamp, untouched)."""
        self.assertAlmostEqual(
            calculate_probability("pts", 20.0, 20.0, 5.0), 0.5, places=9
        )

    def test_none_std_falls_back_to_stat_default(self):
        expected = calculate_probability("pts", 25.0, 20.0, STD_DEFAULTS["pts"])
        self.assertAlmostEqual(
            calculate_probability("pts", 25.0, 20.0, None), expected, places=9
        )

    def test_nan_std_falls_back_to_stat_default(self):
        expected = calculate_probability("reb", 8.0, 6.5, STD_DEFAULTS["reb"])
        self.assertAlmostEqual(
            calculate_probability("reb", 8.0, 6.5, float("nan")), expected, places=9
        )

    def test_tiny_std_is_floored(self):
        """A near-zero rolling std must be lifted to STD_FLOOR, not divide
        the z-score into a near-certain probability."""
        got = calculate_probability("pts", 21.0, 20.0, 1e-6)
        expected = float(1.0 - norm.cdf((20.0 - 21.0) / STD_FLOOR))
        self.assertAlmostEqual(got, expected, places=9)


class PoissonBranchTests(SimpleTestCase):
    def test_ast_uses_poisson_against_scipy(self):
        mu, line = 6.0, 5.5
        expected = float(1.0 - poisson.cdf(math.floor(line), mu))
        self.assertAlmostEqual(
            calculate_probability("ast", mu, line), expected, places=9
        )

    def test_std_dev_is_ignored_for_poisson_stats(self):
        self.assertAlmostEqual(
            calculate_probability("ast", 6.0, 5.5, std_dev=100.0),
            calculate_probability("ast", 6.0, 5.5, std_dev=None),
            places=12,
        )

    def test_negative_projection_clamps_mu_at_zero(self):
        # mu = 0 -> P(X > 4) = 0 -> clamped to the lower bound
        self.assertEqual(
            calculate_probability("ast", -3.0, 4.5), PROB_CLAMP[0]
        )


class ClampTests(SimpleTestCase):
    def test_extreme_over_is_clamped_high(self):
        self.assertEqual(
            calculate_probability("pts", 60.0, 10.0, 1.0), PROB_CLAMP[1]
        )

    def test_extreme_under_is_clamped_low(self):
        self.assertEqual(
            calculate_probability("pts", 10.0, 60.0, 1.0), PROB_CLAMP[0]
        )
