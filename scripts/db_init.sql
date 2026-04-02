-- =============================================================================
-- scripts/db_init.sql
-- Pipeline-owned schema additions. Django manages its own tables via ORM.
-- This file adds: derived_features_store, pipeline_runs, and views.
-- All statements are idempotent (IF NOT EXISTS / CREATE OR REPLACE).
-- =============================================================================

-- ----------------------------------------------------------------------------
-- derived_features_store
-- Written by PySpark, read by Django inference layer and model retraining.
-- PK: (player_id, game_id)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.derived_features_store (
    player_id                BIGINT           NOT NULL,
    game_id                  VARCHAR(20)      NOT NULL,
    date                     DATE             NOT NULL,
    -- Holt damped trend features
    trend_pts                DOUBLE PRECISION,
    trend_reb                DOUBLE PRECISION,
    trend_ast                DOUBLE PRECISION,
    -- Rolling L10 window features
    min_l10                  DOUBLE PRECISION,
    fga_per_min_l10          DOUBLE PRECISION,
    proj_volume              DOUBLE PRECISION,
    pts_std_l10              DOUBLE PRECISION,
    pts_mean_l10             DOUBLE PRECISION,
    cv_l10                   DOUBLE PRECISION,
    -- Opponent defense context (L10 rolling, no leakage)
    opp_avg_pts_allowed_l10  DOUBLE PRECISION,
    opp_avg_reb_allowed_l10  DOUBLE PRECISION,
    opp_avg_ast_allowed_l10  DOUBLE PRECISION,
    -- Audit
    created_at               TIMESTAMP        DEFAULT NOW(),
    CONSTRAINT pk_derived_features PRIMARY KEY (player_id, game_id)
);

CREATE INDEX IF NOT EXISTS idx_derived_features_player_date
    ON public.derived_features_store (player_id, date);

CREATE INDEX IF NOT EXISTS idx_derived_features_game
    ON public.derived_features_store (game_id);

-- ----------------------------------------------------------------------------
-- pipeline_runs
-- Audit log for each Airflow DAG execution.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.pipeline_runs (
    id           BIGSERIAL    PRIMARY KEY,
    dag_id       VARCHAR(100) NOT NULL,
    run_id       VARCHAR(200) NOT NULL UNIQUE,
    status       VARCHAR(20)  NOT NULL DEFAULT 'RUNNING',
    started_at   TIMESTAMP    DEFAULT NOW(),
    finished_at  TIMESTAMP,
    rows_written INTEGER,
    error_msg    TEXT
);

-- ----------------------------------------------------------------------------
-- view_base_data
-- Denormalized player game logs. Joins Django-managed tables where period=0
-- (full-game stats only). This is the Spark pipeline's primary input.
--
-- NOTE: This view references Django ORM tables (nba_betting_*) that are
-- created by `python manage.py migrate`. If migrations haven't run yet,
-- this CREATE OR REPLACE will fail — that is expected. The DAG's
-- recreate_view task will re-run it after migrations complete.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.view_base_data AS
SELECT
    ps.player_id,
    ps.game_id,
    g.date,
    g.season,
    p.first_name || ' ' || p.last_name  AS player_name,
    CASE
        WHEN ps.team_id = g.home_team_id THEN g.away_team_id
        ELSE g.home_team_id
    END                                  AS opponent_id,
    ps.min,
    ps.pts,
    ps.reb,
    ps.ast,
    ps.fga,
    ps.fgm
FROM  public.nba_betting_playerstats  ps
JOIN  public.nba_betting_game         g  ON g.game_id   = ps.game_id
JOIN  public.nba_betting_player       p  ON p.nba_id    = ps.player_id
WHERE ps.period = 0;

-- ----------------------------------------------------------------------------
-- view_final_features
-- Joins base data with derived store. Empty until the first Spark run.
-- Recreated by the DAG's recreate_final_features_view task after each run.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.view_final_features AS
SELECT
    b.*,
    d.trend_pts,
    d.trend_reb,
    d.trend_ast,
    d.min_l10,
    d.fga_per_min_l10,
    d.proj_volume,
    d.pts_std_l10,
    d.pts_mean_l10,
    d.cv_l10,
    d.opp_avg_pts_allowed_l10,
    d.opp_avg_reb_allowed_l10,
    d.opp_avg_ast_allowed_l10
FROM  public.view_base_data          b
JOIN  public.derived_features_store  d
   ON b.player_id = d.player_id
  AND b.game_id   = d.game_id;
