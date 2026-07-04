# Perchance

> **Understand players, not just lines.**

[![CI](https://github.com/andomo3/nbaPropsPrediction/actions/workflows/ci.yml/badge.svg)](https://github.com/andomo3/nbaPropsPrediction/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Perchance is an open-source analytics platform that goes beyond win/loss prediction. It answers the question serious bettors and basketball analysts actually care about: *under what conditions does a player become predictable — or unpredictable — and why?*

Instead of chasing projections, the platform builds a full behavioral profile for each player: where the model has edge and where it doesn't, how performance shifts by rest, form, and matchup, and what the realistic floor and ceiling look like on any given night. The goal is insight, not a bet slip.

**Honesty first.** Every metric this platform reports is measured against *synthetic* baselines (a player's own rolling average), not sportsbook lines, and the full list of assumptions and limitations is first-class documentation, not fine print. Before citing any number, read [docs/METHODOLOGY.md](docs/METHODOLOGY.md). The methodology was adversarially audited before release ([docs/audit/](docs/audit/)), and the leakage guarantees are enforced by CI tests. A runnable, small-scale walkthrough of the entire methodology — including a demonstration of how data leakage inflates results — lives in [notebooks/methodology_walkthrough.ipynb](notebooks/methodology_walkthrough.ipynb).

> ⚠️ **This is an analytics research project, not betting advice.** Backtested results against self-generated baselines do not imply profitability against real sportsbooks. If you gamble, do so legally and responsibly.

---

## What it does

- **Edge Calibration** — measures whether the model's projected edge (projection vs. line) actually translates to higher hit rates. Broken down by rest days, recent form, and edge × rest cross-tabs.
- **Floor / Ceiling Profiling** — distribution of player outputs with p5–p95 percentiles, boom/bust classification, and condition-specific splits (B2B, hot streak, cold stretch).
- **Opponent Exploitability** — per-matchup delta vs. season average, hit rate, model bias, and ROI. Surfaces which opponents to target and which to avoid.
- **Behavioral Fingerprint** — five-dimension radar profile (consistency, edge reliability, matchup sensitivity, form dependence, rest sensitivity) with archetype labeling and a plain-English betting profile.
- **Predictability Leaderboard** — composite score (R², CV, hit-rate excess) that ranks players by how reliably the model tracks their output. Includes cross-season comparison and rolling tier history.

---

## Architecture

```
┌─────────────────┐     REST API      ┌──────────────────────┐
│   React + Vite  │ ────────────────► │   Django + DRF       │
│   (Recharts,    │                   │   (XGBoost, SHAP,    │
│    Radix UI)    │                   │    CatBoost)         │
└─────────────────┘                   └──────────┬───────────┘
                                                 │
                              ┌──────────────────┼──────────────────┐
                              ▼                  ▼                  ▼
                         PostgreSQL           Redis           Apache Airflow
                         (results,            (cache)         (ETL pipeline)
                          models)
```

| Layer | Tech |
|-------|------|
| Frontend | React 18, Vite, Tailwind CSS, Recharts, Radix UI |
| Backend | Django 5, Django REST Framework, Gunicorn |
| ML | XGBoost, CatBoost, scikit-learn, SHAP |
| Data | ESPN unofficial API (box scores), Kaggle NBA box-score archive (training), The Odds API (optional) |
| Pipeline | Apache Airflow, Apache Spark |
| Database | PostgreSQL 15 |
| Cache | Redis |
| Containers | Docker Compose |

---

## Quickstart

### Prerequisites

- Docker Desktop
- Git

### 1. Clone and configure

```bash
git clone https://github.com/andomo3/nbaPropsPrediction.git
cd nbaPropsPrediction
cp .env.example .env
```

Edit `.env` and set at minimum:

```
SECRET_KEY=a-long-random-string
ODDS_API_KEY=your-key-from-the-odds-api.com   # optional for local dev
```

### 2. Start all services

```bash
docker compose up -d
```

The first run builds nine containers (Django, two Postgres instances, Redis, Airflow webserver/scheduler/init, Spark master + worker) and compiles the ML stack — expect **5–10 minutes**. Subsequent starts are fast. Once up:

- `web` — Django API at http://localhost:8000 (sanity check: http://localhost:8000/health/ → `{"status": "ok"}`; the bare root URL is a 404, that's normal)
- `db` — PostgreSQL at port 5432
- `redis` — Redis at port 6379
- `airflow-webserver` — Airflow UI at http://localhost:8080 (login `admin` / `admin`)
- `spark-master` — Spark master UI at http://localhost:8081

### 3. Initialize the database and load data

```bash
docker compose exec web python manage.py migrate

# Pull real box scores from ESPN's unofficial API — no key required.
# --days 60 is a quick taste; the backtests below only cover whatever
# window you sync, so more days = more complete results.
docker compose exec web python manage.py sync_espn_games --days 60

# Precompute season backtests for the player roster
docker compose exec web python manage.py seed_season_backtest --season 2026
```

The seed command logs a warning for any player/date range it has no synced games for — with a partial sync that's expected, not an error. To backfill the full 2025–26 season (roughly 15–30 minutes of polite ESPN polling), sync from opening night onward, then re-seed:

```bash
docker compose exec web python manage.py sync_espn_games --date 20260630 --days 260
docker compose exec web python manage.py seed_season_backtest --season 2026 --force
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

---

## Data pipeline

Day-to-day game data comes from ESPN's unofficial API — free, no key required:

```bash
# Sync today's games / a specific date / a backfill window
docker compose exec web python manage.py sync_espn_games
docker compose exec web python manage.py sync_espn_games --date 20260110
docker compose exec web python manage.py sync_espn_games --days 60

# Generate daily picks from synced games
docker compose exec web python manage.py generate_daily_picks

# Backfill backtest results for a season
docker compose exec web python manage.py seed_season_backtest --season 2026 --force
```

The Spark feature-engineering pipeline runs through Airflow — trigger it from http://localhost:8080 (`admin` / `admin`).

**Retraining models** is optional — trained models ship in `data/models/`. It requires the full historical box-score CSV (a Kaggle-hosted archive of NBA API box scores, ~300 MB, not tracked in git; see [data/sample/README.md](data/sample/README.md) for provenance). Place it at `data/raw/PlayerStatistics.csv`, then:

```bash
docker compose exec web python manage.py train_models
```

---

## Project structure

```
nbaPropsPrediction/
├── backend/
│   └── nba_betting/
│       ├── models.py               # ORM: BacktestRun, BacktestResult, ...
│       ├── views/                  # API views (predictions, picks, backtests, intelligence)
│       ├── urls.py
│       ├── ml/                     # Training pipeline + model serving
│       │   ├── train_regression.py # Feature engineering, chronological splits, training
│       │   └── predictor.py
│       ├── services/               # Business logic
│       │   ├── backtest.py         # Season simulation engine
│       │   ├── probability.py      # Single prob_over implementation
│       │   ├── statistical_validation.py
│       │   ├── edge_calibration.py
│       │   ├── floor_ceiling.py
│       │   ├── opponent_analysis.py
│       │   ├── player_fingerprint.py
│       │   └── variance_decomp.py
│       ├── tests/                  # Leakage, parity, probability, validation tests
│       ├── utils/
│       │   └── stats.py            # Shared predictability scoring
│       └── management/commands/    # CLI data pipeline commands
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── intelligence/       # EdgeCalibration, FloorCeiling, OpponentExploitability, BehavioralFingerprint
│       │   └── ui/                 # Reusable primitives (SectionCard, Skeleton, InsightText)
│       └── utils/
│           ├── constants.js        # API base, player list, stats
│           └── format.js           # Number/color formatters
├── docs/                           # ARCHITECTURE, METHODOLOGY, API docs, audit reports
├── notebooks/                      # methodology_walkthrough.ipynb
├── dags/                           # Airflow DAGs
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

---

## API reference

All endpoints are prefixed with `/api/`.

| Endpoint | Description |
|----------|-------------|
| `GET /backtest/leaderboard/` | Predictability scores for all players |
| `GET /backtest/leaderboard-comparison/?season_a=2025&season_b=2026` | Cross-season score comparison |
| `GET /analysis/tier-history/?player_name=&stat=&season=` | Rolling predictability tier history |
| `GET /intelligence/edge/?player_name=&stat=&season=` | Edge calibration analysis |
| `GET /intelligence/floor-ceiling/?player_name=&stat=&season=` | Floor/ceiling profile |
| `GET /intelligence/opponents/?player_name=&stat=&season=` | Per-opponent exploitability |
| `GET /intelligence/fingerprint/?player_name=&stat=&season=` | Behavioral fingerprint |

---

## Predictability score

The composite score that ranks players on the leaderboard is:

```
score = R²(50%) + inverse-CV(30%) + hit-rate-excess(20%)
```

- **R²** — the share of the player's game-to-game variance the model explains: `1 − Var(errors) / Var(actuals)`, floored at 0
- **Inverse-CV** — how consistent the player's raw output is (low variance relative to mean = high score)
- **Hit-rate excess** — how far above the 52.4% (-110) break-even the model's backtest hit rate lands, measured against the synthetic L5 baseline line (see [docs/METHODOLOGY.md](docs/METHODOLOGY.md))

Tiers: **High** ≥ 65 · **Moderate** ≥ 40 · **Low** < 40

The canonical implementation lives in [`backend/nba_betting/utils/stats.py`](backend/nba_betting/utils/stats.py).

---

## Documentation

| Doc | What it covers |
|---|---|
| [docs/METHODOLOGY.md](docs/METHODOLOGY.md) | Models, features, splits, validation tests, and the full assumptions & limitations list |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, data flow, ML pipeline, API reference |
| [docs/ML_FEATURE_GUIDE.md](docs/ML_FEATURE_GUIDE.md) | Every model feature with its exact formula |
| [notebooks/methodology_walkthrough.ipynb](notebooks/methodology_walkthrough.ipynb) | Runnable small-scale walkthrough, including the leakage demonstration |
| [docs/audit/](docs/audit/) | The pre-release adversarial methodology audit and remediation log |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All skill levels welcome — data engineering, ML, frontend, and docs are all in scope.

## License

MIT — see [LICENSE](LICENSE).
