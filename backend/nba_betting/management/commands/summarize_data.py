from django.core.management.base import BaseCommand
from django.db.models import Count, Max, Min

from nba_betting.models import Game, Player, PlayerStats, Team


class Command(BaseCommand):
    help = "Summarize ingested data coverage for quick sanity checks."

    def handle(self, *args, **options):
        total_teams = Team.objects.count()
        total_players = Player.objects.count()
        total_games = Game.objects.count()
        total_stats = PlayerStats.objects.count()

        games_with_stats = (
            PlayerStats.objects.values("game_id").distinct().count()
        )
        players_with_stats = (
            PlayerStats.objects.values("player_id").distinct().count()
        )

        full_games = (
            PlayerStats.objects.values("game_id")
            .annotate(periods=Count("period", distinct=True))
            .filter(periods=5)
            .count()
        )

        missing_games = max(games_with_stats - full_games, 0)

        date_range = Game.objects.aggregate(
            min_date=Min("date"), max_date=Max("date")
        )

        periods = (
            PlayerStats.objects.values("period")
            .annotate(rows=Count("id"))
            .order_by("period")
        )

        incomplete = (
            PlayerStats.objects.values("game_id")
            .annotate(periods=Count("period", distinct=True))
            .filter(periods__lt=5)
            .order_by("periods")
        )[:10]

        self.stdout.write("=== Data Summary ===")
        self.stdout.write(f"Teams: {total_teams}")
        self.stdout.write(f"Players: {total_players} (with stats: {players_with_stats})")
        self.stdout.write(f"Games: {total_games} (with stats: {games_with_stats})")
        self.stdout.write(f"PlayerStats rows: {total_stats}")
        self.stdout.write(
            f"Game date range: {date_range['min_date']} -> {date_range['max_date']}"
        )
        self.stdout.write(
            f"Games fully covered (periods 0-4): {full_games}"
        )
        self.stdout.write(f"Games missing periods: {missing_games}")

        self.stdout.write("\nPer-period row counts:")
        for entry in periods:
            self.stdout.write(f"  Period {entry['period']}: {entry['rows']}")

        if incomplete:
            self.stdout.write("\nSample incomplete games (game_id: periods_count):")
            for entry in incomplete:
                self.stdout.write(
                    f"  {entry['game_id']}: {entry['periods']}"
                )
