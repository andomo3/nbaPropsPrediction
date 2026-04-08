"""
Django management command to train XGBoost / CatBoost regression models.

Usage:
    python manage.py train_models
    python manage.py train_models --csv-path /path/to/PlayerStatistics.csv
    python manage.py train_models --model-dir /path/to/models
    python manage.py train_models --no-catboost   # faster, skip CatBoost
"""

import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from nba_betting.ml.train_regression import train_all_regression_models


class Command(BaseCommand):
    help = "Train XGBoost and CatBoost regression models for NBA player props prediction."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv-path",
            type=str,
            default=None,
            help="Path to PlayerStatistics.csv (defaults to data/raw/PlayerStatistics.csv)",
        )
        parser.add_argument(
            "--model-dir",
            type=str,
            default=None,
            help="Directory to save trained models (defaults to data/models)",
        )
        parser.add_argument(
            "--no-catboost",
            action="store_true",
            help="Skip CatBoost training (faster iteration during dev)",
        )

    def handle(self, *args, **options):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")

        csv_path  = options.get("csv_path")
        model_dir = options.get("model_dir")
        skip_cb   = options.get("no_catboost", False)

        self.stdout.write("Starting regression model training...")
        if csv_path:
            self.stdout.write(f"  CSV: {csv_path}")
        if model_dir:
            self.stdout.write(f"  Model dir: {model_dir}")
        if skip_cb:
            self.stdout.write("  CatBoost: skipped")

        try:
            metadata = train_all_regression_models(
                csv_path=csv_path,
                model_dir=Path(model_dir) if model_dir else None,
                skip_catboost=skip_cb,
            )

            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("TRAINING SUMMARY"))
            self.stdout.write("=" * 60)

            for stat, info in metadata.get("stats", {}).items():
                xgb = info.get("xgb", {})
                test = xgb.get("test", {})
                self.stdout.write(
                    f"  [{stat.upper()}]  "
                    f"Test MAE={test.get('mae', '?'):.3f}  "
                    f"Test RMSE={test.get('rmse', '?'):.3f}  "
                    f"({info.get('test_samples', '?'):,} test rows)"
                )

            self.stdout.write(self.style.SUCCESS("\nTraining complete!"))

        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Training failed: {exc}"))
            raise
