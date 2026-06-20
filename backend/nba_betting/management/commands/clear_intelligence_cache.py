"""
Clear Redis cache entries for all intelligence endpoints.

Run after reseeding backtest data to force fresh computations:
    python manage.py clear_intelligence_cache
    python manage.py clear_intelligence_cache --player "Nikola Jokic" --stat pts
"""

from django.core.cache import cache
from django.core.management.base import BaseCommand

from nba_betting.constants import SEASON_REPORT_PLAYERS


class Command(BaseCommand):
    help = "Clear Redis cache for intelligence endpoints"

    def add_arguments(self, parser):
        parser.add_argument("--player", help="Clear only this player (partial match ok)")
        parser.add_argument("--stat",   help="Clear only this stat (pts/reb/ast)")

    def handle(self, *args, **options):
        player_filter = (options.get("player") or "").lower()
        stat_filter   = (options.get("stat") or "").lower()
        seasons       = [2024, 2025, 2026]
        stats         = [stat_filter] if stat_filter else ["pts", "reb", "ast"]
        endpoints     = ["edge", "floor_ceiling", "opponents", "fingerprint", "validation"]

        cleared = 0
        for player in SEASON_REPORT_PLAYERS:
            if player_filter and player_filter not in player.lower():
                continue
            for stat in stats:
                for endpoint in endpoints:
                    for season in seasons:
                        slug = player.lower().replace(" ", "_")
                        key = f"intel:{endpoint}:{slug}:{stat}:{season}"
                        if cache.delete(key):
                            self.stdout.write(f"  cleared: {key}")
                            cleared += 1

        self.stdout.write(self.style.SUCCESS(f"\nDone — {cleared} cache entries cleared."))
