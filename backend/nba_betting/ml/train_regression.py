"""
Regression-based NBA player props training.

Trains XGBoost (and optionally CatBoost) regression models to predict actual
stat values (pts, reb, ast) from player rolling features + opponent defensive
context.  Replaces the old binary classifier in model_trainer.py.

Data source: data/raw/PlayerStatistics.csv (NBA API historical data).

Usage:
    # Via management command (recommended):
    python manage.py train_models

    # Directly:
    python -m nba_betting.ml.train_regression
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import xgboost as xgb

try:
    from catboost import CatBoostRegressor
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

VALID_GAME_TYPES = {"Regular Season", "Playoffs", "Play-in Tournament"}
MIN_YEAR = 2016      # Filter to modern-era data
MIN_MINUTES = 10     # Exclude DNP / garbage-time rows

# ── Per-stat feature sets ─────────────────────────────────────────────────────
# Keys must match what features.py builds at inference time.

FEATURE_COLUMNS: Dict[str, List[str]] = {
    "pts": [
        "is_home", "days_rest",
        "pts_L5", "pts_L10", "pts_ema_L5", "pts_std_L10",
        "reb_L5", "ast_L5",          # role context
        "min_L5", "min_L10",
        "fg_pct_L5", "fg_pct_L10",
        "season_avg_pts", "hot_cold_pts",
        "opp_pts_allowed_L10",
    ],
    "reb": [
        "is_home", "days_rest",
        "reb_L5", "reb_L10", "reb_ema_L5", "reb_std_L10",
        "pts_L5", "min_L5", "min_L10",
        "season_avg_reb", "hot_cold_reb",
        "opp_reb_allowed_L10",
    ],
    "ast": [
        "is_home", "days_rest",
        "ast_L5", "ast_L10", "ast_ema_L5", "ast_std_L10",
        "pts_L5", "min_L5", "min_L10",
        "fg_pct_L5",
        "season_avg_ast", "hot_cold_ast",
        "opp_ast_allowed_L10",
    ],
}

# CSV column → target variable name
STAT_TARGET: Dict[str, str] = {
    "pts": "points",
    "reb": "reboundsTotal",
    "ast": "assists",
}

XGB_PARAMS: Dict = {
    "objective": "reg:squarederror",
    "max_depth": 6,
    "eta": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "eval_metric": "rmse",
    "seed": 42,
    "nthread": -1,
}


# ── Path helpers ──────────────────────────────────────────────────────────────

def _repo_root() -> Path:
    # __file__ = .../backend/nba_betting/ml/train_regression.py
    # parents[3] = repo root
    return Path(__file__).resolve().parents[3]


def _default_csv_path() -> Path:
    return _repo_root() / "data" / "raw" / "PlayerStatistics.csv"


def _default_model_dir() -> Path:
    return Path(os.getenv("MODEL_DIR", str(_repo_root() / "data" / "models")))


# ── Data loading ──────────────────────────────────────────────────────────────

def _parse_minutes(series: pd.Series) -> pd.Series:
    """Parse numMinutes: handles both float values and 'MM:SS' strings."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    def _convert(val):
        if pd.isna(val):
            return np.nan
        s = str(val).strip()
        if ":" in s:
            parts = s.split(":")
            try:
                return int(parts[0]) + int(parts[1]) / 60.0
            except (ValueError, IndexError):
                return np.nan
        try:
            return float(s)
        except ValueError:
            return np.nan

    return series.apply(_convert)


