from django.db import models


class Player(models.Model):
    name = models.CharField(max_length=100)
    team = models.CharField(max_length=50)
    nba_id = models.PositiveIntegerField(unique=True)


class Game(models.Model):
    game_id = models.CharField(max_length=20, unique=True)
    date = models.DateField()
    home_team = models.CharField(max_length=50)
    away_team = models.CharField(max_length=50)


class PlayerGameStats(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    min = models.DecimalField(max_digits=5, decimal_places=2)
    pts = models.PositiveSmallIntegerField()
    reb = models.PositiveSmallIntegerField()
    ast = models.PositiveSmallIntegerField()


class PlayerQuarterStats(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    quarter = models.IntegerField(help_text="1, 2, 3, or 4")
    pts = models.IntegerField(default=0)
    reb = models.IntegerField(default=0)
    ast = models.IntegerField(default=0)
    fga = models.IntegerField(default=0)
    fgm = models.IntegerField(default=0)
    min = models.FloatField(default=0.0)
    fouls = models.IntegerField(default=0)

    class Meta:
        unique_together = ["player", "game", "quarter"]
        indexes = [
            models.Index(fields=["player", "quarter"], name="pqs_player_quarter_idx"),
        ]


class GameBettingLine(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    home_spread = models.FloatField()
    over_under = models.FloatField()
    favorite = models.CharField(max_length=50)


class PlayerPropLine(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    stat_type = models.CharField(max_length=32)
    period = models.PositiveSmallIntegerField()
    threshold = models.FloatField()
    odds = models.IntegerField()
    bookmaker = models.CharField(max_length=100)


class Prediction(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    stat_type = models.CharField(max_length=32)
    period = models.PositiveSmallIntegerField()
    threshold = models.FloatField()
    predicted_prob = models.FloatField()
    is_over_recommended = models.BooleanField()
