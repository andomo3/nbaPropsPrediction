# NBA Period Prop Predictor

Full-stack scaffold for period-specific NBA prop prediction.

## Quick Start (Backend)

```bash
docker-compose up -d
py -m pip install -r backend/requirements.txt
py backend/manage.py migrate
py backend/manage.py runserver
```

The API will be available at `http://localhost:8000`.

If you change Django models, run:
```bash
py backend/manage.py makemigrations
py backend/manage.py migrate
```

## Frontend (Vite)

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:5173`.
