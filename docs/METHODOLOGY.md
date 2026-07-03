# Perchance — Methodology

This document describes, end to end, how Perchance turns historical box scores into player-prop projections, probabilities, backtests, and statistical verdicts — and, just as importantly, what the system assumes and where it falls short. **Section 8 (Assumptions & Limitations) is first-class content**: if you plan to cite any number this system produces, read it.

The code is the source of truth. Every claim below cites the implementing file; if this document and the code ever disagree, the code wins and this document has a bug. Metrics and split dates reflect the models trained on **2026-07-03** (`data/models/model_metadata.json`).

Contents:

1. [Data](#1-data)
2. [Features](#2-features)
3. [Models & evaluation](#3-models--evaluation)
4. [Backtesting](#4-backtesting)
5. [Probability model](#5-probability-model)
6. [Statistical validation](#6-statistical-validation)
7. [Predictability score & variance decomposition](#7-predictability-score--variance-decomposition)
8. [Assumptions & limitations](#8-assumptions--limitations)

---

## 1. Data

### Training source

Models are trained from a single flat file, `data/raw/PlayerStatistics.csv` — a Kaggle-distributed export of NBA API historical player box scores (one row per player per game). Loading and filtering happen in `load_and_filter_csv()` in `backend/nba_betting/ml/train_regression.py`:

- **Game types** — only `Regular Season`, `Playoffs`, and `Play-in Tournament` rows are kept (`VALID_GAME_TYPES`).
- **Modern era** — only games whose **NBA season-start year is ≥ 2016** are kept (`MIN_YEAR = 2016`, i.e. the 2016-17 season onward). The season-start year is derived from the game date with an **October 1 boundary**: a game in Oct–Dec belongs to the season of that calendar year; a game in Jan–Sep belongs to the previous year's season (`_season_start_year()`). The filter is derived from the parsed date — the CSV has no year column — and raises if it empties the dataset rather than silently no-opping. After filtering, the dataset is roughly 296,000 player-game rows spanning the 2016-17 through 2024-25 seasons.
- **Minutes eligibility** — rows where the player logged **fewer than 10 minutes** (`MIN_MINUTES = 10`) are *kept in the frame* so that rolling windows, season averages, days-rest, and opponent team totals see the full game universe, but they are **NaN-masked inside rolling windows** (they occupy a window slot without contributing a value) and are **excluded as training/evaluation targets** (`eligible_rows()`). After target eligibility, 206,994 rows remain (140,382 fit + 25,093 validation + 41,519 test; `data/models/model_metadata.json`).

### Serving source

Live predictions and backtests do **not** read the CSV. They read an ESPN-synced Django database (`Player`, `PlayerStats`, `Game` models), from which `backend/nba_betting/services/features.py` rebuilds the same features at request time.

> **Known train/serve source difference.** Training features come from the Kaggle/NBA-API CSV; serving and backtest features come from the ESPN-synced database. The pipeline *assumes* the two sources record identical minutes, field-goal splits, and box-score values for the same games. No reconciliation between the sources is performed. See §8.

---

## 2. Features

Each stat (`pts`, `reb`, `ast`) has its own model with its own feature list, defined once in `FEATURE_COLUMNS` in `backend/nba_betting/ml/train_regression.py` and consumed verbatim by the serving pipeline (`backend/nba_betting/services/features.py`) and the backtester (`backend/nba_betting/services/backtest.py`). That dictionary is the authoritative feature list; any other document describing features is derivative.

### The leakage rule

**Every rolling quantity applies `shift(1)` before the window.** The feature row aligned with game *t* is computed exclusively from games *t−1* and earlier — the target game never contributes to its own features. This holds for L5/L10 means, EMAs, rolling standard deviations, expanding season averages, and opponent-defense windows, in training (`build_player_features()`, `build_opponent_defense()`) and serving (`_add_rolling_features()`, `_get_season_avg()`, `_get_opponent_stat_allowed()`) alike.

### Feature definitions

For a player's chronologically ordered games, with sub-10-minute games NaN-masked inside windows (masked games consume a window slot but contribute no value):

| Feature | Definition |
|---|---|
| `{stat}_L5`, `{stat}_L10` | Mean of the stat over the previous 5 (10) games: `x.shift(1).rolling(w, min_periods=1).mean()` |
| `{stat}_ema_L5` | Exponentially weighted mean, span 5 (α = 2⁄6 ≈ 0.333): `x.shift(1).ewm(span=5, adjust=False).mean()` |
| `{stat}_std_L10` | Sample standard deviation (ddof = 1) over the previous ≤ 10 games, requiring ≥ 5 valid observations: `x.shift(1).rolling(10, min_periods=5).std()` |
| `season_avg_{stat}` | Expanding mean within (player, season), season bounded at **Oct 1**, over **all** games including sub-10-minute ones: `x.shift(1).expanding(min_periods=1).mean()` grouped by `(personId, season_year)` |
| `hot_cold_{stat}` | Recent form vs. season baseline: `(L5 − season_avg) / (|season_avg| + 0.1)` |
| `days_rest` | Days since the player's previous game (any game, regardless of minutes), `fillna(3)` for a player's first observed game, clipped at 10: `date.diff().dt.days.fillna(3).clip(upper=10)` |
| `is_home` | 1 if the player's team is the home team, else 0 |
| `fg_pct_L5`, `fg_pct_L10` | Rolling means of per-game FG% = FGM ⁄ FGA (0.0 when FGA = 0) |
| `min_L5`, `min_L10` | Rolling means of minutes played |
| `opp_{stat}_allowed_L10` | Opponent defensive context: for each (game, defending team), sum the stat over **all** opposing players (no minutes filter — team totals), then per defending team take `shift(1).rolling(10, min_periods=1).mean()` (`build_opponent_defense()`) |

### Per-stat feature sets

- **pts** (15): `is_home`, `days_rest`, `pts_L5`, `pts_L10`, `pts_ema_L5`, `pts_std_L10`, `reb_L5`, `ast_L5`, `min_L5`, `min_L10`, `fg_pct_L5`, `fg_pct_L10`, `season_avg_pts`, `hot_cold_pts`, `opp_pts_allowed_L10`
- **reb** (12): `is_home`, `days_rest`, `reb_L5`, `reb_L10`, `reb_ema_L5`, `reb_std_L10`, `pts_L5`, `min_L5`, `min_L10`, `season_avg_reb`, `hot_cold_reb`, `opp_reb_allowed_L10`
- **ast** (13): `is_home`, `days_rest`, `ast_L5`, `ast_L10`, `ast_ema_L5`, `ast_std_L10`, `pts_L5`, `min_L5`, `min_L10`, `fg_pct_L5`, `season_avg_ast`, `hot_cold_ast`, `opp_ast_allowed_L10`

### Serving fallbacks

When a live feature cannot be computed (short history, missing opponent data), the serving layer substitutes fixed constants: rolling stds fall back to `STD_DEFAULTS = {pts: 5.0, reb: 2.0, ast: 1.5}` (`backend/nba_betting/constants.py`), opponent-defense to a database-computed league average with hardcoded final fallbacks (112 / 44 / 26 for pts/reb/ast), season averages to 15 / 5 / 4, FG% to 0.45, and `days_rest` to 3 (`backend/nba_betting/services/features.py`). All missing-value substitution is NaN-aware (`_num_or()`), preserving legitimate zeros. Predictions built on fallbacks are extrapolations, not model-driven inferences — see §8.

### One-game staleness at live inference

`get_model_inputs()` (`backend/nba_betting/services/features.py`) anchors on the last *completed* game's feature row, whose `shift(1)` windows end at the game before that. Live predictions for the *upcoming* game therefore exclude the player's most recent completed game from every window, and `days_rest` describes the rest before the last game rather than before the game being predicted. This is a deliberate anti-leakage construction, but it means live features lag actual form by one game relative to the aligned features used in training and backtesting. See §8.

---

## 3. Models & evaluation

### Models

For each stat, four regressors are trained on the identical feature matrix (`train_all_regression_models()` in `backend/nba_betting/ml/train_regression.py`), each predicting the raw stat value (`reg:squarederror` / RMSE loss):

| Model | Role | Key settings |
|---|---|---|
| **XGBoost** | Primary serving model | depth 6, η 0.05, subsample 0.8, colsample 0.8, min_child_weight 5, ≤ 1000 rounds, early stopping 50 |
| Random Forest | Backtest comparison | 200 trees, depth 8, min leaf 5 |
| Linear Regression | Backtest comparison / sanity floor | OLS |
| CatBoost | Optional comparison | depth 6, lr 0.05, ≤ 1000 iterations, early stopping 50 |

### Three-way chronological split

`time_split()` sorts all target-eligible rows by date and cuts twice — no shuffling, no random folds:

| Partition | Date range | Rows | Purpose |
|---|---|---|---|
| **Fit** | < 2022-11-07 | 140,382 | Gradient fitting only |
| **Validation** | 2022-11-07 → 2023-12-06 | 25,093 | Early stopping only |
| **Test** | ≥ 2023-12-06 | 41,519 | Reported metrics only |

(The newest 20% of rows form the test set; the newest 15% of the remaining training rows form the validation slice — `VAL_FRAC`. Dates from `data/models/model_metadata.json`.)

**Early-stopping discipline.** XGBoost and CatBoost select their boosting-round count on the *validation* slice — a chronological carve-out from the tail of the training period. The test partition takes no part in any selection decision. XGBoost boosters are sliced to the selected rounds before saving, so the served model is exactly the model validation chose (`train_xgboost_regression()`).

For research-style evaluation, `walk_forward_splits()` additionally provides season-by-season folds (train on all seasons strictly before season *S*, test on *S*), with seasons defined by the same Oct-1 boundary.

### Held-out test performance

Test-set metrics for the 2026-07-03 models (`data/models/model_metadata.json`; test = Dec 2023 – Jun 2025, n = 37,241 per stat after per-stat feature dropna):

| Stat | XGBoost MAE | XGBoost RMSE | RF MAE | LinReg MAE | CatBoost MAE |
|---|---|---|---|---|---|
| Points | **4.95** | 6.36 | 4.96 | 4.97 | 4.95 |
| Rebounds | **1.99** | 2.61 | 1.99 | 1.99 | 1.99 |
| Assists | **1.49** | 1.96 | 1.49 | 1.49 | 1.48 |

Read these honestly: a typical points projection misses by about **5 points**, rebounds by **2**, assists by **1.5**. Two things are worth noticing. First, train/val/test metrics are close (pts MAE 4.65 / 4.90 / 4.95), so the models are not badly overfit. Second, **plain linear regression is within ~0.03 MAE of XGBoost on every stat** — nearly all of the extractable signal lives in the rolling averages themselves, and player-game outcomes are dominated by variance no box-score feature set explains. Perchance's headline value is *quantifying* that predictability ceiling per player, not claiming to beat it.

---

## 4. Backtesting

`run_backtest()` in `backend/nba_betting/services/backtest.py` replays a player's season game-by-game and simulates a betting record.

**The line is synthetic.** Real sportsbook lines are not stored. The "line" for each game is the player's own `{stat}_L5` — the shift(1) rolling 5-game average entering that game. Every hit rate, PnL, and ROI figure in the system is measured **against this self-generated baseline, not a market line**. Beating your own recent average is a much lower bar than beating a vigged, efficient sportsbook number; treat all backtest results as *relative benchmarks of model skill over a naive baseline*, never as evidence of market profitability.

Mechanics, per game in the requested window:

- **Eligibility** — only games where the player logged **≥ 10 minutes** are scored, matching the training-target population (`min >= 10` filter).
- **Bet direction** — OVER if `projection > line`, else UNDER.
- **Pushes voided** — if `actual == line` the game is skipped entirely, as a sportsbook would void the bet; pushes never count as wins or losses.
- **PnL at −110** — a correct call wins **+1.0** unit; an incorrect call loses **−1.1** units (`WIN_UNIT`, `LOSS_UNIT`), simulating standard two-way juice. Staking is flat (1 unit per bet).
- **ROI** — `total_pnl / (total_bets × 1.1) × 100`, i.e. profit over total risked units.
- **Features** — rebuilt from the ESPN-synced database with the same shift(1) windows, Oct-1 season averages (`_add_season_features()`), and all-player opponent team totals (`_batch_opponent_defense()`) as training.
- **Models** — any of `xgb`, `rf`, `lr`, or a `naive` baseline that projects the player's season average with no ML.

**Per-season seeding.** A management command pre-seeds backtests for every combination of the 18-player report roster (`SEASON_REPORT_PLAYERS`), three stats, four models, and four seasons (2022-23 through 2025-26, date ranges in `SEASON_DATES`, `backend/nba_betting/constants.py`). Cached `BacktestRun`/`BacktestResult` rows feed everything downstream: statistical validation, variance decomposition, the predictability leaderboard, and intelligence views.

**Backtest windows overlap the training data.** There is no guard preventing a backtest range from intersecting the model's training window. With the current split: the 2022-23 season lies inside the fit/validation partitions (partially in-sample for model weights); 2023-24 games before 2023-12-06 lie in the validation slice; 2023-24 games from Dec 2023 onward and all of 2024-25 lie in the *test* partition (out-of-sample for fitting and selection); and 2025-26 postdates the training CSV entirely (fully out-of-sample). Per-season results should be weighted accordingly. See §8.

---

## 5. Probability model

`calculate_probability()` in `backend/nba_betting/services/probability.py` is the single source of truth for `P(actual > line)`. Both consumers — the manual prediction endpoint (`backend/nba_betting/views.py`) and the daily-picks generator (`backend/nba_betting/management/commands/generate_daily_picks.py`) — route through it.

**Low-count stats (`ast`, `stl`, `blk`) — Poisson.** Discrete, right-skewed, low-mean counts are poorly served by a symmetric continuous density near half-point lines, so:

```
P(over) = 1 − F_Poisson(⌊line⌋; μ),   μ = max(projection, 0)
```

The Poisson's variance is tied to its mean, so no separate dispersion estimate is needed and no continuity correction is missed.

**High-count stats (`pts`, `reb`, `pra`) — Normal.** The actual is modeled as Normal, centered on the model projection, with the player's rolling std as dispersion:

```
P(over) = 1 − Φ((line − projection) / σ),   σ = max(std_L10, 0.5)
```

where `std_L10` is the player's `{stat}_std_L10` feature (sample std of the last ≤ 10 games, ≥ 5 observations required). NaN/missing stds fall back to `STD_DEFAULTS` and a hard floor `STD_FLOOR = 0.5` guards against degenerate near-zero stds (`backend/nba_betting/constants.py`). All fallback handling is NaN-safe.

**Clamping.** Every reported probability is clamped to **[0.01, 0.99]** (`PROB_CLAMP`). With 10-game dispersion windows and no injury or lineup information, the system cannot support near-certain claims, so it is not allowed to make them.

**What this model is not.** The projection is treated as the *exact* conditional mean (zero model uncertainty), the dispersion is the player's *marginal* game-to-game std rather than the residual std of the projection, and — critically — **no shrinkage is applied to `std_L10`**: it is a raw n ≤ 10 sample estimate with roughly 24–35% relative sampling error. These are material limitations, expanded in §8.

---

## 6. Statistical validation

`compute_statistical_validation()` in `backend/nba_betting/services/statistical_validation.py` answers, for one player + stat + season of cached backtest rows, four questions. All tests operate on the XGBoost run's per-game outcomes.

**Test 1 — Hit-rate significance (one-sided exact binomial).**
H₀: the true hit probability p = 0.524 (the break-even rate for −110 two-way pricing, 1.1⁄2.1). H₁: p > 0.524. `binomtest(hits, n, 0.524, alternative="greater")`. One-sided because the claim being tested is directional. Note the null value is only *borrowed* from sportsbook pricing — the hits are measured against the synthetic L5 line (§4), so rejecting H₀ does not imply profitability against real books; the payload says so explicitly.

**Test 2 — Edge–hit correlation (one-sided Spearman).**
Does a larger projected edge (|projection − line|) predict a higher hit rate? H₀: ρ ≤ 0; H₁: ρ > 0. `spearmanr(edges, corrects, alternative="greater")`, matching the directional claim (a two-sided p gated on ρ > 0 would be an inconsistent effective α). **Gate:** skipped entirely when n < 15 (`MIN_N_EDGE`). Degenerate samples (e.g. every prediction correct) return "not computable" rather than a NaN or a fake zero. A significant positive ρ is an *association* claim only.

**Test 3 — Calibration / bias (two-sided one-sample t-test).**
H₀: mean signed error (actual − projection) = 0; H₁: ≠ 0. `ttest_1samp(errors, 0.0)`. A significant result is labeled with its direction (under-/over-projects). A **non-significant result is labeled "No detectable bias" — never "well-calibrated"** — with an explicit low-power qualifier when n < 30; absence of evidence is not evidence of absence. NaN p-values (constant or singleton errors) are coerced to 1.0 rather than propagated.

**Test 4 — Sample adequacy.**
Plain-English gates rather than a hypothesis test: n < 30 (`MIN_N_RELIABLE`) flags all results as low-confidence and forces the overall verdict to "Insufficient data"; fewer than 5 games with edge ≥ 2 flags high-edge conclusions as unreliable.

**Standing disclosures.** Four methodological caveats ship inside *every* validation payload (`DISCLOSURES`), independent of the sample: (1) the backtest line is the player's own L5 average, not a sportsbook line, so beating 52.4% does not imply market profitability; (2) each panel is one of ~54 uncorrected player-stat tests, so some significant results are expected by chance alone; (3) the tests treat a player's games as independent draws, which serial dependence violates; (4) the roster was hand-selected for durability and consistency and results do not generalize to the league. These are restated as limitations in §8.

An overall verdict ("Strong/Moderate/Weak/No reliable signal") counts how many of the three tests came out favorably — it is a descriptive badge for one panel, not portfolio-level evidence.

---

## 7. Predictability score & variance decomposition

### Predictability score

The leaderboard score is computed by `pred_score_tier()` in `backend/nba_betting/utils/stats.py` from one season of backtest rows (actuals *y*, signed errors *e*, hit rate *h*). With population variances (÷ n):

```
R²   = max(0, 1 − Var(e) / Var(y))                    (variance explained by the model)
CV   = sd(y) / mean(y)                                (raw output volatility)

r2_s = clamp(R², 0, 1)
cv_s = clamp(1 − CV, 0, 1)                            (consistency: low volatility scores high)
hr_s = clamp((h − 0.524) / 0.476, 0, 1)               (hit-rate excess over −110 break-even)

score = 50·r2_s + 30·cv_s + 20·hr_s                   (0–100)
```

Tiers: **High ≥ 65**, **Moderate ≥ 40**, **Low < 40**. Returns nothing below 5 games. The 50/30/20 weights are design choices, not fitted parameters, and the hit-rate term inherits the synthetic-line caveat of §4.

### Variance decomposition

`compute_variance_decomposition()` in `backend/nba_betting/services/variance_decomp.py` partitions a player-season's observed stat variance:

```
Var(y) = model_r2 + opponent_delta + residual        (shares of total variance)
```

- **model_r2** — `max(0, 1 − SS_res/SS_total)` of the XGBoost projections.
- **opponent_eta2** — one-way ANOVA η² of opponent identity on raw actuals (*marginal*, descriptive; unadjusted for its ~25–30 groups and reported separately, not summed into the decomposition).
- **opponent_delta** — *incremental* opponent information: opponent dummies are regressed on the model residuals, and the result is used only if the regression **F-test rejects at α = 0.05**; the **degrees-of-freedom-adjusted R²** is then rescaled to total-variance units as `max(0, adj_R²) × (1 − model_r2)`. Raw R² of ~25–30 dummies on 60–80 games would be mechanically inflated (E[R²] ≈ p/n under pure noise), which is why both the adjustment and the gate exist.
- **residual** — `max(0, 1 − model_r2 − opponent_delta)`, the unexplained noise floor.

The module also reports distributional stats (CV, MAD, error skewness/kurtosis, Shapiro-Wilk or D'Agostino normality on errors), an intraclass correlation across opponents, and a per-model comparison table. All inputs are one player-season (~60–80 games), so every component carries wide sampling error — see §8.

---

## 8. Assumptions & limitations

This section is the heart of the document. It consolidates the assumption inventory from the 2026-07-02 methodology audit (`docs/audit/METHODOLOGY_AUDIT_2026-07-02.md`), deduplicated and updated for the fixes that landed with the 2026-07-03 retrain. Everything here is a *current* property of the system.

### 8.1 Data & provenance

- **Two unreconciled data sources.** Training features come from the Kaggle-distributed NBA API CSV (`data/raw/PlayerStatistics.csv`); serving and backtest features come from an ESPN-synced database. The pipeline assumes both report identical minutes, FG splits, and box scores for the same games. No reconciliation, cross-checking, or drift monitoring exists between them (`backend/nba_betting/ml/train_regression.py` vs. `backend/nba_betting/services/features.py`).
- **The CSV is trusted as-is.** No independent audit of the box-score values has been performed; any upstream data errors flow directly into models and metrics.
- **Era stationarity.** Restricting to season-start year ≥ 2016 assumes feature–target relationships are stable across 2016–2025 (rule changes, pace drift, three-point volume). Nothing enforces stationarity *within* that window.
- **Box scores only.** The models see no injury reports, lineup news, minutes projections, Vegas totals, or play-by-play context. Every prediction assumes the player takes the floor in a roughly typical role; the system has no way to know otherwise.
- **Same-date ordering.** `shift(1)` assumes no player logs two games with the same date; date ties would make the shift order ambiguous (harmless in the NBA schedule, but an assumption).

### 8.2 Evaluation design

- **Single chronological split.** All reported MAE/RMSE come from one fit/val/test cut (§3). There are no cross-validated uncertainty bands on the metrics themselves; a different split point would give somewhat different numbers.
- **Round count is the only formally protected hyperparameter.** Early stopping is disciplined (validation slice only, test untouched), but the remaining hyperparameters (depth, learning rate, feature sets, window lengths) were chosen during iterative development with repeated looks at this dataset. Informal selection effects of that kind are not quantified.
- **Backtest windows are not guarded against the training window.** `run_backtest()` accepts any date range. Under the current split: the 2022-23 season is partially in-sample for model weights (fit/val partitions); 2023-24 before Dec 2023 was the early-stopping validation slice; Dec 2023 – Jun 2025 is the test partition (out-of-sample for fitting and selection, but the same games whose aggregate metrics are reported in §3); only 2025-26 postdates the training data entirely. Aggregate hit rates that pool seasons mix these regimes, and the significance tests of §6 inherit the mixture.
- **Live inference is one game stale.** By construction (§2), live features exclude the player's most recent completed game, and `days_rest` describes the previous game rather than the one being predicted. Backtest rows use correctly aligned features, so backtest results modestly *overstate* live serving quality — the most recent game is the strongest single predictor in a 5-game window.
- **Fallback-driven predictions are not model-driven.** When history is too short or opponent data is missing, hardcoded circa-2024 constants (§2) stand in for features. Outputs built on fallbacks are not flagged as such in API responses.

### 8.3 Betting realism

- **The line is the player's own L5 average — not a market line.** This is the single most important caveat in the system. All hit rates, PnL, ROI, hit-rate significance verdicts, predictability scores, and intelligence views inherit it (`backend/nba_betting/services/backtest.py`). The 52.4% break-even null (§6) borrows a sportsbook constant and applies it to a non-sportsbook baseline: statistical significance against the L5 line is evidence of skill over a naive baseline, **not** of profitability against efficient, vigged, line-moving markets.
- **Idealized execution.** Flat 1-unit staking, constant −110 pricing on both sides, no line movement, no limits, no closing-line-value measurement, no bet sizing. Pushes are voided (as books do), but pushes against a rolling-average line are an artifact rather than a market phenomenon.
- **The public picks feed is selection-conditioned.** Daily picks are filtered to confidence ≥ 0.55 on the *recommended* side (`PICKS_MIN_CONFIDENCE`, `backend/nba_betting/views.py`); any published feed performance is conditional on that threshold, not the model's unconditional accuracy.
- **The Monte Carlo simulator is a separate model.** The simulator's prop table (`backend/nba_betting/services/simulator.py`) comes from a different generative process — an AR(1) around the season mean with Gaussian innovations, values clipped at 0, and *unclamped* empirical probabilities. Its probabilities and §5's can legitimately disagree for the same player and line.

### 8.4 Probability model

- **No shrinkage on `std_L10` — a noisy n ≤ 10 estimate.** The Normal dispersion is a ddof-1 sample std from as few as 5 and at most 10 games (~35% relative sampling error at n = 5, ~24% at n = 10), with a 0.5 floor as the only regularization. Shrinkage toward a player-season or league prior, or blending with the model's test RMSE, is **not implemented**. Consequences: understating σ by 30% inflates a true 60% edge to a reported ~63–65%, and the same player + line can swing several probability points week to week from estimator noise alone.
- **Marginal std, not residual std.** The Normal model uses the player's raw game-to-game std around the *projection*, treating the model's conditional mean as carrying the player's full marginal variance. The conceptually correct dispersion — the residual std of the projection (per-stat test RMSE is stored in `data/models/model_metadata.json`) — is not used at inference.
- **The projection is treated as exact.** No model uncertainty (estimation error in the XGBoost mean) enters the probability; the stated probabilities are conditional on the projection being the true mean.
- **Distributional shape assumptions.** Normal stats assume homoskedastic, symmetric errors; rebounds are discrete and right-skewed but modeled as Normal without continuity correction (only `ast`/`stl`/`blk` get the Poisson treatment). Poisson assumes equidispersion (variance = mean), which real assist distributions only approximate.
- **Clamping.** All reported probabilities are truncated to [0.01, 0.99]; the system deliberately never reports near-certainty (§5).

### 8.5 Statistical inference

- **Independence is assumed and known to be false.** The binomial, Spearman, and t-tests treat one player's games as i.i.d. draws. Streaks, role and minutes changes, schedule effects, and rest patterns induce serial dependence — the simulator itself fits a nonzero AR(1) φ to the same data — making nominal p-values anti-conservative (`backend/nba_betting/services/statistical_validation.py`).
- **~54 uncorrected panels, up to ~162 tests.** 18 players × 3 stats × 3 tests, each at per-test α = 0.05, with no family-wise or FDR correction. Under a global null, several "Significant" badges are expected by pure chance, and users browsing panels will naturally cherry-pick the green ones. The payload disclosure states this; Benjamini–Hochberg correction is an acknowledged upgrade over disclosure, not yet implemented.
- **Survivorship-biased roster.** The 18 report players were hand-selected *post hoc* for games played (70+), health, and consistency, with injury-shortened players explicitly replaced (`backend/nba_betting/constants.py`). Those are precisely the properties that make players easy to predict. Every per-player and aggregate result conditions on this favorable selection and does not generalize to NBA players at large.
- **Calibration test caveats.** The t-test assumes approximately normal errors or CLT-sized n; count-stat errors are right-skewed and n can be small. A non-significant result is reported as "No detectable bias" (with a low-power qualifier below n = 30) — it is not affirmative evidence of calibration.
- **Edge correlation is association, not profitability.** The Spearman outcome variable is binary and tie-heavy (reduced power), and a significant positive ρ says larger edges hit more often *within this sample against the synthetic line* — nothing about edge magnitudes being profitable.
- **Small-sample intelligence modules.** Variance decomposition, ICC, floor/ceiling profiles, and per-opponent views all operate on single player-seasons (~60–80 games, opponent groups of 2–3 games). `opponent_delta` is F-gated and df-adjusted (§7), which controls false positives but leaves low power; `opponent_eta2` remains an unadjusted descriptive quantity that overstates matchup effects at these group sizes; distributional labels (skewness, kurtosis, normality) carry wide sampling error.
- **The predictability score is a heuristic.** The 50/30/20 weights and tier cutoffs (§7) are design choices, not fitted or validated parameters; R² is floored at zero (a model worse than the mean scores 0, not negative); and the hit-rate component inherits every backtest caveat above.

### 8.6 Historical results

Results generated **before the 2026-07-03 retrain** — including `research/paper.tex`, its result CSVs, and documents in `docs/archive/` — were produced by a pipeline with defects that have since been fixed: an inactive modern-era filter (models actually trained on 1951–2025 data), a calendar-year season boundary in training, early stopping on the test partition, opponent-defense totals computed from a different player universe than serving, and a NaN-std bug that reported 99% confidence for data-poor players. **Do not cite pre-2026-07-03 numbers as describing the current system.** The research scripts have not yet been re-run against the retrained models; until they are, the paper's quantitative claims should be considered superseded.

---

*Questions or corrections: open an issue. If you find a claim in this document that the code contradicts, that is a bug in the document — please report it.*
