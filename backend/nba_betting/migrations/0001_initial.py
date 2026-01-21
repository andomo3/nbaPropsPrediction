from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Game",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("game_id", models.CharField(max_length=20, unique=True)),
                ("date", models.DateField()),
                ("home_team", models.CharField(max_length=50)),
                ("away_team", models.CharField(max_length=50)),
                ("home_score", models.PositiveSmallIntegerField()),
                ("away_score", models.PositiveSmallIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name="Player",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("team", models.CharField(max_length=50)),
                ("position", models.CharField(max_length=20)),
                ("height", models.CharField(max_length=10)),
                ("weight", models.PositiveSmallIntegerField()),
                ("nba_id", models.PositiveIntegerField(unique=True)),
            ],
        ),
        migrations.CreateModel(
            name="GameBettingLine",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("home_spread", models.FloatField()),
                ("over_under", models.FloatField()),
                ("favorite", models.CharField(max_length=50)),
                (
                    "game",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="nba_betting.game"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PlayerGameStats",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("min", models.DecimalField(decimal_places=2, max_digits=5)),
                ("pts", models.PositiveSmallIntegerField()),
                ("reb", models.PositiveSmallIntegerField()),
                ("ast", models.PositiveSmallIntegerField()),
                (
                    "game",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="nba_betting.game"
                    ),
                ),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="nba_betting.player"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PlayerPropLine",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("stat_type", models.CharField(max_length=32)),
                ("period", models.PositiveSmallIntegerField()),
                ("threshold", models.FloatField()),
                ("odds", models.IntegerField()),
                ("bookmaker", models.CharField(max_length=100)),
                (
                    "game",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="nba_betting.game"
                    ),
                ),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="nba_betting.player"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PlayerQuarterStats",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("quarter", models.PositiveSmallIntegerField()),
                ("pts", models.PositiveSmallIntegerField()),
                ("reb", models.PositiveSmallIntegerField()),
                ("ast", models.PositiveSmallIntegerField()),
                ("min", models.DecimalField(decimal_places=2, max_digits=5)),
                (
                    "game",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="nba_betting.game"
                    ),
                ),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="nba_betting.player"
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("player", "game", "quarter"),
                        name="unique_player_game_quarter",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Prediction",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("stat_type", models.CharField(max_length=32)),
                ("period", models.PositiveSmallIntegerField()),
                ("threshold", models.FloatField()),
                ("predicted_prob", models.FloatField()),
                ("is_over_recommended", models.BooleanField()),
                (
                    "game",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="nba_betting.game"
                    ),
                ),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="nba_betting.player"
                    ),
                ),
            ],
        ),
    ]
