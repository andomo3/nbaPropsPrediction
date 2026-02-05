import os
import django
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.db.models import Count  # noqa
from nba_betting.models import Team, Player, Game, PlayerStats, PlayerPropLine, Prediction  # noqa

def main():
    print("=== DB SUMMARY ===")
    print(f"Teams: {Team.objects.count()}")
    print(f"Players: {Player.objects.count()}")
    print(f"Games: {Game.objects.count()}")
    print(f"PlayerStats: {PlayerStats.objects.count()}")
    print(f"PropLines: {PlayerPropLine.objects.count()}")
    print(f"Predictions: {Prediction.objects.count()}")

    print("\nTop 5 players by stats rows:")
    for row in (
        PlayerStats.objects.values("player__first_name", "player__last_name")
        .annotate(cnt=Count("id"))
        .order_by("-cnt")[:5]
    ):
        print(f"  {row['player__first_name']} {row['player__last_name']}: {row['cnt']}")

    print("\nRecent 5 games:")
    for game in Game.objects.order_by("-date")[:5]:
        print(f"  {game.game_id} | {game.date} | {game.home_team.abbreviation} vs {game.away_team.abbreviation}")

    print("\nPlayerStats periods distribution:")
    for row in (
        PlayerStats.objects.values("period")
        .annotate(cnt=Count("id"))
        .order_by("period")
    ):
        print(f"  Period {row['period']}: {row['cnt']}")

if __name__ == "__main__":
    main()
