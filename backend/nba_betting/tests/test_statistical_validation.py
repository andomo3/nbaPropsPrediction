"""Statistical validation service — helpers and end-to-end against the ORM.

The end-to-end tests seed synthetic BacktestRun/BacktestResult rows (no
model files, no real backtests) and check the reported p-values against
hand-computed scipy quantities.
"""

import math
from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from scipy.stats import binom

from nba_betting.constants import SEASON_DATES
from nba_betting.models import BacktestResult, BacktestRun
from nba_betting.services.statistical_validation import (
    BREAK_EVEN,
    DISCLOSURES,
    _overall_verdict,
    _sample_warnings,
    compute_statistical_validation,
)

SEASON = 2026


def _assert_no_nan(testcase, obj, path="payload"):
    """Recursively assert no float NaN anywhere in a JSON-ready payload."""
    if isinstance(obj, float):
        testcase.assertFalse(math.isnan(obj), f"NaN at {path}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _assert_no_nan(testcase, v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _assert_no_nan(testcase, v, f"{path}[{i}]")


def _seed_run(player_name, stat, records, season=SEASON):
    """Create a BacktestRun + per-game results matching the model='xgb'
    season-window signature that compute_statistical_validation queries."""
    date_from, date_to = SEASON_DATES[season]
    wins = sum(1 for r in records if r["correct"])
    run = BacktestRun.objects.create(
        player_name=player_name,
        stat=stat,
        model="xgb",
        date_from=date_from,
        date_to=date_to,
        total_bets=len(records),
        wins=wins,
        accuracy=wins / len(records),
        total_pnl=0.0,
        roi=0.0,
    )
    BacktestResult.objects.bulk_create([
        BacktestResult(
            run=run,
            game_date=date_from + timedelta(days=i),
            opponent="BOS",
            actual=r["projection"] + r["error"],
            line=r["line"],
            prob_over=r["projection"],  # field stores the projection
            predicted_over=r["projection"] > r["line"],
            correct=r["correct"],
            pnl=1.0 if r["correct"] else -1.1,
            error=r["error"],
        )
        for i, r in enumerate(records)
    ])
    return run


class OverallVerdictTests(SimpleTestCase):
    def test_small_sample_is_insufficient_regardless_of_results(self):
        self.assertEqual(
            _overall_verdict(10, True, 0.9, True, 0.5, False, 0.0),
            ("Insufficient data", "slate"),
        )

    def test_three_positives_is_strong(self):
        self.assertEqual(
            _overall_verdict(50, True, 0.60, True, 0.3, False, 0.1),
            ("Strong signal", "green"),
        )

    def test_two_positives_is_moderate(self):
        self.assertEqual(
            _overall_verdict(50, True, 0.60, False, None, False, 0.1),
            ("Moderate signal", "amber"),
        )

    def test_one_positive_is_weak(self):
        # Only the no-material-bias criterion holds.
        self.assertEqual(
            _overall_verdict(50, False, 0.50, False, None, False, 0.1),
            ("Weak signal", "red"),
        )

    def test_zero_positives_is_no_reliable_signal(self):
        self.assertEqual(
            _overall_verdict(50, False, 0.50, False, None, True, 1.0),
            ("No reliable signal", "red"),
        )


class SampleWarningsTests(SimpleTestCase):
    def test_small_n_triggers_all_three_small_sample_warnings(self):
        warnings = _sample_warnings(10, 6, [])
        self.assertEqual(len(warnings), 3)
        self.assertTrue(any("low-confidence" in w for w in warnings))
        self.assertTrue(any("Edge correlation skipped" in w for w in warnings))
        self.assertTrue(any("edge ≥ 2" in w for w in warnings))

    def test_adequate_n_with_few_hits_warns_on_binomial_power(self):
        warnings = _sample_warnings(40, 5, [2.5] * 10)
        self.assertEqual(len(warnings), 1)
        self.assertIn("low power", warnings[0])

    def test_healthy_sample_has_no_warnings(self):
        self.assertEqual(_sample_warnings(40, 25, [2.5] * 6), [])


class ComputeValidationTests(TestCase):
    PLAYER = "Test Player"

    def _mixed_records(self, n=40, hits=26):
        """Alternating +/-0.5 errors (mean 0, t-stat 0 -> no bias), cyclic
        edges including >=5 games with edge >= 2."""
        records = []
        for i in range(n):
            projection = 20.0 + ((i % 5) - 2) * 1.2   # edges 0 / 1.2 / 2.4
            records.append({
                "projection": projection,
                "line": 20.0,
                "error": 0.5 if i % 2 == 0 else -0.5,
                "correct": i < hits,
            })
        return records

    def test_binomial_p_value_matches_hand_computed_scipy(self):
        n, hits = 40, 26
        _seed_run(self.PLAYER, "pts", self._mixed_records(n, hits))
        payload = compute_statistical_validation(self.PLAYER, "pts", SEASON)

        # One-sided binomial: P(X >= hits) under p = BREAK_EVEN.
        expected_p = float(binom.sf(hits - 1, n, BREAK_EVEN))
        self.assertEqual(payload["hit_rate"]["p_value"], round(expected_p, 4))
        self.assertEqual(payload["hit_rate"]["hits"], hits)
        self.assertEqual(payload["hit_rate"]["n"], n)
        self.assertEqual(payload["hit_rate"]["value"], round(hits / n, 4))
        self.assertEqual(payload["n_games"], n)

    def test_zero_mean_errors_report_no_detectable_bias(self):
        _seed_run(self.PLAYER, "pts", self._mixed_records())
        payload = compute_statistical_validation(self.PLAYER, "pts", SEASON)

        cal = payload["calibration"]
        self.assertFalse(cal["significant"])
        self.assertEqual(cal["direction"], "negligible")
        self.assertEqual(cal["label"], "No detectable bias")
        self.assertAlmostEqual(cal["mean_error"], 0.0, places=9)
        self.assertTrue(payload["sample_adequacy"]["adequate"])

    def test_disclosures_ship_with_every_payload(self):
        _seed_run(self.PLAYER, "pts", self._mixed_records())
        payload = compute_statistical_validation(self.PLAYER, "pts", SEASON)
        self.assertEqual(len(payload["disclosures"]), 4)
        self.assertEqual(payload["disclosures"], DISCLOSURES)

    def test_degenerate_all_correct_sample_produces_no_nan(self):
        """Every prediction correct + constant errors: Spearman rho and the
        t-test are undefined — the payload must degrade to None/1.0, never
        NaN."""
        n = 35
        records = [{
            "projection": 20.0 + (i % 7) * 0.5,
            "line": 20.0,
            "error": 0.0,
            "correct": True,
        } for i in range(n)]
        _seed_run(self.PLAYER, "reb", records)
        payload = compute_statistical_validation(self.PLAYER, "reb", SEASON)

        _assert_no_nan(self, payload)
        self.assertIsNone(payload["edge_correlation"]["rho"])
        self.assertIsNone(payload["edge_correlation"]["p_value"])
        self.assertEqual(payload["edge_correlation"]["label"], "Insufficient data")
        self.assertEqual(payload["calibration"]["p_value"], 1.0)
        self.assertEqual(payload["hit_rate"]["hits"], n)

    def test_missing_backtest_raises_value_error(self):
        with self.assertRaises(ValueError):
            compute_statistical_validation("Nobody Nowhere", "pts", SEASON)
