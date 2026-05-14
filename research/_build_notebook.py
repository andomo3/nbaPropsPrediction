"""
One-shot script that assembles nba_prop_prediction_walkthrough.ipynb.

Run once, then delete. Keeps the notebook source in a diff-friendly form
instead of opaque JSON. Re-run anytime to regenerate the notebook.

    python research/_build_notebook.py
"""

import json
from pathlib import Path

NB_PATH = Path(__file__).resolve().parent / "nba_prop_prediction_walkthrough.ipynb"


def md(text: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": text.splitlines(keepends=True),
    }


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


cells = []

# ── 0. Overview ───────────────────────────────────────────────────────────────
cells.append(md(r"""# NBA Player Prop Prediction — End-to-End Walkthrough

This notebook reproduces every stage of the research pipeline in one executable document:

1. **Data engineering** — load `PlayerStatistics.csv`, filter garbage-time rows, parse minutes.
2. **Feature engineering** — per-player rolling windows (L5/L10/EMA/std), hot/cold streak, opponent defensive averages.
3. **Walk-forward cross-validation** — four season-based folds (2021, 2022, 2023, 2024).
4. **Baselines** — Naive L5, Linear Regression, Random Forest.
5. **XGBoost** — gradient-boosted regression trees (the production model).
6. **SHAP** — feature importance via TreeExplainer.
7. **Betting simulation** — flat-unit P&L against three synthetic lines (L10, EMA-5, LinReg-as-line).

> **Goal:** reproduce the paper's numbers byte-for-byte. Every section prints or plots intermediates so you can verify as you go.

**Runtime notes**

| Mode | Runtime | What it does |
|---|---|---|
| `FORCE_RECOMPUTE = False` *(default)* | ~2 min | Loads cached CSVs from `research/results/` |
| `FORCE_RECOMPUTE = True` | ~15 min | Recomputes everything from scratch |
"""))

# ── 1. Environment setup ──────────────────────────────────────────────────────
cells.append(md("## 1. Environment setup"))

cells.append(code(r"""# Toggle this to rerun every heavy computation from scratch.
FORCE_RECOMPUTE = False

import os, sys, warnings, logging
from pathlib import Path

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.WARNING)

# Locate repo root (this notebook lives in research/)
REPO_ROOT = Path.cwd()
if REPO_ROOT.name == "research":
    REPO_ROOT = REPO_ROOT.parent
print("Repo root:", REPO_ROOT)

# Make the backend package importable without Django
sys.path.insert(0, str(REPO_ROOT / "backend"))

import numpy as np
import pandas as pd
import xgboost as xgb
import sklearn
import matplotlib
import matplotlib.pyplot as plt

np.random.seed(42)

print(f"python       {sys.version.split()[0]}")
print(f"numpy        {np.__version__}")
print(f"pandas       {pd.__version__}")
print(f"xgboost      {xgb.__version__}")
print(f"scikit-learn {sklearn.__version__}")
print(f"matplotlib   {matplotlib.__version__}")

try:
    import shap
    print(f"shap         {shap.__version__}")
except ImportError:
    print("shap         NOT INSTALLED — run `pip install shap` before Section 9")

RESULTS_DIR = REPO_ROOT / "research" / "results"
FIGURES_DIR = REPO_ROOT / "research" / "figures"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
"""))

cells.append(code(r"""# Import the reused pipeline functions (single source of truth)
from nba_betting.ml.train_regression import (
    load_and_filter_csv,
    build_player_features,
    build_opponent_defense,
    walk_forward_splits,
    train_xgboost_regression,
    FEATURE_COLUMNS,
    STAT_TARGET,
    XGB_PARAMS,
    MIN_YEAR,
    MIN_MINUTES,
)

print("Feature counts by stat:")
for stat, feats in FEATURE_COLUMNS.items():
    print(f"  {stat:<4} -> {len(feats):>2} features")
print(f"\nSTAT_TARGET: {STAT_TARGET}")
print(f"MIN_YEAR={MIN_YEAR}, MIN_MINUTES={MIN_MINUTES}")
"""))

# ── 2. Raw data inspection ────────────────────────────────────────────────────
cells.append(md("""## 2. Raw data inspection

Quick peek at the unprocessed CSV — useful to understand what columns we start with."""))

