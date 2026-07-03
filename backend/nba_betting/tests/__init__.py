"""Test suite for nba_betting.

Modules:
    test_leakage                — shift(1) discipline, chronological splits,
                                  sub-10-minute masking (publication-protecting)
    test_feature_parity         — training vs. serving feature builders agree
    test_probability            — calculate_probability (Normal + Poisson)
    test_statistical_validation — validation service vs. hand-computed scipy
    test_stats_utils            — predictability score / tier math
    test_backtest_scoring       — push-void and >=10-minute scoring conventions

All tests run on synthetic fixtures only: no data/raw CSVs, no Redis,
no Docker, no trained model files.
"""
