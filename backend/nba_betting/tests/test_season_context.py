from datetime import date

from django.test import SimpleTestCase

from nba_betting.constants import season_context, season_label


class SeasonLabelTests(SimpleTestCase):
    def test_end_year_becomes_hyphenated_label(self):
        self.assertEqual(season_label(2026), "2025-26")
        self.assertEqual(season_label(2023), "2022-23")


class SeasonContextTests(SimpleTestCase):
    def test_mid_season_day_is_in_season(self):
        ctx = season_context(date(2026, 1, 15))
        self.assertEqual(ctx["status"], "in_season")
        self.assertEqual(ctx["label"], "2025-26")
        self.assertIsNone(ctx["next_start"])

    def test_season_boundaries_are_inclusive(self):
        self.assertEqual(season_context(date(2025, 10, 22))["status"], "in_season")
        self.assertEqual(season_context(date(2026, 6, 20))["status"], "in_season")

    def test_gap_between_seasons_reports_the_next_start(self):
        ctx = season_context(date(2025, 8, 1))
        self.assertEqual(ctx["status"], "off_season")
        self.assertIsNone(ctx["label"])
        self.assertEqual(ctx["next_start"], "2025-10-22")
        self.assertEqual(ctx["last_completed"], "2024-25")

    def test_after_the_last_modelled_season_has_no_next_start(self):
        # No 2026-27 entry exists in SEASON_DATES, so the calendar must say it
        # does not know rather than inventing a tip-off date.
        ctx = season_context(date(2026, 8, 1))
        self.assertEqual(ctx["status"], "off_season")
        self.assertIsNone(ctx["next_start"])
        self.assertEqual(ctx["last_completed"], "2025-26")

    def test_before_every_modelled_season_has_no_completed_season(self):
        ctx = season_context(date(2020, 1, 1))
        self.assertEqual(ctx["status"], "off_season")
        self.assertEqual(ctx["next_start"], "2022-10-18")
        self.assertIsNone(ctx["last_completed"])
