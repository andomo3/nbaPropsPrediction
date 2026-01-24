from django.db import models


class Team(models.Model):
    city = models.CharField(max_length=50)
    nickname = models.CharField(max_length=50)
    abbreviation = models.CharField(max_length=10)


class Bookmaker(models.Model):
    name = models.CharField(max_length=100)
    site_url = models.URLField(max_length=200, blank=True)


class Player(models.Model):
    nba_id = models.PositiveIntegerField(primary_key=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    position = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    current_team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True
    )


class Game(models.Model):
    game_id = models.CharField(max_length=20, primary_key=True)
    date = models.DateField()
    season = models.CharField(max_length=9)
    home_score = models.PositiveSmallIntegerField()
    away_score = models.PositiveSmallIntegerField()
    home_team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="home_games"
    )
    away_team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="away_games"
    )


class PlayerStats(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    period = models.IntegerField(help_text="0=Full, 1-4=Quarter")
    pts = models.IntegerField(default=0)
    reb = models.IntegerField(default=0)
    ast = models.IntegerField(default=0)
    min = models.FloatField(default=0.0)
    fga = models.IntegerField(default=0)
    fgm = models.IntegerField(default=0)

    class Meta:
        unique_together = ["player", "game", "period"]


class PlayerPropLine(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    bookmaker = models.ForeignKey(Bookmaker, on_delete=models.CASCADE)
    prop_type = models.CharField(max_length=50)
    period = models.IntegerField()
    line = models.FloatField()
    odds_over = models.IntegerField()
    odds_under = models.IntegerField()
    timestamp = models.DateTimeField()

    class Meta:
        unique_together = ["player", "game", "bookmaker", "prop_type", "period"]


class Prediction(models.Model):
    prop_line = models.ForeignKey(PlayerPropLine, on_delete=models.CASCADE)
    model_version = models.CharField(max_length=50)
    prediction_timestamp = models.DateTimeField()
    prob_over = models.FloatField()
    recommendation = models.CharField(max_length=50)
