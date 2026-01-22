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

## Frontend (Vite)

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:5173`.
