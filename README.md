# NBA Props Intelligence

> **Understand players, not just lines.**

NBA Props Intelligence is an open-source analytics platform that goes beyond win/loss prediction. It answers the question serious bettors and basketball analysts actually care about: *under what conditions does a player become predictable — or unpredictable — and why?*

Instead of chasing projections, the platform builds a full behavioral profile for each player: where the model has edge and where it doesn't, how performance shifts by rest, form, and matchup, and what the realistic floor and ceiling look like on any given night. The goal is insight, not a bet slip.

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
| Data | NBA API, The Odds API |
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

This starts:
- `web` — Django API at http://localhost:8000
- `db` — PostgreSQL at port 5432
- `redis` — Redis at port 6379
- `airflow-webserver` — Airflow UI at http://localhost:8080
- `spark-master` — Spark master at http://localhost:8081

### 3. Initialize the database

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_season_backtest --season 2026
```

To seed historical seasons:

```bash
docker compose exec web python manage.py seed_season_backtest --season 2025 --force
docker compose exec web python manage.py seed_season_backtest --season 2024 --force
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

The full pipeline runs through Airflow. Trigger it from http://localhost:8080, or run individual steps manually:

```bash
# Pull latest game data from NBA API
docker compose exec web python manage.py collect_nba_data

# Pull odds
docker compose exec web python manage.py collect_odds_api

# Train models (XGBoost + CatBoost per player/stat)
docker compose exec web python manage.py train_models

# Backfill backtest results for a season
docker compose exec web python manage.py seed_season_backtest --season 2026 --force
```

---

## Project structure

```
nbaPropsPrediction/
├── backend/
│   └── nba_betting/
│       ├── models.py               # ORM: BacktestRun, BacktestResult, ...
│       ├── views.py                # API views
│       ├── urls.py
│       ├── services/               # Business logic
│       │   ├── edge_calibration.py
│       │   ├── floor_ceiling.py
│       │   ├── opponent_analysis.py
│       │   ├── player_fingerprint.py
│       │   └── variance_decomp.py
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

- **R²** — how much of the player's actual variance is explained by the model's errors
- **Inverse-CV** — how consistent the player's raw output is (low variance relative to mean = high score)
- **Hit-rate excess** — how far above the 52.4% betting break-even the model performs

Tiers: **High** ≥ 65 · **Moderate** ≥ 40 · **Low** < 40

The canonical implementation lives in [`backend/nba_betting/utils/stats.py`](backend/nba_betting/utils/stats.py).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All skill levels welcome — data engineering, ML, frontend, and docs are all in scope.

## License

MIT — see [LICENSE](LICENSE).
