# PropEdge — System Architecture

> Last updated: April 2026. Supersedes `IMPLEMENTATION_PLAN.md` for the current production system.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Tech Stack](#2-tech-stack)
3. [Data Flow — End to End](#3-data-flow--end-to-end)
4. [ML Pipeline](#4-ml-pipeline)
5. [Feature Engineering](#5-feature-engineering)
6. [API Reference](#6-api-reference)
7. [Deployment Architecture](#7-deployment-architecture)
8. [Backtesting](#8-backtesting)
9. [Known Limitations](#9-known-limitations)
10. [Next Steps](#10-next-steps)

---

## 1. System Overview

PropEdge is a full-stack NBA player props prediction platform. It predicts the probability that a player exceeds their rolling average for points, rebounds, or assists in a given game.

There are two active branches:

| Branch | Purpose |
|---|---|
| `mvp` | The live production system. ESPN data ingestion, trained XGBoost/CatBoost models, LITE daily picks, backtesting. Deployed on Railway + Vercel. |
| `arch-migration` | A batch-processing architecture using Apache Airflow + Apache Spark + PostgreSQL. Built for distributed feature engineering at scale. Not yet deployed. |

This document covers the **`mvp` branch** — the live system.

---

## 2. Tech Stack

### Backend
- **Django 6 + Django REST Framework** — API server
- **PostgreSQL** — primary database (Railway managed)
- **Gunicorn** — WSGI server in production
- **Whitenoise** — serves Django static files without a separate web server
- **dj-database-url** — parses `DATABASE_URL` environment variable
- **django-cors-headers** — CORS for the React frontend

### ML
- **XGBoost** — primary classifier (binary: over vs under rolling average)
- **CatBoost** — secondary classifier (ensemble candidate)
- **Pandas / NumPy** — feature computation
- **Scikit-learn** — train/test splitting, metrics

### Frontend
- **React 18 + Vite** — SPA framework
- **React Router 7** — client-side routing
- **Recharts** — P&L charts on the backtesting page
- **Tailwind CSS + shadcn/ui** — styling
- **Lucide React** — icons

### Data
- **ESPN Unofficial API** — live game data, no auth required
  - Scoreboard: `site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard`
  - Box score: `site.api.espn.com/apis/site/v2/sports/basketball/nba/summary`
- **Historical CSVs** (Kaggle) — used for model training only, not needed at runtime

### Infrastructure
- **Railway** — Django backend + PostgreSQL
- **Vercel** — React frontend
- **Docker** — Railway deployment container
- **Git LFS** — large CSV files on `arch-migration` branch

---

## 3. Data Flow — End to End

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
│                                                                 │
│  ESPN Unofficial API          Historical CSVs (Kaggle)          │
│  (live, daily)                (one-time, training only)         │
└──────────────┬──────────────────────────┬───────────────────────┘
               │                          │
               ▼                          ▼
┌──────────────────────┐    ┌─────────────────────────────┐
│  sync_espn_games     │    │  notebooks/                 │
│  (management cmd)    │    │  feature_engineering.py     │
│                      │    │  model_trainer.py           │
│  Pulls box scores    │    │                             │
│  → Team, Game,       │    │  Produces:                  │
│    Player,           │    │  data/models/*.json/.cbm    │
│    PlayerStats       │    │  (XGBoost + CatBoost files) │
└──────────┬───────────┘    └─────────────────────────────┘
           │                          │
           ▼                          ▼ (baked into Docker image)
┌──────────────────────────────────────────────────────────────┐
│                     PostgreSQL (Railway)                      │
│                                                              │
│  nba_betting_team          nba_betting_player                │
│  nba_betting_game          nba_betting_playerstats           │
│  nba_betting_dailypick     nba_betting_backtestrun           │
│                            nba_betting_backtestresult        │
└──────────────────────────────┬───────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               │                               │
               ▼                               ▼
┌──────────────────────┐         ┌─────────────────────────┐
│ generate_daily_picks │         │  On-demand prediction   │
│ (cron, 10 AM ET)     │         │  POST /api/predict/     │
│                      │         │  manual/                │
│ Reads PlayerStats    │         │                         │
│ → computes features  │         │ Reads PlayerStats       │
│ → runs ML model      │         │ → computes features     │
│ → writes DailyPick   │         │ → runs ML model         │
└──────────┬───────────┘         └────────────┬────────────┘
           │                                  │
           └──────────────┬───────────────────┘
                          │
                          ▼
           ┌──────────────────────────┐
           │   Django REST API        │
           │                          │
           │  GET  /api/options/      │
           │  GET  /api/players/      │
           │  POST /api/predict/      │
           │  GET  /api/picks/        │
           │  POST /api/backtest/     │
           │  GET  /health/           │
           └──────────────┬───────────┘
                          │
                          ▼
           ┌──────────────────────────┐
           │   React Frontend         │
           │   (Vercel)               │
           │                          │
           │  /          Home         │
           │  /overview  Model docs   │
           │  /picks     Daily picks  │
           │  /backtest  Backtesting  │
           └──────────────────────────┘
```

### Daily cycle (production)
1. **10 AM ET** — Railway cron runs `sync_espn_games` (fetches last night's box scores)
2. **10 AM ET** — Railway cron runs `generate_daily_picks` (generates picks for tonight's games)
3. Users visit `/picks` to see today's LITE picks throughout the day

---

## 4. ML Pipeline

### Training (offline, local)
Training was done once using ~3 seasons of historical NBA data from Kaggle CSVs. The pipeline is:

```
data/raw/PlayerStatistics.csv
    → notebooks/feature_engineering.py   (rolling features, no-leakage)
    → exports/nba_model_ready.csv
    → notebooks/model_trainer.py         (time-based train/test split)
    → data/models/pts_xgb.json           (one model per stat per algorithm)
       data/models/pts_catboost.cbm
       data/models/reb_xgb.json
       data/models/reb_catboost.cbm
       data/models/ast_xgb.json
       data/models/ast_catboost.cbm
       data/models/model_metadata.json   (AUC, feature importance, dates)
```

**Model target:** Binary classification — did the player exceed their rolling L5 average for the stat?

**Train/test split:** Time-based (earlier seasons = train, most recent season = test) to prevent data leakage.

**Reported AUC:** ~0.62–0.65 (pts), ~0.62 (reb), ~0.62 (ast). Better than random (0.50) but reflects the inherent difficulty of predicting individual game outcomes.

### Inference (live, in Django)
The trained model files are **baked into the Docker image** at build time (`COPY . /app` in `Dockerfile`). At inference time:

1. `ModelPredictor` (singleton in `ml/predictor.py`) loads model files lazily on first request
2. `features.py` queries PostgreSQL for the player's recent games and opponent's recent games
3. 17 features are computed (see Section 5)
4. `predictor.predict_probability()` returns `P(actual > rolling_L5_avg)`

The model does **not** retrain on Railway. Retraining requires running the notebooks locally and pushing updated model files.

---

## 5. Feature Engineering

All 17 features must be computed at prediction time using only historical data (no leakage).

| Feature | Description | Leakage-safe? |
|---|---|---|
| `is_home` | 1 if player's team is home | ✓ |
| `days_rest` | Days since previous game (NaN → 3) | ✓ |
| `opp_pts_allowed_L10` | Opponent's avg pts allowed, last 10 games | ✓ |
| `pts_L5` | Player's avg points, last 5 games | ✓ |
| `pts_L10` | Player's avg points, last 10 games | ✓ |
| `pts_ema_L5` | Exponential moving avg points, span=5 | ✓ |
| `pts_std_L10` | Std dev of points, last 10 games | ✓ |
| `reb_L5` | Player's avg rebounds, last 5 games | ✓ |
| `reb_L10` | Player's avg rebounds, last 10 games | ✓ |
| `reb_ema_L5` | Exponential moving avg rebounds, span=5 | ✓ |
| `ast_L5` | Player's avg assists, last 5 games | ✓ |
| `ast_L10` | Player's avg assists, last 10 games | ✓ |
| `ast_ema_L5` | Exponential moving avg assists, span=5 | ✓ |
| `min_L5` | Player's avg minutes, last 5 games | ✓ |
| `min_L10` | Player's avg minutes, last 10 games | ✓ |
| `fg_pct_L5` | Player's avg FG%, last 5 games | ✓ |
| `fg_pct_L10` | Player's avg FG%, last 10 games | ✓ |

**Key design choices:**
- All rolling windows exclude the current game (`shift(1)` equivalent)
- Games with `min < 10` (garbage time) are excluded from rolling calculations
- `opp_pts_allowed_L10` falls back to league average if opponent has fewer than 3 games of history

---

## 6. API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health/` | Health check — returns `{"status": "ok"}` |
| `GET` | `/api/options/` | Returns all player names + team abbreviations |
| `GET` | `/api/players/?q=<query>` | Player autocomplete search |
| `POST` | `/api/predict/manual/` | Run a single prediction (see below) |
| `GET` | `/api/picks/?stat=pts&date=YYYY-MM-DD` | Today's LITE picks |
| `POST` | `/api/backtest/` | Run historical backtest for a player |

### POST /api/predict/manual/
```json
Request:  { "player_name": "LeBron James", "opponent_ticker": "GSW", "is_home": true, "line": 25.5 }
Response: { "pts": {"prob_over": 0.61, "line": 25.5, "edge": "Over"}, "reb": {...}, "ast": {...} }
```

### POST /api/backtest/
```json
Request:  { "player_name": "LeBron James", "stat": "pts", "date_from": "2023-10-01", "date_to": "2024-04-30" }
Response: {
  "run_id": 1,
  "aggregate": { "total_bets": 67, "wins": 41, "accuracy": 0.612, "total_pnl": 5.9, "roi": 8.8 },
  "per_game": [{ "date": "2023-10-25", "opponent": "DEN", "actual": 28, "line": 26.4,
                 "prob_over": 0.63, "correct": true, "pnl": 1.0, "cumulative_pnl": 1.0 }, ...]
}
```

---

## 7. Deployment Architecture

```
GitHub (andomo3/nbaPropsPrediction)
    │
    ├── main branch ──→ Vercel (auto-deploy)
    │                   React SPA
    │                   nba-props-prediction.vercel.app
    │
    └── mvp branch ───→ Railway (auto-deploy on push to main)
                        Docker container
                        nbapropsprediction-production.up.railway.app
                        │
                        ├── Django + Gunicorn (1 worker)
                        │   WORKDIR: /app/backend
                        │   CMD: migrate && gunicorn backend.wsgi:application
                        │
                        └── PostgreSQL (Railway managed)
                            Internal URL: postgres.railway.internal
                            Public URL:   crossover.proxy.rlwy.net:PORT
```

### Environment variables (Railway)

| Variable | Value |
|---|---|
| `SECRET_KEY` | Strong random key |
| `DEBUG` | `false` |
| `ALLOWED_HOSTS` | `nbapropsprediction-production.up.railway.app` |
| `CORS_ALLOW_ALL_ORIGINS` | `true` (can restrict to Vercel URL later) |
| `CORS_ALLOWED_ORIGINS` | `https://nba-props-prediction.vercel.app` |
| `DATABASE_URL` | Auto-set by Railway PostgreSQL plugin |
| `MODEL_DIR` | `/app/data/models` |

### Dockerfile summary
```dockerfile
FROM python:3.12-slim
ENV DJANGO_SETTINGS_MODULE=backend.settings
WORKDIR /app
COPY requirements.txt → pip install
COPY . /app                          # includes data/models/ (model files)
RUN collectstatic
WORKDIR /app/backend
CMD migrate && gunicorn              # migrations run on every startup
```

### Vercel
- Root directory: `frontend/`
- Framework: Vite
- `vercel.json` rewrites all routes to `/` (SPA routing)
- Env var: `VITE_API_BASE=https://nbapropsprediction-production.up.railway.app`

---

## 8. Backtesting

The backtesting engine (`services/backtest.py`) simulates historical betting performance using the trained model.

### How it works
1. Load all of a player's historical games from the DB
2. For each game in `[date_from, date_to]`: compute the same 17 features the model would have had available on that date (no future leakage)
3. Run `predictor.predict_probability()` → get `prob_over`
4. Compare prediction to actual result
5. Simulate P&L at **-110 odds**: correct = +1.0 unit, wrong = -1.1 units

### Caching
`BacktestRun` records act as a cache. The same player + stat + date range returns cached results instantly on subsequent calls.

### Interpreting results

| Metric | What it means |
|---|---|
| **Accuracy** | % of bets where the model's prediction direction was correct |
| **P&L** | Net units won/lost over the sample period at -110 odds |
| **ROI** | `total_pnl / total_bets × 100%` |
| **Breakeven** | Need ~52.4% accuracy to break even at -110 |

A model with 55% accuracy over 100+ bets is genuinely valuable. The AUC of ~0.63 translates roughly to this range in practice.

### Limitations
- Backtesting uses the **same model** for all historical dates — the model was trained on data that includes some of those dates, which can inflate backtest results
- Real betting lines differ from the rolling L5 average used as the line here
- Sample sizes under ~50 games are statistically noisy

---

## 9. Known Limitations

### Model
- **Line is rolling L5 average, not sportsbook line.** Real sportsbooks set lines that are harder to beat. The model's edge vs. its own rolling average doesn't directly translate to edge vs. DraftKings.
- **No injury/lineup adjustment.** The model assumes a player plays their usual rotation. Minutes-restricted players will be overestimated.
- **No pace/pace-of-play features.** Faster games produce more counting stats. This is partially captured by opponent defense but not directly.
- **AUC ~0.63** is real signal but modest. Expect variance on short samples.

### Data
- **ESPN data only goes back 60 days by default.** Players with limited recent history get league-average opponent defense as a fallback.
- **ESPN unofficial API** — endpoints are undocumented and could change. The box score stats array indices (`[0]=MIN, [1]=FG, [6]=REB, [7]=AST, [13]=PTS`) are the most fragile part.

### Infrastructure
- **1 gunicorn worker** on Railway free tier. Concurrent requests queue. Upgrade to 2+ workers when on a paid plan.
- **No Redis/caching layer.** Every prediction re-queries the DB. Fine for MVP traffic, will need caching at scale.
- **Migrations run on every container start.** No-op when up to date, but adds ~1s to cold start.

---

## 10. Next Steps

### Immediate (before wider launch)
- [ ] **Run `generate_daily_picks`** after backfill completes — populates the `/picks` page
- [ ] **Set up Railway cron** (`0 14 * * *`) to auto-run `sync_espn_games && generate_daily_picks` daily
- [ ] **Restrict `CORS_ALLOW_ALL_ORIGINS`** — change to `false` once confirmed working, rely on `CORS_ALLOWED_ORIGINS`
- [ ] **Set `ALLOWED_HOSTS`** to the Railway domain in production

### Model improvement
- [ ] **Retrain with ESPN data** — current model was trained on Kaggle CSVs. Retraining on ESPN-sourced data would make features consistent between training and inference
- [ ] **Add real sportsbook lines** — use The Odds API to get actual market lines instead of rolling L5 average. This makes backtesting realistic
- [ ] **Calibration** — apply `CalibratedClassifierCV` so `prob_over=0.65` actually means 65% historically
- [ ] **Ensemble** — blend XGBoost + CatBoost outputs (e.g., `0.6 * xgb + 0.4 * catboost`)
- [ ] **More features** — back-to-back games flag, travel distance, season segment (playoff push)

### Backtesting improvements
- [ ] **Walk-forward validation** — retrain model on rolling window, test on next month. More realistic than static model on historical data
- [ ] **Real line comparison** — compare model's pick to actual sportsbook line (requires historical Odds API data)
- [ ] **Kelly criterion** — use `prob_over` to size bets instead of flat 1 unit

### Infrastructure
- [ ] **`arch-migration` branch** — the Airflow + Spark pipeline is built for weekly batch feature recomputation at scale. Merge into production when data volume grows
- [ ] **Add Redis** — cache `get_model_inputs()` results for 1 hour. Critical for `/picks` page under load
- [ ] **Upgrade Railway plan** — 2+ workers, persistent volume for model files (removes them from Docker image)
- [ ] **Monitoring** — add Sentry for error tracking, log prediction counts

### Testing
See `docs/TESTING.md` (to be written) for the full test plan. Key areas:
- Unit tests for `features.py` rolling calculations (verify no leakage)
- Integration tests for ESPN sync command with mock API responses
- Backtest regression tests (golden dataset: known player + date range = known P&L)
- API contract tests for all endpoints
