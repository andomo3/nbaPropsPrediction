# Open-Source Readiness Plan

Goal: publish this repo as a credible open-source analytics project. Everything below is ordered so that methodology verification happens **before** documentation is written (docs must describe the verified system, not the current one), and refactoring happens before both notebook and docs so they don't reference code that's about to move.

Agent roster after this plan: `product-architect` (orchestrates), `backend-engineer`, `frontend-engineer`, `code-reviewer`, **`methodology-auditor`** (new, read-only stats referee), **`docs-writer`** (new, docs-only writer). Plus the **`frontend-viewership`** project skill and the **`methodology-audit`** saved workflow.

---

## Phase 1 — Methodology audit (verify before you publish)

Run the `methodology-audit` workflow (or the `methodology-auditor` agent per dimension). It checks five dimensions and adversarially verifies each finding: leakage, train/serve skew, hypothesis-test correctness, uncertainty modeling, docs-vs-code drift.

Known issues it must confirm or refute:

| # | Issue | Where | Suspected severity |
|---|-------|-------|--------------------|
| 1 | `season_avg` uses calendar year in training but an Oct-1 season heuristic at inference (train/serve skew) | `ml/train_regression.py` vs `services/features.py` | MAJOR |
| 2 | `ManualPredictionView` hardcodes a Normal prob_over while `services/probability.py` prescribes Poisson for low-count stats | `views.py`, `services/probability.py` | MAJOR |
| 3 | Multiple comparisons: ~18 players × 3 stats × 4 tests with per-test α, no correction or framing | `services/statistical_validation.py` | MAJOR (as a disclosure) |
| 4 | Selection bias: roster is 18 hand-picked stars; aggregate claims don't generalize | `constants.py` | Disclosure |
| 5 | `std_L10` (n=10 sample std) as the dispersion estimate is noisy; fallbacks differ across files | `features.py`, `views.py` | MINOR–MAJOR |
| 6 | Binomial test treats a player's games as iid | `statistical_validation.py` | Disclosure |

**Deliverable:** confirmed-findings list + the canonical assumptions list (feeds Phase 4's METHODOLOGY.md). Fixes for confirmed CRITICAL/MAJOR items go to `backend-engineer` before anything else proceeds.

## Phase 2 — Refactor & simplify

Owner: `backend-engineer` / `frontend-engineer`, reviewed by `code-reviewer`; finish with `/simplify` and `/code-review`.

1. **Delete dead code**: `ml/model_trainer.py` (858 lines, superseded), `ml/visualizations.py` (only imported by it), empty stubs `ml/data_collector.py` / `ml/feature_engineering.py`, `exports/test.py`. Update `docs/ARCHITECTURE.md` references.
2. **Unify feature engineering** (the highest-value refactor — it *removes* the class of train/serve skew found in Phase 1): one module, e.g. `nba_betting/ml/features.py`, that both `train_regression.py` and `services/features.py`/`backtest.py` call. One definition of "season", one set of fallback constants.
3. **Split `views.py`** (1,321 lines) into a `views/` package: `views/predictions.py`, `views/backtest.py`, `views/intelligence.py`, plus `views/_shared.py` for the preamble/cache helpers.
4. **Single source for the player roster**: backend `constants.py` stays canonical; expose `GET /api/meta/players/` and have the frontend fetch it (or generate `constants.js` at build time). Kill the triplicated list.
5. **Centralize magic numbers**: `BREAK_EVEN=0.524`, default std devs, league-average fallbacks, `SEASON_DATES`, `DEFAULT_SEASON` → one constants module with comments explaining each value's origin.
6. **Unify the probability model**: route `ManualPredictionView` through `services/probability.py` (resolves issue #2 above).

## Phase 3 — Tests (minimum credible suite)

Owner: `backend-engineer`. Pytest + `pytest-django`.

- **Leakage regression tests** (the ones that protect the publication claim): synthetic fixture where the target of game *t* is poisoned into features unless `.shift(1)` is applied — assert every rolling feature is unaffected; assert `time_split` is strictly chronological.
- **Parity test**: training feature builder vs. inference feature builder produce identical rows for the same fixture (locks in the Phase 2 unification).
- Unit tests for `utils/stats.py` (predictability score math), `statistical_validation.py` (each test against hand-computed values), `probability.py`.
- Smoke tests for each API endpoint (200 + expected keys, empty-data behavior).
- CI: GitHub Actions running backend tests + frontend build on PR.

## Phase 4 — Documentation

Owner: `docs-writer` (claims verified against post-refactor code).

- **`docs/METHODOLOGY.md`** (the publication-critical doc): data sources & filters (MIN_YEAR=2016, MIN_MINUTES=10), feature definitions with formulas, model training & chronological/walk-forward splits, the leakage-prevention design, probability model, the four validation tests with their null hypotheses, and a first-class **Assumptions & Limitations** section built from the Phase 1 assumptions list.
- **README refresh**: honest scope statement ("insight, not a bet slip" is good — keep it), link METHODOLOGY.md, responsible-gambling note, badges/CI.
- **`docs/API.md`**: every endpoint with params and example responses.
- **Archive stale docs** to `docs/archive/` with deprecation banners: `IMPLEMENTATION_PLAN.md`, `backend/docs/DATA_INGESTION_STRATEGY.md`; rewrite `ML_FEATURE_GUIDE.md` from the unified feature module; update `ARCHITECTURE.md`.
- **One product name everywhere** — decide between "NBA Props Intelligence" (README), "PropEdge" (ARCHITECTURE), "perchave" (frontend assets), then sweep.

## Phase 5 — Methodology walkthrough notebook

Owner: `backend-engineer` (code cells) + `docs-writer` (narrative). New `notebooks/methodology_walkthrough.ipynb`, small-scale and self-contained (one player or a small CSV sample checked into `data/sample/`), consolidating/superseding `temp_mvp_summary.ipynb` and `data_export_and_cleaning.ipynb`:

1. Load sample game logs → 2. Build features, **demonstrating leakage** (show the inflated metric without `.shift(1)`, then the honest one — this is the best teaching moment in the repo) → 3. Chronological split, why random splits lie for time series → 4. Train a small XGBoost, evaluate → 5. Convert projection + line to prob_over → 6. Run the four validation tests on the results → 7. Caveats: sample size, selection bias, multiple comparisons.

Must run top-to-bottom in < ~2 minutes with pinned deps and no DB/Redis/API keys.

## Phase 6 — Frontend viewership pass

Owner: `frontend-engineer` using the `frontend-viewership` skill (which chains the global `dataviz` and `web-interface-guidelines` skills). Review every route at 1440px/375px against the skill checklist: jargon tooltips, chart labeling, empty first-run states, InsightText quality, dark-theme contrast, reduced-motion. Fix blockers; log polish items.

## Phase 7 — Release checklist

- `/security-review` on the branch (check `.env` handling, `SECRET_KEY`, DEBUG defaults, CORS)
- Verify `.env` is untracked and `.env.example` is complete; scrub git history if any key was ever committed
- `docker compose up` from a clean clone following only the README (a fresh-eyes agent can simulate this)
- License headers consistent (MIT), CONTRIBUTING.md current, GitHub issue templates
- Tag v1.0 once the audit findings are fixed and CI is green

---

### Maintenance notes for the existing agent files
- `backend-engineer.md` says Django 4.2; README says Django 5 — verify and align.
- `frontend-engineer.md` says react-router v6; installed is v7 — align.
- Consider adding `model:` frontmatter: `methodology-auditor` benefits from the strongest available model; mechanical agents can run on a faster tier.
