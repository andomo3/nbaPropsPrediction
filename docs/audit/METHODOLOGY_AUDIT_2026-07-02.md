# Methodology Audit — 2026-07-02

Produced by the `methodology-audit` workflow (5 dimension auditors, every finding adversarially verified by an independent agent). **43 confirmed findings** (6 critical, 15 major, 22 minor), 0 refuted, 42 assumptions to disclose in METHODOLOGY.md.

## Remediation log (updated 2026-07-03)

**Batch 1 — training pipeline (fixed, retrained, re-seeded):**
- Modern-era filter now derived from the game date (NBA season-start year ≥ 2016) and fails loudly; dataset went from ~1.1M rows (1946–2025) to 295,900 rows (2016–2025).
- Season boundary unified to Oct-1 across training / inference / backtest (`season_year`).
- Early stopping (XGBoost + CatBoost) now uses a chronological validation slice carved from the training tail (fit < 2022-11-07 | val → 2023-12-06 | test ≥ 2023-12-06); XGBoost boosters are sliced to the selected rounds before saving.
- Training now mirrors serving: sub-10-minute games NaN-masked inside rolling windows (not row-dropped), season averages over all games, opponent-defense totals from all players, days_rest over all games with fillna(3)+clip(10) on both paths.
- Backtest scores only ≥10-minute games and voids pushes (actual == line); `_batch_opponent_defense` memoized on (row count, latest date).
- All models retrained 2026-07-03; all four seasons re-seeded (780 runs; 84 skips are pre-existing DB coverage gaps for older seasons).

**Batch 2 — serving layer (fixed):**
- NaN `std_L10` → prob_over 0.99 bug fixed (`_num_or` NaN-safe fallbacks in features.py, including days_rest and fg_pct zero-coercion).
- `services/probability.py` is now the single prob_over path (Poisson for ast/stl/blk, Normal otherwise, clamped [0.01, 0.99]); ManualPredictionView and generate_daily_picks route through it.
- Fallback std constants unified in `constants.py` (`STD_DEFAULTS`), replacing three divergent copies.
- LitePicksView filters on the recommended side's probability (Unders no longer discarded); confidence_pct reports the recommended side.

**Batch 3 — statistical framing (fixed):**
- Four standing disclosures added to the validation payload (synthetic L5 line vs. 52.4% break-even, ~54 uncorrected panels, iid assumption, roster selection bias).
- Spearman edge–hit test is now one-sided (matching the directional claim); degenerate samples return "not computable" instead of NaN.
- Calibration label changed from "Well-calibrated" to "No detectable bias" (with low-power caveat below n=30); NaN t-test p-values no longer propagate.
- Insight narrative no longer overclaims (correlation ≠ profitability; break-even framed vs. its own L5 baseline).

