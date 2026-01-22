from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nba_betting", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="player",
            name="position",
        ),
        migrations.RemoveField(
            model_name="player",
            name="height",
        ),
        migrations.RemoveField(
            model_name="player",
            name="weight",
        ),
        migrations.RemoveField(
            model_name="game",
            name="home_score",
        ),
        migrations.RemoveField(
            model_name="game",
            name="away_score",
        ),
        migrations.AddField(
            model_name="playerquarterstats",
            name="fga",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="playerquarterstats",
            name="fgm",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="playerquarterstats",
            name="fouls",
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="playerquarterstats",
            name="quarter",
            field=models.IntegerField(help_text="1, 2, 3, or 4"),
        ),
        migrations.AlterField(
            model_name="playerquarterstats",
            name="pts",
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="playerquarterstats",
            name="reb",
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="playerquarterstats",
            name="ast",
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="playerquarterstats",
            name="min",
            field=models.FloatField(default=0.0),
        ),
        migrations.AlterUniqueTogether(
            name="playerquarterstats",
            unique_together={("player", "game", "quarter")},
        ),
        migrations.AddIndex(
            model_name="playerquarterstats",
            index=models.Index(
                fields=["player", "quarter"], name="pqs_player_quarter_idx"
            ),
        ),
    ]
