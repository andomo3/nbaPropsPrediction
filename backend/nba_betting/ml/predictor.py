"""
Prediction module for loading trained models and making inferences.

Supports both XGBoost and CatBoost classification models for predicting
over/under probabilities on player props.
"""

import os
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

import pandas as pd
import xgboost as xgb

try:
    from catboost import CatBoostClassifier
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False


# Feature columns expected by the models (must match training)
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


class ModelPredictor:
    """Loads and manages trained models for inference."""

    def __init__(self, model_dir: Optional[str] = None):
        """
        Initialize the predictor.

        Args:
            model_dir: Directory containing trained models.
                       Defaults to MODEL_DIR env var or 'data/models'.
        """
        if model_dir is None:
            model_dir = os.getenv("MODEL_DIR") or "data/models"
        self.model_dir = Path(model_dir)
        self._models: Dict[str, Union[xgb.Booster, "CatBoostClassifier"]] = {}

    def load_model(
        self, stat: str, model_type: str = "xgb"
    ) -> Optional[Union[xgb.Booster, "CatBoostClassifier"]]:
        """
        Load a trained model for a given stat.

        Args:
            stat: The stat to predict ('pts', 'reb', 'ast')
            model_type: 'xgb' for XGBoost or 'catboost' for CatBoost

        Returns:
            Loaded model or None if not found
        """
        cache_key = f"{stat}_{model_type}"

        # Return cached model if available
        if cache_key in self._models:
            return self._models[cache_key]

        stat_key = stat.lower().strip()

        if model_type == "xgb":
            model = self._load_xgboost(stat_key)
        elif model_type == "catboost":
            model = self._load_catboost(stat_key)
        else:
            return None

        if model is not None:
            self._models[cache_key] = model

        return model

    def _load_xgboost(self, stat: str) -> Optional[xgb.Booster]:
        """Load XGBoost model from JSON file."""
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

    def _load_catboost(self, stat: str) -> Optional["CatBoostClassifier"]:
        """Load CatBoost model from CBM file."""
        if not CATBOOST_AVAILABLE:
            return None

        model_path = self.model_dir / f"{stat}_catboost.cbm"
        if not model_path.exists():
            return None

        model = CatBoostClassifier()
        model.load_model(str(model_path))
        return model

    def predict_probability(
        self,
        feature_row: pd.DataFrame,
        stat: str,
        model_type: str = "xgb",
    ) -> Optional[float]:
        """
        Predict the probability of going over the line.

        Args:
            feature_row: DataFrame with feature columns (single row)
            stat: The stat being predicted ('pts', 'reb', 'ast')
            model_type: 'xgb' or 'catboost'

        Returns:
            Probability of over (0.0 to 1.0) or None if model not found
        """
        model = self.load_model(stat, model_type)
        if model is None:
            return None

        # Ensure correct column order
        features = feature_row[FEATURE_COLUMNS]

        if model_type == "xgb":
            dmatrix = xgb.DMatrix(features, feature_names=FEATURE_COLUMNS)
            prob = model.predict(dmatrix)
            return float(prob[0])
        else:
            prob = model.predict_proba(features)
            return float(prob[0, 1])

    def predict_with_both_models(
        self, feature_row: pd.DataFrame, stat: str
    ) -> Dict[str, Optional[float]]:
        """
        Predict using both XGBoost and CatBoost models.

        Args:
            feature_row: DataFrame with feature columns
            stat: The stat being predicted

        Returns:
            Dictionary with 'xgb' and 'catboost' probabilities
        """
        return {
            "xgb": self.predict_probability(feature_row, stat, "xgb"),
            "catboost": self.predict_probability(feature_row, stat, "catboost"),
        }


# Global predictor instance (lazy loaded)
_predictor: Optional[ModelPredictor] = None


def get_predictor() -> ModelPredictor:
    """Get or create the global predictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = ModelPredictor()
    return _predictor


def predict_scenario(
    player_id: int,
    prop_type: str,
    period: int,
    user_line: float,
) -> Dict:
    """
    Predict over/under probabilities for a player prop scenario.

    This is the main entry point for predictions, compatible with
    the existing API contract.

    Args:
        player_id: NBA player ID
        prop_type: Type of prop ('pts', 'reb', 'ast', etc.)
        period: Period (0 for full game, 1-4 for quarters)
        user_line: The betting line value

    Returns:
        Dictionary with projected value and probabilities
    """
    # Note: This function is a bridge to the new classification models.
    # The actual feature fetching happens in views.py via get_model_inputs().
    # This function signature is kept for backward compatibility.
    raise NotImplementedError(
        "Use ModelPredictor.predict_probability() with feature_row instead. "
        "See views.py for the complete inference flow."
    )
