# ML Feature Guide

> Last updated: 2026-07-03. Describes the features consumed by the deployed
> Perchance regression models.

The **authoritative feature list** is `FEATURE_COLUMNS` in
`backend/nba_betting/ml/train_regression.py`. Three code paths build these features and
intentionally implement identical conventions:

| Path | File | Data source |
|---|---|---|
| Training | `backend/nba_betting/ml/train_regression.py` (`build_player_features`, `build_opponent_defense`) | `data/raw/PlayerStatistics.csv` |
| Live serving | `backend/nba_betting/services/features.py` (`get_model_inputs`) | ESPN-synced PostgreSQL |
| Backtest | `backend/nba_betting/services/backtest.py` (reuses `features.py` helpers + `_add_season_features`, `_batch_opponent_defense`) | ESPN-synced PostgreSQL |

> **Note on `notebooks/feature_engineering.py`:** that script is an **orphaned experimental
> pipeline** (Holt damped trends `trend_pts/reb/ast`, `fga_per_min_l10`, `proj_volume`,
> `cv_l10`, `opp_avg_*_allowed_l10`, written to `exports/nba_model_ready.csv`). None of its
> outputs are consumed by any deployed model. It is **not** the source of the features
> documented here — see [Appendix](#appendix-orphaned-experimental-pipeline).

---

## Per-stat feature sets

Each stat has its own model and its own feature set (from `FEATURE_COLUMNS`):

### Points model (15 features)

`is_home`, `days_rest`,
`pts_L5`, `pts_L10`, `pts_ema_L5`, `pts_std_L10`,
`reb_L5`, `ast_L5` (role context),
`min_L5`, `min_L10`,
`fg_pct_L5`, `fg_pct_L10`,
`season_avg_pts`, `hot_cold_pts`,
`opp_pts_allowed_L10`

### Rebounds model (12 features)

`is_home`, `days_rest`,
`reb_L5`, `reb_L10`, `reb_ema_L5`, `reb_std_L10`,
`pts_L5`, `min_L5`, `min_L10`,
`season_avg_reb`, `hot_cold_reb`,
`opp_reb_allowed_L10`

### Assists model (13 features)

`is_home`, `days_rest`,
`ast_L5`, `ast_L10`, `ast_ema_L5`, `ast_std_L10`,
`pts_L5`, `min_L5`, `min_L10`,
`fg_pct_L5`,
`season_avg_ast`, `hot_cold_ast`,
`opp_ast_allowed_L10`

The target for each model is the raw stat value of the next game
(`points` / `reboundsTotal` / `assists`), predicted by regression.

---

## Exact definitions

All rolling/expanding computations are grouped per player and use `shift(1)` first, so only
games **strictly before** the target game contribute (see [Leakage rules](#leakage-rules)).
Sub-10-minute games are NaN-masked before any rolling computation (see
[Garbage-time masking](#garbage-time-masking)).

### Context

| Feature | Definition |
|---|---|
| `is_home` | 1 if the player's team is the home team, else 0. At serving time it is supplied by the caller for the upcoming game. |
| `days_rest` | `date.diff().dt.days` between consecutive games, `fillna(3)` for a player's first recorded game, then `clip(upper=10)`. Applied identically on **both** the training path (`build_player_features`) and the serving path (`_load_player_history`), so long layoffs are capped at the same value the model saw in training. Computed over every game, including sub-10-minute ones. |

### Rolling form (L5 / L10 means)

For each base stat `s ∈ {pts, reb, ast, min, fg_pct}` and window `w ∈ {5, 10}`:

```
s_Lw = s.shift(1).rolling(w, min_periods=1).mean()
```

- Computed on the NaN-masked series (sub-10-minute games contribute nothing).
- `min_periods=1`: a single valid prior game already yields a value, so early-season
  values are noisy averages of very few games.
- `fg_pct` per game is `fgm / fga`, defined as `0.0` when `fga == 0` — a genuine 0-for-N
  game contributes 0.0 (both paths preserve legitimate zeros; serving fallbacks use
  NaN-safe checks, never falsy `or`).

### Exponential moving average

For `s ∈ {pts, reb, ast}`:

```
s_ema_L5 = s.shift(1).ewm(span=5, adjust=False).mean()
```

Span 5 ⇒ α = 2/(5+1) = ⅓: the most recent valid game carries roughly one-third of the
weight, which makes the feature react quickly to role/usage breakouts while still smoothing
single-game noise.

### Rolling volatility

For `s ∈ {pts, reb, ast}`:

```
s_std_L10 = s.shift(1).rolling(10, min_periods=5).std()
```

- Sample standard deviation (ddof=1) over up to 10 prior valid games.
- `min_periods=5`: players with fewer than 5 valid prior games get **NaN**. At serving
  time a NaN std falls back to `STD_DEFAULTS` (`pts` 5.0, `reb` 2.0, `ast` 1.5, from
  `backend/nba_betting/constants.py`) via an explicit NaN check.
- `pts_std_L10` doubles as the dispersion σ of the Normal probability model in
  `services/probability.py` (floored at 0.5). It is the player's marginal game-to-game
  std over ≤10 games — a noisy, unshrunk estimate (a disclosed limitation).

### Season average

```
season_avg_s = s.shift(1).expanding(min_periods=1).mean()
               grouped by (player, season_year)
```

- **Season boundary is Oct 1 everywhere**: a game in Oct–Dec belongs to that calendar
  year's season; Jan–Sep games belong to the previous year's season
  (`_season_start_year` in training; the same rule in `services/features.py::_get_season_avg`
  and `services/backtest.py::_add_season_features`).
- Computed over **all games of the season, including sub-10-minute ones** (raw, unmasked
  values) — on both training and serving paths.
- At live serving, the average covers all season games strictly **before** the reference
  date; if the player has no prior games this season, fixed defaults are used
  (`pts` 15.0, `reb` 5.0, `ast` 4.0).

### Hot/cold streak

```
hot_cold_s = (s_L5 − season_avg_s) / (|season_avg_s| + 0.1)
```

The relative deviation of recent form (L5) from the season baseline; the `+ 0.1` guards
against division by ~0 for very low-average players. Positive = running hot; negative =
running cold. Identical formula in training (`build_player_features`), serving
(`get_model_inputs`), and backtest (`_add_season_features`).

### Opponent defense

```
opp_s_allowed_L10:
  per (game, defending team): sum s over ALL opposing players   # no minutes filter
  per defending team:         sum.shift(1).rolling(10, min_periods=1).mean()
```

- The "allowed" total is the **full team total** — every opposing player's stat is summed,
  with no minutes cutoff, in training (`build_opponent_defense`, which runs before any
  target-eligibility filtering), serving (`_get_opponent_stat_allowed`), and backtest
  (`_batch_opponent_defense`).
- `min_periods=1`: an opponent with a single prior game already yields a (1-game) value.
  The **league-average fallback applies only when no prior-game data exists at all**
  (the rolling value is None/NaN). The league average is computed from the database
  (`_get_league_avg_allowed`); hardcoded constants (112 pts / 44 reb / 26 ast per game)
  are used only if that query fails or returns nothing.
- Team totals, not positional matchups: aggregating what the whole team allows gives a
  more stable defensive signal than any single-player matchup proxy.

---

## Leakage rules

- Every rolling, EMA, std, expanding-season, and opponent-defense feature applies
  `shift(1)` **before** the window computation: the target game never contributes to its
  own features.
- Training targets are the same rows whose features end at the previous game, so the model
  learns P(next game | information through the prior game).
- No future game influences any current-row feature value on any path.
- One consequence at **live** serving: features are anchored on the player's last completed
  game row, so the most recent completed game is itself excluded from every window — live
  features are one game stale relative to the upcoming game being predicted (see
  Limitations).

---

## Garbage-time masking

Games with fewer than 10 minutes played (`MIN_MINUTES = 10`) are **NaN-masked, not
dropped**, before rolling computation — on both the training path
(`build_player_features` masks `points/reboundsTotal/assists/numMinutes/fg_pct`; NaN
minutes are masked too) and the serving path (`_add_rolling_features`). A masked game
occupies a window slot but contributes no value.

- **Why:** short injury exits and garbage-time stints would otherwise drag a player's
  rolling averages far below their true rotation form.
- **Frozen-feature effect:** after a sub-10-minute appearance, the EMA carries forward
  unchanged and the rolling means change only by the oldest game dropping out of the
  window — the player's form rating is effectively paused across short stints.
- **Targets:** games below 10 minutes are excluded as training/eval targets
  (`eligible_rows` in training) and are not scored by the backtest
  (`min >= 10` filter in `run_backtest`), so the model is never asked to predict — nor
  evaluated on — a game it structurally cannot see coming (early injury exits).
- Season averages and `days_rest` deliberately use **all** games (see above); only the
  rolling-window features are masked.

---

## Behaviors & limitations

- **"Conditional minutes" bias.** The model projects performance assuming the player's
  historical rotation minutes. It has no injury-report or minutes-restriction input, so
  players on minute caps (e.g. returning from injury) will be over-projected.
- **The "microwave" trade-off.** High-efficiency short stints (7 points in 8 minutes) are
  masked out along with the "2 minutes, 0 points" games. Rare instant-offense outliers are
  sacrificed to keep the far more common garbage-time noise out of the form features.
- **One-game staleness at live inference.** `get_model_inputs` reads the shifted feature
  row of the last completed game, so live predictions exclude the most recent game from
  every window, and `days_rest` describes the rest before that last game rather than
  before the game being predicted. Training and backtest rows are correctly aligned; only
  the live path lags by one game.
- **Early-window noise.** `min_periods=1` on the L5/L10 means and the opponent-defense
  rolling means that early-season values can be built from a single game; `std_L10`
  requires 5 valid prior games and falls back to fixed defaults below that.

---

## Appendix: orphaned experimental pipeline

`notebooks/feature_engineering.py` (a PostgreSQL/SQL-view + statsmodels pipeline that
writes `exports/nba_model_ready.csv`) is an experiment from an earlier batch-processing
effort. It produces a **different** feature family: Holt damped-trend features (`trend_pts`, `trend_reb`,
`trend_ast`), volume/volatility features (`fga_per_min_l10`, `proj_volume`, `cv_l10`),
and opponent features under different names (`opp_avg_pts_allowed_l10` etc., with a
3-game minimum and league-average fill — conventions the production pipeline does
**not** use).

None of these columns appear in `FEATURE_COLUMNS`, and no trained or deployed model
consumes them. Treat that script as historical experimentation, not documentation of the
live system.
