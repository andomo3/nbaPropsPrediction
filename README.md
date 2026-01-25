# NBA Period Prop Predictor

Full-stack scaffold for period-specific NBA prop prediction.

## Architecture Diagram

![EERD Diagram](docs/erdplus.png)

## Quick Start (Backend)

```bash
docker-compose up -d
py -m pip install -r backend/requirements.txt
py backend/manage.py migrate
py backend/manage.py verify_schema_integrity
py backend/manage.py runserver
```

The API will be available at `http://localhost:8000`.

If you change Django models, run:
```bash
py backend/manage.py makemigrations
py backend/manage.py migrate
```

If you want to run Django inside Docker:
```bash
docker-compose up -d --build
docker-compose exec web python backend/manage.py migrate
```

If migrations were reset and tables are missing in SQLite, delete
`backend/db.sqlite3` and run migrations again.

## Data Ingestion

Source of truth: `backend/docs/DATA_INGESTION_STRATEGY.md`

Dry run (prints a single game's JSON):
```bash
python backend/manage.py ingest_history --dry-run
```

Limit games for testing:
```bash
python backend/manage.py ingest_history --season 2023-24 --max-games 5
```

Tune network timeouts/retries if the NBA API is slow:
```bash
python backend/manage.py ingest_history --season 2023-24 --timeout 90 --max-retries 5
```

Skip games already fully ingested:
```bash
python backend/manage.py ingest_history --season 2023-24 --skip-existing
```

The ingestion script uses jittered delays, exponential cool-downs on timeouts,
and will skip already ingested periods when resuming.

Quick ingestion summary:
```bash
python backend/manage.py summarize_data
```

## Data Export & Cleaning

MVP export (full-game only, period=0):
```bash
python backend/manage.py export_raw
```
Output includes `player_team`, `home_team`, and `away_team` for matchup features.

Cleaning pipeline (wide format):
```bash
python notebooks/data_cleaning_pipeline.py
```

Exports are written to the `exports/` folder in the repo root.
If `exports/nba_mvp_data.csv` exists, the pipeline outputs
`exports/nba_training_mvp_v1.csv`. Otherwise it uses
`exports/nba_raw_long.csv` and outputs `exports/nba_training_wide_v1.csv`.

Notebook (combined export + cleaning):
```bash
data_export_and_cleaning.ipynb
```

Feature engineering guide:
```bash
docs/ML_FEATURE_GUIDE.md
```

## Betting Engine API

Manual prediction:
```bash
POST /api/predict/manual/
{ "player_name": "Jayson Tatum", "stat": "pts", "line": 26.5, "opponent": "MIA", "is_home": true, "days_rest": 2 }
```

Options for dropdowns:
```bash
GET /api/options/
```

Environment:
- `MODEL_DIR` points to XGBoost model JSON files (e.g. `data/models/pts_xgb.json`).
- `ODDS_API_KEY` enables on-demand odds fetching in `services/odds_api.py`.

## Frontend (Vite)

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:5173`.
