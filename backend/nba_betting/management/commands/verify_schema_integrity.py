from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.utils import timezone

from nba_betting.models import (
    Bookmaker,
    Game,
    Player,
    PlayerPropLine,
    PlayerStats,
    Prediction,
    Team,
)


class Command(BaseCommand):
    help = "Verify schema integrity using dummy data (no external API calls)."

    def handle(self, *args, **options):
        team, _ = Team.objects.get_or_create(
            city="Test City",
            nickname="Test Team",
            abbreviation="TST",
        )
        away_team, _ = Team.objects.get_or_create(
            city="Test Away",
            nickname="Away Team",
            abbreviation="TSA",
        )
        player, _ = Player.objects.get_or_create(
            nba_id=9999999,
            defaults={
                "first_name": "Test",
                "last_name": "Player",
                "position": "G",
                "is_active": True,
                "current_team": team,
            },
        )
        game, _ = Game.objects.get_or_create(
            game_id="TEST_GAME_0001",
            defaults={
                "date": "2024-01-01",
                "season": "2023-24",
                "home_score": 100,
                "away_score": 95,
                "home_team": team,
                "away_team": away_team,
            },
        )

        PlayerStats.objects.filter(
            player=player, game=game, period=1
        ).delete()

        PlayerStats.objects.create(
            player=player,
            game=game,
            team=team,
            period=1,
            pts=8,
            reb=4,
            ast=2,
            fga=6,
            fgm=3,
            min=10.5,
        )
        self.stdout.write("✅ Basic Insertion Passed")

        bookmaker, _ = Bookmaker.objects.get_or_create(
            name="TestBook",
            defaults={"site_url": "https://example.com"},
        )
        PlayerPropLine.objects.update_or_create(
            player=player,
            game=game,
            bookmaker=bookmaker,
            prop_type="points",
            period=1,
            defaults={
                "line": 25.5,
                "odds_over": -110,
                "odds_under": -110,
                "timestamp": timezone.now(),
            },
        )

        try:
            with transaction.atomic():
                PlayerStats.objects.create(
                    player=player,
                    game=game,
                    team=team,
                    period=1,
                    pts=8,
                    reb=4,
                    ast=2,
                    fga=6,
                    fgm=3,
                    min=10.5,
                )
        except IntegrityError:
            self.stdout.write("✅ Duplicate Protection Passed")
        else:
            raise CommandError("Duplicate Protection Failed: row inserted twice.")

        try:
            with transaction.atomic():
                Prediction.objects.create(
                    prop_line_id=9999999,
                    model_version="test",
                    prediction_timestamp=timezone.now(),
                    prob_over=0.5,
                    recommendation="N/A",
                )
        except IntegrityError:
            self.stdout.write("✅ Orphan Protection Passed")
        else:
            raise CommandError("Orphan Protection Failed: invalid FK inserted.")
