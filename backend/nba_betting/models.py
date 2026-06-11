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
    # Nullable so ESPN sync can insert in-progress/upcoming games before scores exist
    home_score = models.SmallIntegerField(null=True, blank=True)
    away_score = models.SmallIntegerField(null=True, blank=True)
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


class DailyPick(models.Model):
    """Pre-generated morning picks for the LITE top-20 player list."""

    STAT_CHOICES = [("pts", "Points"), ("reb", "Rebounds"), ("ast", "Assists")]

    pick_date = models.DateField(db_index=True)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    opponent_abbr = models.CharField(max_length=10)
    is_home = models.BooleanField()
    stat = models.CharField(max_length=10, choices=STAT_CHOICES)
    line = models.FloatField(help_text="L5 rolling average used as the model line")
    prob_over = models.FloatField()
    projection = models.FloatField()
    edge = models.CharField(max_length=10)  # "Over" | "Under"
    model_version = models.CharField(max_length=50, default="xgb_v1")
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["pick_date", "player", "stat"]
        ordering = ["-prob_over"]


class BacktestRun(models.Model):
    """Header + aggregate results for a single backtest request. Acts as a cache key."""

    MODEL_CHOICES = [
        ("xgb",   "XGBoost"),
        ("rf",    "Random Forest"),
        ("lr",    "Linear Regression"),
        ("naive", "Naive (Season Avg)"),
    ]

    player_name = models.CharField(max_length=100)
    stat = models.CharField(max_length=10)
    model = models.CharField(max_length=20, default="xgb", choices=MODEL_CHOICES)
    date_from = models.DateField()
    date_to = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    total_bets = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    accuracy = models.FloatField(default=0.0)
    total_pnl = models.FloatField(default=0.0)
    roi = models.FloatField(default=0.0, help_text="Return on investment as a percentage")

    class Meta:
        indexes = [
            models.Index(fields=["player_name", "stat", "model", "date_from", "date_to"]),
        ]


class BacktestResult(models.Model):
    """One row per game within a BacktestRun."""

    run = models.ForeignKey(BacktestRun, on_delete=models.CASCADE, related_name="results")
    game_date = models.DateField()
    opponent = models.CharField(max_length=10)
    actual = models.FloatField()
    line = models.FloatField()
    prob_over = models.FloatField()
    predicted_over = models.BooleanField()
    correct = models.BooleanField()
    pnl = models.FloatField(help_text="+1.0 if correct, -1.1 if wrong (simulates -110 odds)")
    error = models.FloatField(default=0.0, help_text="actual - projection (signed prediction error)")

    class Meta:
        ordering = ["game_date"]
