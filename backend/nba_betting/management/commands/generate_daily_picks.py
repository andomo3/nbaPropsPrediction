"""
management/commands/generate_daily_picks.py

Generates LITE daily picks for the top-20 NBA players.
Runs every morning via Railway cron (0 14 * * * UTC = ~10 AM ET).

Usage:
    python manage.py generate_daily_picks              # today
    python manage.py generate_daily_picks --date 2026-04-02
    python manage.py generate_daily_picks --dry-run    # log only, no DB writes
"""

from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand

from nba_betting.constants import STD_DEFAULTS
from nba_betting.ml.predictor import ModelPredictor
from nba_betting.models import DailyPick, Game, Player
from nba_betting.services.features import _find_player, get_model_inputs
from nba_betting.services.probability import calculate_probability
from nba_betting.utils.dates import et_today

# ------------------------------------------------------------------
# LITE player list — top 20 by market popularity
# ------------------------------------------------------------------
LITE_PLAYERS = [
    "LeBron James",
    "Stephen Curry",
    "Kevin Durant",
    "Luka Doncic",
    "Jayson Tatum",
    "Joel Embiid",
    "Giannis Antetokounmpo",
    "Nikola Jokic",
    "Shai Gilgeous-Alexander",
    "Anthony Edwards",
    "Devin Booker",
    "Trae Young",
    "Jaylen Brown",
    "Anthony Davis",
    "Damian Lillard",
    "Karl-Anthony Towns",
    "Bam Adebayo",
    "Tyrese Haliburton",
    "Donovan Mitchell",
    "Cade Cunningham",
]

STATS = ["pts", "reb", "ast"]


class Command(BaseCommand):
    help = "Generate LITE daily picks for top-20 players playing today."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            help="ISO date (YYYY-MM-DD) to generate picks for (default: today)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Log picks without writing to the database",
        )

    def handle(self, *args, **options):
        pick_date = (
            date.fromisoformat(options["date"]) if options["date"] else et_today()
        )
        dry_run = options["dry_run"]

        self.stdout.write(
            f"Generating picks for {pick_date}"
            + (" [DRY RUN]" if dry_run else "")
        )

        # Build today's game schedule: team_abbr → (opponent_abbr, is_home)
        schedule = _build_schedule(pick_date)
        if not schedule:
            self.stdout.write(
                self.style.WARNING(
                    f"No games found for {pick_date}. "
                    "Run sync_espn_games first or check the date."
                )
            )
            return

        self.stdout.write(f"  Games found: {len(schedule) // 2} matchups")

        predictor = ModelPredictor()
        generated = 0
        skipped = 0

        for player_name in LITE_PLAYERS:
            player = _find_player(player_name)
            if not player:
                self.stdout.write(f"  [SKIP] {player_name} — not in DB")
                skipped += 1
                continue

            team_abbr = (
                player.current_team.abbreviation if player.current_team else None
            )
            if not team_abbr or team_abbr not in schedule:
                self.stdout.write(f"  [SKIP] {player_name} — not playing today")
                skipped += 1
                continue

            opponent_abbr, is_home = schedule[team_abbr]

            for stat in STATS:
                try:
                    player_obj, feature_row = get_model_inputs(
                        player_name, opponent_abbr, stat, is_home=is_home
                    )
                    if player_obj is None:
                        self.stdout.write(
                            f"  [SKIP] {player_name} {stat} — feature build failed: {feature_row}"
                        )
                        continue

                    projection = predictor.predict_projection(feature_row, stat, "xgb")
                    if projection is None:
                        continue

                    line_col = f"{stat}_L5"
                    if line_col not in feature_row.columns:
                        continue

                    line = float(feature_row[line_col].iloc[0])
                    std_col = f"{stat}_std_L10"
                    std_dev = (
                        float(feature_row[std_col].iloc[0])
                        if std_col in feature_row.columns
                        else STD_DEFAULTS[stat]
                    )
                    prob_over = calculate_probability(
                        stat, float(projection), line, std_dev
                    )
                    edge = "Over" if projection > line else "Under"

                    if not dry_run:
                        DailyPick.objects.update_or_create(
                            pick_date=pick_date,
                            player=player,
                            stat=stat,
                            defaults={
                                "opponent_abbr": opponent_abbr,
                                "is_home": is_home,
                                "line": round(line, 2),
                                "prob_over": round(prob_over, 4),
                                "projection": round(float(projection), 2),
                                "edge": edge,
                                "model_version": "xgb_v1",
                            },
                        )

                    self.stdout.write(
                        f"  [PICK] {player_name} {stat.upper()} "
                        f"{'vs' if not is_home else '@'} {opponent_abbr} — "
                        f"{edge} {line:.1f} (proj={projection:.1f}, "
                        f"prob={prob_over*100:.0f}%)"
                    )
                    generated += 1

                except Exception as exc:
                    self.stderr.write(
                        f"  [ERROR] {player_name} {stat}: {exc}"
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {generated} picks generated, {skipped} players skipped"
            )
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_schedule(pick_date: date) -> dict[str, tuple[str, bool]]:
    """
    Build a lookup dict: team_abbr → (opponent_abbr, is_home)
    from today's Game records. Requires sync_espn_games to have run first.
    """
    games = (
        Game.objects.filter(date=pick_date)
        .select_related("home_team", "away_team")
    )
    schedule: dict[str, tuple[str, bool]] = {}
    for game in games:
        if game.home_team and game.away_team:
            home_abbr = game.home_team.abbreviation
            away_abbr = game.away_team.abbreviation
            schedule[home_abbr] = (away_abbr, True)   # home team plays at home
            schedule[away_abbr] = (home_abbr, False)  # away team plays away
    return schedule
