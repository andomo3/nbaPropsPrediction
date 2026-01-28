"""
Model training module for XGBoost and CatBoost classification models.

Trains binary classifiers to predict over/under outcomes for player props
(points, rebounds, assists) using rolling averages as dynamic line thresholds.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import xgboost as xgb
from catboost import CatBoostClassifier
from scipy.stats import randint, uniform
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    log_loss,
    make_scorer,
    roc_auc_score,
)
from sklearn.model_selection import RandomizedSearchCV
from xgboost import XGBClassifier

from .visualizations import (
    TrainingVisualizer,
    get_catboost_feature_importance,
    get_xgb_feature_importance,
)


# Feature columns used for training (must match inference features)
FEATURE_COLUMNS = [
    "is_home",
    "days_rest",
    "opp_pts_allowed_L10",
    "pts_L5",
    "pts_L10",
    "pts_ema_L5",
    "pts_std_L10",
    "reb_L5",
    "reb_L10",
    "reb_ema_L5",
    "ast_L5",
    "ast_L10",
    "ast_ema_L5",
    "min_L5",
    "min_L10",
    "fg_pct_L5",
    "fg_pct_L10",
]

# Stats to train models for
TARGET_STATS = ["pts", "reb", "ast"]

# Corresponding rolling average columns for dynamic line thresholds
STAT_TO_LINE_COL = {
    "pts": "pts_L5",
    "reb": "reb_L5",
    "ast": "ast_L5",
}

# Hyperparameter search spaces for RandomizedSearchCV
XGBOOST_PARAM_DIST = {
    "max_depth": randint(3, 10),
    "learning_rate": uniform(0.01, 0.29),  # 0.01 to 0.30
    "n_estimators": randint(100, 500),
    "subsample": uniform(0.6, 0.4),  # 0.6 to 1.0
    "colsample_bytree": uniform(0.6, 0.4),  # 0.6 to 1.0
    "min_child_weight": randint(1, 10),
    "gamma": uniform(0, 0.5),
    "reg_alpha": uniform(0, 1),
    "reg_lambda": uniform(0.5, 1.5),  # 0.5 to 2.0
}

CATBOOST_PARAM_DIST = {
    "depth": randint(4, 10),
    "learning_rate": uniform(0.01, 0.29),  # 0.01 to 0.30
    "iterations": randint(100, 500),
    "l2_leaf_reg": uniform(1, 9),  # 1 to 10
    "border_count": randint(32, 224),  # 32 to 255
    "bagging_temperature": uniform(0, 1),
    "random_strength": uniform(0, 1),
}


class NBADataLoader:
    """Loads and prepares NBA data for model training."""

    def __init__(self, csv_path: str):
        """
        Initialize the data loader.

        Args:
            csv_path: Path to the nba_model_ready.csv file
        """
        self.csv_path = csv_path
        self.df: Optional[pd.DataFrame] = None

    def load(self) -> pd.DataFrame:
        """Load the CSV data and parse dates."""
        print(f"Loading data from {self.csv_path}...")
        self.df = pd.read_csv(self.csv_path)
        self.df["date"] = pd.to_datetime(self.df["date"])
        print(f"Loaded {len(self.df):,} rows")
        return self.df

    def get_features(self) -> pd.DataFrame:
        """Extract feature columns from the dataframe."""
        if self.df is None:
            raise ValueError("Data not loaded. Call load() first.")
        return self.df[FEATURE_COLUMNS].copy()

    def create_target(self, stat: str) -> pd.Series:
        """
        Create binary target for a given stat.

        Target = 1 if player's actual stat > their rolling 5-game average
        Target = 0 otherwise

        Args:
            stat: One of 'pts', 'reb', 'ast'

        Returns:
            Binary series (0 or 1)
        """
        if self.df is None:
            raise ValueError("Data not loaded. Call load() first.")

        if stat not in STAT_TO_LINE_COL:
            raise ValueError(f"Unknown stat: {stat}. Must be one of {TARGET_STATS}")

        line_col = STAT_TO_LINE_COL[stat]
        target = (self.df[stat] > self.df[line_col]).astype(int)
        print(f"Target '{stat}': {target.sum():,} over ({target.mean():.1%}), "
              f"{(~target.astype(bool)).sum():,} under ({1 - target.mean():.1%})")
        return target

    def time_split(
        self, train_ratio: float = 0.8
    ) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
        """
        Split data chronologically to prevent data leakage.

        Args:
            train_ratio: Fraction of data to use for training (by time)

        Returns:
            Tuple of (train_df, test_df, train_indices, test_indices)
        """
        if self.df is None:
            raise ValueError("Data not loaded. Call load() first.")

        # Sort by date
        sorted_df = self.df.sort_values("date").reset_index(drop=True)
        split_idx = int(len(sorted_df) * train_ratio)

        train_df = sorted_df.iloc[:split_idx].copy()
        test_df = sorted_df.iloc[split_idx:].copy()

        train_dates = train_df["date"]
        test_dates = test_df["date"]

        print(f"Train: {len(train_df):,} rows ({train_dates.min().date()} to {train_dates.max().date()})")
        print(f"Test:  {len(test_df):,} rows ({test_dates.min().date()} to {test_dates.max().date()})")

        return train_df, test_df, train_df.index.values, test_df.index.values


class ModelTrainer:
    """Trains and evaluates XGBoost and CatBoost classifiers."""

    def __init__(self, model_dir: str = "data/models"):
        """
        Initialize the trainer.

        Args:
            model_dir: Directory to save trained models
        """
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.metrics: Dict[str, Dict] = {}

    def train_xgboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        stat: str,
    ) -> Tuple[xgb.Booster, Dict]:
        """
        Train an XGBoost classifier.

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            stat: Stat being predicted (for logging)

        Returns:
            Tuple of (Trained XGBoost Booster, evaluation history dict)
        """
        print(f"\nTraining XGBoost for '{stat}'...")

        dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=FEATURE_COLUMNS)
        dval = xgb.DMatrix(X_val, label=y_val, feature_names=FEATURE_COLUMNS)

        params = {
            "objective": "binary:logistic",
            "eval_metric": ["logloss", "auc"],
            "max_depth": 6,
            "eta": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "seed": 42,
        }

        evals_result: Dict = {}
        evals = [(dtrain, "train"), (dval, "val")]
        model = xgb.train(
            params,
            dtrain,
            num_boost_round=500,
            evals=evals,
            evals_result=evals_result,
            early_stopping_rounds=50,
            verbose_eval=50,
        )

        return model, evals_result

    def train_catboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        stat: str,
    ) -> Tuple[CatBoostClassifier, Dict]:
        """
        Train a CatBoost classifier.

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            stat: Stat being predicted (for logging)

        Returns:
            Tuple of (Trained CatBoostClassifier, evaluation history dict)
        """
        print(f"\nTraining CatBoost for '{stat}'...")

        model = CatBoostClassifier(
            iterations=500,
            learning_rate=0.1,
            depth=6,
            loss_function="Logloss",
            eval_metric="AUC",
            random_seed=42,
            verbose=50,
            early_stopping_rounds=50,
        )

        model.fit(
            X_train,
            y_train,
            eval_set=(X_val, y_val),
            use_best_model=True,
        )

        # Extract evaluation history in same format as XGBoost
        evals_result = {
            "train": {
                "logloss": model.get_evals_result()["learn"]["Logloss"],
                "auc": model.get_evals_result()["learn"]["AUC"],
            },
            "val": {
                "logloss": model.get_evals_result()["validation"]["Logloss"],
                "auc": model.get_evals_result()["validation"]["AUC"],
            },
        }

        return model, evals_result

    def tune_xgboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        stat: str,
        n_iter: int = 50,
        cv: int = 5,
        n_jobs: int = -1,
        random_state: int = 42,
    ) -> Tuple[XGBClassifier, Dict]:
        """
        Tune XGBoost hyperparameters using RandomizedSearchCV.

        Args:
            X_train: Training features
            y_train: Training labels
            stat: Stat being predicted (for logging)
            n_iter: Number of parameter settings to sample
            cv: Number of cross-validation folds
            n_jobs: Number of parallel jobs (-1 for all cores)
            random_state: Random seed for reproducibility

        Returns:
            Tuple of (best model, best parameters)
        """
        print(f"\nTuning XGBoost hyperparameters for '{stat}'...")
        print(f"  Iterations: {n_iter}, CV folds: {cv}")

        base_model = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=random_state,
            early_stopping_rounds=50,
        )

        search = RandomizedSearchCV(
            estimator=base_model,
            param_distributions=XGBOOST_PARAM_DIST,
            n_iter=n_iter,
            scoring="roc_auc",
            cv=cv,
            n_jobs=n_jobs,
            random_state=random_state,
            verbose=1,
            refit=True,
        )

        # Fit with eval_set for early stopping
        search.fit(
            X_train,
            y_train,
            eval_set=[(X_train, y_train)],
            verbose=False,
        )

        best_params = search.best_params_
        best_score = search.best_score_

        print(f"\n  Best CV AUC-ROC: {best_score:.4f}")
        print(f"  Best parameters:")
        for param, value in best_params.items():
            print(f"    {param}: {value}")

        return search.best_estimator_, best_params

    def tune_catboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        stat: str,
        n_iter: int = 50,
        cv: int = 5,
        n_jobs: int = -1,
        random_state: int = 42,
    ) -> Tuple[CatBoostClassifier, Dict]:
        """
        Tune CatBoost hyperparameters using CatBoost's native randomized_search.

        Args:
            X_train: Training features
            y_train: Training labels
            stat: Stat being predicted (for logging)
            n_iter: Number of parameter settings to sample
            cv: Number of cross-validation folds
            n_jobs: Number of parallel jobs (-1 for all cores)
            random_state: Random seed for reproducibility

        Returns:
            Tuple of (best model, best parameters)
        """
        from catboost import Pool

        print(f"\nTuning CatBoost hyperparameters for '{stat}'...")
        print(f"  Iterations: {n_iter}, CV folds: {cv}")

        # Create CatBoost Pool for training
        train_pool = Pool(X_train, y_train)

        # Define parameter grid for CatBoost's randomized_search
        # CatBoost uses list ranges instead of scipy distributions
        param_grid = {
            "depth": list(range(4, 10)),
            "learning_rate": [0.01, 0.03, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3],
            "iterations": [100, 200, 300, 400, 500],
            "l2_leaf_reg": [1, 3, 5, 7, 9],
            "border_count": [32, 64, 128, 200, 254],
            "bagging_temperature": [0, 0.2, 0.5, 0.8, 1.0],
            "random_strength": [0, 0.2, 0.5, 0.8, 1.0],
        }

        # Use CatBoost's native randomized_search
        model = CatBoostClassifier(
            loss_function="Logloss",
            eval_metric="AUC",
            random_seed=random_state,
            verbose=0,
        )

        result = model.randomized_search(
            param_grid,
            train_pool,
            n_iter=n_iter,
            cv=cv,
            search_by_train_test_split=True,
            refit=True,
            shuffle=True,
            verbose=False,
            plot=False,
        )

        best_params = result["params"]
        # Get the best CV score from results
        cv_results = result.get("cv_results", {})
        if cv_results:
            best_score = cv_results.get("test-AUC-mean", [0])[-1]
        else:
            best_score = 0.0

        print(f"\n  Best CV AUC: {best_score:.4f}")
        print(f"  Best parameters:")
        for param, value in best_params.items():
            print(f"    {param}: {value}")

        return model, best_params

    def train_xgboost_with_params(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        stat: str,
        params: Optional[Dict] = None,
    ) -> Tuple[xgb.Booster, Dict]:
        """
        Train XGBoost with custom parameters (e.g., from tuning).

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            stat: Stat being predicted
            params: Custom parameters (if None, uses defaults)

        Returns:
            Tuple of (Trained XGBoost Booster, evaluation history dict)
        """
        print(f"\nTraining XGBoost for '{stat}' with tuned parameters...")

        dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=FEATURE_COLUMNS)
        dval = xgb.DMatrix(X_val, label=y_val, feature_names=FEATURE_COLUMNS)

        # Default parameters
        xgb_params = {
            "objective": "binary:logistic",
            "eval_metric": ["logloss", "auc"],
            "seed": 42,
        }

        # Map sklearn-style params to xgboost native params
        if params:
            param_mapping = {
                "learning_rate": "eta",
                "n_estimators": None,  # Handled separately
                "max_depth": "max_depth",
                "subsample": "subsample",
                "colsample_bytree": "colsample_bytree",
                "min_child_weight": "min_child_weight",
                "gamma": "gamma",
                "reg_alpha": "alpha",
                "reg_lambda": "lambda",
            }
            for sklearn_name, xgb_name in param_mapping.items():
                if sklearn_name in params and xgb_name:
                    xgb_params[xgb_name] = params[sklearn_name]

        num_boost_round = params.get("n_estimators", 500) if params else 500

        evals_result: Dict = {}
        evals = [(dtrain, "train"), (dval, "val")]
        model = xgb.train(
            xgb_params,
            dtrain,
            num_boost_round=num_boost_round,
            evals=evals,
            evals_result=evals_result,
            early_stopping_rounds=50,
            verbose_eval=50,
        )

        return model, evals_result

    def train_catboost_with_params(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        stat: str,
        params: Optional[Dict] = None,
    ) -> Tuple[CatBoostClassifier, Dict]:
        """
        Train CatBoost with custom parameters (e.g., from tuning).

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            stat: Stat being predicted
            params: Custom parameters (if None, uses defaults)

        Returns:
            Tuple of (Trained CatBoostClassifier, evaluation history dict)
        """
        print(f"\nTraining CatBoost for '{stat}' with tuned parameters...")

        # Default parameters
        cat_params = {
            "loss_function": "Logloss",
            "eval_metric": "AUC",
            "random_seed": 42,
            "verbose": 50,
            "early_stopping_rounds": 50,
        }

        # Merge tuned parameters
        if params:
            cat_params.update(params)

        model = CatBoostClassifier(**cat_params)

        model.fit(
            X_train,
            y_train,
            eval_set=(X_val, y_val),
            use_best_model=True,
        )

        # Extract evaluation history
        evals_result = {
            "train": {
                "logloss": model.get_evals_result()["learn"]["Logloss"],
                "auc": model.get_evals_result()["learn"]["AUC"],
            },
            "val": {
                "logloss": model.get_evals_result()["validation"]["Logloss"],
                "auc": model.get_evals_result()["validation"]["AUC"],
            },
        }

        return model, evals_result

    def evaluate(
        self,
        model,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        model_type: str,
        stat: str,
    ) -> Dict:
        """
        Evaluate model performance.

        Args:
            model: Trained model (XGBoost Booster or CatBoostClassifier)
            X_test: Test features
            y_test: Test labels
            model_type: 'xgb' or 'catboost'
            stat: Stat being predicted

        Returns:
            Dictionary of metrics
        """
        # Get probability predictions
        if model_type == "xgb":
            dtest = xgb.DMatrix(X_test, feature_names=FEATURE_COLUMNS)
            y_prob = model.predict(dtest)
        else:
            y_prob = model.predict_proba(X_test)[:, 1]

        # Binary predictions at 0.5 threshold
        y_pred = (y_prob >= 0.5).astype(int)

        # Calculate metrics
        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "auc_roc": roc_auc_score(y_test, y_prob),
            "log_loss": log_loss(y_test, y_prob),
            "brier_score": brier_score_loss(y_test, y_prob),
        }

        # Calibration curve data
        prob_true, prob_pred = calibration_curve(y_test, y_prob, n_bins=10)
        metrics["calibration"] = {
            "prob_true": prob_true.tolist(),
            "prob_pred": prob_pred.tolist(),
        }

        print(f"\n{model_type.upper()} {stat} Results:")
        print(f"  Accuracy:    {metrics['accuracy']:.4f}")
        print(f"  AUC-ROC:     {metrics['auc_roc']:.4f}")
        print(f"  Log Loss:    {metrics['log_loss']:.4f}")
        print(f"  Brier Score: {metrics['brier_score']:.4f}")

        return metrics

    def save_xgboost(self, model: xgb.Booster, stat: str) -> str:
        """Save XGBoost model to JSON file."""
        path = self.model_dir / f"{stat}_xgb.json"
        model.save_model(str(path))
        print(f"Saved XGBoost model to {path}")
        return str(path)

    def save_catboost(self, model: CatBoostClassifier, stat: str) -> str:
        """Save CatBoost model to CBM file."""
        path = self.model_dir / f"{stat}_catboost.cbm"
        model.save_model(str(path))
        print(f"Saved CatBoost model to {path}")
        return str(path)

    def save_metadata(
        self,
        all_metrics: Dict,
        best_params: Optional[Dict] = None,
        tuning_enabled: bool = False,
    ) -> str:
        """Save training metadata, metrics, and best hyperparameters to JSON."""
        metadata = {
            "training_date": datetime.now().isoformat(),
            "feature_columns": FEATURE_COLUMNS,
            "target_stats": TARGET_STATS,
            "tuning_enabled": tuning_enabled,
            "metrics": all_metrics,
        }

        if best_params:
            # Convert numpy types to Python types for JSON serialization
            serializable_params = {}
            for stat, models in best_params.items():
                serializable_params[stat] = {}
                for model_type, params in models.items():
                    serializable_params[stat][model_type] = {
                        k: int(v) if isinstance(v, (np.integer, np.int64)) else
                           float(v) if isinstance(v, (np.floating, np.float64)) else v
                        for k, v in params.items()
                    }
            metadata["best_hyperparameters"] = serializable_params

        path = self.model_dir / "model_metadata.json"
        with open(path, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"Saved metadata to {path}")
        return str(path)


def train_all_models(
    csv_path: str,
    model_dir: str = "data/models",
    plots_dir: str = "data/plots",
    tune: bool = False,
    n_iter: int = 50,
    cv: int = 3,
    generate_plots: bool = True,
) -> Dict:
    """
    Train XGBoost and CatBoost models for all target stats.

    Args:
        csv_path: Path to nba_model_ready.csv
        model_dir: Directory to save models
        plots_dir: Directory to save visualization plots
        tune: Whether to perform hyperparameter tuning
        n_iter: Number of iterations for RandomizedSearchCV (if tune=True)
        cv: Number of cross-validation folds (if tune=True)
        generate_plots: Whether to generate diagnostic plots

    Returns:
        Dictionary of all metrics
    """
    # Load data
    loader = NBADataLoader(csv_path)
    loader.load()

    # Time-based split
    train_df, test_df, _, _ = loader.time_split(train_ratio=0.8)

    # Initialize trainer and visualizer
    trainer = ModelTrainer(model_dir)
    visualizer = TrainingVisualizer(plots_dir) if generate_plots else None
    
    all_metrics = {}
    all_best_params = {} if tune else None
    
    # Store data for combined plots
    all_predictions = {}

    for stat in TARGET_STATS:
        print(f"\n{'='*60}")
        print(f"Training models for: {stat.upper()}")
        if tune:
            print(f"(Hyperparameter tuning enabled: {n_iter} iterations, {cv}-fold CV)")
        print("=" * 60)

        # Create targets
        line_col = STAT_TO_LINE_COL[stat]
        y_train = (train_df[stat] > train_df[line_col]).astype(int)
        y_test = (test_df[stat] > test_df[line_col]).astype(int)

        print(f"Train target distribution: {y_train.mean():.1%} over")
        print(f"Test target distribution:  {y_test.mean():.1%} over")

        # Extract features
        X_train = train_df[FEATURE_COLUMNS]
        X_test = test_df[FEATURE_COLUMNS]

        # Store predictions for visualization
        stat_predictions = {"y_test": y_test.values}

        if tune:
            # Hyperparameter tuning mode
            all_best_params[stat] = {}

            # Tune and train XGBoost
            _, xgb_best_params = trainer.tune_xgboost(
                X_train, y_train, stat, n_iter=n_iter, cv=cv
            )
            all_best_params[stat]["xgboost"] = xgb_best_params
            xgb_model, xgb_evals = trainer.train_xgboost_with_params(
                X_train, y_train, X_test, y_test, stat, xgb_best_params
            )
            xgb_metrics = trainer.evaluate(xgb_model, X_test, y_test, "xgb", stat)
            trainer.save_xgboost(xgb_model, stat)

            # Tune and train CatBoost
            _, cat_best_params = trainer.tune_catboost(
                X_train, y_train, stat, n_iter=n_iter, cv=cv
            )
            all_best_params[stat]["catboost"] = cat_best_params
            cat_model, cat_evals = trainer.train_catboost_with_params(
                X_train, y_train, X_test, y_test, stat, cat_best_params
            )
            cat_metrics = trainer.evaluate(cat_model, X_test, y_test, "catboost", stat)
            trainer.save_catboost(cat_model, stat)
        else:
            # Default training mode (no tuning)
            xgb_model, xgb_evals = trainer.train_xgboost(X_train, y_train, X_test, y_test, stat)
            xgb_metrics = trainer.evaluate(xgb_model, X_test, y_test, "xgb", stat)
            trainer.save_xgboost(xgb_model, stat)

            cat_model, cat_evals = trainer.train_catboost(X_train, y_train, X_test, y_test, stat)
            cat_metrics = trainer.evaluate(cat_model, X_test, y_test, "catboost", stat)
            trainer.save_catboost(cat_model, stat)

        all_metrics[stat] = {
            "xgboost": xgb_metrics,
            "catboost": cat_metrics,
        }

        # Generate visualizations for this stat
        if visualizer:
            print(f"\nGenerating visualizations for {stat.upper()}...")

            # Get predictions for plots
            dtest = xgb.DMatrix(X_test, feature_names=FEATURE_COLUMNS)
            xgb_probs = xgb_model.predict(dtest)
            cat_probs = cat_model.predict_proba(X_test)[:, 1]
            
            stat_predictions["xgb_prob"] = xgb_probs
            stat_predictions["cat_prob"] = cat_probs

            # 1. Learning curves
            visualizer.plot_learning_curves(xgb_evals, stat, "xgb", "logloss")
            visualizer.plot_learning_curves(cat_evals, stat, "catboost", "logloss")

            # 2. ROC curves (comparison)
            roc_results = {
                "XGBoost": (y_test.values, xgb_probs, xgb_metrics["auc_roc"]),
                "CatBoost": (y_test.values, cat_probs, cat_metrics["auc_roc"]),
            }
            visualizer.plot_roc_curves(roc_results, stat)

            # 3. Calibration curves
            cal_results = {
                "XGBoost": (y_test.values, xgb_probs),
                "CatBoost": (y_test.values, cat_probs),
            }
            visualizer.plot_calibration_curves(cal_results, stat)

            # 4. Confusion matrices
            xgb_preds = (xgb_probs >= 0.5).astype(int)
            cat_preds = (cat_probs >= 0.5).astype(int)
            visualizer.plot_confusion_matrix(y_test.values, xgb_preds, stat, "xgb")
            visualizer.plot_confusion_matrix(y_test.values, cat_preds, stat, "catboost")

            # 5. Feature importance
            xgb_importance = get_xgb_feature_importance(xgb_model)
            cat_importance = get_catboost_feature_importance(cat_model, FEATURE_COLUMNS)
            visualizer.plot_feature_importance(xgb_importance, stat, "xgb")
            visualizer.plot_feature_importance(cat_importance, stat, "catboost")
            visualizer.plot_feature_importance_comparison(xgb_importance, cat_importance, stat)

            # 6. Prediction distributions
            visualizer.plot_prediction_distribution(y_test.values, xgb_probs, stat, "xgb")
            visualizer.plot_prediction_distribution(y_test.values, cat_probs, stat, "catboost")

        all_predictions[stat] = stat_predictions

    # Generate summary plot across all stats
    if visualizer:
        print(f"\nGenerating summary plots...")
        visualizer.plot_metrics_summary(all_metrics)

    # Save metadata
    trainer.save_metadata(all_metrics, all_best_params, tuning_enabled=tune)

    print(f"\n{'='*60}")
    print("Training complete!")
    if visualizer:
        print(f"Plots saved to: {plots_dir}")
    print("=" * 60)

    return all_metrics
