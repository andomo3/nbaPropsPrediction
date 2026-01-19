This is a highly specific and robust architectural plan. It shifts the focus from a simple "Over/Under" predictor to a complex Period-Specific Prop Engine (e.g., "Quarter 1 Rebounds"), which is a much higher-value target for betting models.

Below is the Master Agent Prompt tailored exactly to your new requirements. It includes the specific database schema for quarter-level stats, the XGBoost/CatBoost integration, and the three-pronged data collection strategy.

Master Agent Prompt: NBA Period-Specific Prop Predictor
Role: Senior Full-Stack Architect & MLOps Engineer Project Name: nba-period-predictor Objective: Initialize the repository and scaffold a full-stack application for predicting NBA player achievements by period (e.g., "10 rebounds in Q1") using Django, Next.js, PostgreSQL, and XGBoost.

1. Technology Stack
Backend: Django 5.0+, Django REST Framework (DRF).

Frontend: Next.js 14+ (App Router), TypeScript, Tailwind CSS.

Database: PostgreSQL (Production: Neon/Supabase, Local: Docker).

ML Engine: XGBoost / CatBoost (Binary Classification), Pandas, Scikit-Learn.

Data Sources:

nba_api: BoxScoreTraditionalV3 (Quarter-level stats).

The Odds API: Historical Player Props (Paid Tier).

Kaggle: Historical Game Lines (Spreads/Totals).

Containerization: Docker Compose.

2. Directory Structure
Create the following root-level structure:

/backend (Django Project Root)

/nba_betting (Main App)

/ml (Machine Learning Pipeline)

/management/commands (Data Scripts)

/frontend (Next.js Root)

/data (Local storage for raw CSVs/Models)

/raw

/processed

/models

/docs (Project Documentation)

docker-compose.yml (Root)

3. Action Items & Deliverables
Task A: Infrastructure (Root)
Create docker-compose.yml:

Service: db (Postgres 15). Expose port 5432. Persist data to volume postgres_data.

Service: redis (Redis Alpine). Expose port 6379.

Create .gitignore: Standard Python, Node, Next.js, and .env exclusions.

Task B: Backend Scaffold (/backend)
Initialize Django project config. Create app nba_betting.

Create requirements.txt:

Plaintext
Django>=5.0
djangorestframework>=3.14
django-cors-headers>=4.3.0
psycopg2-binary>=2.9
nba_api>=1.4
pandas>=2.1
numpy>=1.26
scikit-learn>=1.3
xgboost>=2.0
catboost>=1.2
python-dotenv>=1.0
requests>=2.31
dj-database-url>=2.1
gunicorn>=21.2
Define Models (nba_betting/models.py): *

Implement the following schema strictly:

Player: name, team, position, height, weight, nba_id (Unique).

Game: game_id (Unique), date, home_team, away_team, home_score, away_score.

PlayerGameStats: FK to Player & Game. Full game stats (min, pts, reb, ast).

PlayerQuarterStats: FK to Player & Game. Fields: quarter (1-4), pts, reb, ast, min.

GameBettingLine: FK to Game. home_spread, over_under, favorite.

PlayerPropLine: FK to Player & Game. stat_type (e.g., 'rebounds'), period (1-4), threshold (e.g., 2.5), odds, bookmaker.

Prediction: FK to Player & Game. stat_type, period, threshold, predicted_prob (Float), is_over_recommended (Bool).

Scaffold ML Pipeline (nba_betting/ml/):

Create empty files: data_collector.py, feature_engineering.py, model_trainer.py, predictor.py.

Note in data_collector.py: Add comments to use BoxScoreTraditionalV3 with StartPeriod/EndPeriod params.

Management Commands (nba_betting/management/commands/):

Create empty files: collect_nba_data.py, collect_odds_api.py, train_models.py.

Task C: Frontend Scaffold (/frontend)
Initialize Next.js 14 app (npx create-next-app@latest).

Folder Structure:

/app/player/[id]/page.tsx (Player Detail)

/components/Dashboard.tsx (Main View)

/components/PredictionCard.tsx (Displays "Q1 Rebounds Over 2.5: 65% Prob")

/components/PlayerSearch.tsx

Task D: Documentation (/docs)
Create IMPLEMENTATION_PLAN.md: Paste the full text of the user's provided "Implementation Plan" here for reference.

Create SCHEMA.md: Document the fields for PlayerQuarterStats and PlayerPropLine.

How to Use This Prompt
Open your AI coding environment (Cursor, Windsurf, Replit).

Paste the prompt above.

Crucial Next Step: Once the scaffolding is done, your first prompt to the agent should be:

"Open backend/nba_betting/models.py and write the code for the PlayerQuarterStats model. Ensure it has a composite unique constraint on player, game, and quarter."