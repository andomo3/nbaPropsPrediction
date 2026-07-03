# Feature Engineering

The feature documentation lives in **[`docs/ML_FEATURE_GUIDE.md`](docs/ML_FEATURE_GUIDE.md)**,
which is written from the authoritative feature definitions in
`backend/nba_betting/ml/train_regression.py` (`FEATURE_COLUMNS`) and
`backend/nba_betting/services/features.py`.

> An earlier version of this file described `notebooks/feature_engineering.py` as "the
> current leakage-safe feature engineering pipeline". That script is an orphaned
> experimental pipeline whose outputs (Holt trend features, `proj_volume`, `cv_l10`,
> `opp_avg_*_allowed_l10`) are not consumed by any deployed model — see the appendix of
> `docs/ML_FEATURE_GUIDE.md`.
