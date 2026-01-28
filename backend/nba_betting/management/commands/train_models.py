"""
Django management command to train XGBoost and CatBoost classification models.

Usage:
    python manage.py train_models
    python manage.py train_models --tune --n-iter 50 --cv 3
    python manage.py train_models --csv-path /path/to/data.csv
    python manage.py train_models --model-dir /path/to/models
    python manage.py train_models --no-plots  # Skip plot generation
"""

from pathlib import Path

from django.core.management.base import BaseCommand

from nba_betting.ml.model_trainer import train_all_models


class Command(BaseCommand):
    help = "Train XGBoost and CatBoost classification models for player props prediction."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv-path",
            type=str,
            default=None,
            help="Path to nba_model_ready.csv (defaults to exports/nba_model_ready.csv)",
        )
        parser.add_argument(
            "--model-dir",
            type=str,
            default=None,
            help="Directory to save trained models (defaults to data/models)",
        )
        parser.add_argument(
            "--tune",
            action="store_true",
            help="Enable hyperparameter tuning with RandomizedSearchCV",
        )
        parser.add_argument(
            "--n-iter",
            type=int,
            default=50,
            help="Number of iterations for RandomizedSearchCV (default: 50)",
        )
        parser.add_argument(
            "--cv",
            type=int,
            default=3,
            help="Number of cross-validation folds (default: 3)",
        )
        parser.add_argument(
            "--plots-dir",
            type=str,
            default=None,
            help="Directory to save visualization plots (defaults to data/plots)",
        )
        parser.add_argument(
            "--no-plots",
            action="store_true",
            help="Skip generating diagnostic plots",
        )

    def handle(self, *args, **options):
        # Determine project root (nbaPropsPrediction/)
        # train_models.py is at backend/nba_betting/management/commands/
        # So parents[4] = nbaPropsPrediction/
        project_root = Path(__file__).resolve().parents[4]

        # Set default paths
        csv_path = options["csv_path"]
        if csv_path is None:
            csv_path = project_root / "exports" / "nba_model_ready.csv"
        else:
            csv_path = Path(csv_path)

        model_dir = options["model_dir"]
        if model_dir is None:
            model_dir = project_root / "data" / "models"
        else:
            model_dir = Path(model_dir)

        plots_dir = options["plots_dir"]
        if plots_dir is None:
            plots_dir = project_root / "data" / "plots"
        else:
            plots_dir = Path(plots_dir)

        tune = options["tune"]
        n_iter = options["n_iter"]
        cv = options["cv"]
        generate_plots = not options["no_plots"]

        # Validate CSV exists
        if not csv_path.exists():
            self.stderr.write(
                self.style.ERROR(f"CSV file not found: {csv_path}")
            )
            return

        self.stdout.write(self.style.SUCCESS(f"CSV path: {csv_path}"))
        self.stdout.write(self.style.SUCCESS(f"Model directory: {model_dir}"))
        self.stdout.write(self.style.SUCCESS(f"Plots directory: {plots_dir}"))
        if tune:
            self.stdout.write(
                self.style.WARNING(
                    f"Hyperparameter tuning ENABLED (n_iter={n_iter}, cv={cv})"
                )
            )
        else:
            self.stdout.write("Hyperparameter tuning: disabled (use --tune to enable)")
        
        if generate_plots:
            self.stdout.write("Diagnostic plots: ENABLED")
        else:
            self.stdout.write("Diagnostic plots: disabled (use without --no-plots to enable)")

        # Run training
        self.stdout.write("\nStarting model training...")
        try:
            metrics = train_all_models(
                csv_path=str(csv_path),
                model_dir=str(model_dir),
                plots_dir=str(plots_dir),
                tune=tune,
                n_iter=n_iter,
                cv=cv,
                generate_plots=generate_plots,
            )

            # Print summary
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("TRAINING SUMMARY"))
            self.stdout.write("=" * 60)

            for stat, stat_metrics in metrics.items():
                self.stdout.write(f"\n{stat.upper()}:")
                for model_type, m in stat_metrics.items():
                    self.stdout.write(
                        f"  {model_type}: AUC={m['auc_roc']:.4f}, "
                        f"LogLoss={m['log_loss']:.4f}, "
                        f"Accuracy={m['accuracy']:.4f}"
                    )

            self.stdout.write("\n" + self.style.SUCCESS("Training complete!"))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Training failed: {e}"))
            raise
