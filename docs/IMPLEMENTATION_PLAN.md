# Implementation Plan

This plan expands the initial prompt into a step-by-step guide for building a
period-specific NBA props predictor. The goal is to predict quarter-level
outcomes (ex: "Q1 rebounds over 2.5") using a Django API, a Next.js frontend, and
an ML pipeline that ingests stats and betting lines.

## Goals
- Support quarter-level player props with model-backed probabilities.
- Build a full-stack baseline: data ingestion, feature prep, model training, and prediction serving.
- Keep the existing UI in `public/index.html` and `src/index.css` unchanged.

## Technology Stack
- Backend: Django 5.0+, Django REST Framework.
- Frontend: Next.js 14+ (App Router), TypeScript, Tailwind CSS.
- Database: PostgreSQL (Neon/Supabase for prod, Docker for local).
- ML: XGBoost/CatBoost, Pandas, Scikit-Learn.
- Data: nba_api (BoxScoreTraditionalV3), The Odds API (player props), Kaggle (game lines).
- Infra: Docker Compose, Redis for async tasks later if needed.

## Directory Structure
- `backend/` Django project root
  - `backend/` settings/urls/asgi/wsgi
  - `nba_betting/` app: models, ml pipeline, management commands
- `frontend/` Next.js app
- `data/` storage for raw/processed datasets and trained models
- `docs/` documentation
- `docker-compose.yml` root-level services

## Data Model Notes
- Player and Game are the core entities.
- PlayerQuarterStats stores quarter-only stats with a unique constraint on (player, game, quarter).
- PlayerPropLine stores sportsbook odds tied to a player/game/period/stat_type.
- Prediction ties the model output back to a player/game/period threshold.

## Data Ingestion Strategy
1. NBA stats
   - Use `BoxScoreTraditionalV3` with StartPeriod/EndPeriod for quarter slices.
   - Store per-quarter stats in PlayerQuarterStats.
2. Betting lines
   - Use The Odds API for historical player prop lines.
   - Normalize stat_type names to a consistent set (points, rebounds, assists).
3. Game lines
   - Import Kaggle CSVs for spreads and totals.
   - Populate GameBettingLine and align by game_id/date.

## Feature Engineering Outline
- Player form: rolling averages for the same period (last N quarters).
- Matchup context: opponent team, home/away, pace proxy from totals/spreads.
- Usage proxy: player minutes in the period and overall minutes trend.
- Line context: threshold and odds (converted to implied probability).

## Modeling Plan
- Target: binary outcome (over vs under) for a given stat_type/period/threshold.
- Baseline: XGBoost classifier; compare CatBoost for categorical handling.
- Split: time-based split to prevent leakage (train on earlier dates).
- Metrics: AUC, log loss, calibration curve, and Brier score.
- Artifacts: save model files to `data/models` with metadata (date, features, metric).

## API Shape (Draft)
- `GET /api/players` list players
- `GET /api/players/:id` player profile + recent quarter trends
- `GET /api/props?player_id=&game_id=&period=&stat_type=` odds lines
- `POST /api/predict` request prediction for a player/period/line
- `GET /api/predictions?game_id=` list predictions for a game

## Frontend Usage
- `app/player/[id]/page.tsx` renders player detail and example prediction card.
- `components/Dashboard.tsx` placeholder for period summary panels.
- `components/PredictionCard.tsx` renders the "Q1 Rebounds Over 2.5: 65% Prob" tile.
- `components/PlayerSearch.tsx` placeholder search input.

## Environment Variables (Expected)
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DATABASE_URL` (Postgres connection)
- `CORS_ALLOWED_ORIGINS`
- `ODDS_API_KEY` (if using The Odds API)

## Local Development Steps
1. `docker compose up -d` for Postgres/Redis.
2. Create a venv, install `backend/requirements.txt`, and run migrations.
3. Run `python backend/manage.py runserver`.
4. Install frontend deps in `frontend/` and run `npm run dev`.

## Testing and Verification
- Django model validation: create fixtures for Player/Game/PlayerQuarterStats.
- Data ingestion: dry-run collectors and confirm row counts.
- Model training: verify metrics and model artifact creation.
- API integration: ensure prediction output matches expected schema.
