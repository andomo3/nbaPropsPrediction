# Perchance — System Architecture

> Last updated: 2026-07-03. Describes the current production system: per-stat **regression** models
> (the earlier binary over/under classifier is retired — see [History](#11-history)).
> Statistical methodology, validation tests, and assumptions are covered by
> [`docs/METHODOLOGY.md`](METHODOLOGY.md).

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Tech Stack](#2-tech-stack)
3. [Data Flow — End to End](#3-data-flow--end-to-end)
4. [ML Pipeline](#4-ml-pipeline)
5. [Feature Engineering](#5-feature-engineering)
6. [Probability Derivation](#6-probability-derivation)
7. [API Reference](#7-api-reference)
8. [Backtesting](#8-backtesting)
9. [Deployment Architecture](#9-deployment-architecture)
10. [Known Limitations](#10-known-limitations)
11. [History](#11-history)

---

## 1. System Overview

Perchance is a full-stack NBA player-props analysis platform. For a chosen player,
stat (points, rebounds, or assists), and opponent, it:

1. **Projects the stat value** with a per-stat XGBoost regression model
   (`backend/nba_betting/ml/train_regression.py`, served by `backend/nba_betting/ml/predictor.py`).
2. **Derives a probability** of clearing a given line from that projection
   (`backend/nba_betting/services/probability.py`).
3. **Backtests** the model against each player's historical game log
   (`backend/nba_betting/services/backtest.py`), and layers intelligence analyses
   (statistical validation, edge calibration, floor/ceiling, opponent splits, variance
   decomposition) on top of the backtest results.

The models predict **actual stat values** (regression), not over/under labels. Over/under
recommendations and probabilities are derived downstream by comparing the projection to a line.

---

## 2. Tech Stack

### Backend
- **Django 5 + Django REST Framework** — API server (`backend/requirements.txt`: `Django>=5.0`)
- **PostgreSQL** — primary database
- **Redis** — response cache for the intelligence/season endpoints (24 h TTL, `backend/backend/settings.py`)
- **Gunicorn + Whitenoise** — production serving
- **django-cors-headers, dj-database-url** — CORS / DB URL parsing

### ML
- **XGBoost** — primary regressor (`reg:squarederror`), one model per stat
- **Random Forest, Linear Regression** (scikit-learn) and **CatBoost** — comparison models
  trained alongside XGBoost and exposed in the backtest model-comparison endpoints
- **Pandas / NumPy** — feature computation
- **SciPy** — probability derivation and statistical validation tests
- **SHAP** — feature-importance analysis endpoint

### Frontend
- **React 18 + Vite**, **React Router 7**, **Recharts**, **Tailwind CSS**,
  **framer-motion / GSAP** for animation (`frontend/package.json`)

### Data
- **ESPN unofficial API** — live game data for the serving database
  (`sync_espn_games` management command)
- **Historical player-game CSV** (`data/raw/PlayerStatistics.csv`, NBA-API-derived box scores) —
  model training only, not needed at runtime

---

## 3. Data Flow — End to End

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
│                                                                 │
│  ESPN Unofficial API              data/raw/PlayerStatistics.csv │
│  (live, daily)                    (historical, training only)   │
└──────────────┬──────────────────────────┬───────────────────────┘
               │                          │
               ▼                          ▼
┌──────────────────────┐    ┌──────────────────────────────────┐
│  sync_espn_games     │    │  python manage.py train_models   │
│  (management cmd)    │    │  → ml/train_regression.py        │
│                      │    │                                  │
│  Pulls box scores    │    │  Produces per stat (pts/reb/ast):│
│  → Team, Game,       │    │   {stat}_xgb.json                │
│    Player,           │    │   {stat}_rf.pkl, {stat}_lr.pkl   │
│    PlayerStats       │    │   {stat}_catboost.cbm            │
└──────────┬───────────┘    │   model_metadata.json            │
           │                └──────────────────────────────────┘
           ▼                          │ (model files in data/models/)
┌──────────────────────────────────────────────────────────────┐
│                         PostgreSQL                            │
│  Team / Player / Game / PlayerStats                           │
│  DailyPick / BacktestRun / BacktestResult                     │
└──────────────────────────────┬───────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               │                               │
               ▼                               ▼
┌──────────────────────┐         ┌─────────────────────────────┐
│ generate_daily_picks │         │  On-demand APIs             │
│ (management cmd)     │         │  /api/predict/manual/       │
│                      │         │  /api/backtest/...          │
│ features → projection│         │  /api/intelligence/...      │
│ → prob (probability  │         │  /api/analysis/...          │
│   service) → DailyPick│        │  (Redis-cached where noted) │
└──────────┬───────────┘         └────────────┬────────────────┘
           │                                  │
           └──────────────┬───────────────────┘
                          ▼
                 React frontend (Vite)
```

Serving-time features are computed from the ESPN-synced PostgreSQL data
(`services/features.py`); training features are computed from the historical CSV
(`ml/train_regression.py`). The two pipelines intentionally implement the **same
conventions** (see Section 5) so the model sees the same feature semantics at train
and serve time.

---

## 4. ML Pipeline

### Target and models

For each stat (`pts`, `reb`, `ast`) the pipeline trains a **regression** model that predicts
the actual stat value for the next game (`objective: reg:squarederror`,
`ml/train_regression.py`). Four model families are trained and saved per stat:

| Model | File | Role |
|---|---|---|
| XGBoost | `data/models/{stat}_xgb.json` | Primary — used by `/api/predict/manual/` and daily picks |
| Random Forest | `data/models/{stat}_rf.pkl` | Comparison model (backtest) |
| Linear Regression | `data/models/{stat}_lr.pkl` | Comparison model (backtest) |
| CatBoost | `data/models/{stat}_catboost.cbm` | Comparison model |

The backtest engine additionally supports a `naive` baseline (projection = the player's
season average; `services/backtest.py`, `BACKTEST_MODELS` in `constants.py`).

### Training data

`data/raw/PlayerStatistics.csv`, filtered to Regular Season / Playoffs / Play-in games with
an **NBA season-start year ≥ 2016** (Oct–Dec games belong to that calendar year's season;
Jan–Sep games to the previous one). The filter is derived from the game date and raises an
error if it would empty the dataset (`load_and_filter_csv`). Sub-10-minute rows are **kept**
in the dataset so rolling windows, season averages, days-rest, and opponent totals see the
full game universe, but only games with ≥ 10 minutes are used as training/eval **targets**
(`eligible_rows`, `MIN_MINUTES = 10`).

### Three-way chronological split

`train_all_regression_models` splits eligible rows chronologically, twice
(`time_split` in `ml/train_regression.py`):

```
all eligible rows ── 80/20 by date ──► train_full | test
train_full        ── 85/15 by date ──► fit        | val
```

Per the current `data/models/model_metadata.json` (trained 2026-07-03):

| Partition | Rows | Date range |
|---|---|---|
| fit | 140,382 | < 2022-11-07 |
| val | 25,093 | 2022-11-07 → 2023-12-06 |
| test | 41,519 | ≥ 2023-12-06 |

**Early stopping never sees the test partition.** XGBoost (`early_stopping_rounds=50`) and
CatBoost (`use_best_model=True`) select their boosting-round count on the **val** slice only;
the XGBoost booster is then sliced to the selected rounds before saving, so serving uses
exactly the model that validation chose. Test metrics come from a partition that took no
part in any fitting or selection decision.

### Test metrics (XGBoost, current models)

MAE = mean(|projection − actual|); RMSE = √mean((projection − actual)²), both on the test
partition (`data/models/model_metadata.json`):

| Stat | Test MAE | Test RMSE |
|---|---|---|
| pts | 4.95 | 6.36 |
| reb | 1.99 | 2.61 |
| ast | 1.49 | 1.96 |

RF, LR, and CatBoost test MAEs are within ~0.03 of XGBoost on every stat — the model
comparison endpoints exist to make that visible rather than to claim a large gap.

### Inference

Model files are loaded lazily by the `ModelPredictor` singleton (`ml/predictor.py`), which
exposes **`predict_projection(feature_row, stat, model_type)`** → projected stat value.
(There is no `predict_probability` — probabilities are derived downstream, Section 6.)
Models do not retrain in production; retraining is `python manage.py train_models` locally,
then shipping the updated `data/models/` files.

---

## 5. Feature Engineering

Each stat has its own feature set — 15 features for `pts`, 12 for `reb`, 13 for `ast` —
defined authoritatively in `FEATURE_COLUMNS` in `backend/nba_betting/ml/train_regression.py`
and mirrored at serving time by `backend/nba_betting/services/features.py`.
**See `docs/ML_FEATURE_GUIDE.md` for the per-stat lists and exact definitions.**

Conventions shared by the training and serving pipelines:

- **Leakage guard:** every rolling/expanding feature uses `shift(1)` — only games strictly
  before the target game contribute.
- **Sub-10-minute games are NaN-masked inside rolling windows** (they occupy a window slot
  but contribute no value) on **both** paths — training no longer row-drops them.
- **Season averages** (`season_avg_*`): expanding mean of all prior games in the current
  season, with the season boundary at **Oct 1** everywhere (training `season_year`,
  serving `_get_season_avg`, backtest `_add_season_features`). Computed over all games,
  including sub-10-minute ones.
- **`days_rest`**: difference of consecutive game dates, `fillna(3)` for a player's first
  game, `clip(upper=10)` — applied identically in training
  (`ml/train_regression.py::build_player_features`) and serving
  (`services/features.py::_load_player_history`).
- **Opponent defense** (`opp_{stat}_allowed_L10`): rolling 10-game mean (shifted by 1,
  `min_periods=1`) of the **full team total** the opponent allowed — summed over all
  opposing players with no minutes filter, in training, serving, and backtest alike.
  With `min_periods=1` a single prior game already yields a value; the league-average
  fallback (computed from the DB, hardcoded constants only on error) applies **only when
  no prior-game data exists at all**.

---

## 6. Probability Derivation

`backend/nba_betting/services/probability.py` is the single source of truth for
`prob_over`; both `/api/predict/manual/` and `generate_daily_picks` route through
`calculate_probability(stat, projection, line, std_dev)`:

- **Low-count stats** (`ast`, `stl`, `blk`): Poisson —
  `prob_over = 1 − F_Poisson(⌊line⌋; μ = max(projection, 0))`.
- **Other stats** (`pts`, `reb`): Normal centered on the projection —
  `prob_over = 1 − Φ((line − projection) / σ)`, where σ is the player's rolling
  `{stat}_std_L10` (NaN-safe fallback to `STD_DEFAULTS`, floored at `STD_FLOOR = 0.5`).
- Output is **clamped to [0.01, 0.99]** (`PROB_CLAMP` in `constants.py`): with 10-game
  dispersion windows and no injury/lineup information the model cannot support
  near-certain claims.

Derived quantities:

- **edge** = `projection − line`; recommendation is OVER if edge > 0 else UNDER.
- **confidence** (daily picks feed) = `max(prob_over, 1 − prob_over)` — the probability of
  the **recommended** side. `/api/picks/` filters on this value (default threshold 0.55),
  so Under picks surface symmetrically with Overs.

---

## 7. API Reference

From `backend/nba_betting/urls.py` (all under `/api/`):

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/options/` | Player names + team abbreviations |
| `GET` | `/api/players/?q=` | Player autocomplete search |
| `POST` | `/api/predict/manual/` | Single projection + probability (see below) |
| `GET` | `/api/picks/?stat=pts&date=YYYY-MM-DD` | Pre-generated daily picks |
| `POST` | `/api/backtest/` | Per-game backtest for a player/stat/date range |
| `GET` | `/api/backtest/season-summary/` | Season report card per player/stat |
| `GET` | `/api/backtest/model-comparison/` | XGB vs RF vs LR vs naive on the same window |
| `GET` | `/api/backtest/leaderboard/` | Predictability leaderboard across the seed roster |
| `GET` | `/api/backtest/leaderboard-comparison/` | Leaderboard across seasons |
| `GET` | `/api/simulator/` | Monte Carlo season simulator |
| `GET` | `/api/analysis/shap/` | SHAP feature-importance analysis |
| `GET` | `/api/analysis/variance/` | Variance decomposition |
| `GET` | `/api/analysis/tier-history/` | Tier history |
| `GET` | `/api/intelligence/edge/` | Edge calibration |
| `GET` | `/api/intelligence/floor-ceiling/` | Floor/ceiling quantile profile |
| `GET` | `/api/intelligence/opponents/` | Opponent splits |
| `GET` | `/api/intelligence/fingerprint/` | Player fingerprint (radar) |
| `GET` | `/api/intelligence/validation/` | Statistical validation panel (with disclosures) |

### POST /api/predict/manual/

```json
Request:  { "player_name": "LeBron James", "stat": "pts",
            "opponent_ticker": "GSW", "is_home": true, "line": 25.5 }
Response: { "player": "LeBron James", "stat": "pts", "line": 25.5,
            "projection": 27.3, "edge": 1.8, "recommendation": "OVER",
            "prob_over": 0.62, "prob_under": 0.38 }
```

### POST /api/backtest/

```json
Request:  { "player_name": "LeBron James", "stat": "pts",
            "date_from": "2024-10-22", "date_to": "2025-06-22" }
Response: {
  "run_id": 1, "player_name": "...", "stat": "pts", "model": "xgb",
  "aggregate": { "total_bets": 67, "wins": 41, "accuracy": 0.612,
                 "total_pnl": 5.9, "roi": 8.0 },
  "per_game": [ { "date": "...", "opponent": "DEN", "actual": 28, "line": 26.4,
                  "projection": 27.9, "predicted_over": true, "correct": true,
                  "pnl": 1.0, "error": 0.1, "cumulative_pnl": 1.0 }, ... ]
}
```

---

## 8. Backtesting

The backtest engine (`backend/nba_betting/services/backtest.py`) replays the trained
regression model over a player's historical game log and simulates a flat-stake betting
record at −110 odds.

### How it works
1. Load the player's full history from the DB and compute the same rolling/season/opponent
   features the model uses (all `shift(1)`-based — no same-game leakage).
2. **Score only games with ≥ 10 minutes played**, matching the training target eligibility.
3. The "line" for each game is the player's **shift(1) rolling L5 average** for the stat —
   real sportsbook lines are not stored. This is a synthetic baseline, not a market line.
4. **Pushes are voided:** games where `actual == line` are skipped entirely (a sportsbook
   returns the stake on a push; scoring it as a decided outcome would distort the hit rate).
5. Predict with the selected model (`xgb` | `rf` | `lr` | `naive`), compare
   `projection > line` to `actual > line`, and settle at −110:
   correct → **+1.0** unit, wrong → **−1.1** units.

### Metric definitions

| Metric | Formula |
|---|---|
| **Accuracy** (hit rate) | `wins / total_bets` |
| **P&L** | `Σ pnl` where pnl ∈ {+1.0, −1.1} |
| **ROI** | `total_pnl / (total_bets × 1.1) × 100` — profit per unit **risked** (each bet risks 1.1 units at −110), not per bet |
| **Break-even** | hit rate of `1.1 / 2.1 ≈ 52.4%` at −110 pricing |

Note the ROI denominator: dividing by units risked makes reported ROI a factor 1.1 smaller
than a naive `pnl / bets` convention. When comparing against other ROI figures, check the
denominator convention first.

### Caching
`BacktestRun` rows cache results per (player, stat, model, date range). The opponent-defense
lookup table is memoized on (row count, latest game date) and rebuilds only when new games
are synced.

---

## 9. Deployment Architecture

- **Backend:** Docker container (Django + Gunicorn); model files from `data/models/` are
  included in the image (`MODEL_DIR` env var overrides the path). Migrations run on startup.
- **Database:** managed PostgreSQL (`DATABASE_URL`).
- **Cache:** Redis (`REDIS_URL`), 24-hour default TTL for intelligence/season endpoints.
- **Frontend:** Vite build, deployed as a static SPA; `VITE_API_BASE` points at the backend.
- **Daily cycle:** scheduled runs of `sync_espn_games` (pull last night's box scores) then
  `generate_daily_picks` (compute tonight's picks into `DailyPick`).

---

## 10. Known Limitations

These are first-class caveats, not footnotes. The audit record
(`docs/audit/METHODOLOGY_AUDIT_2026-07-02.md`) and `docs/METHODOLOGY.md` treat them in full.

### Evaluation
- **The backtest line is the player's own L5 rolling average, not a sportsbook line.**
  Beating this synthetic baseline at better than 52.4% does not establish profitability
  against real market lines.
- **Backtest windows may overlap the model's training data.** The API accepts arbitrary date
  ranges and does not guard against the training/validation partitions (fit < 2022-11-07,
  val < 2023-12-06); backtests over those periods are partially in-sample.
- **The season-report roster (18 players, `constants.py`) is hand-picked for durability and
  consistency** — survivorship bias. Aggregate results describe this roster, not NBA players
  at large. The validation endpoint ships these disclosures in its payload.
- **Hypothesis tests treat a player's consecutive games as independent** and run across
  ~54 player-stat panels without multiple-comparisons correction (disclosed in the
  validation payload).

### Model
- **Live features are one game stale by construction:** `get_model_inputs` uses the shifted
  features of the player's last completed game, so the most recent game is excluded from
  every rolling window and `days_rest` describes the previous game, not the one being
  predicted.
- **No injury/lineup/minutes-restriction awareness.** The model assumes the player plays
  their usual rotation; minutes-capped players will be over-projected.
- **Dispersion for the Normal probability model is the player's raw 10-game rolling std**
  (as few as 5 observations, no shrinkage), not the model's residual std.
- **No pace-of-play features** beyond what opponent-defense totals capture implicitly.

### Data
- **Training uses the historical CSV; serving uses the ESPN-synced DB.** The pipelines apply
  identical feature conventions, but the two sources are assumed to record identical box
  scores for the same games — no reconciliation is performed.
- **ESPN unofficial API** endpoints are undocumented and can change without notice.

---

## 11. History

- The original system was a **binary over/under classifier** (single shared 17-feature set,
  AUC ≈ 0.62–0.65, `predict_probability`). It was replaced by the per-stat regression
  pipeline described above; its trainer (`backend/nba_betting/ml/model_trainer.py`) remains
  in the tree as unused legacy code (imported by nothing) and is slated for removal — do not
  reuse it: its hyperparameter search uses shuffled, non-chronological splits.
- Earlier design documents (`docs/archive/IMPLEMENTATION_PLAN.md` — quarter-level predictor,
  Next.js; `docs/archive/DATA_INGESTION_STRATEGY.md` — quarter-slice ingestion) are archived
  and kept for historical reference only.