**Batch 4 — analytics & research (fixed):**
- variance_decomp (C3): opponent_delta now uses df-adjusted R², an F-test gate (α=0.05), and is rescaled to total-variance units; phantom "Situational" component removed from the docstring; normality-vs-calibration conflation fixed in the insight text.
- `disclosures` rendered in the frontend (`StatisticalValidation.jsx`, collapsible "Methodology notes & limitations").
- Research scripts fixed (eligible_rows target filter, Oct-1 season years, chronological validation slices for early stopping) and re-run 2026-07-03: `research/results/*.csv` and `research/figures/*.png` regenerated from the corrected pipeline.
- `docs/METHODOLOGY.md` created (assumptions consolidated from this audit's 42 items).

**Batch 5 — docs & paper (fixed):**
- `research/paper.tex` fully corrected against the regenerated results: dataset (295,900 rows / 206,994 targets, 2016-17+ seasons), NBA-season walk-forward folds with a 15% fit/val split, honest MAEs (XGB 4.92/1.99/1.45), SHAP re-ranked from the 2024-25 hold-out (the "home-court playmaking" finding did not survive), betting ROI vs LinReg line revised +13.1% → +6.4% with narrow-margin framing, Table 3 caption fixed, single data-provenance story, new iid/baseline-relativity limitations paragraph.
- `docs/ARCHITECTURE.md` rewritten for the regression system (classifier confined to a History section) with a Known Limitations section; `docs/METHODOLOGY.md` created; `docs/ML_FEATURE_GUIDE.md` rewritten from `FEATURE_COLUMNS`; `README_FEATURES.md` replaced with a pointer; stale docs archived to `docs/archive/` with banners.

**Still open:** floor_ceiling distributional claims, backtest range guard vs. model windows, Benjamini–Hochberg as an upgrade over disclosure, README score-formula wording (R² term description garbled at line ~189), frontend viewership pass, tests/CI, notebook, dead-code removal + views.py split (plan phases 2-3/5-6).


## CRITICAL (6)

### C1. season_avg uses calendar-year season boundary in training but Oct-1 NBA-season boundary at inference and in backtest

**Where:** `backend/nba_betting/ml/train_regression.py:242`

**Evidence:** train_regression.py:239-247 groups season_avg by _season_year = CSV 'year' column else pd.to_datetime(df['date']).dt.year. I verified data/raw/PlayerStatistics.csv has NO 'year' column (header: firstName,lastName,personId,gameId,gameDateTimeEst,...), so the calendar-year fallback is definitively the active path. At inference, services/features.py:233-235 uses `season_start_year = ref.year if ref.month >= 10 else ref.year - 1; season_start = Timestamp(f"{season_start_year}-10-01")`. In backtest, services/backtest.py:274-276 uses `d.year if d.month >= 10 else d.year - 1`. So the model was trained on a season_avg that resets every Jan 1 (splitting each real NBA season in two and merging the Jan-Jun tail of season N with the Oct-Dec start of season N+1), while both serving paths compute a correctly Oct-bounded season average.

**Why it matters:** season_avg_{pts,reb,ast} and the derived hot_cold_{stat} (train_regression.py:251-253, which divides by season_avg) are core features in all three models. The trained model learned coefficients/splits against a systematically different feature distribution than it receives at serve time: in Oct-Dec the training feature was a fresh same-calendar-year expanding mean (1-30 games) while serving supplies a mean since Oct 1 of the same season; in Jan-Jun training's feature reset to near-empty while serving's has 30+ games. Every backtest hit-rate/ROI figure and every live projection is produced under this skew, so published accuracy claims do not measure the model as trained.

**Fix:** In build_player_features, replace the calendar-year fallback with the same Oct-1 heuristic: _season_year = date.dt.year.where(date.dt.month >= 10, date.dt.year - 1); retrain, and delete the misleading comment at train_regression.py:237-239 claiming the calendar year is 'consistent across both sources'.

<details><summary>Verifier verdict</summary>

CONFIRMED train/serve skew. Training (backend/nba_betting/ml/train_regression.py:239-248) groups the season_avg expanding mean by (personId, _season_year) where _season_year falls back to calendar year of the game date; I verified data/raw/PlayerStatistics.csv has no 'year' column (header: firstName,lastName,personId,gameId,gameDateTimeEst,...), so the calendar-year fallback is the active path. The only other 'year' source, walk_forward_splits (line 352), is also calendar-year, so no ordering scenario changes this. Inference (services/features.py:234-235) computes season_avg from an Oct-1 NBA-season boundary and feeds it into the model row (features.py:60-62, 86, 94, 102); backtest (services/backtest.py:274-276) also uses the Oct boundary. Consequence: training season_avg resets every Jan 1 (splitting each real NBA season and merging Oct-Dec of season N+1 with Jan-Jun of season N in the grouping key), while both serving paths compute a full-season Oct-bounded average — the feature distributions differ materially Jan-Jun. The skew also propagates to hot_cold_* (train_regression.py:250-253), which is derived from season_avg. The code comment at train_regression.py:237-238 claiming consistency is false relative to serving code.

</details>

### C2. NaN std_L10 silently produces prob_over = 0.99 for players with short history (live API and daily picks)

**Where:** `backend/nba_betting/services/features.py:73`

**Evidence:** features.py:73-75 uses `float(latest.get("pts_std_L10") or 5.0)` — np.nan is truthy, so NaN bypasses the `or` fallback. Rows with <6 valid prior games survive get_model_inputs' dropna (features.py:36-39 only checks L5/L10 columns built with min_periods=1) while std_L10 needs min_periods=5 (features.py:216). The NaN then reaches views.py:143-149: `max(nan, 0.5)` returns nan, `norm.cdf(nan)` is nan, and `max(0.01, min(0.99, 1-nan))` evaluates to exactly 0.99 because `nan < 0.99` is False in Python's min(). Identical arithmetic in generate_daily_picks.py:134-142, where the fabricated prob_over=0.99 is persisted to DailyPick, passes the PICKS_MIN_CONFIDENCE=0.55 filter (views.py:192-195), and sorts to the top of the feed (models.py:99, ordering=["-prob_over"]).

**Why it matters:** The system reports maximal (99%) confidence precisely when it has the least data — regardless of whether the projection is above or below the line. prob_under is simultaneously reported as 0.01 even when the recommendation is UNDER. Any calibration analysis, and the public picks feed, are contaminated by data-poor players surfacing as the most confident picks.

**Fix:** Replace the truthiness fallback with an explicit NaN check: `v = latest.get(f"{stat}_std_L10"); std = float(v) if v is not None and not pd.isna(v) else default` (backtest.py's _safe() at backtest.py:132-134 already does this correctly — reuse it), and add an `assert not math.isnan(std_dev)` guard before the z-score in views.py and generate_daily_picks.py.

<details><summary>Verifier verdict</summary>

Confirmed by reading every link in the chain. (1) features.py:73-75 uses `float(latest.get("pts_std_L10") or 5.0)`; NaN is truthy so the fallback never triggers. (2) The dropna at features.py:36-39 only covers mean columns built with min_periods=1 (features.py:206), while *_std_L10 needs 5 valid prior games (min_periods=5, features.py:216) and is not in the dropna subset — so a player with 1-4 valid prior games yields a surviving row with NaN std (finding's '<6 valid prior games' is a harmless off-by-one; exact condition is <=4 valid priors). (3) {stat}_std_L10 is in FEATURE_COLUMNS for all stats (train_regression.py:52,61,68), so views.py:142-143 reads the NaN from the feature row instead of using the line-145 default. (4) XGBoost treats NaN as missing (predictor.py:117-119), so a real projection is returned and execution reaches the probability math. (5) views.py:146 max(nan, 0.5)=nan; norm.cdf(nan)=nan; views.py:149 min(0.99, nan)=0.99 because nan<0.99 is False and 0.99 is the first argument, then max(0.01, 0.99)=0.99 — prob_over is exactly 0.99. (6) generate_daily_picks.py:133-142 has identical arithmetic and persists prob_over=0.99 to DailyPick (lines 146-158). (7) It passes the PICKS_MIN_CONFIDENCE=0.55 filter (views.py:192-195) and sorts first via models.py:99 ordering=["-prob_over"], which LitePicksView does not override. Refutation attempts (column-presence guard, get_std_for_stat's correct dropna, XGBoost NaN handling, the try/except in the command) all fail — none intercepts the NaN path.

</details>

### C3. Variance decomposition mixes variance scales and ignores degrees of freedom: opponent_delta is mechanically inflated noise presented as 'matchup sensitivity'

**Where:** `backend/nba_betting/services/variance_decomp.py:229`

**Evidence:** variance_decomp.py:229-238 regresses model residuals on ~up-to-29 opponent dummies over a single-season sample (n>=5 accepted, typically 60-80 games) and takes raw `ols_result.rsquared` with no adjustment: under the null of zero opponent effect, expected R^2 ≈ (g-1)/(n-1) ≈ 0.3-0.4. The insight threshold at line 408 declares 'meaningful matchup sensitivity' at opp_d >= 0.08 — far below the null expectation. Separately, line 241 computes `residual = 1.0 - model_r2 - opponent_delta`, subtracting a fraction of RESIDUAL variance from TOTAL-variance shares; the correct total-variance share is opponent_delta*(1-model_r2). The module docstring (lines 9, 17) also promises a 'Situational' component that is never computed.

**Why it matters:** Both errors push in the same direction: opponent effects are overstated (overfit R^2, then over-weighted by the unit mix) and the noise floor understated. The user-facing insight ('Opponent identity explains an additional X% of variance beyond the model') will assert matchup effects that are pure sampling noise for essentially every player, invalidating the headline claim of the decomposition.

**Fix:** Use adjusted R^2 (or an F-test p-value gate) for the opponent-dummy regression, convert to total-variance units via opponent_share = max(0, adj_R2)*(1-model_r2) before computing residual, and remove 'Situational' from the docstring or implement it.

<details><summary>Verifier verdict</summary>

Verified in backend/nba_betting/services/variance_decomp.py. (1) Lines 229-238: model residuals are regressed on pd.get_dummies(opponents, drop_first=True) — up to 29 dummies for a full-season run (SEASON_DATES in constants.py:38-43 spans whole Oct-Jun seasons, so n ≈ 60-82) — and line 234 takes raw ols_result.rsquared with no adjusted-R², F-test, or df correction. Under the null E[R²] = (g-1)/(n-1) ≈ 0.35-0.45, and the only guards (n>=5 at line 102, g<n at line 229) allow even worse ratios (n=30, g=25 → null E[R²] ≈ 0.83). Line 408 flags 'meaningful matchup sensitivity' at opp_d >= 0.08, far below the null expectation, so the insight fires mechanically. (2) Line 241 computes residual = 1 - model_r2 - opponent_delta, mixing scales: opponent_delta is a fraction of residual variance (R² of the error regression) subtracted directly from total-variance shares; the consistent share is opponent_delta*(1-model_r2). The insight text at lines 409-411 then presents the mis-scaled value as a percent of total variance. (3) Docstring line 9 promises a 'Situational' component; the returned dict (lines 243-248) contains only model_r2, opponent_eta2, opponent_delta, residual — it is never computed. Severity: MAJOR — opponent_delta is upward-biased noise presented as a substantive matchup-sensitivity claim for essentially every player.

</details>

### C4. docs/ARCHITECTURE.md describes a binary classification system (AUC 0.62-0.65, 17 shared features, predict_probability) that no longer exists — production is per-stat regression

**Where:** `docs/ARCHITECTURE.md:170`

**Evidence:** ARCHITECTURE.md:48 'XGBoost — primary classifier (binary: over vs under rolling average)'; :170 'Model target: Binary classification'; :174 'Reported AUC: ~0.62-0.65'; :186-217 a single 17-feature table; :184 'predictor.predict_probability() returns P(actual > rolling_L5_avg)'; :326 'The AUC of ~0.63 translates roughly to this range'. Actual code: ml/train_regression.py:49-93 trains reg:squarederror regressors with stat-specific feature sets of 15 (pts), 12 (reb), 13 (ast) features including season_avg_*, hot_cold_*, opp_reb/ast_allowed_L10 (absent from the doc's table); ml/predictor.py:93 exposes predict_projection (there is no predict_probability); services/backtest.py:176-184 compares projection to the L5 line. The doc also references notebooks/model_trainer.py (:90, :164) which does not exist (notebooks/ contains only data_cleaning_pipeline.py and feature_engineering.py), claims 'Django 6' (:40) vs backend/requirements.txt 'Django>=5.0', and 'trained once using ~3 seasons of historical NBA data' (:154) vs the actual 1.12M-row multi-decade training set.

**Why it matters:** The doc self-describes as 'Last updated: April 2026 ... the current production system'. Anyone auditing or reproducing the system from this document will evaluate the wrong model class, wrong target, wrong feature set and wrong metrics (AUC is undefined for the current regression models).

**Fix:** Rewrite sections 2, 4, 5 and 8 of ARCHITECTURE.md against ml/train_regression.py, ml/predictor.py and services/backtest.py, or mark the document as historical (mvp-branch) and point to current docs.

<details><summary>Verifier verdict</summary>

Confirmed. Every quoted doc passage exists (ARCHITECTURE.md:48 binary classifier, :170 binary target, :174 AUC 0.62-0.65, :190-210 single 17-feature table, :182/:311 predict_probability, :326 AUC translation, :88 model_trainer.py, :40 Django 6, :154 ~3 seasons) and every code contradiction verified: ml/train_regression.py:49-74/:84 trains reg:squarederror regressors with per-stat feature sets of 15/12/13 including season_avg_*, hot_cold_*, opp_reb/ast_allowed_L10 absent from the doc table; its docstring says it replaces the old binary classifier. predictor.py:93 exposes predict_projection and grep finds zero predict_probability in the backend; all callers (views.py:127, backtest.py:176, generate_daily_picks.py:125) use predict_projection. backtest.py:124,:181-183 compares projection to the L5 line. notebooks/ has no model_trainer.py. requirements.txt says Django>=5.0. model_metadata.json shows 896,643 train + 224,174 test rows (~1.12M, MIN_YEAR=2016 — so 'multi-decade' in the finding slightly overstates, it is ~one decade, but the doc's '~3 seasons' is still wrong). The doc claims 'Last updated April 2026' and to describe the current production system, so it is not an intentionally historical document. MINOR/doc-severity but real.

</details>

### C5. Paper's '2016+ modern-era' dataset claim is false — the year filter in the code silently no-ops and models train on 1951-2025 data

**Where:** `research/paper.tex:224`

**Evidence:** paper.tex:221-231 claims: 'restricting to seasons from 2016 onward to reflect modern-era play style, 1,120,817 records remain across 4,273 unique players' (abstract line 68: 'Trained on 1.1 million player-game observations spanning 2016--2024'). But backend/nba_betting/ml/train_regression.py:150-151 only applies the MIN_YEAR=2016 filter 'if "year" in df.columns', and data/raw/PlayerStatistics.csv has NO 'year' column (verified: header contains firstName..plusMinusPoints, no year). Empirical check: gameType + min>=10 filters alone (no year filter) yield exactly 1,120,817 rows spanning 1951-11-11 to 2025-06-22 with 4,273 unique players; only 230,900 rows are from Oct 2015 onward. data/models/model_metadata.json corroborates: split_date '2015-12-15' with train_rows 896,643 — i.e. the production 80/20 chronological split places 80% of training data before Dec 2015.

**Why it matters:** Every published number (MAE table, betting ROI, SHAP importances, production model) was computed on ~74 years of data, 80% of it pre-2016, while the paper explicitly argues that including pre-2016 data 'risks introducing distribution mismatch'. The paper's own methodological rationale is contradicted by what the code actually did; the headline sample-size and era claims are unverifiable as stated and provably wrong as implemented.

**Fix:** In load_and_filter_csv, derive the season year from gameDateTimeEst (e.g. NBA season-start year) and apply the >=2016 filter unconditionally; re-run training, walk_forward_eval.py, betting_simulation.py and shap_analysis.py; or correct the paper to state the data actually spans 1951-2025.

<details><summary>Verifier verdict</summary>

Confirmed by direct code reading and empirical reproduction. (1) backend/nba_betting/ml/train_regression.py:150-151 applies the MIN_YEAR=2016 filter only `if "year" in df.columns`; the CSV header of data/raw/PlayerStatistics.csv (read directly) has no `year` column, so the filter silently no-ops. (2) Reproducing the pipeline's remaining filters (gameType in {Regular Season, Playoffs, Play-in Tournament} + numMinutes>=10) on the raw 1,648,656-row CSV yields exactly 1,120,817 rows and exactly 4,273 unique players — the precise figures paper.tex:221-226 attributes to the post-2016 dataset — spanning 1951-11-11 to 2025-06-22, with only 230,900 rows on/after 2015-10-01. (3) data/models/model_metadata.json (trained 2026-06-15) corroborates: train_rows 896,643 + test_rows 224,174 = 1,120,817, and split_date "2015-12-15"; time_split (train_regression.py:317-324) puts the split at the 80th-percentile date, and my reproduction of that percentile on the year-unfiltered data is exactly 2015-12-15 — arithmetically impossible if the data were 2016+. Hence paper.tex:224-225 ("restricting to seasons from 2016 onward... 1,120,817 records") and abstract line 68 ("spanning 2016--2024") are false: production models train on 1951-2025 data, with ~80% of training rows predating Dec 2015. All refutation attempts (alternate data path adding a year column, stale metadata, coincidental counts) failed.

</details>

### C6. Paper's walk-forward fold definitions (Train 2016-2020 -> Test 2021, per season) do not match the code, which trains on 1951-2020 and slices test folds by calendar year

**Where:** `research/paper.tex:349`

**Evidence:** paper.tex Table 2 (lines 341-355) states folds 'Train 2016--2020 / Test 2021' etc., and section 4.2 says the model 'is tested on the immediately following season only'. In train_regression.py:348-359, walk_forward_splits falls back to df['year'] = pd.to_datetime(df['date']).dt.year when no 'year' column exists (which is the case, see finding 1), then uses df[df['year'] < test_year] for train. So fold 1 actually trains on ALL data 1951-2020 and tests on calendar-year 2021 games — a slice mixing the end of the 2020-21 season and the start of the 2021-22 season, not a single NBA season.

**Why it matters:** The temporal-generalization protocol described in the paper (season-aligned rolling-origin CV over a fixed 2016+ window) is not the protocol that produced Tables 3, 6 and the betting results (N=94,462 = 28,338+23,212+20,338+22,574 calendar-year rows). Reviewers/readers cannot reproduce the claimed folds from the described design.

**Fix:** Either implement true NBA-season folds (season-start-year from date) with the 2016 cutoff and re-run, or rewrite section 4.2/Table 2 to describe calendar-year folds over all-era training data.

<details><summary>Verifier verdict</summary>

CONFIRMED. (1) data/raw/PlayerStatistics.csv has no 'year' column (verified header), so the MIN_YEAR=2016 filter in load_and_filter_csv (train_regression.py:150-151) is silently skipped; running the actual function yields 1,120,817 rows spanning 1951-2025 with 898,896 rows before 2016. (2) walk_forward_splits (train_regression.py:348-358) falls back to calendar year from date and trains on df[year < test_year] with no lower bound, so fold 1 trains on 1,007,957 rows from 1951-2020, contradicting paper.tex:349 'Train 2016--2020'. (3) The 2021 test fold in research/results/walk_forward_predictions.csv spans 2021-01-02 to 2021-12-31 (months 1-7 and 10-12), mixing the end of the 2020-21 season with the start of 2021-22, contradicting paper.tex:338-339 'tested on the immediately following season only'. (4) The paper's reported fold sizes (28,338 for 2021, 20,338 for 2023; paper.tex:359-360) exactly match research/results/walk_forward_metrics.csv produced by research/walk_forward_eval.py via this exact code path, proving the published results came from the mismatched pipeline. The anomaly that 2021 is the largest fold is itself a fingerprint of calendar-year slicing (two partial seasons in one calendar year).

</details>

## MAJOR (15)

### M1. README_FEATURES.md claims to describe 'the current leakage-safe feature engineering pipeline' but documents features that do not exist in the code and are not used by any trained model

**Where:** `README_FEATURES.md:40`

**Evidence:** README_FEATURES.md:40-46 documents a `rest_category` feature ('0: back-to-back, 1: one day rest, 2: two or more days rest') and says 'days_rest is currently retained' — grep of notebooks/ finds neither rest_category nor days_rest. :57-59 names the trend features `pts_trend_holt_damped`/`reb_trend_holt_damped`/`ast_trend_holt_damped` — notebooks/feature_engineering.py:205 produces `trend_pts`/`trend_reb`/`trend_ast`. :86 claims 'opp_pts_allowed_L10 (compatibility alias to opp_avg_pts_allowed_L10)' — no such alias is created (feature_engineering.py:235-265 emits only opp_avg_*_allowed_l10). More fundamentally, none of the documented features (Holt trends, fga_per_min_L10, proj_volume, cv_L10) appear in FEATURE_COLUMNS (train_regression.py:49-74), so the 'current' pipeline described here feeds no deployed model.

**Why it matters:** A contributor or reviewer reading this guide would believe the shipped models consume trajectory/volume/volatility features that in reality are an orphaned Spark/Postgres pipeline; methodological claims about the model's inputs are wrong.

**Fix:** Retitle the doc as describing the experimental notebooks/arch-migration pipeline, fix the feature names (trend_pts etc.), delete the rest_category and alias claims, and add a pointer to FEATURE_COLUMNS in ml/train_regression.py as the authoritative model feature list.

<details><summary>Verifier verdict</summary>

Confirmed on all evidence points. (1) rest_category (README_FEATURES.md:40-43) exists nowhere in code — repo-wide grep matches only the README itself; notebooks/feature_engineering.py never computes it. (2) days_rest is absent from notebooks/feature_engineering.py, the file the README section documents (though it does exist in backend train_regression.py:227 and services/features.py:191, so the 'retained' sentence is only misleading in context, not flatly false). (3) README:57-59 names pts/reb/ast_trend_holt_damped, but feature_engineering.py:205 (and derived_cols at 280-282, SQL view at 30-32) produce trend_pts/trend_reb/trend_ast; no *_holt_damped name exists anywhere. (4) README:86's claimed alias opp_pts_allowed_L10 → opp_avg_pts_allowed_L10 is never created; feature_engineering.py:235-241/289-291 emit only opp_avg_*_allowed_l10, and the backend's opp_pts_allowed_L10 is computed independently in train_regression.py:293-303. (5) None of the notebook pipeline's outputs (trend_*, fga_per_min_l10, proj_volume, cv_l10) appear in FEATURE_COLUMNS (train_regression.py:49-74) or anywhere in backend/ (grep returns zero matches), and model_metadata.json feature lists match train_regression's columns — so the 'current' pipeline the README describes feeds no deployed model. Docs-vs-code mismatch, within methodology-auditor scope; severity is doc-level (MINOR/MAJOR) since no computation is wrong, but the finding as stated is real.

</details>

### M2. Hand-picked 18-player roster is selected on durability and consistency (survivorship bias); no caveat attaches to any result

**Where:** `backend/nba_betting/constants.py:12`

**Evidence:** constants.py:12-34 comments state the selection criteria explicitly: "Kept — full/near-full 2025-26 seasons", "Replacing injury-shortened players", "Expansion — 70+ games, high consistency". views.py:377-390 hard-rejects any player outside this list, and the rankings view (views.py:660-711) aggregates hit_rate/ROI across exactly these players. Neither statistical_validation.py's payload nor the rankings payload carries any selection-bias caveat.

**Why it matters:** Players were chosen on the very properties (low variance, high minutes, no injuries) that make them easiest to predict and that inflate hit rates. Injury-shortened players were replaced after the fact — literal survivorship bias. Any aggregate or per-player significance claim conditions on this favorable selection and cannot generalize to NBA players at large; the binomial p-values answer "is THIS hand-picked player predictable" while the UI framing implies model-level skill.

**Fix:** Add a roster-selection disclosure to the validation payload (and docs/METHODOLOGY.md): players were selected post hoc for games played and consistency, so results describe this roster only. For any model-level claim, evaluate on an unselected or pre-registered player set.

<details><summary>Verifier verdict</summary>

Verified on all points. constants.py:12-34 contains the exact selection-criteria comments claimed ("Kept — full/near-full 2025-26 seasons", "Replacing injury-shortened players", "Expansion — 70+ games, high consistency"), i.e., players chosen for durability/consistency. views.py:377-390 returns 404 for any player outside SEASON_REPORT_PLAYERS, and the rankings view (views.py:660-711) computes hit_rate/ROI/PnL rows exclusively over that roster (filter player_name__in=SEASON_REPORT_PLAYERS at line 668) with no caveat field in the response. statistical_validation.py's warnings (_sample_warnings, lines 162-183) cover only sample-size issues, never selection bias; a repo-wide grep for selection/survivorship/caveat finds no disclosure in any payload or docs/METHODOLOGY.md. The repo's own docs/OPEN_SOURCE_READINESS_PLAN.md:20 acknowledges this exact gap as an open disclosure item, and the auditor checklist (methodology-auditor.md:32) requires the caveat. Only trivial nit: the rankings view reports per-player metrics across the roster rather than a single pooled aggregate, but the substance of the finding stands.

</details>

### M3. XGBoost early stopping (and CatBoost use_best_model) selects boosting rounds on the test set itself — eval set is not past-only

**Where:** `backend/nba_betting/ml/train_regression.py:395`

**Evidence:** train_xgboost_regression builds dtest from the chronological TEST partition and passes it as the early-stopping eval set: `evals=[(dtrain, "train"), (dtest, "eval")], early_stopping_rounds=early_stopping` (lines 391-398). train_all_regression_models calls it with X_test/y_test from time_split (lines 537-539). CatBoost does the same: `model.fit(X_train, y_train, eval_set=(X_test, y_test), use_best_model=True)` (lines 457-461). Per data/models/model_metadata.json the split_date is 2015-12-15, so the eval window spans 2015-12-15 through the present — including the 2023-2026 seasons that services/backtest.py and services/statistical_validation.py later score as out-of-sample.

**Why it matters:** The number of boosting rounds is a model-selection decision made using test-set outcomes, so the 'test' MAE/RMSE in model_metadata.json are optimistically biased and no longer held-out estimates. Worse, the deployed xgb model's stopping round was tuned on the exact games later used for backtest hit rates and for the binomial/Spearman/t-test p-values in statistical_validation.py, formally breaking the independence between model selection and evaluation that those significance tests assume. This directly violates the checklist item 'early-stopping validation set is drawn from the past relative to the test period'.

**Fix:** Carve a chronological validation slice from the tail of the training period (e.g., train < date A, valid [A, split_date), test >= split_date) and pass only that slice as the early-stopping eval set for both XGBoost and CatBoost; report test metrics from a partition never seen by any selection step.

<details><summary>Verifier verdict</summary>

Confirmed. train_xgboost_regression (ml/train_regression.py:388-398) passes dtest — built from the chronological TEST partition — as the last eval set with early_stopping_rounds=50, so XGBoost selects the boosting-round count on the same data whose MAE/RMSE are reported as test metrics (lines 400-403); train_all_regression_models supplies X_test/y_test from time_split (lines 497, 529-539), which produces only train/test with no separate validation partition (lines 317-324; walk_forward_splits at 327 is unused here). CatBoost has the identical defect at lines 457-461 (eval_set=(X_test, y_test), use_best_model=True). Per data/models/model_metadata.json (split_date 2015-12-15, trained_at 2026-06-15) the test/eval window runs from 2015-12-15 to the present, and services/statistical_validation.py:29,41-50 with constants.py:38-45 (SEASON_DATES 2023-2026) plus services/backtest.py score exactly those seasons as out-of-sample using the saved xgb model — so they overlap the early-stopping selection window. This violates the checklist item at .claude/agents/methodology-auditor.md:20. Severity caveat: only one hyperparameter (n rounds) leaks, so the optimism is mild; RF/LR models are unaffected. A side observation strengthens the finding: the MIN_YEAR=2016 filter (train_regression.py:150-151) is conditional on a 'year' column and evidently never fired (an 80/20 split of 2016+ data could not land at 2015-12-15), so the eval window is even wider than intended.

</details>

### M4. MIN_YEAR era filter silently no-ops (CSV has no 'year' column), placing the chronological split at 2015-12-15 instead of the modern era

**Where:** `backend/nba_betting/ml/train_regression.py:150`

**Evidence:** load_and_filter_csv guards the era filter with `if "year" in df.columns:` (lines 150-151). The actual data/raw/PlayerStatistics.csv header (verified) is `firstName,lastName,personId,gameId,gameDateTimeEst,...` — no 'year' column — so the >= 2016 filter never runs. Consequence visible in data/models/model_metadata.json: `"csv_min_year": 2016` but `"split_date": "2015-12-15"` with 896,643 train rows — i.e., 80% of all rows predate Dec 2015, meaning the dataset spans the full NBA history and the deployed models' weights are fit almost entirely on pre-2016 basketball. The same missing column makes `_season_year` fall back to calendar year (lines 239-242), so training season_avg groups Jan-Dec while inference (features.py:234) and backtest (backtest.py:274) use Oct-start seasons.

**Why it matters:** The split is still chronological (no leakage of future rows into training weights), but it is not where the code claims: every modern season (2016-2026) sits in the early-stopping eval partition, amplifying the finding above, and the metadata claim csv_min_year=2016 is false as applied. It also means the model evaluated in backtests learned from a data distribution (1946-2015) that does not match documentation.

**Fix:** Filter on the parsed date instead: after building df['date'], apply `df = df[df['date'].dt.year >= MIN_YEAR]` (or derive an NBA season-start year from the date and filter/group on that), and fail loudly rather than silently skipping the filter.

<details><summary>Verifier verdict</summary>

CONFIRMED. (1) train_regression.py:150-151 guards the MIN_YEAR=2016 filter (line 43) with `if "year" in df.columns:`; the actual data/raw/PlayerStatistics.csv header (verified directly; default path per train_regression.py:104-105) has no 'year' column, so the era filter silently never executes. (2) data/models/model_metadata.json corroborates: "csv_min_year": 2016 alongside "split_date": "2015-12-15" and 896,643 train rows — an 80/20 chronological split landing in Dec 2015 is only possible if pre-2016 rows survived, and the ~1.12M total rows are far too many for 2016+ data alone (~250-300k). The deployed models are therefore trained almost entirely on pre-2016 basketball while metadata claims a modern-era dataset. (3) The same missing column makes _season_year fall back to calendar year (train_regression.py:239-242, Jan-Dec grouping), while inference (features.py:234) and backtest (backtest.py:274-276) both use Oct-start NBA seasons — a real train/serve skew in season_avg_* and the derived hot_cold_* features; the code comment at train_regression.py:237-238 claiming consistency is false. No refutation angle succeeded.

</details>

### M5. Opponent-defense features computed from >=10-minute players only in training but from all players at inference and backtest

**Where:** `backend/nba_betting/ml/train_regression.py:155`

**Evidence:** load_and_filter_csv drops all rows with numMinutes < 10 (train_regression.py:44, 155) BEFORE build_opponent_defense(df) is called (line 494), so team_game 'pts_allowed'/'reb_allowed'/'ast_allowed' (lines 274-288) sum only players who logged >=10 minutes. At inference, features.py:_get_opponent_stat_allowed (lines 269-290) sums ALL PlayerStats rows of the attacking team with no minutes filter; backtest.py:_batch_opponent_defense (lines 313-346) likewise has no minutes filter. Sub-10-minute bench/garbage-time players' points, rebounds and assists are therefore included at serve time but excluded at train time.

**Why it matters:** opp_pts_allowed_L10 / opp_reb_allowed_L10 / opp_ast_allowed_L10 are systematically higher at serving than the distribution the model saw in training (bench players under 10 minutes collectively contribute a nontrivial share of team totals). The model's learned response to opponent defense is applied at a shifted operating point for every prediction and every backtest row, biasing projections in a stat-dependent direction.

**Fix:** Apply the same minutes cutoff in both serving aggregations (filter rows with min < 10 before summing in features.py:_get_opponent_stat_allowed and backtest.py:_batch_opponent_defense), or drop the minutes filter before build_opponent_defense in training so all three sum full team totals.

<details><summary>Verifier verdict</summary>

Confirmed with file:line evidence. Training: train_regression.py:155 drops all rows with numMinutes < 10 (MIN_MINUTES=10, line 44) inside load_and_filter_csv, called at line 486 before build_opponent_defense at line 494; the per-(gameId, opponentteamName) sums at lines 274-288 therefore exclude sub-10-minute players from pts_allowed/reb_allowed/ast_allowed. Inference: features.py:_get_opponent_stat_allowed (269-316) sums ALL attacking-team PlayerStats rows (period=0) with no minutes filter; the same file applies a min<10 mask for player rolling features at features.py:200-201, proving sub-10-minute rows exist in the DB and the filter is omitted only for opponent defense. Backtest: backtest.py:_batch_opponent_defense (305-369) likewise sums all rows with no minutes filter. Refutation attempt failed: ingestion (load_raw_csvs.py:257-270, ingest_history.py:401-402) stores all player rows regardless of minutes, so serve-time sums genuinely include sub-10-minute players. Result is a real train/serve skew: opp_*_allowed_L10 is systematically lower in training than at inference/backtest.

</details>

### M6. Backtest scores games with 1-9 minutes played that training excluded entirely

**Where:** `backend/nba_betting/services/backtest.py:90`

**Evidence:** backtest.py:90 filters `full_df[full_df["min"] > 0]`, keeping games with 1-9 minutes as prediction/betting rows (features.py:35 does the same for the inference anchor row). Training drops all rows with numMinutes < 10 from both train and test sets (train_regression.py:44, 155), so the model was never trained or evaluated on such games.

**Why it matters:** Early-exit injury games (e.g. 4 minutes, 2 points) enter the backtest as bets where 'actual' is mechanically far below any projection, inflating apparent UNDER accuracy (line = pts_L5 of healthy games, projection near normal output). The reported hit-rate/ROI is computed over a game population that differs from the model's training/test population, biasing the headline backtest numbers that statistical_validation.py then tests for significance.

**Fix:** Filter the backtest window to `min >= 10` (matching MIN_MINUTES) or disclose that sub-10-minute games are included and quantify their effect.

<details><summary>Verifier verdict</summary>

Verified. backtest.py:90 filters only `min > 0`, so 1-9 minute games survive as betting rows: _load_player_history (features.py:158) has no minutes filter, _add_rolling_features (features.py:197-219) masks <10-min games only in a copy used for rolling calcs and returns the original df with real actuals intact, and the dropna at backtest.py:94-99 doesn't remove them since their features come from prior games via shift(1). These rows are predicted and scored into accuracy/ROI (backtest.py:176-212). Training excludes all such games: train_regression.py:44 sets MIN_MINUTES=10, :155 filters numMinutes >= 10 inside load_and_filter_csv, which runs (:486) before time_split (:497), so both train and test sets never contain <10-minute games. The backtest therefore evaluates the model on a game population (injury exits, garbage-time stints with near-zero actuals vs an L5-average line) it was never trained or validated on, biasing backtest accuracy/ROI. features.py:35 applies the same min>0 filter at inference, confirming the skew is systemic.

</details>

### M7. All inference features are stale by one game: the most recent completed game is excluded from every rolling window, season average, opponent-defense average, and days_rest

**Where:** `backend/nba_betting/services/features.py:43`

**Evidence:** get_model_inputs takes `latest = history_df.iloc[-1]` (features.py:43) and reads its rolling columns, which were computed with shift(1) (features.py:205-217) — so pts_L5 etc. at the last row cover games t-5..t-1, excluding the last completed game t. The prediction target is the NEXT upcoming game t+1, whose correct window is t-4..t. Same off-by-one in _get_season_avg (features.py:238, `date < ref` where ref is the last game's date), in _get_opponent_stat_allowed (features.py:311-315, shift(1).rolling then iloc[-1] excludes the opponent's most recent game), and days_rest (features.py:80) is the rest before the LAST game, not before the game being predicted. In training, the feature row for target game t correctly uses games through t-1 (train_regression.py:211).

**Why it matters:** Training conditions on all information through game t-1 when predicting game t; serving conditions on information through t-1 when predicting game t+1 — one full game of signal (including the most recent performance, the strongest predictor in an L5 window) is systematically discarded. Live projections therefore lag actual form, and days_rest for the target game is simply wrong (it describes a different game). Reported model quality (trained/backtested with correct alignment) overstates live-serving quality.

**Fix:** For the upcoming-game row, compute features without the final shift: append a synthetic 'next game' row (with the actual upcoming date for days_rest) and take its shifted features, or equivalently use unshifted rolling values of the last row; same for _get_season_avg (use date <= ref) and _get_opponent_stat_allowed (take rolling including the last game).

<details><summary>Verifier verdict</summary>

Verified in code. features.py:43 takes the last completed game's row (game t) whose rolling features are shift(1)-computed (features.py:205-217), covering t-5..t-1 and excluding game t; the prediction target is the upcoming game t+1, whose training-consistent window ends at t (train_regression.py:210-223 aligns shift(1) features with the same row's label, so the model expects features through the game immediately before the target). _get_season_avg excludes the last game via `date < ref` (features.py:238); _get_opponent_stat_allowed is doubly stale — filters `date < as_of` at features.py:300 (the pd.Timestamp passes the isinstance date guard at 298) AND applies shift(1).rolling before iloc[-1] at 311-315, vs a single aligned shift in training (train_regression.py:297-299); days_rest (features.py:80, computed at :191) is the rest before the last completed game, not before the predicted game — no caller supplies the upcoming game's date (get_model_inputs has no date parameter). Both live callers (views.py:113, generate_daily_picks.py:116) use the row uncorrected. Genuine one-game train/serve skew affecting all rolling, season-avg, opponent-defense, and rest features.

</details>

### M8. days_rest: training clips to 10 and fills NaN with 3; both serving paths are unclipped and features.py substitutes 2 (also swallowing legitimate 0 values)

**Where:** `backend/nba_betting/services/features.py:80`

**Evidence:** Training: train_regression.py:227-233 `.fillna(3).clip(upper=10)`. Serving: _load_player_history (features.py:191) does `.diff().dt.days.fillna(3)` with NO clip, and get_model_inputs line 80 uses `float(latest.get("days_rest") or 2)` — the `or` coerces a valid 0.0 to 2, and the missing-value default is 2 not 3. Backtest: backtest.py:139 `_safe("days_rest", 2.0)` — default 2 vs training's 3, also unclipped.

**Why it matters:** A player returning from a 25-day injury layoff gets days_rest=25 at serve/backtest time, a value the model never saw (training max is 10) — XGBoost extrapolates via its last split arbitrarily. The 3-vs-2 default and the 0→2 coercion shift the feature for exactly the cold-start and back-to-back cases where rest matters most.

**Fix:** Apply `.clip(upper=10)` in _load_player_history's days_rest, use pd.isna-based fallback with the same constant 3 in features.py:80 and backtest.py:139.

<details><summary>Verifier verdict</summary>

Verified at all cited locations. Training (backend/nba_betting/ml/train_regression.py:227-233) computes days_rest as diff().dt.days.fillna(3).clip(upper=10). Serving (backend/nba_betting/services/features.py:191) computes it as diff().dt.days.fillna(3) with no clip, so e.g. a 30-day injury layoff feeds a value outside the training range. features.py:80 then does float(latest.get("days_rest") or 2) — the truthiness `or` coerces a legitimate 0.0 (consecutive same-date rows) to 2, and encodes a default of 2 vs training's 3. Backtest (backend/nba_betting/services/backtest.py:139) uses _safe("days_rest", 2.0) (default 2 vs 3) and sources days_rest from the same unclipped _load_player_history (backtest.py:27-29, 84-88); no clip exists anywhere in the backtest path. One softening nuance: because fillna(3) runs upstream at features.py:191, the 2-vs-3 default mismatch at lines 80/139 rarely fires in practice (NaN is already 3 by then; the `or 2` mainly bites the 0.0 case) — but the unclipped train/serve skew and the 0→2 coercion are real defects exactly as claimed.

</details>

### M9. std_L10 dispersion estimate: n=5-10 sample std with no shrinkage, and it is the marginal player std, not the residual std of the projection

**Where:** `backend/nba_betting/services/features.py:216`

**Evidence:** features.py:215-217 (and identically train_regression.py:222-224) computes `x.shift(1).rolling(10, min_periods=5).std()` — a ddof=1 sample std from as few as 5 observations (relative sampling error ~35% at n=5, ~24% at n=10), with no shrinkage toward a player-season or league prior; the only guard is a 0.5 floor (views.py:146). This std is then used in views.py:148 as the dispersion of the actual around the XGBoost projection, i.e. it treats the model's conditional-mean projection as having the player's full marginal game-to-game variance, while the trained models' test RMSE (computed at train_regression.py:373-376 and stored in metadata) is never used at inference.

**Why it matters:** A noisy scale parameter directly distorts prob_over: understating sigma by 30% turns a true 60% edge into a reported ~63-65% and inflates the tails symmetrically; week-to-week the same player+line can swing many probability points purely from estimator noise. Conceptually, the residual std around the model projection (RMSE) is the quantity the Normal model calls for.

**Fix:** Shrink std_L10 toward the player's season std (e.g. Bayesian/empirical-Bayes weighting by window count) or blend with the stored per-stat test RMSE from model metadata; disclose the choice in docs/METHODOLOGY.md.

<details><summary>Verifier verdict</summary>

Verified against the code. (1) backend/nba_betting/services/features.py:214-217 computes `x.shift(1).rolling(10, min_periods=5).std()` — a ddof=1 sample std from as few as 5 observations, with no shrinkage toward a player-season or league prior anywhere in the pipeline; train_regression.py:221-224 is identical. (2) backend/nba_betting/views.py:141-149 uses this marginal player std as the dispersion of the actual around the XGBoost projection (`z = (line_value - projection) / std_dev`, line 148), with the 0.5 floor at line 146 as the only guard — treating the conditional-mean projection as carrying the player's full marginal game-to-game variance. (3) Test RMSE is computed at train_regression.py:373-376 and saved to model_metadata.json (lines 594-597), but ml/predictor.py never loads that metadata, and services/probability.py:10 `calculate_probability(..., rmse=6.0)` — the only RMSE consumer — has zero callers (dead code). Attempted refutations (shrinkage in get_std_for_stat at features.py:119-135, RMSE use via probability.py, metadata loading in the predictor) all failed. Only trivial evidence discrepancy: the training loop starts at line 221, not 222.

</details>

### M10. Normal/Poisson inconsistency: services/probability.py is dead code; Normal CDF hardcoded for all stats including low-count assists

**Where:** `backend/nba_betting/services/probability.py:10`

**Evidence:** probability.py:10 defines calculate_probability() prescribing Poisson for LOW_COUNT_STATS={"stl","blk","ast"} (line 6, 16-19), but a repo-wide grep shows it is never imported or called. ManualPredictionView (views.py:148-149) and generate_daily_picks.py:140-141 both hardcode `1 - norm.cdf((line - projection)/std_dev)` for every stat. probability.py also uses a fixed rmse=6.0 default while views.py uses per-player std_L10 — two contradictory dispersion conventions in the codebase.

**Why it matters:** Assists are a discrete, right-skewed, low-mean count (typical mu 4-9). A symmetric continuous Normal without continuity correction misestimates tail probabilities near half-point lines (e.g. P(over 3.5) for a mu=4, sigma=2 player differs materially between Normal and Poisson). Keeping a prescriptive-but-unused module also makes documentation claims about the probability model unverifiable against the running code.

**Fix:** Either delete probability.py, or route views.py and generate_daily_picks.py through calculate_probability() with one documented distribution choice per stat; add a continuity correction (or Poisson) for ast.

<details><summary>Verifier verdict</summary>

Verified against the code. (1) backend/nba_betting/services/probability.py:6,10,16-19 defines calculate_probability() prescribing Poisson for LOW_COUNT_STATS={"stl","blk","ast"}, but a repo-wide grep shows calculate_probability is never imported or called anywhere — dead code. (2) views.py:148-149 (ManualPredictionView) and management/commands/generate_daily_picks.py:140-141 both hardcode 1 - norm.cdf((line - projection)/std_dev) for every stat, including assists (views.py fallback dict at line 145 includes "ast": 2.0), so the Normal CDF is used for low-count stats contrary to probability.py's prescription. (3) Dispersion conventions are contradictory — in fact three-way: probability.py uses fixed rmse=6.0 default; views.py:141-145 uses per-player std_L10 with fallbacks {pts:6.0, reb:2.5, ast:2.0}; generate_daily_picks.py:134-138 uses std_L10 with different fallbacks {pts:6.1, reb:2.6, ast:1.8}. This matches the auditor checklist's flagged KNOWN ISSUE (methodology-auditor.md:35) and violates the fallback-consistency check (line 25). Every element of the claimed evidence holds at the cited lines.

</details>

### M11. Binomial test null (52.4% break-even) is misapplied: hit rate is measured against a synthetic self-generated line, not a market line

**Where:** `backend/nba_betting/services/statistical_validation.py:71`

**Evidence:** statistical_validation.py:31 sets BREAK_EVEN = 0.524 and line 71 runs binomtest(hits, n, BREAK_EVEN, alternative="greater"); the insight text (lines 219-222) publishes "statistically above the 52.4% break-even (p=...)". But the bets being tested come from services/backtest.py:124, where the "line" is the player's own L5 rolling average (`row[f"{stat}_L5"]`), with the module docstring (backtest.py:7-8) admitting "real sportsbook lines aren't stored". The 52.4% threshold is the break-even for -110 two-way pricing against an efficient book line.

**Why it matters:** The test's sidedness itself is correct (one-sided 'greater'), but the null hypothesis value is only meaningful for bets against a real market. Beating your own L5 average 55% of the time says nothing about profitability at -110 odds against a sportsbook, yet the significance verdict and insight sentence frame it exactly that way. Every 'Significant' hit-rate result is therefore an overclaim about betting viability.

**Fix:** Keep the one-sided binomial test but reframe: either test against 0.5 ("better than a coin flip vs its own baseline line") or keep 0.524 and add an explicit caveat in the payload/insight that the line is a synthetic L5 average, so break-even significance does not imply profitability against real books.

<details><summary>Verifier verdict</summary>

All cited evidence verified. statistical_validation.py:31 defines BREAK_EVEN = 0.524 and line 71 runs binomtest(hits, n, BREAK_EVEN, alternative="greater"); the insight text at lines 219-222 publishes "statistically above the 52.4% break-even (p=...)" with no caveat. The hits being tested come from BacktestResult.correct, computed in backtest.py:181-183 against line = row[f"{stat}_L5"] (backtest.py:124) — the player's own L5 rolling average — and the module docstring (backtest.py:7-8) explicitly admits real sportsbook lines aren't stored. 52.4% (= 1.1/2.1) is the break-even hit rate for -110 two-way pricing against a market line (the same juice hardcoded at backtest.py:32-34), so applying it as the null for hit rates against a naive self-generated baseline is a category error: beating an L5 average >52.4% of the time does not imply beating an efficient book line >52.4% of the time, yet the published narrative asserts exactly that. Refutation attempts failed: the validation service reads only stored backtest rows and never surfaces the synthetic-line disclosure; the auditor checklist mandates the test form but does not sanction the market-line conflation. Severity: CRITICAL under the auditor rubric (invalidates a published claim).

</details>

### M12. 162 hypothesis tests (18 players x 3 stats x 3 tests) each at per-test alpha=0.05 with no multiple-comparisons correction or framing

**Where:** `backend/nba_betting/services/statistical_validation.py:73`

**Evidence:** Each call runs three tests at alpha=0.05: hr_sig at line 73, edge_sig at line 80, bias_sig at line 89, then _overall_verdict (lines 186-204) converts them into badges ("Strong signal", green). views.py:1305-1321 exposes this per player/stat, and constants.py:12-34 enumerates 18 roster players x 3 stats = 54 panels = 162 tests. No Benjamini-Hochberg/Bonferroni correction, no q-values, and no caveat field anywhere in the returned dict (lines 115-157) noting the family size.

**Why it matters:** Under a global null, ~8 of 162 tests are expected to come up p<0.05 by chance, so several "Significant"/"Strong signal" badges are essentially guaranteed even if the model has zero edge. Users browsing 54 cards will cherry-pick the green ones — a textbook garden-of-forking-paths exposure. docs/OPEN_SOURCE_READINESS_PLAN.md:19 already acknowledges this as MAJOR but nothing is implemented in code.

**Fix:** Minimal: add a fixed disclosure string to the payload (e.g. in warnings) stating results are one of 54 uncorrected player-stat panels and some significant results are expected by chance. Better: apply Benjamini-Hochberg across the roster per stat before labeling anything "Significant", or report the FDR-adjusted p alongside the raw p.

<details><summary>Verifier verdict</summary>

Every element of the evidence verified against the code, and refutation attempts failed. (1) Three hypothesis tests per player/stat panel, each at uncorrected per-test alpha=0.05: backend/nba_betting/services/statistical_validation.py:73 (`hr_sig = hr_pval < 0.05`, one-sided binomial vs 52.4%), :80 (`edge_sig = edge_pval < 0.05 and rho > 0`, Spearman), :89 (`bias_sig = bias_pval < 0.05`, one-sample t-test). (2) `_overall_verdict` (lines 186-204) counts these significance booleans into badge verdicts ("Strong signal"/green at 3 positives, amber, red). (3) Family size confirmed: constants.py:12-34 lists exactly 18 SEASON_REPORT_PLAYERS, and views.py:1203-1223 (`_intelligence_preamble`) restricts stat to ("pts","reb","ast") and player to that roster; StatisticalValidationView at views.py:1305-1321 serves each panel, giving 54 panels and up to 162 tests (slight caveat: the edge test is skipped when n<15 per lines 76-83, so 162 is an upper bound — this does not change the substance). (4) No correction exists: a repo-wide case-insensitive grep for bonferroni/benjamini/hochberg/fdr/multipletests/q-value hits zero backend code — only docs/OPEN_SOURCE_READINESS_PLAN.md:19, which itself lists this exact issue as a MAJOR unaddressed disclosure gap, corroborating the finding. (5) The returned dict (lines 115-157) contains no family-size/multiple-comparisons caveat; `_sample_warnings` (162-183) covers only per-panel sample size. No user-facing framing exists elsewhere either: frontend/src has no multiple-comparisons text, and docs/METHODOLOGY.md does not exist. Statistically, at alpha=0.05 across 54 panels one expects roughly 2-3 spuriously "Significant" green labels per test family even under the null, so uncorrected green "Strong signal" badges will appear by chance — exactly what the methodology-auditor checklist (item: multiple comparisons, .claude/agents/methodology-auditor.md:31) requires be corrected or disclosed. Severity: MAJOR as a missing-disclosure/framing defect (per-panel p-values themselves are computed correctly).

</details>

### M13. Calibration t-test labels results "Well-calibrated" from a non-significant p-value at any n, with no normality check or low-n gate

**Where:** `backend/nba_betting/services/statistical_validation.py:86`

**Evidence:** Line 86 runs ttest_1samp(errors, popmean=0.0) unconditionally — unlike the Spearman block, there is no minimum-n gate. Line 89 sets bias_sig = bias_pval < 0.05, and lines 146-149 emit label "Well-calibrated" whenever the test fails to reject, with the insight (lines 253-256) asserting "the model is well-calibrated on average". Signed errors for count stats (ast, reb) are right-skewed, and n can be far below 30 (the overall verdict gates on n>=30 at line 191, but the calibration sub-dict is populated and labeled regardless).

**Why it matters:** Two problems: (1) absence of evidence is presented as evidence of absence — at n=10 the t-test has almost no power, so "Well-calibrated" is an affirmative claim the data cannot support; (2) the t-test assumes approximately normal errors or n large enough for the CLT, neither checked nor disclosed. A skewed error distribution at small n produces unreliable p-values in both directions.

**Fix:** Gate the calibration test on n >= MIN_N_RELIABLE (mirror the Spearman gate) and change the non-significant label to "No detectable bias" with a power caveat when n < 30; disclose the normality/CLT assumption in the payload or docs.

<details><summary>Verifier verdict</summary>

All cited evidence verified in backend/nba_betting/services/statistical_validation.py. Line 86 runs ttest_1samp(errors, popmean=0.0) with no minimum-n gate and no normality check, unlike the Spearman block (lines 76-83) which is gated on n>=15. Line 89 sets bias_sig = bias_pval < 0.05, lines 146-149 label the calibration 'Well-calibrated' whenever the test fails to reject, and lines 252-256 assert 'the model is well-calibrated on average' in the insight — an accept-the-null claim made exactly when power is lowest. The n>=30 gate at line 191 applies only to the overall verdict; the calibration sub-dict is populated and labeled at any n. Refutation attempts fail: the generic low-n warning in _sample_warnings does not qualify the calibration label, and at n=1 ttest_1samp yields p=nan, so nan<0.05 is False and the output is literally label='Well-calibrated' with p_value=nan. No normality/skew handling exists anywhere in the file despite errors being signed residuals of right-skewed count stats (ast, reb).

</details>

### M14. LitePicksView's prob_over >= 0.55 filter silently discards every UNDER pick and mislabels confidence

**Where:** `backend/nba_betting/views.py:195`

**Evidence:** generate_daily_picks.py:143 labels picks `edge = "Over" if projection > line else "Under"` and stores the raw prob_over (an Under pick has prob_over < 0.5 by construction). views.py:192-195 then filters `prob_over__gte=min_conf` (0.55), so all Under picks are excluded from the API response, and views.py:214 reports `confidence_pct = round(p.prob_over * 100)`, which for any surviving near-threshold pick conflates P(over) with confidence in the recommendation.

**Why it matters:** The public feed is one-sided by construction (only Overs ever shown), which biases any hit-rate evaluation of the picks endpoint, and 'confidence' as displayed is not the probability of the recommended side. Combined with the NaN bug, the feed preferentially surfaces fabricated 99% Overs.

**Fix:** Filter on `max(prob_over, 1-prob_over) >= min_conf` (e.g. annotate Greatest(prob_over, 1-prob_over)) and set confidence_pct from the recommended side's probability.

<details><summary>Verifier verdict</summary>

CONFIRMED (core claim). generate_daily_picks.py:140-143 computes prob_over = 1 - norm.cdf((line - projection)/std) — Normal centered at projection — so edge="Under" (projection <= line) mathematically implies prob_over <= 0.5; the raw value is stored (line 154) with no other writer to DailyPick.prob_over. views.py:192-195 filters prob_over__gte=PICKS_MIN_CONFIDENCE (0.55 default, settings.py:100), so every Under pick is silently excluded from /api/picks/ — the endpoint is structurally Over-only despite the edge field advertising both directions. One sub-claim is overstated: views.py:214's confidence_pct = round(prob_over*100) is not actively wrong, because the filter guarantees all surviving picks are Over picks (prob_over >= 0.55 > 0.5 => projection > line => edge="Over"), for which P(over) equals confidence in the recommendation; the mislabeling is latent, symptomatic of the same root cause (directionless prob_over used as confidence). Minimal fix: filter on max(prob_over, 1-prob_over) >= min_conf (e.g., Q(prob_over__gte=0.55) | Q(prob_over__lte=0.45)) and set confidence_pct from the probability of the recommended side.

</details>

### M15. docs/ML_FEATURE_GUIDE.md attributes the model's feature dictionary to notebooks/feature_engineering.py, which no longer produces any of those columns, and its garbage-time claim is false for the training pipeline

**Where:** `docs/ML_FEATURE_GUIDE.md:46`

**Evidence:** ML_FEATURE_GUIDE.md:3 says it 'describes the engineered features produced by notebooks/feature_engineering.py' and lists pts_L5/L10, EMA span=5, pts_std_L10, opp_pts_allowed_L10 — notebooks/feature_engineering.py produces none of these (it builds trend_*, min_l10, fga_per_min_l10, proj_volume, cv_l10, opp_avg_*_allowed_l10); the real producers are ml/train_regression.py (training) and services/features.py (inference). The guide also omits season_avg_* and hot_cold_* which the models do use. :46-47 claims 'Games where min < 10 are treated as NaN ... (not removal) ... while still keeping the game as a valid prediction row' — the training pipeline REMOVES those rows entirely before feature computation (train_regression.py:155 `df = df[df["numMinutes"] >= MIN_MINUTES]`), so the documented 'Frozen Feature' behavior (:60-63) exists only at inference (services/features.py:199-201), a train/serve divergence the doc presents as uniform design.

**Why it matters:** The guide's leakage/garbage-time narrative is the project's main methodological documentation; it describes a masking scheme the trained models never saw, so training rolling windows differ from inference rolling windows around sub-10-minute games.

**Fix:** Re-point the guide at ml/train_regression.py and services/features.py, document the season_avg/hot_cold features, and either align training with the NaN-masking scheme or document that training drops min<10 rows outright.

<details><summary>Verifier verdict</summary>

Verified on all points. (1) ML_FEATURE_GUIDE.md:3 attributes its feature dictionary to notebooks/feature_engineering.py, but that script produces trend_pts/reb/ast (Holt), min_l10, fga_per_min_l10, proj_volume, pts_std_l10, pts_mean_l10, cv_l10, and opp_avg_{pts,reb,ast}_allowed_l10 (derived_cols at :276-292) — none of the guide's pts_L5/L10, *_ema_L5, fg_pct_L5/L10, pts_std_L10 (as specified: min_periods=5 + garbage-time masking), or opp_pts_allowed_L10. The real producers are ml/train_regression.py:200-248 (training) and services/features.py:197-219 (inference). The guide also omits season_avg_* and hot_cold_*, which are in FEATURE_COLUMNS (train_regression.py:49-74) and built at train_regression.py:246-253 / features.py:65-70 / backtest.py:266-298. (2) The garbage-time claim (guide:46-47, 'NaN ... not removal ... keeping the game as a valid prediction row') is false for training: train_regression.py:44 MIN_MINUTES=10 and :155 `df = df[df["numMinutes"] >= MIN_MINUTES]` removes those rows before any feature computation, so the 'Frozen Feature' effect (guide:60-63) exists only at inference (features.py:199-201 masks min<10 to NaN, keeps rows) — a train/serve divergence the doc presents as uniform design. Only refutation candidates: the notebook's near-namesake pts_std_l10 (different spec, different pipeline, not used by the models) and the still-correct output filename at guide:74; neither rescues the doc. Severity: MINOR-to-MAJOR doc-vs-code defect (stale doc misattributes the live feature set and masks a real train/serve skew).

</details>

## MINOR (22)

### M1. Legacy classifier trainer still ships with shuffled, non-chronological train/test splitting

**Where:** `backend/nba_betting/ml/model_trainer.py:424`

**Evidence:** CatBoost randomized_search is invoked with `search_by_train_test_split=True, ... shuffle=True` (model_trainer.py:419-429). Grep confirms no live module imports model_trainer (only a docstring mention in train_regression.py:6), so it is dead code today.

**Why it matters:** Shuffled splits on autocorrelated player-game time series leak future games into training folds; keeping this code in the ml/ package invites reuse that would violate the 'chronological only' rule, and it contradicts any documentation stating no random splits exist in the codebase.

**Fix:** Delete model_trainer.py or move it to an archive/ directory with a deprecation header stating its splits are leaky and must not be reused.

<details><summary>Verifier verdict</summary>

Verified: model_trainer.py:419-429 does call CatBoost randomized_search with search_by_train_test_split=True and shuffle=True — a shuffled, non-chronological split of the training pool used to select hyperparameters, violating the audit checklist's 'chronological only' rule; the XGBoost path (lines 336-352) has the same defect via RandomizedSearchCV with KFold-style cv. Dead-code claim also verified: no module imports model_trainer (only a docstring mention at train_regression.py:6; live training goes through train_regression.py via management/commands/train_models.py:16, and docs/OPEN_SOURCE_READINESS_PLAN.md:30 already marks it for deletion). Important scoping caveat: the module's primary holdout split IS chronological (time_split sorts by date, model_trainer.py:146-178, used at line 711), so the shuffled split taints only hyperparameter tuning, not final test evaluation. Real finding, MINOR severity (dead code, tuning-split-only).

</details>

### M2. MIN_YEAR=2016 modern-era filter is silently inactive because the CSV has no 'year' column

**Where:** `backend/nba_betting/ml/train_regression.py:150`

**Evidence:** train_regression.py:150-151 applies the >= MIN_YEAR filter only `if "year" in df.columns`; the actual data/raw/PlayerStatistics.csv header (verified) contains no 'year' column, so no year filtering occurs and model_metadata.json records "csv_min_year": 2016 (line 507) regardless. Training data may include pre-2016 (pace-and-era-different) games contrary to the documented filter.

**Why it matters:** The trained feature distributions (opp_pts_allowed_L10 especially) blend eras with materially different league scoring environments while serving only ever sees current-era DB data — an additional distribution shift — and the metadata misdocuments the training population.

**Fix:** Derive the filter from the parsed date column (`df = df[df['date'].dt.year >= MIN_YEAR]`) after date parsing at line 158-161, and only then write csv_min_year to metadata.

<details><summary>Verifier verdict</summary>

Confirmed. train_regression.py:150-151 gates the MIN_YEAR=2016 filter on `if "year" in df.columns`, but the actual data/raw/PlayerStatistics.csv header (read directly) contains no 'year' column (columns run firstName...plusMinusPoints), so the filter never executes. The CSV spans back to 1946; a verified 2010 row (Regular Season, 31.0 minutes) passes the only active filters (gameType at line 147, numMinutes>=10 at line 155), and grep confirms no other date cutoff exists in the file — so pre-2016 games do enter training. Meanwhile line 507 unconditionally records "csv_min_year": 2016 in model_metadata.json, documenting a filter that never ran. The 'silently inactive modern-era filter' finding holds in full.

</details>

### M3. run_backtest accepts arbitrary date ranges with no guard against the model's training/eval windows

**Where:** `backend/nba_betting/services/backtest.py:46`

**Evidence:** run_backtest(player_name, stat, date_from, date_to) filters the player's history only by the caller-supplied range (backtest.py:101-104) and views.py:264-280 passes user-supplied ISO dates straight through with no comparison against model_metadata.json's split_date (2015-12-15) or the early-stopping eval window. The per-game feature construction itself never peeks at same-day-or-future rows (all inputs are shift(1)-based and the opponent lookup at lines 127-129 returns pre-game values), but nothing prevents scoring games the model saw during weight fitting or round selection.

**Why it matters:** Any backtest window overlapping the training partition would be scored as if out-of-sample, silently inflating accuracy/ROI; today the exposure is via the early-stopping eval overlap (all SEASON_DATES windows, 2023-2026, are inside it), and it would become weight-level in-sample leakage the moment the ESPN DB backfills pre-2016 games or the model is retrained with a later split_date.

**Fix:** Load split_date (and the eval-window bounds) from model_metadata.json and reject or flag backtest ranges that overlap them; at minimum record in the BacktestRun whether the range is truly out-of-sample.

<details><summary>Verifier verdict</summary>

Confirmed. backtest.py:101-104 filters the player's history only by the caller-supplied date_from/date_to; neither backtest.py nor ml/predictor.py ever reads model_metadata.json's split_date (2015-12-15, metadata line 5), and views.py:264-280 validates only ISO format and date_from < date_to before calling run_backtest. train_regression.py:317-323 confirms a chronological 80/20 split with all pre-2015-12-15 games in training, and lines 395-396 confirm the test set doubles as the XGBoost early-stopping eval set, so even post-split backtests overlap round-selection data. The finding's concessions also check out: features are shift(1)-based (features.py:206-216, backtest.py:285/359) and the opponent lookup (backtest.py:127-129) returns pre-game rolling values. Net effect: a user can backtest games the model was trained on and receive in-sample accuracy/ROI presented as out-of-sample. MAJOR severity.

</details>

### M4. Push games (actual == line) are scored as unders and fed into the binomial test as full bets

**Where:** `backend/nba_betting/services/backtest.py:182`

**Evidence:** backtest.py:181-184: predicted_over = projection > line; actual_over = actual > line; correct = predicted_over == actual_over. When actual exactly equals the L5 line (possible since the line is a mean of 5 integers), the game counts as an 'under' outcome and gets full win/loss pnl; statistical_validation.py:67 then counts these rows in hits/n for the binomial test.

**Why it matters:** Real -110 bets push (stake returned) on a tie; scoring them as decided outcomes adds asymmetric noise to the hit-rate numerator and denominator that the 52.4% break-even null does not account for. Effect is small but systematically distorts the tested proportion.

**Fix:** Exclude actual == line games from hits/n (and pnl) or count them separately as pushes before running binomtest.

<details><summary>Verifier verdict</summary>

CONFIRMED. All elements of the finding hold up against the code. (1) backtest.py:181-184: `predicted_over = projection > line; actual_over = actual > line; correct = predicted_over == actual_over` — when actual == line, `actual_over` is False, so the game is graded as an under outcome, and line 184 assigns full pnl (+1.0 WIN_UNIT if the model predicted under, -1.1 LOSS_UNIT if it predicted over). There is no push branch; a real -110 prop bet landing exactly on the line refunds the stake (pnl 0) and is excluded from the record. (2) Pushes are genuinely possible, not just theoretical: the line is `{stat}_L5` (backtest.py:124), computed in features.py:206 as `x.shift(1).rolling(w, min_periods=1).mean()` over pts/reb/ast, which are IntegerFields (models.py:46-48). With min_periods=1, the line for a player's second qualifying game equals a single prior integer game exactly, and any 2-5 game window whose sum divides evenly by the count yields an exact integer float (integer sums and integer-result divisions are exact in float64), so `actual == line` compares exactly true. (3) These push rows inflate total_bets/wins/accuracy (backtest.py:208-212) and flow into the binomial test: statistical_validation.py:64,67 builds `corrects`/`hits` from all BacktestResult rows and line 71 runs `binomtest(hits, n, BREAK_EVEN, alternative='greater')` with pushes counted as full Bernoulli trials. Since ties always grade toward "under," pushes are systematically scored as wins whenever projection <= line, biasing hit rate, pnl, ROI, and the significance test. Minor nit: the evidence cited statistical_validation.py:67 (hits computation) while the binomtest itself is at line 71 — substance unaffected. Minimal fix: detect actual == line, set pnl = 0, exclude from wins/total_bets and from the binomial n.

</details>

### M5. Inference season average includes sub-10-minute games that training's season_avg excludes

**Where:** `backend/nba_betting/services/features.py:243`

**Evidence:** _get_season_avg (features.py:237-246) takes the mean of raw `history_df[stat]` for the season window; the <10-minute masking is applied only inside _add_rolling_features to a copy (calc_df, features.py:199-201) and never to the raw pts/reb/ast columns, and get_model_inputs only filters `min > 0` (line 35). Training computes season_avg_{stat} on a dataframe already filtered to numMinutes >= 10 (train_regression.py:155, 244-248). Backtest's _add_season_features (backtest.py:284-286) similarly uses unmasked raw stat columns.

**Why it matters:** Players with occasional short injury games get a serving-time season_avg (and hence hot_cold, which divides by it) dragged below the training-time definition — a small but systematic downward bias in two features for exactly the injury-prone players.

**Fix:** Exclude min < 10 rows when computing the season mean in features.py:_get_season_avg and mask them in backtest.py:_add_season_features, matching training.

<details><summary>Verifier verdict</summary>

Confirmed train/serve skew. Training drops all rows with numMinutes < 10 (train_regression.py:44 MIN_MINUTES=10, :155) before computing season_avg_{stat} as a shifted expanding mean (train_regression.py:244-248), so its season average covers only 10+-minute games. At inference, _get_season_avg (features.py:237-246) means the raw history_df[stat] over the season window; the <10-minute masking in _add_rolling_features is applied only to the calc_df copy (features.py:198-201) and never propagates to the raw pts/reb/ast columns, and get_model_inputs filters only min > 0 (features.py:35) — sub-10-minute game rows survive (their rolling columns are valid, so the dropna at lines 36-39 keeps them) and are included in the season average. Backtest matches the contaminated inference definition: backtest.py:88-90 filters only min > 0 and _add_season_features (backtest.py:284-286) expanding-means the unmasked raw stat columns. Consequence: season_avg_{stat} is biased low at inference/backtest for players with injury/garbage-time games, and hot_cold_{stat} (features.py:65-70) is correspondingly inflated, feeding the model a feature distribution different from training.

</details>

### M6. Falsy-value ('or') fallbacks in features.py coerce legitimate zero features to defaults; backtest's _safe preserves zeros, so the two serving paths disagree with each other and with training

**Where:** `backend/nba_betting/services/features.py:108`

**Evidence:** features.py:73-75 `float(latest.get("pts_std_L10") or 5.0)` (a real std of 0.0 becomes 5.0), lines 108-109 `float(latest.get("fg_pct_L5") or 0.45)` (a true 0-for-N shooting stretch, which training encodes as 0.0 via np.where at train_regression.py:173-177, becomes 0.45), line 80 days_rest 0→2. backtest.py:132-134 _safe uses pd.isna and keeps 0.0. Training has no substitution at all — rows with NaN are dropped (train_regression.py:522-523).

**Why it matters:** Zero is a valid, informative value for fg_pct_L5 and std_L10; silently replacing it with a league-ish constant feeds the model a fabricated input on exactly the anomalous games, and the live path and backtest path produce different feature vectors for the same player-game.

**Fix:** Replace `or`-based fallbacks in features.py with explicit `pd.isna(...)` checks (as backtest._safe does) using one shared constants module.

<details><summary>Verifier verdict</summary>

Verified in code. features.py:73-75 and 108-109 use falsy `or` fallbacks (`float(latest.get("pts_std_L10") or 5.0)`, `float(latest.get("fg_pct_L5") or 0.45)`) that coerce legitimate 0.0 values to defaults; 0.0 is producible since features.py:215-217 computes rolling std (identical values give 0.0) and features.py:168/206 encode 0-attempt or 0-for-N games as fg_pct 0.0 with min_periods=1, matching training's np.where encoding at train_regression.py:173-177. backtest.py:132-134 `_safe` uses pd.isna and preserves 0.0 (lines 143, 154), so the backtest and live-serving paths map the same value to different model inputs. Training (train_regression.py:521-523) uses dropna with no substitution, so the model learned 0.0 as 0.0 — both inference fallback schemes deviate from training and from each other. One caveat: the days_rest 0→2 sub-example is weak because days_rest is computed as date.diff().days in both training (train_regression.py:227-233) and inference (features.py:191), making 0 unreachable except for duplicate-date rows; this does not invalidate the core finding. Additionally, the `or` construct fails its intended purpose: NaN is truthy, so genuinely missing std values pass through as NaN while legitimate zeros are replaced.

</details>

### M7. floor_ceiling.py makes distributional claims its sample sizes cannot support and mislabels statistics

**Where:** `backend/nba_betting/services/floor_ceiling.py:192`

**Evidence:** (a) floor_ceiling.py:192-193 passes `mean` into the insight text '...with a median of {mean}' — the median (p50) is computed but the mean is printed. (b) Condition splits accept groups of n>=5 (line 83) and report p10/p90 'floor'/'ceiling' (lines 89-91) — with n=5 these interpolate between the extreme order statistics, i.e. they are essentially the min/max of 5 games. (c) Lines 216-220 assert 'form is the better ceiling predictor than rest' whenever hot-form p90 exceeds rested p90 by 10%, a point comparison of two noisy extreme quantiles with no uncertainty assessment. (d) The comment at line 41 calls (p90-p10)/p50 a 'normalised interquartile range'; it is the interdecile range.

**Why it matters:** User-facing narrative text presents extreme-quantile point estimates from 5-observation subsets as stable player traits and makes a comparative predictive claim with no significance test; the mean/median mislabel misstates a central-tendency figure directly in the insight.

**Fix:** Print p50 in the insight, raise the condition-split minimum to n>=15 (or report p25/p75 instead of p10/p90 for small n), gate the hot-vs-rested claim on a bootstrap CI or drop the causal phrasing, and fix the comment.

<details><summary>Verifier verdict</summary>

All four evidence points verified in backend/nba_betting/services/floor_ceiling.py. (a) Lines 192-193: the insight text says "with a median of {mean}" — _insight (line 188) receives only `mean`, never p50, so the mean is printed and labeled as the median. (b) Line 83 admits condition-split groups with n>=5, and lines 89-91 report p10/p90 as floor/ceiling via _pct_from_sorted (lines 131-135); with n=5 these interpolate at idx 0.4 and 3.6, i.e. essentially the sample min/max of 5 games presented as decile estimates. (c) Lines 216-219 assert "form is the better ceiling predictor than rest" from a single point comparison hot p90 > 1.1 * rested p90, with no uncertainty quantification — and the hot-form group (line 79) is selected on recent high output, mechanically inflating its p90. (d) Line 41 comment calls (p90-p10)/p50 a "normalised interquartile range"; it is the interdecile range (IQR would be p75-p25), and this misnamed metric drives archetypes and roster rankings.

</details>

### M8. Binomial test's independence (iid Bernoulli) assumption is undisclosed — a player's consecutive games are serially dependent

**Where:** `backend/nba_betting/services/statistical_validation.py:71`

**Evidence:** binomtest at line 71 treats the n game outcomes as independent Bernoulli trials with constant p. The trials are consecutive games of one player whose model line is his own L5 average — hit/miss outcomes cluster with hot/cold streaks, minutes changes, and role shifts (the codebase itself models this: hot_cold features, AR(1) simulator in views.py:714-730). Neither _sample_warnings (lines 162-183) nor _insight (lines 207-259) mentions the assumption.

**Why it matters:** Positive serial correlation reduces the effective sample size, so the reported binomial p-values are anti-conservative — significance is overstated. The methodology-auditor checklist requires this assumption to be disclosed.

**Fix:** Add a fixed warning string (e.g. in _sample_warnings) that p-values assume independent games and are optimistic under streakiness; disclose in docs/METHODOLOGY.md.

<details><summary>Verifier verdict</summary>

Verified. statistical_validation.py:71 runs binomtest(hits, n, 0.524, alternative="greater") on one player's consecutive game outcomes (single BacktestRun filtered by player_name/stat/season at lines 43-55), which assumes iid Bernoulli trials. The hit/miss trials are serially dependent by construction: the backtest line is the player's own L5 rolling average (backtest.py:7-8, 124), so outcomes cluster with streaks, minutes, and role changes — dependence the codebase itself models via hot_cold_* features (backtest.py:159-161, 266-298) and an AR(1) Monte Carlo simulator (views.py:714-730, ar1_phi). Positive serial correlation makes the binomial p-value anti-conservative, overstating significance. The assumption is disclosed nowhere: _sample_warnings (lines 162-183) covers only sample-size issues, _insight (lines 207-259) asserts "statistically above the 52.4% break-even" with no caveat, and the module docstring omits it. The audit checklist (.claude/agents/methodology-auditor.md:28) explicitly requires this disclosure. MINOR severity (missing caveat), but real.

</details>

### M9. Edge-correlation insight overclaims causally/profitably: "larger model edges do translate to higher hit rates" with no correlation-vs-profitability caveat

**Where:** `backend/nba_betting/services/statistical_validation.py:233`

**Evidence:** Lines 233-237: when edge_sig, the insight says "Edge size is a **meaningful predictor** of outcomes ... larger model edges do translate to higher hit rates." The required caveat that a positive Spearman rho between |projection - line| and correctness does not imply the edges are large enough to be profitable at -110 (or against real market lines) is absent everywhere in the module. Note the minimum-n gate itself is correctly implemented (n >= 15 at line 76, MIN_N_EDGE at line 33).

**Why it matters:** A significant rho of e.g. 0.2 can coexist with an unprofitable strategy; monotone association between edge and hit says nothing about calibration of the edge magnitude or about beating juice. The checklist explicitly requires the "correlation != profitability" caveat.

**Fix:** Append one sentence to the edge_sig branch: association between edge size and hits does not by itself establish profitability; profitability depends on hit rate at real odds.

<details><summary>Verifier verdict</summary>

Verified. backend/nba_betting/services/statistical_validation.py:233-237 emits, whenever edge_sig is true, "Edge size is a **meaningful predictor** of outcomes ... larger model edges do translate to higher hit rates" with no correlation-vs-profitability caveat anywhere in the 260-line module (checked _insight, _sample_warnings, the edge_correlation response dict, and the docstring). The auditor checklist (.claude/agents/methodology-auditor.md:29) explicitly requires the "correlation ≠ profitability" caveat to be present. Worse, this sentence is generated independently of the break-even binomial test (lines 71-73), so the "higher hit rates" claim can appear even when the overall hit rate is not significantly above 52.4%. The evidence's ancillary claims also hold: MIN_N_EDGE=15 at line 33 and the n>=15 gate at line 76 are correctly implemented. Severity: MINOR (missing caveat) per the auditor's rubric.

</details>

### M10. Spearman significance mixes a two-sided p-value with a one-directional claim, inconsistent with the one-sided binomial test

**Where:** `backend/nba_betting/services/statistical_validation.py:77`

**Evidence:** Line 77 calls spearmanr(edges, corrects) with the default two-sided alternative; line 80 then requires edge_pval < 0.05 AND rho > 0. This is effectively a one-sided test at alpha=0.025 (conservative), while the hit-rate test at line 71 is explicitly one-sided at alpha=0.05. Additionally, corrects is binary with heavy ties, so the reported p-value relies on the t-approximation for rho, which is rough at n near 15.

**Why it matters:** Inconsistent sidedness across the panel means the three "significant" flags are not at a common alpha, which matters when _overall_verdict (lines 193-197) counts them as equal votes. The tie-heavy binary variable makes the small-n p-value approximation additionally unreliable near the n=15 gate.

**Fix:** Use spearmanr(..., alternative="greater") for a genuine one-sided test at alpha=0.05 matching the binomial test, or (equivalently) rank-biserial/Mann-Whitney of edge for hits vs misses; document the tie/approximation caveat.

<details><summary>Verifier verdict</summary>

Verified against backend/nba_betting/services/statistical_validation.py and scipy 1.15.2. Line 77 calls spearmanr(edges, corrects) with the default alternative="two-sided" (confirmed via inspect.signature on the installed scipy), and line 80 gates significance on edge_pval < 0.05 AND rho > 0. Empirically confirmed the two-sided p is exactly 2x the one-sided p when rho > 0, so this compound condition is a one-sided test at effective alpha=0.025 — inconsistent with the hit-rate binomial test at line 71, which is explicitly one-sided (alternative="greater") at alpha=0.05, despite both answering directional questions per the module docstring (lines 6-13). The two-sided p-value is also reported alongside one-directional claims in the output ("Positive & significant" label, line 134; "larger model edges do translate to higher hit rates", lines 233-237). The ties claim also holds: corrects is binary (line 64, int(r.correct)) so one variable is heavily tied, n can be as low as MIN_N_EDGE=15 (lines 33, 76), and scipy's spearmanr p-value uses the t-approximation (df=n-2), which is rough under heavy ties at n≈15. Caveat on severity: the mixing is conservative (alpha 0.025 instead of 0.05), so it under-declares significance rather than inflating results — this is a MINOR inconsistency/documentation defect, not a result-invalidating one.

</details>

### M11. NaN propagation into the JSON payload when spearmanr or ttest_1samp is degenerate (constant corrects or constant/singleton errors)

**Where:** `backend/nba_betting/services/statistical_validation.py:77`

**Evidence:** If corrects is constant (all hits or all misses at n>=15) spearmanr returns (nan, nan); lines 78-79 cast to float(nan), line 131 does round(nan, 4), and _insight formats "rho=nan". Same for ttest_1samp at line 86 when errors are identical or n==1: bias_pval = nan, bias_sig = (nan < 0.05) = False, and line 143 emits round(nan, 4). Nothing filters NaN before serialization.

**Why it matters:** NaN is not valid strict JSON — DRF/json will either emit literal NaN (breaking frontend JSON.parse) or error, and the insight text degrades to "p=nan". A 15+ game all-correct streak or a cached run with one game triggers it. Statistically, reporting "Not significant (p=nan)" for a 100% hit streak is also the wrong message.

**Fix:** After each test, check math.isnan and fall back to None (as the n<15 branch already does) with an explanatory warning string.

<details><summary>Verifier verdict</summary>

Verified at backend/nba_betting/services/statistical_validation.py. The n>=15 gate (line 76) checks count only, so constant `corrects` (all hits/misses) reaches spearmanr (line 77), which returns (nan, nan); float() casts (78-79) preserve NaN, `rho is not None` is True for NaN so line 131 emits round(nan,4) and _insight (lines 231, 241) formats "ρ=nan, p=nan". ttest_1samp (line 86) has no n-gate at all — the query only requires total_bets__gt=0, so n==1 is reachable and yields pvalue=nan; bias_sig = (nan < 0.05) = False mislabels it "Well-calibrated" (line 148) while line 143 emits round(nan,4). No isnan filtering exists anywhere in the file or in the consumer (views.py:1305-1321), and the NaN-bearing dict is cached for 24h (views.py:1195). One nuance: repo has no REST_FRAMEWORK renderer config, so DRF's default STRICT_JSON=True makes json.dumps raise at render time — outside the view's try/except — so the observed symptom is an unhandled 500 plus a poisoned cache rather than a literal NaN token in the body (a non-strict renderer would emit invalid-JSON NaN). Minor imprecision: identical nonzero errors give ±inf/pvalue 0.0 in current scipy, not nan; the n==1 and all-zero-error cases sustain the claim. Core defect (unfiltered NaN under degenerate inputs breaking the response) is real.

</details>

### M12. variance_decomp conflates error normality with calibration and floors R-squared at zero while claiming 'explains X% of variance'

**Where:** `backend/nba_betting/services/variance_decomp.py:437`

**Evidence:** Lines 437-440 render 'Prediction errors are approximately normal ... consistent with well-calibrated residuals' from a normality test alone — normality says nothing about calibration (a model biased by +5 with normal errors passes). Lines 213 and 339 compute `max(0.0, 1.0 - ss_res/ss_total)`, hiding negative R-squared (model worse than the player-mean baseline), while the insight (lines 388-397) asserts 'The XGBoost model explains {r2*100}% of the variance'.

**Why it matters:** Both are overclaims: a truncated R-squared of 0.0 is presented as a lower bound rather than 'worse than the mean baseline', and the calibration language implies probabilistic reliability that was never tested (no reliability curve or PIT check exists anywhere in the codebase).

**Fix:** Report signed R-squared (or flag 'below-baseline'), and change the normality sentence to describe only the error shape, e.g. 'consistent with a symmetric error distribution' — reserve 'calibrated' for an actual calibration test.

<details><summary>Verifier verdict</summary>

Verified against backend/nba_betting/services/variance_decomp.py. (1) Lines 437-440 literally emit "consistent with well-calibrated residuals" from an error-shape check alone (gated on |skew|<=1.0 and |kurt|<=1.5 at lines 425/431 — not even the formal normality_p computed at 164-176, which is never consulted); a model with constant +5 bias has skew~0/kurt~0 and passes, and bias never enters _generate_insight (it only appears in the comparison table via line 338). (2) Line 213 and line 339 both floor R² with max(0.0, ...), so a model worse than the player-mean baseline reports R²=0.000 with no disclosure. (3) Lines 388-397 then assert "The XGBoost model explains {r2*100}% of the variance", so negative-R² models read as "explains 0%... noise-driven" instead of "worse than baseline"; the flooring also propagates into residual = max(0.0, 1 - r2 - opp_delta) at line 241, silently renormalizing the advertised Var(y) partition. Only correction: the calibration sentence is triggered by skew/kurtosis thresholds rather than "a normality test alone" — a mechanical nuance that strengthens, not weakens, the finding.

</details>

### M13. Divergent fallback constants across paths: std defaults 5.0/2.0/1.5 (features.py) vs 6.0/2.5/2.0 (views.py); season_avg fallback 15/5/4 constants (features.py) vs pts_L10-then-15/5/4 chain (backtest.py); opponent-defense fallback hardcoded 112/44/26 (backtest.py) vs DB-computed league average (features.py)

**Where:** `backend/nba_betting/views.py:145`

**Evidence:** views.py:145 `std_dev = {"pts": 6.0, "reb": 2.5, "ast": 2.0}.get(stat_key, 4.0)` vs features.py:73-75 and 121 `{"pts": 5.0, "reb": 2.0, "ast": 1.5}` default 3.0. Season avg: features.py:230 `_defaults = {"pts": 15.0, "reb": 5.0, "ast": 4.0}` (also generic 10.0 at 241) vs backtest.py:156-158 `_safe("season_avg_pts", _safe("pts_L10", 15.0))`. Opponent defense: backtest.py:118 and 127-129 use frozen constants {"pts": 112.0, "reb": 44.0, "ast": 26.0} whenever the (stat, opponent, date) key is missing, while features.py:52-57 falls back to _get_league_avg_allowed which computes the actual league mean from the DB (constants only on exception, features.py:321).

**Why it matters:** The checklist requires fallback constants to be identical across features.py, views.py, probability.py; here the same missing-data event yields different feature values (and different prob_over via std_dev) depending on which code path handled the request, making live behavior, backtest behavior, and validation results non-reproducible relative to each other.

**Fix:** Move all default constants into nba_betting/constants.py and import them everywhere; make backtest fall back to the same _get_league_avg_allowed computation as the live path.

<details><summary>Verifier verdict</summary>

All cited evidence verified by reading the code. (1) views.py:145 hardcodes std fallbacks {pts:6.0, reb:2.5, ast:2.0}/4.0 while features.py:73-75 and 121-124 use {5.0, 2.0, 1.5}/3.0 and backtest.py:143/147/151 also use 5.0/2.0/1.5 — constants genuinely diverge, though the views.py branch is currently dead code because FEATURE_COLUMNS (train_regression.py:49-74) always includes {stat}_std_L10, so this leg is a latent inconsistency, not an active bias. (2) Season-avg fallbacks diverge as claimed: features.py:230/241/245 returns constants 15/5/4 (generic 10.0), while backtest.py:156-158 chains season_avg -> {stat}_L10 -> 15/5/4. (3) Opponent-defense imputation diverges as claimed and is live skew: backtest.py:118,127-129 substitutes frozen 112/44/26 whenever the exact (stat, opponent, date) key is missing, whereas inference (features.py:52-57) falls back to _get_league_avg_allowed, a DB-computed league mean, with the 112/44/26 constants (features.py:321) only on empty data/exception. This directly violates the methodology-auditor checklist item requiring identical fallback/default values across features.py, views.py, and related paths, and legs 2-3 create real inference-vs-backtest inconsistency.

</details>

### M14. Fallback std-dev defaults differ across three files (and two of the fallback branches are dead code)

**Where:** `backend/nba_betting/views.py:145`

**Evidence:** views.py:145 uses {pts: 6.0, reb: 2.5, ast: 2.0}; generate_daily_picks.py:138 uses {pts: 6.1, reb: 2.6, ast: 1.8}; features.py:73-75/121 and backtest.py:143-151 use {pts: 5.0, reb: 2.0, ast: 1.5}. The views.py and generate_daily_picks.py branches are unreachable because {stat}_std_L10 is always in FEATURE_COLUMNS (train_regression.py:52,61,68), so the columns check always passes; features.py's get_std_for_stat (features.py:119-135) is itself never called anywhere.

**Why it matters:** Violates the checklist requirement that fallback constants be identical across features.py/views.py/probability.py; divergent magic numbers make the effective probability model irreproducible from documentation and mask which code path actually runs (the live NaN path, per the CRITICAL finding, not these fallbacks).

**Fix:** Centralize one STD_FALLBACKS dict in constants.py, import it everywhere, and delete the unreachable branches plus the unused get_std_for_stat.

<details><summary>Verifier verdict</summary>

All evidence verified. views.py:145 uses {pts:6.0, reb:2.5, ast:2.0}; generate_daily_picks.py:138 uses {pts:6.1, reb:2.6, ast:1.8}; features.py:73-75 and :121 plus backtest.py:143/147/151 use {pts:5.0, reb:2.0, ast:1.5} — three inconsistent default sets. The dead-code claim also holds: feature rows are built from FEATURE_COLUMNS[stat] (features.py:113-114), which includes {stat}_std_L10 for all three stats (train_regression.py:52,61,68), so the `std_col in columns` check in views.py and generate_daily_picks.py always passes and their fallback branches are unreachable; get_std_for_stat (features.py:119-135) is defined but never called anywhere in the repo (grep confirms only the definition). Severity is tempered by the dead branches never executing, but the inconsistency is real and violates the auditor checklist item requiring identical fallback values across files.

</details>

### M15. Probability clamping to [0.01, 0.99] is undocumented and inconsistently applied across the three prob_over mechanisms

**Where:** `backend/nba_betting/views.py:149`

**Evidence:** views.py:149 and generate_daily_picks.py:140 clamp prob_over to [0.01, 0.99]; no file in docs/ mentions clamping (grep for clamp/0.99/0.01 across docs/ returns nothing; docs/METHODOLOGY.md does not exist). The simulator's Monte Carlo prop_table (simulator.py:210-211) reports unclamped empirical probabilities from an entirely different generative model (AR(1) around the season mean with Gaussian innovations, ignoring the XGBoost projection), so the same player/line can receive contradictory prob_over values from /api/predict vs the simulator endpoint.

**Why it matters:** Clamping changes tail-probability semantics (a reported 0.99 means '>= 0.99'), which matters for any Kelly/EV computation built on prob_over; three coexisting, undocumented probability models (Normal z-score, dead Poisson prescription, AR(1) MC) make the uncertainty methodology unauditable.

**Fix:** Document the clamp bounds and rationale in docs/METHODOLOGY.md, apply the same bounds (or none) in simulator.py's prop_table, and state which model is authoritative per endpoint.

<details><summary>Verifier verdict</summary>

Every evidence element holds under adversarial reading. (1) backend/nba_betting/views.py:149 clamps prob_over via max(0.01, min(0.99, 1-norm.cdf(z))) in ManualPredictionView. (2) backend/nba_betting/management/commands/generate_daily_picks.py:140-142 applies the identical clamp. (3) Grep for clamp/0.99/0.01 across docs/ returns nothing, and docs/METHODOLOGY.md does not exist (docs/ holds only USAGE, IMPLEMENTATION_PLAN, ML_FEATURE_GUIDE, SCHEMA, ARCHITECTURE, OPEN_SOURCE_READINESS_PLAN, erdplus.png); the auditor checklist (.claude/agents/methodology-auditor.md:37) explicitly requires this clamping to be documented. (4) backend/nba_betting/services/simulator.py:210-211 reports raw empirical P(over) = sum(values > line)/n with no clamp (can be exactly 0.0 or 1.0), from an AR(1)-around-season-mean model with Gaussian innovations (simulator.py:82-86, 181-188) that never invokes the XGBoost predictor; it is publicly exposed at /api/simulator/ (urls.py:14, views.py:714-780), so the same player/line can get contradictory prob_over values vs /api/predict, which uses a Normal centered on the XGBoost projection. The finding (undocumented clamp, inconsistently applied: two mechanisms clamp, the third does not) is accurate.

</details>

### M16. ARCHITECTURE.md documents ROI = total_pnl / total_bets, but the code divides by total risked units (bets x 1.1)

**Where:** `docs/ARCHITECTURE.md:323`

**Evidence:** ARCHITECTURE.md:323: 'ROI | total_pnl / total_bets x 100%'. services/backtest.py:212: `roi = (total_pnl / (total_bets * abs(LOSS_UNIT))) * 100` with LOSS_UNIT = -1.1 (backtest.py:34).

**Why it matters:** The API's reported ROI is ~9.1% smaller than the documented definition; anyone comparing documented ROI to the 52.4% break-even framing or to the paper's ROI (which uses profit/n_bets, betting_simulation.py:102) will misinterpret the numbers — three ROI conventions coexist.

**Fix:** Pick one ROI definition (profit per unit risked or per bet), state it in both docs, and make backtest.py and betting_simulation.py consistent.

<details><summary>Verifier verdict</summary>

Verified: docs/ARCHITECTURE.md:323 documents ROI as `total_pnl / total_bets × 100%`, but backend/nba_betting/services/backtest.py:212 computes `roi = (total_pnl / (total_bets * abs(LOSS_UNIT))) * 100` with LOSS_UNIT = -1.1 (line 34), i.e. divides by total units risked (bets × 1.1), not bet count. The formulas differ by a factor of 1.1 (e.g. 55-45 over 100 bets: doc gives 5.5%, code gives 5.0%). This is the only ROI computation in the file; cached reads (line 408) return the same stored value. Docs-vs-code mismatch is real; the code uses the more standard definition, so the fix is to correct the doc (MINOR severity).

</details>

### M17. ARCHITECTURE.md claims opponent-defense falls back to league average below 3 games of history; code uses min_periods=1 and falls back only at zero prior games

**Where:** `docs/ARCHITECTURE.md:215`

**Evidence:** ARCHITECTURE.md:215: 'opp_pts_allowed_L10 falls back to league average if opponent has fewer than 3 games of history'. services/features.py:311-316 computes `.shift(1).rolling(10, min_periods=1).mean()` and returns a value from a single prior game; the league-average fallback (features.py:52-57) triggers only when the rolling value is None/NaN. Training (train_regression.py:297-299) and backtest (backtest.py:358-359) also use min_periods=1. The 3-game minimum exists only in the orphaned notebooks pipeline (feature_engineering.py:240).

**Why it matters:** Early-season opponent-defense features are far noisier than documented (a 1-game 'average' instead of a league-average fallback), which matters for early-season claims like the market-inefficiency literature the paper cites.

**Fix:** Update the doc to min_periods=1, or implement the documented 3-game minimum consistently in features.py, backtest.py and train_regression.py.

<details><summary>Verifier verdict</summary>

Verified. docs/ARCHITECTURE.md:215 states opp_pts_allowed_L10 falls back to league average if the opponent has fewer than 3 games of history, but all live code uses min_periods=1: services/features.py:311-312 (inference, with league-average fallback at features.py:52-57 firing only when the rolling value is None/NaN), ml/train_regression.py:297-299 (training), and services/backtest.py:358-359 with NaN-only default fill at :367. An opponent with 1-2 prior games therefore produces a 1-2 game 'L10' value instead of the documented league-average fallback. The 3-game minimum (min_periods=3) exists only in the orphaned notebooks/feature_engineering.py:240, confirming the doc describes the notebook pipeline rather than production code. Minor caveat: on the inference path the fallback actually fires at 0 or 1 prior games (the latest row's shifted rolling is NaN with one prior game), so the finding's 'only at zero prior games' phrasing is exact for training/backtest but slightly off for inference; this does not affect the validity of the docs-vs-code discrepancy.

</details>

### M18. days_rest documented as 'NaN -> 3' / 'clipped at 10', but inference coerces back-to-back (0 days) to 2 and never clips

**Where:** `docs/ARCHITECTURE.md:196`

**Evidence:** ARCHITECTURE.md:196: 'days_rest | Days since previous game (NaN -> 3)'; paper.tex:249-250: 'days since the player's previous game, clipped at 10'. Training matches (train_regression.py:227-233: .fillna(3).clip(upper=10)). But inference features.py:81 does `float(latest.get("days_rest") or 2)` — Python truthiness turns a legitimate 0.0 (back-to-back game) into 2.0 — and _load_player_history (features.py:191) applies no upper clip, so long layoffs feed values >10 the model never saw in training.

**Why it matters:** Back-to-back games are exactly the rest condition the intelligence features (rest sensitivity, B2B splits) claim to analyze; at inference the model is silently told every B2B is a 2-day-rest game, contradicting both docs and training-time semantics.

**Fix:** In features.py use an explicit None/NaN check instead of `or 2`, fill with 3 and clip at 10 to mirror train_regression.py.

<details><summary>Verifier verdict</summary>

Partially confirmed, and the confirmed half is the substantive defect. VERIFIED: docs/ARCHITECTURE.md:195 documents 'NaN -> 3' and research/paper.tex:249-250 documents 'clipped at 10'; training matches (ml/train_regression.py:227-233: .diff().dt.days.fillna(3).clip(upper=10)); but inference (services/features.py:191) computes days_rest with fillna(3) and NO upper clip, so long layoffs and season openers feed values >10 (often 30-150) that the model never saw in training — real train/serve skew and doc-vs-code contradiction. The truthiness pattern also exists at features.py:80 (`float(latest.get("days_rest") or 2)`), and the fallback of 2 mismatches the documented default of 3. REFUTED: the claimed back-to-back mechanism is wrong — a back-to-back yields diff().dt.days == 1 (truthy, passed through unchanged), not 0; days_rest can only be 0 for same-date duplicate rows, and NaN is already filled upstream (NaN is also truthy), so the `or 2` branch is effectively dead code. Finding should be restated as: missing .clip(upper=10) at features.py:191 (MAJOR skew) plus an inconsistent, near-dead `or 2` fallback at features.py:80 (MINOR); the '0-days back-to-back coerced to 2' scenario does not occur.

</details>

### M19. Paper claims ROI 'rises monotonically with threshold for all three statistics' against the L10 line; its own appendix and results CSV show rebounds ROI falling at tau=2.5

**Where:** `research/paper.tex:621`

**Evidence:** paper.tex:621-623: 'Against the L10 line, ROI rises monotonically with threshold for all three statistics'. research/results/betting_summary.csv rows for reb/l10: tau=2.0 ROI +0.4163 (430 bets) -> tau=2.5 ROI +0.4051 (125 bets); the paper's own Appendix Table (lines 908-909) prints +0.416 then +0.405.

**Why it matters:** An overstated monotonicity claim is the kind of internal inconsistency a referee will catch immediately; it also feeds the narrative that edge concentrates at high thresholds.

**Fix:** Soften to 'rises monotonically for points and assists; rebounds plateaus beyond tau=2.0 where N<200'.

<details><summary>Verifier verdict</summary>

Verified against source files. paper.tex:621-623 states verbatim that "Against the L10 line, ROI rises monotonically with threshold for all three statistics." The paper's own Appendix table (paper.tex:908-909, Rebounds/L10 block) shows ROI falling from +0.416 (tau=2.0, N=430, 74.2% win) to +0.405 (tau=2.5, N=125, 73.6% win), and research/results/betting_summary.csv lines 12-13 confirm the underlying values (0.4163 -> 0.4051). Points and assists rows are monotonic (assists only tabulated to tau=1.5), so the violation is exactly the rebounds tau=2.5 case as claimed. Refutation attempts (narrower reading of the sentence, table truncation) do not hold: the sentence is unqualified and cites the full range to tau=2.5. Severity MINOR: an overstated descriptive claim contradicted by the paper's own data, not a methodology flaw; fix is to qualify the sentence for rebounds where N drops to 125.

</details>

### M20. Paper Table 3 caption says 'Only thresholds with N >= 1,000 reported' but the table includes the Assists/LinReg row with N=793

**Where:** `research/paper.tex:574`

**Evidence:** paper.tex:574 caption: 'Only thresholds with N >= 1,000 reported.' Line 593 in the same table: 'LinReg & 1.0 & 793 & +0.156' — and the abstract/conclusion (lines 731-732) cite this N=793 result as a headline ROI.

**Why it matters:** The stated inclusion criterion is violated by the table itself, and the sub-threshold sample is the one used for a headline claim (+15.6% ROI on assists).

**Fix:** Either drop the N=793 row per the caption or change the caption to describe the actual selection rule.

<details><summary>Verifier verdict</summary>

Verified in research/paper.tex: the Table 3 caption at line 574 states "Only thresholds with $N \geq 1{,}000$ reported," yet line 593 includes the Assists/LinReg row with N=793 (+0.156 ROI) — the only row violating the stated criterion. The N=793 result is cited in the body at line 642 ("+15.6% on assists ($N=793$)") and repeated as a headline ROI in the Conclusion at lines 731-732 ("AST: +15.6% at a 1-unit edge threshold"). Minor correction to the claimed evidence: the abstract (lines 78-82) cites only the points result (+13.1%, N=17,685), not the assists figure — the sub-threshold result is promoted in the conclusion only. The caveat at lines 648-650 about small samples does not resolve the caption/table contradiction. The finding stands as a real internal inconsistency.

</details>

### M21. Three contradictory data-provenance claims: paper says ESPN unofficial API, training code says NBA API, ARCHITECTURE says Kaggle CSVs

**Where:** `research/paper.tex:222`

**Evidence:** paper.tex:221-222: 'sourced from the ESPN unofficial public API'. ml/train_regression.py:8: 'Data source: data/raw/PlayerStatistics.csv (NBA API historical data)'. docs/ARCHITECTURE.md:64,154: 'Historical CSVs (Kaggle) — used for model training'. The CSV schema (personId, gameDateTimeEst, reboundsTotal, ...) matches the Kaggle NBA historical dataset, not ESPN's API shape used elsewhere in the repo (ARCHITECTURE.md:345 documents ESPN stats-array indices).

**Why it matters:** Dataset provenance is a basic reproducibility requirement for the paper; a reader cannot obtain '1,648,656 records from the ESPN unofficial public API' as described.

**Fix:** State the actual source (Kaggle/NBA-API-derived PlayerStatistics.csv) and its retrieval date in paper section 3.1 and align the code comment and ARCHITECTURE.md.

<details><summary>Verifier verdict</summary>

CONFIRMED. All three cited claims exist verbatim: (1) research/paper.tex:221-222 says the 1,648,656-record 1951-2025 dataset was "sourced from the ESPN unofficial public API"; (2) backend/nba_betting/ml/train_regression.py:8 says "Data source: data/raw/PlayerStatistics.csv (NBA API historical data)"; (3) docs/ARCHITECTURE.md:64 says "Historical CSVs (Kaggle) — used for model training only" and :154 says "historical NBA data from Kaggle CSVs". Refutation attempts failed: (a) I read the actual file header of data/raw/PlayerStatistics.csv — columns are firstName,lastName,personId,gameId,gameDateTimeEst,...,points,assists,...,reboundsDefensive..., and the sibling files (Games.csv, Players.csv, TeamHistories.csv, TeamStatistics.csv, LeagueSchedule*.csv) are exactly the Kaggle historical-NBA-box-scores dataset layout, not ESPN output; (b) train_regression.py:79,143,159,167 confirms training reads this exact CSV/schema; (c) the ESPN format used elsewhere in the repo is a positional stats array ([0]=MIN, [6]=REB, [13]=PTS per ARCHITECTURE.md:345) — a completely different shape; (d) ARCHITECTURE.md:344 states ESPN data "only goes back 60 days by default", so a 1951-2025 dataset cannot come from the repo's ESPN ingestion; (e) ARCHITECTURE.md:363 explicitly admits "current model was trained on Kaggle CSVs. Retraining on ESPN-sourced data would make features consistent between training and inference", directly contradicting the paper. One nuance: the "NBA API" (code comment) and "Kaggle" (docs) claims are potentially reconcilable if the Kaggle dataset was compiled from the NBA stats API, so the defect is at minimum a two-way contradiction; but the paper's ESPN provenance claim is unambiguously false per the repo's own code, data files, and docs. Severity: CRITICAL under the auditor rubric (a published paper claim about data provenance is invalidated by the implementation).

</details>

### M22. Paper's 'break-even ROI = -0.048' caption does not match the simulation's own ROI definition

**Where:** `research/paper.tex:573`

**Evidence:** paper.tex:573 caption: 'break-even ROI = -0.048 at -110 juice'. betting_simulation.py:54-56 pays +0.9091/-1.0 and defines roi = total_pnl/n_bets (line 102). Under that definition a bettor at the 52.38% break-even rate has ROI exactly 0, and a no-skill 50% bettor has ROI -0.0455; -0.048 (=-0.1/2.1) corresponds to a per-unit-risked convention not used anywhere in the code.

**Why it matters:** It misstates the null benchmark readers compare the reported ROIs against, in a table whose entire point is distance from break-even.

**Fix:** Change the caption to 'break-even ROI = 0; a no-skill (50%) bettor earns -0.045 under this payout' or switch the sim to a per-unit-risked ROI and say so.

<details><summary>Verifier verdict</summary>

Verified. paper.tex:573 caption states 'break-even ROI = -0.048 at -110 juice', but paper.tex:432-433 defines ROI as total profit / number of bets, and betting_simulation.py:54-56,89,101-102 implements exactly that (pnl = +0.9091 win / -1.0 loss; roi = total_pnl/n_bets). Under this definition break-even ROI is exactly 0 (at 52.38%: (11/21)(0.9091) - (10/21)(1.0) = 0), and a no-skill 50% bettor earns -0.0455. The value -0.048 (~ -1/21 = -0.0476, the -110 overround) does not correspond to any ROI convention in the code or the paper; no alternative computation exists in the repo (checked betting_simulation.py, _build_notebook.py, the notebook). Attempted refutation via the charitable 'random-bettor ROI' reading also fails since that yields -0.0455, not -0.048. Caption misstates the Table 5 profitability benchmark; correct fix is break-even ROI = 0 (coin-flip bettor ROI = -0.045).

</details>

## Assumptions to disclose in METHODOLOGY.md

- Early-stopping round selection for the deployed XGBoost/CatBoost models used the 2015-12-15-to-present eval window — the same window later backtested and significance-tested; all reported test metrics and backtest p-values assume this selection bias is negligible.
- The training dataset effectively spans the full NBA history (~1946-present) because the MIN_YEAR=2016 filter never applied; model weights therefore assume stationarity of feature-target relationships across eras, and the documented 'modern-era 2016+' claim does not hold as trained.
- The backtest 'line' is the player's own shift(1) L5 rolling average, not a real sportsbook line; hit-rate comparisons against the 52.4% -110 break-even assume this proxy behaves like a market line.
- Season averages are grouped by calendar year in training (missing 'year' column fallback, train_regression.py:242) but by Oct-1 NBA season start at inference (features.py:234) and in backtest (backtest.py:274-276); leakage-free in all three, but the definitions differ.
- Opponent-defense 'allowed' totals in training sum only players with >=10 minutes (the row filter at train_regression.py:155 precedes team aggregation at 274), while inference and backtest sum all period=0 player rows; the two definitions are assumed equivalent.
- At live inference, feature values are one game stale by construction: get_model_inputs takes the shift(1) features of the last played game's row (features.py:43), so the most recent game is excluded from every rolling window — conservative (anti-leakage) but must be disclosed as intentional.
- shift(1) ordering assumes no team or player plays two games on the same date; date ties would make the shift order ambiguous (harmless in the NBA schedule, but an assumption).
- Backtest rolling features are computed over the ESPN-synced DB while the model was trained on the NBA API CSV; the two sources are assumed to record identical box-score values for the same games.
- Training season_avg treats the calendar year as the season (comment at train_regression.py:237-239); serving and backtest use an Oct-1 season boundary — until unified, any claim about season_avg/hot_cold features must disclose that train and serve define 'season' differently.
- Live inference features are computed 'as of the last completed game' with shift(1), so every rolling feature, season average, opponent-defense average, and days_rest excludes the player's most recent game and days_rest describes the previous game rather than the game being predicted.
- The backtest 'line' is the player's L5 rolling average, not a real sportsbook line; hit-rate and ROI figures are relative to this synthetic line (disclosed in backtest.py docstring but must carry into docs/METHODOLOGY.md).
- Training team-defense totals (opp_*_allowed_L10) are computed only from players who logged >= 10 minutes; serving computes them from all players — a systematic level difference until fixed.
- Training data comes from the NBA API CSV (PlayerStatistics.csv) while serving/backtest features come from the ESPN-synced Django DB; the pipeline assumes the two sources report identical minutes, fg splits, and box-score values for the same games (no reconciliation is performed).
- Fallback constants (league totals 112/44/26; std defaults 5.0/2.0/1.5 or 6.0/2.5/2.0; season averages 15/5/4; fg_pct 0.45; days_rest 2 or 3) are hardcoded circa-2024 league values and are used whenever a player/opponent has insufficient history; predictions built on these fallbacks are not model-driven and should be flagged as such.
- The MIN_YEAR=2016 'modern era' filter documented in the code and metadata is not actually applied because the training CSV lacks a 'year' column; the effective training era is whatever the CSV contains.
- A player's game outcomes are treated as independent, identically distributed Bernoulli trials for the binomial hit-rate test; serial correlation (streaks, minutes/role changes, rest patterns) is ignored, making p-values anti-conservative.
- The 52.4% break-even threshold assumes -110 two-way sportsbook pricing, but the backtest 'line' is the player's own L5 rolling average, not a market line; hit-rate significance therefore does not imply profitability against real books.
- Signed projection errors are assumed approximately normal (or n large enough for the CLT) for the one-sample calibration t-test; no normality check or minimum-n gate is applied to that test.
- Each player-stat panel is tested at per-test alpha=0.05; across the 18-player x 3-stat roster this is ~162 uncorrected tests, so roughly 8 spuriously 'significant' results are expected under a global null; no family-wise or FDR correction is applied.
- The 18-player roster is hand-selected post hoc for games played (70+), health, and consistency (constants.py:12-34); all per-player and aggregate results condition on this survivorship-biased selection and do not generalize to the wider player population.
- Spearman edge-hit correlation uses a binary, tie-heavy outcome variable with the default two-sided p-value gated by rho > 0 (effective alpha 0.025); a significant positive rho is an association claim only and does not establish edge magnitudes are profitable.
- Push games (actual exactly equal to the line) are scored as decided 'under' outcomes rather than voided, slightly distorting the tested hit proportion relative to real betting.
- A non-significant calibration t-test is reported as 'Well-calibrated', i.e., absence of evidence of bias is presented as evidence of absence, including at sample sizes where the test has little power.
- docs/METHODOLOGY.md does not currently exist; none of the above caveats are disclosed in the API payloads or documentation (docs/OPEN_SOURCE_READINESS_PLAN.md acknowledges items 3-6 as planned disclosures only).
- prob_over assumes actual ~ Normal(projection, std_L10): the XGBoost projection is treated as the true conditional mean with zero model uncertainty, and dispersion equals the player's raw last-10-game std — not the model's residual std (RMSE) — homoskedastic and symmetric.
- The Normal model is applied to discrete low-count stats (ast, reb) with no continuity correction; the Poisson alternative in services/probability.py is prescribed but never executed.
- std_L10 is a ddof=1 sample std from 5-10 observations with no shrinkage; a hard floor of 0.5 is the only regularization, and a NaN std currently short-circuits to prob_over=0.99 (bug, must be fixed before disclosure).
- All reported probabilities from views.py and generate_daily_picks.py are clamped to [0.01, 0.99]; simulator prop_table probabilities are not clamped and come from a different generative model (AR(1) around the season mean, Gaussian innovations, values clipped at 0).
- Backtest 'lines' are the player's own L5 rolling average, not sportsbook lines; floor_ceiling and variance_decomp inherit all of their inputs (actuals, errors, hit rates, ROI) from these synthetic-line backtests.
- Variance decomposition components are computed on a single-player, single-season sample (typically 60-80 games) with ~25-30 opponent groups of 2-3 games each; opponent eta-squared and opponent delta are unadjusted for degrees of freedom and are upward-biased at these sample sizes.
- The public picks feed only surfaces picks with prob_over >= 0.55, which under the current code excludes all Under recommendations; any published hit-rate for the feed is conditional on this one-sided selection.
- Games within a player's history and within condition splits (rest, form) are treated as independent draws; serial correlation (the AR(1) phi the simulator itself estimates as nonzero) is ignored by every probability and quantile computation outside the simulator.
- The MIN_YEAR=2016 'modern-era' filter is assumed to be active, but it only fires if the CSV has a 'year' column — data/raw/PlayerStatistics.csv has none, so all trained models, walk-forward results, betting simulations and SHAP analyses actually use 1951-2025 data (verified: 1,120,817 rows spanning 1951-11-11 to 2025-06-22; only 230,900 rows post-Oct-2015). METHODOLOGY.md must disclose the true training-era distribution or the pipeline must be fixed and everything re-run.
- 'Season' means calendar year in training/research (walk_forward_splits derives year via date.dt.year; build_player_features uses the same for season_avg) but means an Oct-1-anchored NBA year at inference (services/features.py:234) and in the backtest (services/backtest.py:274) — season_avg_* and hot_cold_* features therefore have different semantics at train vs serve time.
- XGBoost early stopping uses the evaluation fold itself as the validation set (train_regression.py:391-397, called with the test fold in walk_forward_eval.py:137 and with the 2024 explanation set in shap_analysis.py:106) — all reported XGBoost test MAEs and downstream betting ROIs are mildly optimistic; the paper discloses this in section 4.1 but METHODOLOGY.md should carry it too.
- All betting-simulation results are against synthetic lines (L10 / EMA5 / linear-regression) computable from the same dataset, not sportsbook closing lines; ROI figures are relative benchmarks, not market profitability (paper discloses; README/ARCHITECTURE-level docs should too).
- The backtest engine prices every historical game with the single production model, whose training window (through 2025 per model_metadata.json trained_at 2026-06-15) overlaps the backtested dates — in-sample backtests inflate hit rates fed to statistical_validation.py, edge_calibration.py and the predictability leaderboard.
- statistical_validation.py's binomial, Spearman and t-tests treat one player's games as i.i.d. draws and run ~18 players x 3 stats without any multiple-comparisons correction; the 52.4% break-even reference assumes -110 pricing on both sides.
- prob_over in ManualPredictionView (views.py:148-149) and generate_daily_picks assumes normally distributed outcomes with the noisy n<=10-game rolling std as dispersion, clamped to [0.01, 0.99]; services/probability.py's Poisson treatment for low-count stats is dead code (never called).
- The paper's SHAP 'final model' (trained on data before calendar-2024) is not the shipped production model (trained on an 80/20 chronological split of all data through June 2025, split date 2015-12-15); feature-importance claims transfer to production only by assumption.
- docs/ARCHITECTURE.md describes the retired mvp-branch binary classifier; none of its quantitative claims (AUC 0.62-0.65, 17 features, ~3 seasons of training data) apply to the current system and it must not be cited as current methodology.
- notebooks/feature_engineering.py (Holt trends, cv_l10, proj_volume, rest features) is an orphaned pipeline: none of its outputs are consumed by the trained models, despite README_FEATURES.md and docs/ML_FEATURE_GUIDE.md presenting it as the current feature pipeline.