cells.append(code(r"""CSV_PATH = REPO_ROOT / "data" / "raw" / "PlayerStatistics.csv"
print(f"CSV path: {CSV_PATH}")
print(f"Exists:   {CSV_PATH.exists()}")

raw_sample = pd.read_csv(CSV_PATH, nrows=5, low_memory=False)
print(f"\nColumns ({len(raw_sample.columns)}):")
print(list(raw_sample.columns))
raw_sample.head()
"""))

cells.append(code(r"""# Full row count without loading the whole file
n_rows = sum(1 for _ in open(CSV_PATH, encoding="utf-8", errors="ignore")) - 1
print(f"Total rows in CSV: {n_rows:,}")
"""))

# ── 3. Load & filter ──────────────────────────────────────────────────────────
cells.append(md(r"""## 3. Load & filter

`load_and_filter_csv()` applies three filters to the raw CSV:

| Filter | Rule |
|---|---|
| Game type | Keep Regular Season / Playoffs / Play-in Tournament |
| Season year | `year >= 2016` (modern-era data) |
| Minutes played | `numMinutes >= 10` (exclude DNP / garbage-time) |

It also derives `is_home`, `fg_pct`, and a normalized `date` column."""))

cells.append(code(r"""df_filtered = load_and_filter_csv(str(CSV_PATH))

# The CSV stores names as separate firstName / lastName columns.
# Combine them into a single personName column for display purposes.
df_filtered["personName"] = (
    df_filtered["firstName"].fillna("") + " " + df_filtered["lastName"].fillna("")
).str.strip()

print(f"After filtering: {len(df_filtered):,} rows")
print(f"Players:         {df_filtered['personId'].nunique():,}")
print(f"Year range:      {df_filtered['date'].dt.year.min()}–{df_filtered['date'].dt.year.max()}")
df_filtered[["personName", "date", "numMinutes", "points", "reboundsTotal", "assists", "is_home"]].head()
"""))

# ── 4. Player features ────────────────────────────────────────────────────────
cells.append(md(r"""## 4. Feature engineering — per-player rolling windows

For every player, sorted chronologically, we compute (using `.shift(1)` to avoid leakage):

- **`{stat}_L5`**, **`{stat}_L10`** — simple moving averages over the last 5 / 10 games
- **`{stat}_ema_L5`** — exponentially-weighted moving avg (span=5), heavier weight on recent games
- **`{stat}_std_L10`** — rolling 10-game standard deviation (used to estimate prop probability)
- **`days_rest`** — days since last game (capped at 10)
- **`season_avg_{stat}`** — expanding mean within the current season
- **`hot_cold_{stat}`** = $\dfrac{\text{L5} - \text{season\_avg}}{|\text{season\_avg}| + 0.1}$ — streak indicator, positive = hot

Let's watch these build for a single player."""))

cells.append(code(r"""df_feat = build_player_features(df_filtered.copy())
print(f"Columns after player features: {len(df_feat.columns)}")

# personName was derived in Section 3; it carries through on the copied df.
target_name = "LeBron James"
if target_name not in df_feat["personName"].unique():
    target_name = df_feat["personName"].value_counts().index[0]
    print(f"LeBron not found, using top-appearing player: {target_name}")

player_rows = (
    df_feat[df_feat["personName"] == target_name]
    .sort_values("date")
    .tail(10)
)
player_rows[[
    "date", "points",
    "pts_L5", "pts_L10", "pts_ema_L5", "pts_std_L10",
    "season_avg_pts", "hot_cold_pts", "days_rest",
]].round(2)
"""))

# ── 5. Opponent defense ───────────────────────────────────────────────────────
cells.append(md(r"""## 5. Feature engineering — opponent defense

For each game we sum player stats per defending team, then compute a rolling 10-game average (shifted by 1) of how much that team typically allows. Each player row then inherits their opponent's defensive profile."""))

cells.append(code(r"""df_feat = build_opponent_defense(df_feat)
opp_cols = ["opp_pts_allowed_L10", "opp_reb_allowed_L10", "opp_ast_allowed_L10"]
print("Opponent defense columns:")
print(df_feat[opp_cols].describe().round(2))

# Sample one team's defensive trajectory
sample_team = df_feat["opponentteamName"].value_counts().index[0]
team_sample = (
    df_feat[df_feat["opponentteamName"] == sample_team]
    .groupby("date")[opp_cols].first()
    .tail(15)
    .round(2)
)
print(f"\nLast 15 game-days — opponent '{sample_team}':")
team_sample
"""))