def load_and_filter_csv(csv_path: Optional[str] = None) -> pd.DataFrame:
    """Load PlayerStatistics.csv, apply game-type / year / minutes filters."""
    if csv_path is None:
        csv_path = str(_default_csv_path())

    logger.info(f"Loading CSV: {csv_path}")
    df = pd.read_csv(csv_path, low_memory=False)
    logger.info(f"  Raw rows: {len(df):,}")

    # Game-type filter
    df = df[df["gameType"].isin(VALID_GAME_TYPES)].copy()

    # Season-year filter
    if "year" in df.columns:
        df = df[pd.to_numeric(df["year"], errors="coerce").fillna(0) >= MIN_YEAR]

    # Minutes
    df["numMinutes"] = _parse_minutes(df["numMinutes"])
    df = df[df["numMinutes"] >= MIN_MINUTES]

    # Parse date (drop timezone suffix, keep just the date)
    df["date"] = pd.to_datetime(
        df["gameDateTimeEst"], utc=True, errors="coerce"
    ).dt.tz_localize(None).dt.normalize()
    df = df.dropna(subset=["date"])

    # is_home flag
    df["is_home"] = pd.to_numeric(df["home"], errors="coerce").fillna(0).astype(int)

    # Ensure numeric stat columns
    for col in ["points", "reboundsTotal", "assists",
                "fieldGoalsMade", "fieldGoalsAttempted", "fieldGoalsPercentage"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # fg_pct derived
    df["fg_pct"] = np.where(
        df["fieldGoalsAttempted"] > 0,
        df["fieldGoalsMade"] / df["fieldGoalsAttempted"],
        0.0,
    )

    # Ensure personId is consistent type
    df["personId"] = df["personId"].astype(str)

    logger.info(f"  After filters: {len(df):,} rows | "
                f"{df['personId'].nunique():,} players | "
                f"{df['date'].dt.year.min()}–{df['date'].dt.year.max()}")
    return df


# ── Feature engineering ───────────────────────────────────────────────────────

def build_player_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add per-player rolling features (shift=1 to prevent leakage).

    Modifies df in-place and returns it.
    """
    df = df.sort_values(["personId", "date"]).reset_index(drop=True)

    grp = df.groupby("personId", sort=False)

    # ── Rolling L5 / L10 means ────────────────────────────────────────────────
    stat_map = [
        ("points",        "pts"),
        ("reboundsTotal", "reb"),
        ("assists",       "ast"),
        ("numMinutes",    "min"),
        ("fg_pct",        "fg_pct"),
    ]
    for col, feat in stat_map:
        for window in (5, 10):
            df[f"{feat}_L{window}"] = grp[col].transform(
                lambda x, w=window: x.shift(1).rolling(w, min_periods=1).mean()
            )

    # ── EMA L5 ────────────────────────────────────────────────────────────────
    for col, feat in [("points", "pts"), ("reboundsTotal", "reb"), ("assists", "ast")]:
        df[f"{feat}_ema_L5"] = grp[col].transform(
            lambda x: x.shift(1).ewm(span=5, adjust=False).mean()
        )

    # ── Std L10 ───────────────────────────────────────────────────────────────
    for col, feat in [("points", "pts"), ("reboundsTotal", "reb"), ("assists", "ast")]:
        df[f"{feat}_std_L10"] = grp[col].transform(
            lambda x: x.shift(1).rolling(10, min_periods=5).std()
        )

    # ── Days rest ─────────────────────────────────────────────────────────────
    df["days_rest"] = (
        grp["date"]
        .transform(lambda x: x.diff().dt.days)
        .fillna(3)
        .clip(upper=10)
        .astype(float)
    )

    # ── Season expanding average (shifted, per player per season year) ────────
    # Derive season_year from the CSV 'year' column if present, else from date.
    # NBA seasons span two calendar years (Oct–Jun); we use the calendar year of
    # the game date as a season proxy, which is consistent across both sources.
    if "year" in df.columns:
        df["_season_year"] = pd.to_numeric(df["year"], errors="coerce")
    else:
        df["_season_year"] = pd.to_datetime(df["date"]).dt.year

    grp_season = df.groupby(["personId", "_season_year"], sort=False)
    for col, feat in [("points", "pts"), ("reboundsTotal", "reb"), ("assists", "ast")]:
        df[f"season_avg_{feat}"] = grp_season[col].transform(
            lambda x: x.shift(1).expanding(min_periods=1).mean()
        )

    # ── Hot / cold streak ─────────────────────────────────────────────────────
    for feat in ["pts", "reb", "ast"]:
        season_avg = df[f"season_avg_{feat}"]
        df[f"hot_cold_{feat}"] = (df[f"{feat}_L5"] - season_avg) / (season_avg.abs() + 0.1)

    return df


def build_opponent_defense(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute rolling 10-game defensive averages per team (pts/reb/ast allowed).

    Logic:
      For each game, sum all player stats grouped by (gameId, opponentteamName).
      The opponentteamName is the DEFENDING team — so the sum is what they allowed.
      Then compute a rolling 10-game avg per defending team (shifted by 1).
    """
    if "opponentteamName" not in df.columns:
        logger.warning("opponentteamName column not found — skipping opponent defense features.")
        for feat in ["opp_pts_allowed_L10", "opp_reb_allowed_L10", "opp_ast_allowed_L10"]:
            df[feat] = np.nan
        return df

    # Aggregate per (game, defending team)
    team_game = (
        df.groupby(["gameId", "opponentteamName", "date"], sort=False)[
            ["points", "reboundsTotal", "assists"]
        ]
        .sum()
        .reset_index()
        .rename(columns={
            "opponentteamName": "def_team",
            "points":           "pts_allowed",
            "reboundsTotal":    "reb_allowed",
            "assists":          "ast_allowed",
        })
        .sort_values(["def_team", "date"])
        .reset_index(drop=True)
    )

    # Rolling 10-game averages for each defending team (shifted by 1)
    grp = team_game.groupby("def_team", sort=False)
    for col, feat in [
        ("pts_allowed", "opp_pts_allowed_L10"),
        ("reb_allowed", "opp_reb_allowed_L10"),
        ("ast_allowed", "opp_ast_allowed_L10"),
    ]:
        team_game[feat] = grp[col].transform(
            lambda x: x.shift(1).rolling(10, min_periods=1).mean()
        )

    # Merge back: each player row gets their opponent's defensive averages
    opp_feats = team_game[
        ["gameId", "def_team", "opp_pts_allowed_L10", "opp_reb_allowed_L10", "opp_ast_allowed_L10"]
    ]
    df = df.merge(
        opp_feats,
        left_on=["gameId", "opponentteamName"],
        right_on=["gameId", "def_team"],
        how="left",
    ).drop(columns=["def_team"])

    return df


# ── Train / test split ────────────────────────────────────────────────────────

def time_split(df: pd.DataFrame, test_frac: float = 0.20) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Chronological split: oldest 80% → train, newest 20% → test."""
    df_sorted = df.sort_values("date")
    split_idx = int(len(df_sorted) * (1 - test_frac))
    split_date = df_sorted.iloc[split_idx]["date"]
    train = df_sorted[df_sorted["date"] < split_date]
    test = df_sorted[df_sorted["date"] >= split_date]
    return train.reset_index(drop=True), test.reset_index(drop=True)


def walk_forward_splits(
    df: pd.DataFrame,
    first_test_year: int = 2021,
    last_test_year: int = 2024,
):
    """
    Generate season-by-season walk-forward folds for research evaluation.

    Each fold trains on all seasons strictly before test_year and tests on
    test_year only.  This mirrors real deployment: the model is retrained once
    per season on all available history.

    Yields:
        (train_df, test_df, test_year)

    Example folds (default):
        Train 2016-2020 → Test 2021
        Train 2016-2021 → Test 2022
        Train 2016-2022 → Test 2023
        Train 2016-2023 → Test 2024
    """
    if "year" not in df.columns:
        if "date" not in df.columns:
            raise ValueError("DataFrame must have a 'year' or 'date' column for walk_forward_splits().")
        df = df.copy()
        df["year"] = pd.to_datetime(df["date"]).dt.year

    df = df.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")

    for test_year in range(first_test_year, last_test_year + 1):
        train = df[df["year"] < test_year].reset_index(drop=True)
        test  = df[df["year"] == test_year].reset_index(drop=True)
        if train.empty or test.empty:
            logger.warning(f"  [WF] Skipping fold {test_year}: train={len(train)}, test={len(test)}")
            continue
        logger.info(
            f"  [WF] Fold test_year={test_year} | "
            f"train={len(train):,} rows ({df[df['year'] < test_year]['year'].min():.0f}–{test_year-1}) | "
            f"test={len(test):,} rows"
        )
        yield train, test, test_year


# ── Model training ────────────────────────────────────────────────────────────

def _eval_regression(preds: np.ndarray, actuals: np.ndarray) -> Dict[str, float]:
    mae = float(np.mean(np.abs(preds - actuals)))
    rmse = float(np.sqrt(np.mean((preds - actuals) ** 2)))
    return {"mae": mae, "rmse": rmse}


def train_xgboost_regression(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: List[str],
    num_rounds: int = 1000,
    early_stopping: int = 50,
) -> Tuple[xgb.Booster, Dict]:
    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=feature_names)
    dtest  = xgb.DMatrix(X_test,  label=y_test,  feature_names=feature_names)

    model = xgb.train(
        XGB_PARAMS,
        dtrain,
        num_boost_round=num_rounds,
        evals=[(dtrain, "train"), (dtest, "eval")],
        early_stopping_rounds=early_stopping,
        verbose_eval=100,
    )

    train_metrics = _eval_regression(model.predict(dtrain), y_train)
    test_metrics  = _eval_regression(model.predict(dtest),  y_test)

    return model, {"train": train_metrics, "test": test_metrics}


def train_catboost_regression(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
) -> Tuple[Optional[object], Dict]:
    if not CATBOOST_AVAILABLE:
        return None, {}

    model = CatBoostRegressor(
        loss_function="RMSE",
        eval_metric="RMSE",
        depth=6,
        learning_rate=0.05,
        iterations=1000,
        early_stopping_rounds=50,
        verbose=100,
        random_seed=42,
    )
    model.fit(
        X_train, y_train,
        eval_set=(X_test, y_test),
        use_best_model=True,
    )

    train_metrics = _eval_regression(model.predict(X_train), y_train)
    test_metrics  = _eval_regression(model.predict(X_test),  y_test)
    return model, {"train": train_metrics, "test": test_metrics}


# ── Main entry point ──────────────────────────────────────────────────────────

def train_all_regression_models(
    csv_path: Optional[str] = None,
    model_dir: Optional[Path] = None,
    skip_catboost: bool = False,
) -> Dict:
    """
    Full training pipeline.

    Returns metadata dict with per-stat metrics.
    """
    if model_dir is None:
        model_dir = _default_model_dir()
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    # ── Load & filter CSV ─────────────────────────────────────────────────────
    df = load_and_filter_csv(csv_path)

    # ── Player rolling features ───────────────────────────────────────────────
    logger.info("Computing per-player rolling features ...")
    df = build_player_features(df)

    # ── Opponent defense features ─────────────────────────────────────────────
    logger.info("Computing opponent defensive rolling averages ...")
    df = build_opponent_defense(df)

    # ── Train / test split ────────────────────────────────────────────────────
    train_df, test_df = time_split(df)
    split_date = test_df["date"].min()
    logger.info(
        f"Split date: {split_date.date()}  |  "
        f"Train: {len(train_df):,}  |  Test: {len(test_df):,}"
    )

    metadata: Dict = {
        "trained_at":   datetime.utcnow().isoformat() + "Z",
        "model_type":   "regression",
        "csv_min_year": MIN_YEAR,
        "split_date":   str(split_date.date()),
        "train_rows":   len(train_df),
        "test_rows":    len(test_df),
        "stats":        {},
    }

    # ── Per-stat training ─────────────────────────────────────────────────────
    for stat, target_col in STAT_TARGET.items():
        feats = FEATURE_COLUMNS[stat]
        logger.info(f"\n{'─'*60}")
        logger.info(f"  Stat: {stat.upper()}  |  Target: {target_col}")
        logger.info(f"  Features ({len(feats)}): {feats}")

        cols_needed = feats + [target_col]
        stat_train = train_df[cols_needed].dropna()
        stat_test  = test_df[cols_needed].dropna()

        if stat_train.empty or stat_test.empty:
            logger.error(f"  [SKIP] No valid rows for {stat} after dropna.")
            continue

        X_train = stat_train[feats].values.astype(np.float32)
        y_train = stat_train[target_col].values.astype(np.float32)
        X_test  = stat_test[feats].values.astype(np.float32)
        y_test  = stat_test[target_col].values.astype(np.float32)

        logger.info(f"  Train rows: {len(X_train):,}  |  Test rows: {len(X_test):,}")

        # XGBoost
        xgb_model, xgb_metrics = train_xgboost_regression(
            X_train, y_train, X_test, y_test, feats
        )
        xgb_path = model_dir / f"{stat}_xgb.json"
        xgb_model.save_model(str(xgb_path))
        logger.info(
            f"  [XGB] Train MAE={xgb_metrics['train']['mae']:.3f}  "
            f"Test MAE={xgb_metrics['test']['mae']:.3f}  "
            f"Test RMSE={xgb_metrics['test']['rmse']:.3f}"
        )
        logger.info(f"  Saved → {xgb_path}")

        # CatBoost (optional)
        cb_metrics: Dict = {}
        if CATBOOST_AVAILABLE and not skip_catboost:
            cb_model, cb_metrics = train_catboost_regression(
                X_train, y_train, X_test, y_test
            )
            if cb_model is not None:
                cb_path = model_dir / f"{stat}_catboost.cbm"
                cb_model.save_model(str(cb_path))
                logger.info(
                    f"  [CB]  Train MAE={cb_metrics['train']['mae']:.3f}  "
                    f"Test MAE={cb_metrics['test']['mae']:.3f}  "
                    f"Test RMSE={cb_metrics['test']['rmse']:.3f}"
                )
                logger.info(f"  Saved → {cb_path}")

        metadata["stats"][stat] = {
            "features":      feats,
            "target":        target_col,
            "train_samples": int(len(X_train)),
            "test_samples":  int(len(X_test)),
            "xgb":           xgb_metrics,
            "catboost":      cb_metrics,
        }

    # ── Save metadata ─────────────────────────────────────────────────────────
    meta_path = model_dir / "model_metadata.json"
    with open(meta_path, "w") as fh:
        json.dump(metadata, fh, indent=2)
    logger.info(f"\nMetadata → {meta_path}")
    logger.info("Training complete.\n")

    return metadata


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    train_all_regression_models()
