"""
Flat-Unit Betting Simulation for NBA Player Props.

Reads walk_forward_predictions.csv produced by walk_forward_eval.py and
simulates betting on OVER/UNDER using the XGBoost model's edge against a
synthetic market line (player's L10 rolling average).

Betting logic:
  - Bet OVER  when xgb_pred > line_proxy + threshold
  - Bet UNDER when xgb_pred < line_proxy - threshold
  - Payout: -110 juice → win = +0.909u, loss = -1.0u
  - Break-even win rate = 52.38%

Thresholds tested: 0.0, 0.5, 1.0, 1.5, 2.0, 2.5 (in stat units)

Outputs:
  research/results/betting_summary.csv      — ROI/win-rate by stat + threshold
  research/figures/pnl_curve_pts.png        — cumulative P&L over time (pts)
  research/figures/pnl_curve_reb.png
  research/figures/pnl_curve_ast.png

Usage:
    cd <repo_root>
    python research/walk_forward_eval.py   # run first if predictions CSV missing
    python research/betting_simulation.py
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")   # headless — no display required
import matplotlib.pyplot as plt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

REPO_ROOT   = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "research" / "results"
FIGURES_DIR = REPO_ROOT / "research" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

WIN_PAYOUT  = 0.9091   # -110 odds: risk 1.1 to win 1.0 → net +0.909 per unit
LOSS_PAYOUT = -1.0
BREAKEVEN   = 0.5238   # 52.38% required at -110
THRESHOLDS  = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]


def simulate_bets(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """
    Return a DataFrame of individual bets for a given edge threshold.

    Columns: game_date, stat, actual, line_proxy, xgb_pred,
             edge, bet_direction, correct, pnl
    """
    df = df.copy()
    df["edge"] = df["xgb_pred"] - df["line_proxy"]

    # Bet OVER when edge > threshold, UNDER when edge < -threshold
    over_mask  = df["edge"] >  threshold
    under_mask = df["edge"] < -threshold
    bet_mask   = over_mask | under_mask

    bets = df[bet_mask].copy()
    bets["bet_direction"] = np.where(bets["edge"] > 0, "OVER", "UNDER")

    # Determine if bet won
    over_won  = (bets["bet_direction"] == "OVER")  & (bets["actual"] > bets["line_proxy"])
    under_won = (bets["bet_direction"] == "UNDER") & (bets["actual"] < bets["line_proxy"])
    # Push when actual == line_proxy: counts as loss (conservative)
    bets["correct"] = over_won | under_won
    bets["pnl"]     = np.where(bets["correct"], WIN_PAYOUT, LOSS_PAYOUT)

    return bets[["game_date", "stat", "actual", "line_proxy", "xgb_pred",
                 "edge", "bet_direction", "correct", "pnl"]]


def summarize_bets(bets: pd.DataFrame, stat: str, threshold: float) -> dict:
    if bets.empty:
        return {}
    n_bets    = len(bets)
    n_won     = bets["correct"].sum()
    win_rate  = n_won / n_bets
    total_pnl = bets["pnl"].sum()
    roi       = total_pnl / n_bets   # return per unit risked
    return {
        "stat":          stat,
        "threshold":     threshold,
        "n_bets":        n_bets,
        "n_won":         int(n_won),
        "win_rate":      round(win_rate, 4),
        "roi":           round(roi, 4),
        "cumulative_pnl": round(total_pnl, 2),
    }


def plot_pnl_curve(all_bets_df: pd.DataFrame, stat: str, best_threshold: float):
    """Plot cumulative P&L over time for the best-performing threshold."""
    bets = simulate_bets(all_bets_df[all_bets_df["stat"] == stat], best_threshold)
    if bets.empty:
        return

    bets = bets.sort_values("game_date")
    bets["cum_pnl"] = bets["pnl"].cumsum()

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(pd.to_datetime(bets["game_date"]), bets["cum_pnl"],
            linewidth=1.5, color="#2563eb")
    ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    ax.fill_between(pd.to_datetime(bets["game_date"]), bets["cum_pnl"], 0,
                    where=bets["cum_pnl"] >= 0, alpha=0.15, color="#22c55e")
    ax.fill_between(pd.to_datetime(bets["game_date"]), bets["cum_pnl"], 0,
                    where=bets["cum_pnl"] < 0,  alpha=0.15, color="#ef4444")

    final_pnl  = bets["cum_pnl"].iloc[-1]
    win_rate   = bets["correct"].mean()
    ax.set_title(
        f"Cumulative P&L — {stat.upper()} | Threshold ±{best_threshold} | "
        f"{len(bets):,} bets | Win rate: {win_rate:.1%} | Final: {final_pnl:+.1f}u",
        fontsize=11,
    )
    ax.set_xlabel("Date")
    ax.set_ylabel("Units")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    out = FIGURES_DIR / f"pnl_curve_{stat}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    logger.info(f"  P&L curve saved → {out}")


def run_simulation(predictions_path: str | None = None):
    if predictions_path is None:
        predictions_path = str(RESULTS_DIR / "walk_forward_predictions.csv")

    logger.info("=" * 60)
    logger.info("Betting Simulation")
    logger.info("=" * 60)

    if not Path(predictions_path).exists():
        logger.error(
            f"Predictions file not found: {predictions_path}\n"
            "Run walk_forward_eval.py first."
        )
        sys.exit(1)

    preds = pd.read_csv(predictions_path, parse_dates=["game_date"])
    logger.info(f"Loaded {len(preds):,} prediction rows from {predictions_path}")

    summary_rows = []

    for stat in ["pts", "reb", "ast"]:
        stat_df = preds[preds["stat"] == stat].copy()
        logger.info(f"\n{'─'*50}")
        logger.info(f"  Stat: {stat.upper()}  ({len(stat_df):,} games)")

        stat_summaries = []
        for threshold in THRESHOLDS:
            bets = simulate_bets(stat_df, threshold)
            row  = summarize_bets(bets, stat, threshold)
            if row:
                stat_summaries.append(row)
                logger.info(
                    f"    threshold={threshold:.1f}  "
                    f"n_bets={row['n_bets']:,}  "
                    f"win_rate={row['win_rate']:.1%}  "
                    f"ROI={row['roi']:+.3f}  "
                    f"P&L={row['cumulative_pnl']:+.1f}u"
                )

        summary_rows.extend(stat_summaries)

        # Plot P&L for the threshold with best ROI
        if stat_summaries:
            best = max(stat_summaries, key=lambda x: x["roi"])
            plot_pnl_curve(preds, stat, best["threshold"])

    summary_df = pd.DataFrame(summary_rows)
    out_path = RESULTS_DIR / "betting_summary.csv"
    summary_df.to_csv(out_path, index=False)
    logger.info(f"\nBetting summary saved → {out_path}")

    # ── Print ROI table ───────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("ROI by Stat × Threshold")
    logger.info("=" * 60)
    pivot = summary_df.pivot_table(
        index="threshold", columns="stat", values="roi", aggfunc="first"
    ).round(4)
    logger.info("\n" + pivot.to_string())
    logger.info(f"\nBreak-even ROI at -110 juice: {BREAKEVEN - 1:.4f} ({BREAKEVEN:.2%} win rate)")

    return summary_df


if __name__ == "__main__":
    run_simulation()
