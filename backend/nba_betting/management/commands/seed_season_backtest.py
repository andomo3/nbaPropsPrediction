"""
management/commands/seed_season_backtest.py

Pre-seeds BacktestRun / BacktestResult rows for the Season Report Card
feature by running backtests for the SEASON_REPORT_PLAYERS roster
(constants.py) × 3 stats × all comparison models over a full NBA season.

Runs once (or whenever --force is passed to refresh stale data). Results
are cached in the DB so the Season Report Card API endpoint is instant.

Usage:
    # Seed 2023-24 season (default)
    python manage.py seed_season_backtest

    # Seed a different season
    python manage.py seed_season_backtest --season 2024

    # Log what would run without touching the DB
    python manage.py seed_season_backtest --dry-run

    # Re-run even if a cached result already exists
    python manage.py seed_season_backtest --force
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from nba_betting.constants import (
    BACKTEST_MODELS,
    DEFAULT_SEASON,
    SEASON_DATES,
    SEASON_REPORT_PLAYERS,
)
from nba_betting.models import BacktestRun
from nba_betting.services.backtest import run_backtest

STATS = ["pts", "reb", "ast"]


class Command(BaseCommand):
    help = (
        "Seed season backtest results for the SEASON_REPORT_PLAYERS roster "
        "to power the Season Report Card feature."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--season",
            type=int,
            default=DEFAULT_SEASON,
            help=(
                "NBA season end-year to seed (e.g. 2024 = 2023-24 season). "
                f"Default: {DEFAULT_SEASON}"
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be seeded without running any backtests.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing cached runs and re-seed from scratch.",
        )

    def handle(self, *args, **options):
        season_year = options["season"]
        dry_run = options["dry_run"]
        force = options["force"]

        if season_year not in SEASON_DATES:
            self.stderr.write(
                f"Unknown season year {season_year}. "
                f"Supported: {sorted(SEASON_DATES.keys())}"
            )
            return

        date_from, date_to = SEASON_DATES[season_year]
        season_label = f"{season_year - 1}-{season_year % 100:02d}"

        self.stdout.write(
            f"Seeding Season Report Card — {season_label} "
            f"({date_from} → {date_to})"
            + (" [DRY RUN]" if dry_run else "")
            + (" [FORCE]" if force else "")
        )
        total_jobs = len(SEASON_REPORT_PLAYERS) * len(STATS) * len(BACKTEST_MODELS)
        self.stdout.write(
            f"  Players: {len(SEASON_REPORT_PLAYERS)}  "
            f"Stats: {STATS}  "
            f"Models: {BACKTEST_MODELS}  "
            f"Total jobs: {total_jobs}"
        )

        done = 0
        skipped = 0
        failed = 0

        for player_name in SEASON_REPORT_PLAYERS:
            for stat in STATS:
                for model in BACKTEST_MODELS:
                    label = f"{player_name} / {stat.upper()} / {model}"

                    # ── Force: delete cached run for this combo ───────────────
                    if force and not dry_run:
                        deleted, _ = BacktestRun.objects.filter(
                            player_name=player_name,
                            stat=stat,
                            model=model,
                            date_from=date_from,
                            date_to=date_to,
                        ).delete()
                        if deleted:
                            self.stdout.write(f"  [CLEAR] {label} — removed {deleted} cached run(s)")

                    # ── Skip if already cached ────────────────────────────────
                    if not force:
                        exists = BacktestRun.objects.filter(
                            player_name=player_name,
                            stat=stat,
                            model=model,
                            date_from=date_from,
                            date_to=date_to,
                            total_bets__gt=0,
                        ).exists()
                        if exists:
                            self.stdout.write(f"  [SKIP]  {label} — already cached")
                            skipped += 1
                            continue

                    if dry_run:
                        self.stdout.write(f"  [DRY]   {label} — would run backtest")
                        done += 1
                        continue

                    # ── Run backtest ──────────────────────────────────────────
                    try:
                        result = run_backtest(player_name, stat, date_from, date_to, model=model)
                        agg = result["aggregate"]
                        self.stdout.write(
                            f"  [OK]    {label} — "
                            f"{agg['total_bets']} games, "
                            f"acc={agg['accuracy']:.1%}, "
                            f"roi={agg['roi']:+.1f}%"
                        )
                        done += 1
                    except ValueError as exc:
                        self.stdout.write(
                            self.style.WARNING(f"  [WARN]  {label} — {exc}")
                        )
                        failed += 1
                    except Exception as exc:
                        self.stderr.write(
                            f"  [ERROR] {label} — {exc}"
                        )
                        failed += 1

        # ── Summary ───────────────────────────────────────────────────────────
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone: {done} seeded, {skipped} already cached, {failed} failed"
            )
        )
