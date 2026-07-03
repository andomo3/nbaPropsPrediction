"""Backtest scoring conventions: push-void and >=10-minute eligibility.

Runs run_backtest() with model='naive' (season-average projection), which
exercises the real scoring loop — line construction, push handling,
minutes eligibility, PnL — without requiring any trained model files.
"""

from datetime import date, timedelta

from django.test import TestCase

from nba_betting.models import Game, Player, PlayerStats, Team
from nba_betting.services.backtest import LOSS_UNIT, WIN_UNIT, run_backtest


class BacktestScoringTests(TestCase):
    """Synthetic 9-game season, Jan 2024 (season 2023-24), all vs BOS.

    Points:  [10, 20, 10, 20, 15, 15, 25, 40, 25]
    Minutes: [30, 30, 30, 30, 30, 30, 30,  5, 30]

    Hand-computed expectations for the scored window (games 6-9):
      game 6: L5 line = mean(10,20,10,20,15) = 15.0 == actual -> PUSH, voided
      game 7: line = mean(20,10,20,15,15) = 16.0; naive projection =
              season avg of games 1-6 = 15.0 -> predicts Under; actual 25
              -> wrong -> pnl -1.1
      game 8: 5 minutes -> ineligible, never scored
      game 9: line = mean(20,15,15,25) = 18.75 (the 5-min 40-pt game is
              masked out of the window); projection = raw season avg of
              games 1-8 = 155/8 = 19.375 -> predicts Over; actual 25
              -> correct -> pnl +1.0
    """

    POINTS = [10, 20, 10, 20, 15, 15, 25, 40, 25]
    MINUTES = [30, 30, 30, 30, 30, 30, 30, 5, 30]
    START = date(2024, 1, 1)  # games every 2 days -> Jan 1..17

    def setUp(self):
        self.lal = Team.objects.create(city="Los Angeles", nickname="Lakers",
                                       abbreviation="LAL")
        self.bos = Team.objects.create(city="Boston", nickname="Celtics",
                                       abbreviation="BOS")

    def _create_player_with_games(self, nba_id, last_name, points, minutes):
        player = Player.objects.create(
            nba_id=nba_id, first_name="Test", last_name=last_name,
            position="G", current_team=self.lal,
        )
        for i, (pts, mins) in enumerate(zip(points, minutes)):
            game = Game.objects.create(
                game_id=f"{nba_id}00{i}",
                date=self.START + timedelta(days=2 * i),
                season="2023-24",
                home_team=self.lal,
                away_team=self.bos,
                home_score=100,
                away_score=98,
            )
            PlayerStats.objects.create(
                player=player, game=game, team=self.lal, period=0,
                pts=pts, reb=5, ast=4, min=float(mins), fga=10, fgm=5,
            )
        return player

    def _game_date(self, i):
        return self.START + timedelta(days=2 * i)

    def test_push_and_low_minute_games_are_voided_not_scored(self):
        self._create_player_with_games(1, "Backtester", self.POINTS, self.MINUTES)
        result = run_backtest(
            "Test Backtester", "pts",
            date_from=self._game_date(5),   # game 6
            date_to=self._game_date(8),     # game 9
            model="naive",
        )

        scored_dates = [r["date"] for r in result["per_game"]]
        # Only games 7 and 9 are scored ...
        self.assertEqual(
            scored_dates,
            [str(self._game_date(6)), str(self._game_date(8))],
        )
        # ... the push (game 6, index 5) and the 5-minute game (game 8,
        # index 7) are voided.
        self.assertNotIn(str(self._game_date(5)), scored_dates)
        self.assertNotIn(str(self._game_date(7)), scored_dates)
        self.assertEqual(result["aggregate"]["total_bets"], 2)

    def test_hand_computed_lines_projections_and_pnl(self):
        self._create_player_with_games(1, "Backtester", self.POINTS, self.MINUTES)
        result = run_backtest(
            "Test Backtester", "pts",
            date_from=self._game_date(5), date_to=self._game_date(8),
            model="naive",
        )
        g7, g9 = result["per_game"]

        # Game 7: predicted Under (proj 15.0 < line 16.0), actual Over -> loss
        self.assertEqual(g7["line"], 16.0)
        self.assertEqual(g7["projection"], 15.0)
        self.assertFalse(g7["predicted_over"])
        self.assertFalse(g7["correct"])
        self.assertEqual(g7["pnl"], LOSS_UNIT)

        # Game 9: the 40-point 5-minute game is masked out of the L5 line
        # (18.75, not the unmasked 23.0) but DOES enter the raw season
        # average the naive projection uses (19.375 -> rounded 19.4).
        self.assertEqual(g9["line"], 18.75)
        self.assertEqual(g9["projection"], 19.4)
        self.assertTrue(g9["predicted_over"])
        self.assertTrue(g9["correct"])
        self.assertEqual(g9["pnl"], WIN_UNIT)

        agg = result["aggregate"]
        self.assertEqual(agg["total_bets"], 2)
        self.assertEqual(agg["wins"], 1)
        self.assertEqual(agg["accuracy"], 0.5)
        self.assertAlmostEqual(agg["total_pnl"], WIN_UNIT + LOSS_UNIT, places=6)

    def test_run_and_results_are_persisted(self):
        from nba_betting.models import BacktestResult, BacktestRun

        self._create_player_with_games(1, "Backtester", self.POINTS, self.MINUTES)
        result = run_backtest(
            "Test Backtester", "pts",
            date_from=self._game_date(5), date_to=self._game_date(8),
            model="naive",
        )
        run = BacktestRun.objects.get(pk=result["run_id"])
        self.assertEqual(run.total_bets, 2)
        self.assertEqual(run.model, "naive")
        self.assertEqual(BacktestResult.objects.filter(run=run).count(), 2)

    def test_all_push_window_raises_rather_than_scoring_voids(self):
        # Constant scorer: every game's actual equals its L5 line exactly,
        # so every bet in the window is a push -> nothing to score.
        self._create_player_with_games(2, "Pusher", [15] * 9, [30] * 9)
        with self.assertRaises(ValueError):
            run_backtest(
                "Test Pusher", "pts",
                date_from=self._game_date(5), date_to=self._game_date(8),
                model="naive",
            )