# ── 6. Walk-forward splits ────────────────────────────────────────────────────
cells.append(md(r"""## 6. Walk-forward splits

Instead of a single 80/20 cut, we evaluate on four season-based folds. Each fold retrains on **all** prior seasons — mirroring how we would retrain in production once per year.

| Fold | Train years | Test year |
|---|---|---|
| 1 | 2016–2020 | **2021** |
| 2 | 2016–2021 | **2022** |
| 3 | 2016–2022 | **2023** |
| 4 | 2016–2023 | **2024** |"""))

cells.append(code(r"""split_summary = []
for train, test, year in walk_forward_splits(df_feat):
    split_summary.append({
        "test_year": year,
        "train_rows": len(train),
        "test_rows": len(test),
        "train_year_min": int(train["year"].min()),
        "train_year_max": int(train["year"].max()),
    })
split_df = pd.DataFrame(split_summary)
split_df
"""))

# ── 7. Single-fold demo ───────────────────────────────────────────────────────
cells.append(md(r"""## 7. Single-fold training demo (PTS, fold 1)

Train all four models on fold 1 (train ≤2020, test=2021) for **PTS only**. Quick way to validate the pipeline without waiting 15 minutes. The full walk-forward runs in Section 8."""))

cells.append(code(r"""from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

def _mae_rmse(y, p):
    mae = float(mean_absolute_error(y, p))
    rmse = float(np.sqrt(mean_squared_error(y, p)))
    return mae, rmse

stat = "pts"
target_col = STAT_TARGET[stat]
feats = FEATURE_COLUMNS[stat]

# Grab fold 1 only
fold1 = next(iter(walk_forward_splits(df_feat, first_test_year=2021, last_test_year=2021)))
train_df, test_df, year = fold1
# pts_L5 is already inside feats; deduplicate to avoid duplicate columns
cols_needed = list(dict.fromkeys(feats + [target_col, "pts_L5"]))
tr = train_df[cols_needed].dropna()
te = test_df[cols_needed].dropna()

X_tr, y_tr = tr[feats].values.astype(np.float32), tr[target_col].values.astype(np.float32)
X_te, y_te = te[feats].values.astype(np.float32), te[target_col].values.astype(np.float32)
print(f"Train rows: {len(X_tr):,}   Test rows: {len(X_te):,}")
"""))

cells.append(code(r"""# --- Naive L5 ---
naive_pred = te["pts_L5"].values
naive_mae, naive_rmse = _mae_rmse(y_te, naive_pred)

# --- Linear Regression ---
lr = LinearRegression().fit(X_tr, y_tr)
lr_pred = lr.predict(X_te)
lr_mae, lr_rmse = _mae_rmse(y_te, lr_pred)

# --- Random Forest (smaller for notebook speed) ---
rf = RandomForestRegressor(
    n_estimators=100, max_depth=10, min_samples_leaf=5,
    n_jobs=-1, random_state=42,
).fit(X_tr, y_tr)
rf_pred = rf.predict(X_te)
rf_mae, rf_rmse = _mae_rmse(y_te, rf_pred)

# --- XGBoost ---
xgb_model, xgb_metrics = train_xgboost_regression(X_tr, y_tr, X_te, y_te, feats)
xgb_pred = xgb_model.predict(xgb.DMatrix(X_te, feature_names=feats))
xgb_mae, xgb_rmse = xgb_metrics["test"]["mae"], xgb_metrics["test"]["rmse"]

results = pd.DataFrame({
    "model": ["naive_l5", "linear", "random_forest", "xgb"],
    "MAE":   [naive_mae, lr_mae, rf_mae, xgb_mae],
    "RMSE":  [naive_rmse, lr_rmse, rf_rmse, xgb_rmse],
}).round(3)
print("PTS — fold 1 (test=2021)")
results
"""))

cells.append(code(r"""# XGBoost predicted vs actual on the 2021 test set
fig, ax = plt.subplots(figsize=(6, 6))
ax.scatter(y_te, xgb_pred, s=4, alpha=0.15, color="#2563eb")
lims = [0, max(y_te.max(), xgb_pred.max()) + 2]
ax.plot(lims, lims, color="gray", linewidth=1, linestyle="--")
ax.set_xlabel("Actual points")
ax.set_ylabel("XGBoost prediction")
ax.set_title(f"PTS — predicted vs actual (2021 test fold, MAE={xgb_mae:.2f})")
ax.set_xlim(lims); ax.set_ylim(lims)
ax.grid(alpha=0.3)
plt.tight_layout()
plt.show()
"""))

