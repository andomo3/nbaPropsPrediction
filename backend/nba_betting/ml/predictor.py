"""
Prediction module for loading trained regression models and making inferences.

Supports XGBoost and CatBoost regression models that predict actual stat
values (pts, reb, ast).  The caller compares the projection to the
sportsbook line to derive edge and recommendation.
"""

import os
from pathlib import Path
from typing import Dict, Optional, Union

import joblib
import pandas as pd
import xgboost as xgb

try:
    from catboost import CatBoostRegressor
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False

# Per-stat feature sets (must match train_regression.py exactly)
from nba_betting.ml.train_regression import FEATURE_COLUMNS


class ModelPredictor:
    """Loads and manages trained regression models for inference."""

    def __init__(self, model_dir: Optional[str] = None):
        if model_dir is None:
            # __file__ = /app/backend/nba_betting/ml/predictor.py
            # parents[3] = /app  (repo root)
            _repo_root = Path(__file__).resolve().parents[3]
            _default = _repo_root / "data" / "models"
            model_dir = os.getenv("MODEL_DIR") or str(_default)
        self.model_dir = Path(model_dir)
        self._models: Dict[str, Union[xgb.Booster, "CatBoostRegressor"]] = {}

    # ── Model loading ─────────────────────────────────────────────────────────

    def load_model(
        self, stat: str, model_type: str = "xgb"
    ) -> Optional[Union[xgb.Booster, "CatBoostRegressor"]]:
        cache_key = f"{stat}_{model_type}"
        if cache_key in self._models:
            return self._models[cache_key]

        stat_key = stat.lower().strip()
        if model_type == "xgb":
            model = self._load_xgboost(stat_key)
        elif model_type == "catboost":
            model = self._load_catboost(stat_key)
        elif model_type in ("rf", "lr"):
            model = self._load_sklearn(stat_key, model_type)
        else:
            return None

        if model is not None:
            self._models[cache_key] = model
        return model

    def _load_xgboost(self, stat: str) -> Optional[xgb.Booster]:
        candidates = [
            self.model_dir / f"{stat}_xgb.json",
            self.model_dir / f"{stat}.json",
        ]
        model_path = next((p for p in candidates if p.exists()), None)
        if model_path is None:
            return None
        model = xgb.Booster()
        model.load_model(str(model_path))
        return model

    def _load_sklearn(self, stat: str, model_type: str):
        model_path = self.model_dir / f"{stat}_{model_type}.pkl"
        if not model_path.exists():
            return None
        return joblib.load(str(model_path))

    def _load_catboost(self, stat: str) -> Optional["CatBoostRegressor"]:
        if not CATBOOST_AVAILABLE:
            return None
        model_path = self.model_dir / f"{stat}_catboost.cbm"
        if not model_path.exists():
            return None
        model = CatBoostRegressor()
        model.load_model(str(model_path))
        return model

    # ── Inference ─────────────────────────────────────────────────────────────

    def predict_projection(
        self,
        feature_row: pd.DataFrame,
        stat: str,
        model_type: str = "xgb",
    ) -> Optional[float]:
        """
        Predict the projected stat value (regression output).

        Args:
            feature_row: Single-row DataFrame with stat-specific feature columns.
            stat: 'pts', 'reb', or 'ast'
            model_type: 'xgb' or 'catboost'

        Returns:
            Projected stat value as float, or None if model not found.
        """
        model = self.load_model(stat, model_type)
        if model is None:
            return None

        feats = FEATURE_COLUMNS[stat]
        X = feature_row[feats]

        if model_type == "xgb":
            dmatrix = xgb.DMatrix(X, feature_names=feats)
            result = model.predict(dmatrix)
        else:
            result = model.predict(X.values)
        return float(result[0])

    def predict_with_both_models(
        self, feature_row: pd.DataFrame, stat: str
    ) -> Dict[str, Optional[float]]:
        """Return projections from both XGBoost and CatBoost."""
        return {
            "xgb":      self.predict_projection(feature_row, stat, "xgb"),
            "catboost": self.predict_projection(feature_row, stat, "catboost"),
        }


# ── Global singleton ──────────────────────────────────────────────────────────

_predictor: Optional[ModelPredictor] = None


def get_predictor() -> ModelPredictor:
    """Get (or lazily create) the global ModelPredictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = ModelPredictor()
    return _predictor
