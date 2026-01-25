from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Case, ExpressionWrapper, F, FloatField, Value, When

from nba_betting.models import PlayerStats


class Command(BaseCommand):
    help = "Export full-game (period=0) stats to an MVP-ready CSV."

    def add_arguments(self, parser):
        default_path = (
            Path(settings.BASE_DIR).parent / "exports" / "nba_mvp_data.csv"
        )
        parser.add_argument(
            "--out",
            default=str(default_path),
            help="Output CSV path (default: exports/nba_mvp_data.csv).",
        )

    def handle(self, *args, **options):
        out_path = Path(options["out"]).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        queryset = (
            PlayerStats.objects.filter(period=0)
            .annotate(
                fg_pct=Case(
                    When(
                        fga__gt=0,
                        then=ExpressionWrapper(
                            F("fgm") * 1.0 / F("fga"),
                            output_field=FloatField(),
                        ),
                    ),
                    default=Value(0.0),
                    output_field=FloatField(),
                ),
                fg3_pct=Value(0.0, output_field=FloatField()),
            )
            .values(
                "game__date",
                "game__game_id",
                "player__first_name",
                "player__last_name",
                "team__abbreviation",
                "game__home_team__abbreviation",
                "game__away_team__abbreviation",
                "pts",
                "reb",
                "ast",
                "min",
                "fg_pct",
            )
        )

        df = pd.DataFrame.from_records(queryset)
        if df.empty:
            df.to_csv(out_path, index=False)
            self.stdout.write(
                f"Exported 0 unique player-game rows to {out_path}"
            )
            return

        df = df.rename(
            columns={
                "game__date": "date",
                "game__game_id": "game_id",
                "team__abbreviation": "player_team",
                "game__home_team__abbreviation": "home_team",
                "game__away_team__abbreviation": "away_team",
            }
        )
        df["player_name"] = (
            df["player__first_name"].fillna("").str.strip()
            + " "
            + df["player__last_name"].fillna("").str.strip()
        ).str.strip()
        df = df.drop(columns=["player__first_name", "player__last_name"])
        df = df.drop_duplicates(subset=["game_id", "player_name"])

        df.to_csv(out_path, index=False)

        self.stdout.write(
            f"Exported {len(df)} unique player-game rows to {out_path}"
        )