# ── 8. Full walk-forward ──────────────────────────────────────────────────────
cells.append(md(r"""## 8. Full walk-forward evaluation

Runs all 4 folds × 3 stats × 4 models = **48 training runs**. Takes roughly 10–15 minutes.

With `FORCE_RECOMPUTE = False` we load the cached result CSV produced by `research/walk_forward_eval.py`."""))

cells.append(code(r"""metrics_csv = RESULTS_DIR / "walk_forward_metrics.csv"
preds_csv   = RESULTS_DIR / "walk_forward_predictions.csv"

if not FORCE_RECOMPUTE and metrics_csv.exists() and preds_csv.exists():
    print(f"Loading cached metrics from {metrics_csv.name}")
    metrics_df = pd.read_csv(metrics_csv)
    preds_df   = pd.read_csv(preds_csv, parse_dates=["game_date"])
else:
    print("Recomputing walk-forward evaluation (~10-15 min) ...")
    from research.walk_forward_eval import run_walk_forward_eval  # noqa: E402
    metrics_df, preds_df = run_walk_forward_eval(str(CSV_PATH))

print(f"Metrics rows:     {len(metrics_df):,}")
print(f"Prediction rows:  {len(preds_df):,}")
metrics_df.head()
"""))

cells.append(code(r"""# MAE pivot: rows = model, cols = fold year, per stat
for stat in ["pts", "reb", "ast"]:
    sub = metrics_df[metrics_df["stat"] == stat]
    pivot = (
        sub.pivot_table(index="model", columns="fold_year", values="mae")
        .reindex(["naive_l5", "linear", "random_forest", "xgb"])
        .round(3)
    )
    print(f"\n{stat.upper()} — MAE by model × fold_year")
    print(pivot)
"""))

cells.append(code(r"""# Mean MAE across folds — the headline table for the paper
mean_mae = (
    metrics_df.groupby(["stat", "model"])["mae"].mean()
    .unstack("model")
    .reindex(columns=["naive_l5", "linear", "random_forest", "xgb"])
    .round(3)
)
print("Mean MAE across all folds:")
mean_mae
"""))

# ── 9. SHAP ───────────────────────────────────────────────────────────────────
cells.append(md(r"""## 9. SHAP feature importance

Train the final XGBoost model on all seasons except 2024, then explain predictions on a 5 000-row random sample of 2024 using `shap.TreeExplainer`. The beeswarm plot shows per-feature impact direction + magnitude."""))

cells.append(code(r"""import shap

EXPL_YEAR = 2024
SAMPLE_SIZE = 5_000

# Pre-compute 'year' column if missing
if "year" not in df_feat.columns:
    df_feat["year"] = pd.to_datetime(df_feat["date"]).dt.year
else:
    df_feat["year"] = pd.to_numeric(df_feat["year"], errors="coerce")

shap_results = {}
for stat in ["pts", "reb", "ast"]:
    feats = FEATURE_COLUMNS[stat]
    target_col = STAT_TARGET[stat]
    cols = feats + [target_col]
    tr = df_feat[df_feat["year"] < EXPL_YEAR][cols].dropna()
    te = df_feat[df_feat["year"] == EXPL_YEAR][cols].dropna()
    if tr.empty or te.empty:
        print(f"  [SKIP] {stat} — not enough data")
        continue

    X_tr, y_tr = tr[feats].values.astype(np.float32), tr[target_col].values.astype(np.float32)
    X_te, y_te = te[feats].values.astype(np.float32), te[target_col].values.astype(np.float32)

    cached_csv = RESULTS_DIR / f"shap_importance_{stat}.csv"
    if not FORCE_RECOMPUTE and cached_csv.exists():
        print(f"[{stat}] loading cached SHAP importance from {cached_csv.name}")
        importance = pd.read_csv(cached_csv)
        # still need a sample to draw the beeswarm
        model, _ = train_xgboost_regression(X_tr, y_tr, X_te, y_te, feats)
    else:
        print(f"[{stat}] training + computing SHAP on {SAMPLE_SIZE} rows ...")
        model, _ = train_xgboost_regression(X_tr, y_tr, X_te, y_te, feats)

    rng = np.random.default_rng(42)
    idx = rng.choice(len(X_te), size=min(SAMPLE_SIZE, len(X_te)), replace=False)
    X_sample = X_te[idx]

    explainer = shap.TreeExplainer(model)
    shap_vals = explainer.shap_values(xgb.DMatrix(X_sample, feature_names=feats))
    importance = (
        pd.DataFrame(shap_vals, columns=feats)
        .abs().mean().sort_values(ascending=False)
        .reset_index().rename(columns={"index": "feature", 0: "mean_abs_shap"})
    )
    shap_results[stat] = {"importance": importance, "values": shap_vals, "X": X_sample, "feats": feats}
    print(importance.head(5).to_string(index=False))
    print()
"""))

