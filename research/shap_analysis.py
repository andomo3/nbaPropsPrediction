"""
SHAP Feature Importance Analysis for NBA Player Prop Models.

Trains the final XGBoost model on all available data (same as production),
then uses SHAP TreeExplainer to explain feature contributions on a held-out
sample from the most recent season (2024).

Outputs per stat (pts / reb / ast):
  research/figures/shap_beeswarm_{stat}.png   — beeswarm summary plot
  research/figures/shap_bar_{stat}.png        — mean |SHAP| bar chart
  research/results/shap_importance_{stat}.csv — ranked feature importance table

Usage:
    pip install shap matplotlib
    cd <repo_root>
    python research/shap_analysis.py
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import shap
except ImportError:
    print("ERROR: shap is not installed. Run: pip install shap")
    sys.exit(1)

# ── Path setup ────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from nba_betting.ml.train_regression import (
    load_and_filter_csv,
    build_player_features,
    build_opponent_defense,
    train_xgboost_regression,
    FEATURE_COLUMNS,
    STAT_TARGET,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

RESULTS_DIR = REPO_ROOT / "research" / "results"
FIGURES_DIR = REPO_ROOT / "research" / "figures"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# Number of test-set rows to run SHAP on (keep low for speed)
SHAP_SAMPLE_SIZE = 5_000
EXPLANATION_YEAR = 2024   # hold-out year for SHAP explanations


def run_shap_analysis(csv_path: str | None = None):
    logger.info("=" * 60)
    logger.info("SHAP Feature Importance Analysis")
    logger.info("=" * 60)

    # ── Load and engineer features once ───────────────────────────────────────
    df = load_and_filter_csv(csv_path)
    logger.info("Building player rolling features ...")
    df = build_player_features(df)
    logger.info("Building opponent defense features ...")
    df = build_opponent_defense(df)

    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
    else:
        df["year"] = pd.to_datetime(df["date"]).dt.year

    for stat, target_col in STAT_TARGET.items():
        logger.info(f"\n{'─'*60}")
        logger.info(f"  Stat: {stat.upper()}")

        feats = FEATURE_COLUMNS[stat]
        cols  = feats + [target_col]

        # Train on all data except the explanation year
        train_df = df[df["year"] < EXPLANATION_YEAR][cols].dropna()
        expl_df  = df[df["year"] == EXPLANATION_YEAR][cols].dropna()

        if train_df.empty or expl_df.empty:
            logger.warning(f"  [SKIP] insufficient data for {stat}")
            continue

        X_train = train_df[feats].values.astype(np.float32)
        y_train = train_df[target_col].values.astype(np.float32)
        X_expl  = expl_df[feats].values.astype(np.float32)
        y_expl  = expl_df[target_col].values.astype(np.float32)

        logger.info(f"  Training on {len(X_train):,} rows, explaining on {len(X_expl):,} rows")

        # ── Train final model ─────────────────────────────────────────────────
        model, metrics = train_xgboost_regression(
            X_train, y_train, X_expl, y_expl, feats
        )
        logger.info(
            f"  Final model: Test MAE={metrics['test']['mae']:.3f}  "
            f"RMSE={metrics['test']['rmse']:.3f}"
        )

        # ── SHAP on a random sample ───────────────────────────────────────────
        rng = np.random.default_rng(42)
        n_sample = min(SHAP_SAMPLE_SIZE, len(X_expl))
        idx = rng.choice(len(X_expl), size=n_sample, replace=False)
        X_sample = X_expl[idx]

        logger.info(f"  Computing SHAP values on {n_sample:,} samples ...")
        explainer   = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(
            xgb.DMatrix(X_sample, feature_names=feats)
        )   # shape: (n_sample, n_features)

        shap_df = pd.DataFrame(shap_values, columns=feats)

        # ── Ranked importance table ───────────────────────────────────────────
        importance = (
            shap_df.abs()
            .mean()
            .sort_values(ascending=False)
            .reset_index()
            .rename(columns={"index": "feature", 0: "mean_abs_shap"})
        )
        imp_path = RESULTS_DIR / f"shap_importance_{stat}.csv"
        importance.to_csv(imp_path, index=False)
        logger.info(f"  Importance table saved → {imp_path}")
        logger.info(f"  Top 5 features:\n{importance.head(5).to_string(index=False)}")

        # ── Beeswarm plot ─────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(9, 6))
        shap.summary_plot(
            shap_values,
            X_sample,
            feature_names=feats,
            show=False,
            plot_size=None,
        )
        plt.title(f"SHAP Feature Impact — {stat.upper()} Model (Season {EXPLANATION_YEAR})", fontsize=12)
        plt.tight_layout()
        beeswarm_path = FIGURES_DIR / f"shap_beeswarm_{stat}.png"
        plt.savefig(beeswarm_path, dpi=150, bbox_inches="tight")
        plt.close("all")
        logger.info(f"  Beeswarm plot saved → {beeswarm_path}")

        # ── Bar chart (mean |SHAP|) ───────────────────────────────────────────
        top_n = min(15, len(feats))
        top   = importance.head(top_n)
        fig, ax = plt.subplots(figsize=(8, top_n * 0.45 + 1))
        bars = ax.barh(top["feature"][::-1], top["mean_abs_shap"][::-1],
                       color="#2563eb", alpha=0.85)
        ax.set_xlabel("Mean |SHAP value|")
        ax.set_title(f"Feature Importance — {stat.upper()} Model\n(mean absolute SHAP, {EXPLANATION_YEAR} season)")
        ax.grid(axis="x", alpha=0.3)
        fig.tight_layout()
        bar_path = FIGURES_DIR / f"shap_bar_{stat}.png"
        fig.savefig(bar_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"  Bar chart saved → {bar_path}")

    logger.info("\nSHAP analysis complete.")


if __name__ == "__main__":
    run_shap_analysis()
