"""
Visualization module for model training diagnostics.

Generates plots to diagnose model performance, detect overfitting/underfitting,
and visualize feature importance.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    RocCurveDisplay,
    confusion_matrix,
    roc_curve,
)

try:
    from catboost import CatBoostClassifier
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False


# Set style for all plots
plt.style.use("seaborn-v0_8-whitegrid")


class TrainingVisualizer:
    """Generates diagnostic plots for model training."""

    def __init__(self, plots_dir: str = "data/plots"):
        """
        Initialize the visualizer.

        Args:
            plots_dir: Directory to save plots
        """
        self.plots_dir = Path(plots_dir)
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y-%m-%d")

    def _save_plot(self, name: str) -> str:
        """Save the current plot and return the path."""
        filename = f"{name}_{self.timestamp}.png"
        path = self.plots_dir / filename
        plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
        print(f"  Saved: {path}")
        return str(path)

    def plot_learning_curves(
        self,
        evals_result: Dict,
        stat: str,
        model_type: str,
        metric: str = "logloss",
    ) -> str:
        """
        Plot training vs validation loss over iterations.

        Args:
            evals_result: Dictionary with 'train' and 'val' keys containing metrics
            stat: Stat being predicted ('pts', 'reb', 'ast')
            model_type: 'xgb' or 'catboost'
            metric: Metric to plot ('logloss', 'auc', etc.)

        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        if "train" in evals_result and metric in evals_result["train"]:
            train_metric = evals_result["train"][metric]
            val_metric = evals_result["val"][metric]
            iterations = range(1, len(train_metric) + 1)

            ax.plot(iterations, train_metric, label="Train", linewidth=2)
            ax.plot(iterations, val_metric, label="Validation", linewidth=2)

            # Find best iteration
            if "logloss" in metric.lower() or "loss" in metric.lower():
                best_iter = np.argmin(val_metric) + 1
                best_val = min(val_metric)
            else:
                best_iter = np.argmax(val_metric) + 1
                best_val = max(val_metric)

            ax.axvline(best_iter, color="red", linestyle="--", alpha=0.7, 
                      label=f"Best iteration: {best_iter}")

            # Add gap annotation for overfitting detection
            final_train = train_metric[-1]
            final_val = val_metric[-1]
            gap = abs(final_train - final_val)
            gap_pct = gap / abs(final_val) * 100 if final_val != 0 else 0

            # Overfitting indicator
            if gap_pct > 10:
                status = "⚠️ Possible overfitting"
                color = "red"
            elif gap_pct > 5:
                status = "⚡ Mild gap"
                color = "orange"
            else:
                status = "✓ Good fit"
                color = "green"

            ax.text(0.98, 0.02, f"Train-Val Gap: {gap:.4f} ({gap_pct:.1f}%)\n{status}",
                   transform=ax.transAxes, ha="right", va="bottom",
                   fontsize=10, color=color,
                   bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

        ax.set_xlabel("Iterations", fontsize=12)
        ax.set_ylabel(metric.replace("_", " ").title(), fontsize=12)
        ax.set_title(f"{model_type.upper()} Learning Curve - {stat.upper()}", fontsize=14)
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)

        return self._save_plot(f"{stat}_{model_type}_learning_curve")

    def plot_roc_curves(
        self,
        results: Dict[str, Tuple[np.ndarray, np.ndarray, float]],
        stat: str,
    ) -> str:
        """
        Plot ROC curves comparing multiple models.

        Args:
            results: Dict of {model_name: (y_true, y_prob, auc_score)}
            stat: Stat being predicted

        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=(8, 8))

        colors = {"xgb": "#1f77b4", "catboost": "#ff7f0e", "xgboost": "#1f77b4"}

        for model_name, (y_true, y_prob, auc) in results.items():
            fpr, tpr, _ = roc_curve(y_true, y_prob)
            color = colors.get(model_name.lower(), "#2ca02c")
            ax.plot(fpr, tpr, label=f"{model_name} (AUC = {auc:.3f})",
                   linewidth=2, color=color)

        # Diagonal reference line
        ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="Random (AUC = 0.500)")

        ax.set_xlabel("False Positive Rate", fontsize=12)
        ax.set_ylabel("True Positive Rate", fontsize=12)
        ax.set_title(f"ROC Curves - {stat.upper()}", fontsize=14)
        ax.legend(loc="lower right")
        ax.set_xlim([0, 1])
        ax.set_ylim([0, 1.05])
        ax.grid(True, alpha=0.3)

        return self._save_plot(f"{stat}_roc_curves")

    def plot_calibration_curves(
        self,
        results: Dict[str, Tuple[np.ndarray, np.ndarray]],
        stat: str,
    ) -> str:
        """
        Plot calibration curves comparing multiple models.

        Args:
            results: Dict of {model_name: (y_true, y_prob)}
            stat: Stat being predicted

        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=(8, 8))

        colors = {"xgb": "#1f77b4", "catboost": "#ff7f0e", "xgboost": "#1f77b4"}

        for model_name, (y_true, y_prob) in results.items():
            prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=10)
            color = colors.get(model_name.lower(), "#2ca02c")
            ax.plot(prob_pred, prob_true, marker="o", label=model_name,
                   linewidth=2, color=color, markersize=8)

        # Perfect calibration line
        ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="Perfect calibration")

        ax.set_xlabel("Mean Predicted Probability", fontsize=12)
        ax.set_ylabel("Fraction of Positives", fontsize=12)
        ax.set_title(f"Calibration Curves - {stat.upper()}", fontsize=14)
        ax.legend(loc="upper left")
        ax.set_xlim([0, 1])
        ax.set_ylim([0, 1])
        ax.grid(True, alpha=0.3)

        return self._save_plot(f"{stat}_calibration_curves")

    def plot_confusion_matrix(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        stat: str,
        model_type: str,
    ) -> str:
        """
        Plot confusion matrix.

        Args:
            y_true: True labels
            y_pred: Predicted labels
            stat: Stat being predicted
            model_type: 'xgb' or 'catboost'

        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=(8, 6))

        cm = confusion_matrix(y_true, y_pred)
        disp = ConfusionMatrixDisplay(cm, display_labels=["Under", "Over"])
        disp.plot(ax=ax, cmap="Blues", values_format="d")

        ax.set_title(f"{model_type.upper()} Confusion Matrix - {stat.upper()}", fontsize=14)

        return self._save_plot(f"{stat}_{model_type}_confusion_matrix")

    def plot_feature_importance(
        self,
        importance_dict: Dict[str, float],
        stat: str,
        model_type: str,
        top_n: int = 15,
    ) -> str:
        """
        Plot feature importance as horizontal bar chart.

        Args:
            importance_dict: Dict of {feature_name: importance_score}
            stat: Stat being predicted
            model_type: 'xgb' or 'catboost'
            top_n: Number of top features to show

        Returns:
            Path to saved plot
        """
        # Sort by importance
        sorted_features = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
        top_features = sorted_features[:top_n]

        features = [f[0] for f in top_features][::-1]  # Reverse for horizontal bar
        importances = [f[1] for f in top_features][::-1]

        fig, ax = plt.subplots(figsize=(10, 8))

        colors = plt.cm.Blues(np.linspace(0.4, 0.8, len(features)))[::-1]
        bars = ax.barh(features, importances, color=colors)

        # Add value labels
        for bar, imp in zip(bars, importances):
            ax.text(bar.get_width() + max(importances) * 0.01, bar.get_y() + bar.get_height()/2,
                   f"{imp:.3f}", va="center", fontsize=9)

        ax.set_xlabel("Importance Score", fontsize=12)
        ax.set_title(f"{model_type.upper()} Feature Importance - {stat.upper()}", fontsize=14)
        ax.grid(True, alpha=0.3, axis="x")

        return self._save_plot(f"{stat}_{model_type}_feature_importance")

    def plot_feature_importance_comparison(
        self,
        xgb_importance: Dict[str, float],
        catboost_importance: Dict[str, float],
        stat: str,
        top_n: int = 10,
    ) -> str:
        """
        Compare feature importance between XGBoost and CatBoost.

        Args:
            xgb_importance: XGBoost importance scores
            catboost_importance: CatBoost importance scores
            stat: Stat being predicted
            top_n: Number of top features to show

        Returns:
            Path to saved plot
        """
        # Get union of top features from both models
        xgb_top = set(f[0] for f in sorted(xgb_importance.items(), 
                                           key=lambda x: x[1], reverse=True)[:top_n])
        cat_top = set(f[0] for f in sorted(catboost_importance.items(), 
                                           key=lambda x: x[1], reverse=True)[:top_n])
        all_features = list(xgb_top | cat_top)

        # Normalize importance scores
        xgb_max = max(xgb_importance.values()) if xgb_importance else 1
        cat_max = max(catboost_importance.values()) if catboost_importance else 1

        xgb_normalized = {k: v/xgb_max for k, v in xgb_importance.items()}
        cat_normalized = {k: v/cat_max for k, v in catboost_importance.items()}

        # Sort by average importance
        avg_importance = {f: (xgb_normalized.get(f, 0) + cat_normalized.get(f, 0)) / 2 
                         for f in all_features}
        sorted_features = sorted(avg_importance.keys(), key=lambda x: avg_importance[x])

        fig, ax = plt.subplots(figsize=(12, 8))

        y_pos = np.arange(len(sorted_features))
        width = 0.35

        xgb_vals = [xgb_normalized.get(f, 0) for f in sorted_features]
        cat_vals = [cat_normalized.get(f, 0) for f in sorted_features]

        ax.barh(y_pos - width/2, xgb_vals, width, label="XGBoost", color="#1f77b4", alpha=0.8)
        ax.barh(y_pos + width/2, cat_vals, width, label="CatBoost", color="#ff7f0e", alpha=0.8)

        ax.set_yticks(y_pos)
        ax.set_yticklabels(sorted_features)
        ax.set_xlabel("Normalized Importance", fontsize=12)
        ax.set_title(f"Feature Importance Comparison - {stat.upper()}", fontsize=14)
        ax.legend(loc="lower right")
        ax.grid(True, alpha=0.3, axis="x")

        return self._save_plot(f"{stat}_feature_importance_comparison")

    def plot_prediction_distribution(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        stat: str,
        model_type: str,
    ) -> str:
        """
        Plot distribution of predicted probabilities by actual outcome.

        Args:
            y_true: True labels
            y_prob: Predicted probabilities
            stat: Stat being predicted
            model_type: 'xgb' or 'catboost'

        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        # Separate predictions by actual outcome
        under_probs = y_prob[y_true == 0]
        over_probs = y_prob[y_true == 1]

        bins = np.linspace(0, 1, 21)

        ax.hist(under_probs, bins=bins, alpha=0.6, label=f"Actual Under (n={len(under_probs)})", 
               color="#d62728", edgecolor="black")
        ax.hist(over_probs, bins=bins, alpha=0.6, label=f"Actual Over (n={len(over_probs)})", 
               color="#2ca02c", edgecolor="black")

        ax.axvline(0.5, color="black", linestyle="--", linewidth=2, label="Decision boundary")

        ax.set_xlabel("Predicted Probability (Over)", fontsize=12)
        ax.set_ylabel("Count", fontsize=12)
        ax.set_title(f"{model_type.upper()} Prediction Distribution - {stat.upper()}", fontsize=14)
        ax.legend(loc="upper center")
        ax.grid(True, alpha=0.3)

        return self._save_plot(f"{stat}_{model_type}_prediction_dist")

    def plot_metrics_summary(
        self,
        all_metrics: Dict[str, Dict[str, Dict]],
    ) -> str:
        """
        Plot summary of all metrics across stats and models.

        Args:
            all_metrics: Nested dict {stat: {model_type: {metric: value}}}

        Returns:
            Path to saved plot
        """
        stats = list(all_metrics.keys())
        model_types = ["xgboost", "catboost"]
        metrics = ["accuracy", "auc_roc", "log_loss", "brier_score"]

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        axes = axes.flatten()

        for idx, metric in enumerate(metrics):
            ax = axes[idx]
            x = np.arange(len(stats))
            width = 0.35

            xgb_vals = [all_metrics[s].get("xgboost", {}).get(metric, 0) for s in stats]
            cat_vals = [all_metrics[s].get("catboost", {}).get(metric, 0) for s in stats]

            bars1 = ax.bar(x - width/2, xgb_vals, width, label="XGBoost", color="#1f77b4")
            bars2 = ax.bar(x + width/2, cat_vals, width, label="CatBoost", color="#ff7f0e")

            # Add value labels
            for bar in bars1:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                       f"{bar.get_height():.3f}", ha="center", va="bottom", fontsize=9)
            for bar in bars2:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                       f"{bar.get_height():.3f}", ha="center", va="bottom", fontsize=9)

            ax.set_xlabel("Stat")
            ax.set_ylabel(metric.replace("_", " ").title())
            ax.set_title(metric.replace("_", " ").title())
            ax.set_xticks(x)
            ax.set_xticklabels([s.upper() for s in stats])
            ax.legend()
            ax.grid(True, alpha=0.3, axis="y")

        plt.suptitle("Model Performance Summary", fontsize=16, y=1.02)
        plt.tight_layout()

        return self._save_plot("metrics_summary")


def get_xgb_feature_importance(model: xgb.Booster, importance_type: str = "gain") -> Dict[str, float]:
    """Extract feature importance from XGBoost model."""
    score = model.get_score(importance_type=importance_type)
    return score


def get_catboost_feature_importance(
    model: "CatBoostClassifier", 
    feature_names: List[str]
) -> Dict[str, float]:
    """Extract feature importance from CatBoost model."""
    importances = model.get_feature_importance()
    return dict(zip(feature_names, importances))
