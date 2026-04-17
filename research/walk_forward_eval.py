"""
Walk-Forward Cross-Validation for NBA Player Prop Regression Models.

Evaluates four models per stat (pts/reb/ast) across four season-based folds:
  - Naive L5     : predict player's last-5-game rolling average (zero ML)
  - Linear Reg   : sklearn LinearRegression, same features as XGBoost
  - Random Forest: sklearn RandomForestRegressor, same features
  - XGBoost      : gradient boosting regression (production model)

Outputs:
  research/results/walk_forward_metrics.csv   — MAE/RMSE per model/stat/fold
  research/results/walk_forward_predictions.csv — per-row predictions (feeds betting sim)

Usage:
    cd <repo_root>
    python research/walk_forward_eval.py
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

# ── Path setup: allow importing from backend without installing Django ─────────
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from nba_betting.ml.train_regression import (
    load_and_filter_csv,
    build_player_features,
    build_opponent_defense,
    walk_forward_splits,
    train_xgboost_regression,
    FEATURE_COLUMNS,
    STAT_TARGET,
    XGB_PARAMS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

RESULTS_DIR = REPO_ROOT / "research" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Naive L5 feature name per stat
NAIVE_L5_FEATURE = {"pts": "pts_L5", "reb": "reb_L5", "ast": "ast_L5"}
# Primary synthetic line: L10 rolling average
LINE_PROXY_FEATURE = {"pts": "pts_L10", "reb": "reb_L10", "ast": "ast_L10"}
# Secondary synthetic line: EMA-5 (momentum-weighted, more market-realistic)
EMA_LINE_FEATURE   = {"pts": "pts_ema_L5", "reb": "reb_ema_L5", "ast": "ast_ema_L5"}


def _mae_rmse(actual: np.ndarray, pred: np.ndarray):
    mae  = float(mean_absolute_error(actual, pred))
    rmse = float(np.sqrt(mean_squared_error(actual, pred)))
    return mae, rmse


def evaluate_fold(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    test_year: int,
    stat: str,
    target_col: str,
) -> tuple[list[dict], pd.DataFrame]:
    """
    Train and evaluate all four models for one (stat, fold) combination.

    Returns:
        metrics_rows  — list of metric dicts (one per model)
        pred_rows_df  — DataFrame with per-game predictions for the betting sim
    """
    feats = FEATURE_COLUMNS[stat]
    naive_feat = NAIVE_L5_FEATURE[stat]
    line_feat  = LINE_PROXY_FEATURE[stat]
    ema_feat   = EMA_LINE_FEATURE[stat]

    cols_needed = feats + [target_col, naive_feat, line_feat, ema_feat, "personId", "date"]
    # date may already be in feats for some paths — deduplicate
    cols_needed = list(dict.fromkeys(cols_needed))

    stat_train = train_df[cols_needed].dropna()
    stat_test  = test_df[cols_needed].dropna()

    if stat_train.empty or stat_test.empty:
        logger.warning(f"  [SKIP] {stat.upper()} fold {test_year} — no valid rows after dropna")
        return [], pd.DataFrame()

    X_train = stat_train[feats].values.astype(np.float32)
    y_train = stat_train[target_col].values.astype(np.float32)
    X_test  = stat_test[feats].values.astype(np.float32)
    y_test  = stat_test[target_col].values.astype(np.float32)

    metrics_rows = []

    # ── 1. Naive L5 ───────────────────────────────────────────────────────────
    naive_pred = stat_test[naive_feat].values.astype(np.float32)
    mae, rmse = _mae_rmse(y_test, naive_pred)
    metrics_rows.append({"stat": stat, "model": "naive_l5", "fold_year": test_year,
                          "mae": round(mae, 4), "rmse": round(rmse, 4), "n_samples": len(y_test)})
    logger.info(f"    naive_l5   MAE={mae:.3f}  RMSE={rmse:.3f}")

    # ── 2. Linear Regression ──────────────────────────────────────────────────
    lr = LinearRegression()
    lr.fit(X_train, y_train)
    lr_pred = lr.predict(X_test).astype(np.float32)
    mae, rmse = _mae_rmse(y_test, lr_pred)
    metrics_rows.append({"stat": stat, "model": "linear", "fold_year": test_year,
                          "mae": round(mae, 4), "rmse": round(rmse, 4), "n_samples": len(y_test)})
    logger.info(f"    linear     MAE={mae:.3f}  RMSE={rmse:.3f}")

    # ── 3. Random Forest ──────────────────────────────────────────────────────
    rf = RandomForestRegressor(
        n_estimators=200,
        max_depth=10,
        min_samples_leaf=5,
        n_jobs=-1,
        random_state=42,
    )
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test).astype(np.float32)
    mae, rmse = _mae_rmse(y_test, rf_pred)
    metrics_rows.append({"stat": stat, "model": "random_forest", "fold_year": test_year,
                          "mae": round(mae, 4), "rmse": round(rmse, 4), "n_samples": len(y_test)})
    logger.info(f"    random_forest  MAE={mae:.3f}  RMSE={rmse:.3f}")

    # ── 4. XGBoost ────────────────────────────────────────────────────────────
    xgb_model, xgb_metrics = train_xgboost_regression(
        X_train, y_train, X_test, y_test, feats
    )
    xgb_pred = xgb_model.predict(
        __import__("xgboost").DMatrix(X_test, feature_names=feats)
    ).astype(np.float32)
    mae  = xgb_metrics["test"]["mae"]
    rmse = xgb_metrics["test"]["rmse"]
    metrics_rows.append({"stat": stat, "model": "xgb", "fold_year": test_year,
                          "mae": round(mae, 4), "rmse": round(rmse, 4), "n_samples": len(y_test)})
    logger.info(f"    xgb        MAE={mae:.3f}  RMSE={rmse:.3f}")

    # ── Build per-game prediction rows ────────────────────────────────────────
    pred_df = pd.DataFrame({
        "personId":     stat_test["personId"].values,
        "game_date":    stat_test["date"].values,
        "fold_year":    test_year,
        "stat":         stat,
        "actual":       y_test,
        "line_proxy":   stat_test[line_feat].values.astype(np.float32),
        "ema_line":     stat_test[ema_feat].values.astype(np.float32),
        "naive_l5_pred": naive_pred,
        "linear_pred":  lr_pred,
        "rf_pred":      rf_pred,
        "xgb_pred":     xgb_pred,
    })

    return metrics_rows, pred_df


def run_walk_forward_eval(csv_path: str | None = None):
    logger.info("=" * 60)
    logger.info("Walk-Forward Evaluation")
    logger.info("=" * 60)

    # ── Load & feature-engineer the full dataset once ─────────────────────────
    df = load_and_filter_csv(csv_path)
    logger.info("Building player rolling features ...")
    df = build_player_features(df)
    logger.info("Building opponent defense features ...")
    df = build_opponent_defense(df)

    all_metrics  = []
    all_pred_dfs = []

    for stat, target_col in STAT_TARGET.items():
        logger.info(f"\n{'─'*60}")
        logger.info(f"Stat: {stat.upper()}")

        for train_df, test_df, test_year in walk_forward_splits(df):
            logger.info(f"  Fold {test_year}  (train={len(train_df):,}, test={len(test_df):,})")
            metrics_rows, pred_df = evaluate_fold(
                train_df, test_df, test_year, stat, target_col
            )
            all_metrics.extend(metrics_rows)
            if not pred_df.empty:
                all_pred_dfs.append(pred_df)

    # ── Save metrics ──────────────────────────────────────────────────────────
    metrics_df = pd.DataFrame(all_metrics)
    metrics_path = RESULTS_DIR / "walk_forward_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)
    logger.info(f"\nMetrics saved → {metrics_path}")

    # ── Save per-game predictions ─────────────────────────────────────────────
    preds_df = pd.concat(all_pred_dfs, ignore_index=True)
    preds_path = RESULTS_DIR / "walk_forward_predictions.csv"
    preds_df.to_csv(preds_path, index=False)
    logger.info(f"Predictions saved → {preds_path}")

    # ── Print summary table ───────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY — Mean MAE across folds")
    logger.info("=" * 60)
    summary = (
        metrics_df.groupby(["stat", "model"])["mae"]
        .mean()
        .round(4)
        .unstack("model")
        .reindex(columns=["naive_l5", "linear", "random_forest", "xgb"])
    )
    logger.info("\n" + summary.to_string())

    return metrics_df, preds_df


if __name__ == "__main__":
    run_walk_forward_eval()
