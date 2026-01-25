# ML Feature Guide

This document describes the engineered features produced by `notebooks/feature_engineering.py` and the design choices used to prevent leakage and improve predictive quality.

## Data Dictionary

Base columns (from `exports/nba_mvp_data.csv`):
- `date`: Game date (YYYY-MM-DD).
- `game_id`: NBA game identifier.
- `player_name`: Player full name.
- `player_team`: Team the player played for in that game.
- `home_team`: Home team abbreviation.
- `away_team`: Away team abbreviation.
- `pts`: Points scored by the player (full game).
- `reb`: Rebounds by the player (full game).
- `ast`: Assists by the player (full game).
- `min`: Minutes played by the player (full game).
- `fg_pct`: Field-goal percentage (fgm / fga). Note: `fg3_pct` is a placeholder in the export.

Context features:
- `is_home`: 1 if `player_team` == `home_team`, else 0.
- `opponent`: Opponent team abbreviation.
- `days_rest`: Days since the player’s previous game (NaN filled with 3).

Rolling player form features (leakage-safe):
- `pts_L5`, `pts_L10`: Rolling mean of points using the previous 5/10 games.
- `reb_L5`, `reb_L10`: Rolling mean of rebounds using the previous 5/10 games.
- `ast_L5`, `ast_L10`: Rolling mean of assists using the previous 5/10 games.
- `min_L5`, `min_L10`: Rolling mean of minutes using the previous 5/10 games.
- `fg_pct_L5`, `fg_pct_L10`: Rolling mean of FG% using the previous 5/10 games.
- `pts_std_L10`: Rolling standard deviation of points (last 10 games, min 5).

Breakout detection (EMA):
- `pts_ema_L5`: Exponential moving average of points (span=5) using prior games only.
- `reb_ema_L5`: Exponential moving average of rebounds (span=5) using prior games only.
- `ast_ema_L5`: Exponential moving average of assists (span=5) using prior games only.

Opponent strength feature:
- `opp_pts_allowed_L10`: Rolling mean of total points allowed by the opponent in its last 10 games.

## The Logic

### Leakage Prevention
All rolling and EMA features use `.shift(1)` before calculating statistics. This guarantees features are derived strictly from past games and do not leak information from the current game.

### Garbage Time Handling
Games where `min < 10` are treated as NaN for the purposes of feature calculation (not removal). This prevents short garbage-time appearances from dragging down a player’s rolling averages, while still keeping the game as a valid prediction row.

### DNP Row Removal
Rows where `min = 0` are removed at the final step. These represent players who did not play and would otherwise contaminate the regression target with "coach decision" outcomes.

### Why EMA span=5?
A span of 5 gives roughly 33% weight to the most recent game. This helps the model capture breakouts quickly (e.g., players whose roles or usage spike) while still smoothing noise.

### Opponent Defense (True Team Context)
Opponent strength is computed from total team points allowed, not a single player’s matchup. We aggregate total points allowed to an opponent per game, then compute a rolling mean over the opponent’s last 10 games. This provides a more stable and realistic defensive signal.

## Data Behaviors & Model Limitations

### The "Frozen Feature" Effect
Observation: If a player plays < 10 minutes (e.g., 5.2 mins), their EMA and rolling stats for the next game will remain unchanged (identical to the previous game).
Reasoning: The logic effectively "pauses" the player's form rating during garbage time appearances to prevent artificial drops in their averages.

### "Conditional Minutes" Bias (Crucial Warning)
Observation: The model predicts performance based on historical rotation minutes, ignoring recent short stints.
Risk: The model will overestimate projections for players on minutes restrictions (e.g., returning from injury).
Usage Rule: Do not bet on players with known minute caps; the model assumes they are playing their full rotation.

### The "Microwave" Trade-off
Observation: High-efficiency scoring in short minutes (e.g., 7 points in 8 minutes) is excluded from historical context.
Reasoning: We sacrifice capturing these rare "instant offense" outliers to protect the model from the noise of common "2 minutes, 0 points" games.

## Output
The feature pipeline writes `exports/nba_model_ready.csv`.