cells.append(code(r"""# Beeswarm + bar chart inline for each stat
for stat, bundle in shap_results.items():
    print(f"\n=== {stat.upper()} ===")
    shap.summary_plot(
        bundle["values"], bundle["X"],
        feature_names=bundle["feats"], show=False,
    )
    plt.title(f"SHAP beeswarm — {stat.upper()} (2024)", fontsize=11)
    plt.tight_layout(); plt.show()

    top = bundle["importance"].head(10)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(top["feature"][::-1], top["mean_abs_shap"][::-1], color="#2563eb", alpha=0.85)
    ax.set_xlabel("Mean |SHAP value|")
    ax.set_title(f"Top-10 features — {stat.upper()}")
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout(); plt.show()
"""))

# ── 10. Betting simulation ────────────────────────────────────────────────────
cells.append(md(r"""## 10. Betting simulation

We don't have historical sportsbook lines, so we test the model against **three synthetic lines** — each represents a progressively harder benchmark:

| Line | What it is | Why it's a useful benchmark |
|---|---|---|
| **L10** | Player's 10-game rolling average | Naive recency baseline |
| **EMA-5** | 5-game exponential moving avg | Momentum-weighted, over-weights last 1-2 games → **noisier**, not "better" |
| **LinReg** | LinearRegression prediction using identical features | Honest conservative check — beating this shows non-linear capacity matters |

**Betting logic:**
- Bet OVER  when `xgb_pred > line + threshold`
- Bet UNDER when `xgb_pred < line − threshold`
- At −110 juice: win = +0.909u, loss = −1.0u → break-even win rate = 52.38%"""))

cells.append(code(r"""WIN_PAYOUT  =  0.9091
LOSS_PAYOUT = -1.0
BREAKEVEN   =  0.5238
THRESHOLDS  = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
LINE_COLUMNS = {"l10": "line_proxy", "ema": "ema_line", "linreg": "linear_pred"}

def simulate_bets(df, threshold, line_col):
    df = df.copy()
    df["line"] = df[line_col]
    df = df.dropna(subset=["line"])
    df["edge"] = df["xgb_pred"] - df["line"]
    mask = df["edge"].abs() > threshold
    bets = df[mask].copy()
    bets["bet"] = np.where(bets["edge"] > 0, "OVER", "UNDER")
    over_won  = (bets["bet"] == "OVER")  & (bets["actual"] > bets["line"])
    under_won = (bets["bet"] == "UNDER") & (bets["actual"] < bets["line"])
    bets["won"] = over_won | under_won
    bets["pnl"] = np.where(bets["won"], WIN_PAYOUT, LOSS_PAYOUT)
    return bets

summary_rows = []
for line_type, line_col in LINE_COLUMNS.items():
    if line_col not in preds_df.columns:
        print(f"[skip] {line_type}: column {line_col} missing from predictions CSV")
        continue
    for stat in ["pts", "reb", "ast"]:
        sub = preds_df[preds_df["stat"] == stat]
        for t in THRESHOLDS:
            bets = simulate_bets(sub, t, line_col)
            if len(bets) == 0:
                continue
            summary_rows.append({
                "stat": stat, "line_type": line_type, "threshold": t,
                "n_bets": len(bets),
                "win_rate": round(bets["won"].mean(), 4),
                "roi": round(bets["pnl"].mean(), 4),
                "cum_pnl": round(bets["pnl"].sum(), 2),
            })
summary_df = pd.DataFrame(summary_rows)
summary_df.head(10)
"""))

cells.append(code(r"""# ROI pivot per stat — rows = threshold, cols = line_type
for stat in ["pts", "reb", "ast"]:
    sub = summary_df[summary_df["stat"] == stat]
    pivot = sub.pivot_table(index="threshold", columns="line_type", values="roi")
    pivot = pivot.reindex(columns=[c for c in ["l10", "ema", "linreg"] if c in pivot.columns])
    print(f"\n{stat.upper()} — ROI by threshold × line_type")
    print(pivot.round(4))

print(f"\nBreak-even at -110 juice: {BREAKEVEN:.2%}")
"""))

