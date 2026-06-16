from django.urls import path

from . import views

urlpatterns = [
    path("options/", views.MetadataView.as_view(), name="metadata-options"),
    path("players/", views.PlayerListView.as_view(), name="player-list"),
    path("predict/manual/", views.ManualPredictionView.as_view(), name="manual-prediction"),
    path("picks/", views.LitePicksView.as_view(), name="lite-picks"),
    path("backtest/", views.BacktestView.as_view(), name="backtest"),
    path("backtest/season-summary/", views.SeasonSummaryView.as_view(), name="season-summary"),
    path("backtest/model-comparison/", views.ModelComparisonView.as_view(), name="model-comparison"),
    path("backtest/leaderboard/", views.LeaderboardView.as_view(), name="leaderboard"),
    path("simulator/", views.SimulatorView.as_view(), name="simulator"),
    path("analysis/shap/", views.ShapAnalysisView.as_view(), name="shap-analysis"),
    path("analysis/variance/", views.VarianceDecompView.as_view(), name="variance-decomp"),
    path("backtest/leaderboard-comparison/", views.LeaderboardComparisonView.as_view(), name="leaderboard-comparison"),
    path("analysis/tier-history/", views.TierHistoryView.as_view(), name="tier-history"),
    path("intelligence/edge/", views.EdgeCalibrationView.as_view(), name="edge-calibration"),
    path("intelligence/floor-ceiling/", views.FloorCeilingView.as_view(), name="floor-ceiling"),
    path("intelligence/opponents/", views.OpponentAnalysisView.as_view(), name="opponent-analysis"),
    path("intelligence/fingerprint/", views.PlayerFingerprintView.as_view(), name="player-fingerprint"),
]
