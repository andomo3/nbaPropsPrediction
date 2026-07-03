# Contributing to Perchance

Thanks for your interest. The project is open to contributors of all skill levels — whether you want to improve the ML pipeline, add a new frontend visualization, fix a bug, or improve documentation.

## Ground rules

- One concern per pull request. A focused PR is easier to review and faster to merge.
- Write code that looks like the code around it. No drive-by reformatting.
- If you're adding a new analysis (backend service + view + frontend component), include at least a brief description in your PR of what it measures and why it's meaningful.

## Ways to contribute

| Area | Examples |
|------|---------|
| **Data** | Add a new stat (blocks, steals, 3PA), extend to more players, add new seasons |
| **ML** | Try a new model type, improve feature engineering, reduce prediction error |
| **Backend** | New API endpoint, performance improvement, better error handling |
| **Frontend** | New chart type, mobile layout improvements, accessibility |
| **Docs** | Clarify setup steps, add architecture diagrams, fix typos |
| **Tests** | Unit tests for services, integration tests for API endpoints |

## Local setup

Follow the [Quickstart in the README](README.md#quickstart). The short version:

```bash
git clone https://github.com/andomo3/nbaPropsPrediction.git
cd nbaPropsPrediction
cp .env.example .env
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_season_backtest --season 2026
cd frontend && npm install && npm run dev
```

## Backend

The backend is a standard Django app. Run management commands via:

```bash
docker compose exec web python manage.py <command>
```

Key locations:
- Business logic → `backend/nba_betting/services/`
- Shared stat utilities → `backend/nba_betting/utils/stats.py`
- API views → `backend/nba_betting/views.py`
- URL routing → `backend/nba_betting/urls.py`

When adding a new analysis service, follow the pattern in `services/edge_calibration.py`:
- One public function per file: `compute_<thing>(player_name, stat, season) -> dict`
- Return a plain dict; the view serializes it directly
- Always return an `insight` key with a plain-English summary

## Frontend

The frontend is a Vite + React SPA. Run it locally:

```bash
cd frontend
npm run dev     # dev server at http://localhost:5173
npm run build   # production build
```

Key locations:
- Page components → `frontend/src/components/`
- Intelligence section components → `frontend/src/components/intelligence/`
- Reusable primitives → `frontend/src/components/ui/`
- Shared formatters → `frontend/src/utils/format.js`
- Constants (players, stats, API base) → `frontend/src/utils/constants.js`

When adding a new intelligence section component:
1. Create it in `frontend/src/components/intelligence/`
2. Accept `{ data, loading, error }` props
3. Use `SectionCard`, `Skeleton`, `InsightText` from `../ui/`
4. Import colors and formatters from `../../utils/format`
5. Import it in `PlayerIntelligence.jsx` and add the corresponding `useFetch` call

## Pull request process

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Verify the backend starts: `docker compose up -d && docker compose exec web python manage.py check`
4. Verify the frontend builds: `cd frontend && npm run build`
5. Open a PR with a clear title and description of what changes and why

## Reporting issues

Open a GitHub issue. Include:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Any relevant logs (`docker compose logs web`)