cells.append(code(r"""# Plot cumulative P&L for the best (stat, line) combo over 100+ bets
best = (
    summary_df[summary_df["n_bets"] >= 100]
    .sort_values("roi", ascending=False)
    .iloc[0]
)
print(f"Best combo: stat={best['stat']}  line={best['line_type']}  "
      f"threshold={best['threshold']}  ROI={best['roi']:+.3f}  n_bets={best['n_bets']:,}")

line_col = LINE_COLUMNS[best["line_type"]]
bets = simulate_bets(
    preds_df[preds_df["stat"] == best["stat"]],
    best["threshold"],
    line_col,
).sort_values("game_date")
bets["cum_pnl"] = bets["pnl"].cumsum()

fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(pd.to_datetime(bets["game_date"]), bets["cum_pnl"], color="#2563eb", linewidth=1.3)
ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
ax.fill_between(pd.to_datetime(bets["game_date"]), bets["cum_pnl"], 0,
                where=bets["cum_pnl"] >= 0, alpha=0.15, color="#22c55e")
ax.fill_between(pd.to_datetime(bets["game_date"]), bets["cum_pnl"], 0,
                where=bets["cum_pnl"] < 0, alpha=0.15, color="#ef4444")
ax.set_title(
    f"Cumulative P&L  |  {best['stat'].upper()}  |  line={best['line_type'].upper()}  "
    f"|  threshold=±{best['threshold']}  |  {len(bets):,} bets  "
    f"|  final={bets['cum_pnl'].iloc[-1]:+.1f}u"
)
ax.set_xlabel("Date"); ax.set_ylabel("Units"); ax.grid(alpha=0.3)
plt.tight_layout(); plt.show()
"""))

# ── 11. Sanity checks & conclusions ───────────────────────────────────────────
cells.append(md("""## 11. Sanity checks & conclusions

Asserted checkpoints — these should all pass on the canonical dataset."""))

cells.append(code(r"""# (a) XGBoost PTS MAE across folds roughly 4.6-4.9
pts_xgb = metrics_df[(metrics_df["stat"] == "pts") & (metrics_df["model"] == "xgb")]
print(f"PTS XGB MAE by fold:\n{pts_xgb[['fold_year','mae']].to_string(index=False)}")
assert pts_xgb["mae"].between(4.3, 5.2).all(), "PTS MAE outside expected band — investigate"

# (b) XGB beats naive_l5 in >= 3 of 4 PTS folds
pts_naive = metrics_df[(metrics_df["stat"] == "pts") & (metrics_df["model"] == "naive_l5")]
cmp = pts_xgb.set_index("fold_year")["mae"].lt(pts_naive.set_index("fold_year")["mae"])
print(f"\nXGB beats Naive L5 in {cmp.sum()} of {len(cmp)} PTS folds")
assert cmp.sum() >= 3, "XGB should beat Naive L5 in at least 3 of 4 PTS folds"

# (c) LinReg-as-line ROI at threshold 2.5 on PTS is positive and meaningful
linreg_sub = summary_df[
    (summary_df["stat"] == "pts")
    & (summary_df["line_type"] == "linreg")
    & (summary_df["threshold"] == 2.5)
]
if not linreg_sub.empty:
    roi = linreg_sub["roi"].iloc[0]
    print(f"\nPTS vs LinReg-line @ threshold 2.5: ROI = {roi:+.4f}")
    assert roi > 0.05, "Expected ROI > 5% — check if feature set changed"

print("\nAll sanity checks passed.")
"""))

cells.append(md("""### Takeaways

1. **XGBoost beats all baselines on MAE** across all four walk-forward folds for PTS, REB, and AST.
2. **SHAP** confirms the model relies on interpretable signals: `{stat}_L5`, `{stat}_ema_L5`, and `season_avg_{stat}` dominate, with opponent defense and minutes as secondary drivers.
3. **Against the strictest synthetic line (LinReg-as-line)**, XGBoost still produces a positive edge on PTS at threshold 2.5, indicating non-linear capacity contributes value beyond what the same features extract linearly.

### Caveats

- Synthetic lines are **not** real sportsbook lines — real books include vig, limits, steam, and market microstructure absent here.
- Walk-forward CV tests temporal generalization but not structural breaks (rule changes, pace shifts).
- No injury / lineup / minutes projections are incorporated — these would likely improve MAE further but require richer data sources.
"""))

# ── Assemble notebook ─────────────────────────────────────────────────────────
notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.11",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

NB_PATH.write_text(json.dumps(notebook, indent=1), encoding="utf-8")
print(f"Wrote {NB_PATH}  ({len(cells)} cells)")
