# NBA Feature Engineering Guide

This document describes the current leakage-safe feature engineering pipeline.

Current mode: **Position-Agnostic**.  
Context is derived from **team-level opponent defense** (not player position labels).

## Scope

- SQL context views: `backend/view_creation.sql`
- Python feature pipeline: `notebooks/feature_engineering.py`
- Output dataset: `exports/nba_model_ready.csv`

## 1) SQL Views

### `public.view_base_stats`

Purpose:
- Denormalized full-game player rows with opponent context.

Rules:
- Uses only `period = 0` from `nba_betting_playerstats`.
- Builds `opponent_id` with home/away case logic.
- Contains no position dependency.

### `public.view_opponent_defense_rolling` (snapshot)

Purpose:
- Dashboard-style snapshot of recent opponent defense.
- High values imply weaker defense (more allowed stats).

Important:
- Snapshot only.
- **Do not use directly for model training** due to future leakage risk.

## 2) Python Features (`notebooks/feature_engineering.py`)

### Context

- `rest_category`:
  - `0`: back-to-back
  - `1`: one day rest
  - `2`: two or more days rest
- `days_rest` is currently retained for backward compatibility with existing
  training/inference code paths.

### Volume & Volatility

- `fga_per_min_L10`: rolling 10-game attempts-per-minute using shifted history.
- `proj_volume`: `fga_per_min_L10 * min_L10`.
- `pts_std_L10`: rolling 10-game points standard deviation.
- `pts_mean_L10`: rolling 10-game points mean.
- `cv_L10`: `pts_std_L10 / pts_mean_L10` (zero-safe).

### Trajectory (Holt Damped Trend)

- `pts_trend_holt_damped`
- `reb_trend_holt_damped`
- `ast_trend_holt_damped`

Method:
- Holt’s linear trend with damping (`statsmodels.tsa.holtwinters.Holt`).
- Rolling window: 10 games.
- Uses shifted history (`shift(1)`) to prevent leakage.
- For sparse history (`N < 10`), uses fixed stable params:
  - `smoothing_level=0.3`
  - `smoothing_trend=0.2`
  - `damping_trend=0.9`
- For `N >= 10`, enables `optimized=True` so parameters are fit via MSE.
- Feature returns the latest trend component (slope proxy).

Why damping:
- Captures hot/cold streaks but avoids unrealistic runaway linear projections.

### Opponent Team Defense (No Leakage)

The training feature is rebuilt dynamically in Python:
1. Aggregate opponent totals allowed per game.
2. Compute `rolling(10).mean().shift(1)` by opponent.
3. Merge back to player rows by `(opponent_id, game_id, date)`.

Generated fields:
- `opp_avg_pts_allowed_L10`
- `opp_avg_reb_allowed_L10`
- `opp_avg_ast_allowed_L10`
- `opp_pts_allowed_L10` (compatibility alias to `opp_avg_pts_allowed_L10`)

## 3) Leakage Rules

- Any rolling/trajectory feature must use prior data only (`shift(1)`).
- SQL snapshot views are for monitoring, not for historical training joins.
- No future game should influence current-row feature values.
