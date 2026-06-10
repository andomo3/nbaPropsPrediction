from django.urls import path

from . import views

urlpatterns = [
    path("options/", views.MetadataView.as_view(), name="metadata-options"),
    path("players/", views.PlayerListView.as_view(), name="player-list"),
    path("predict/manual/", views.ManualPredictionView.as_view(), name="manual-prediction"),
    path("picks/", views.LitePicksView.as_view(), name="lite-picks"),
    path("backtest/", views.BacktestView.as_view(), name="backtest"),
    path("backtest/season-summary/", views.SeasonSummaryView.as_view(), name="season-summary"),
]
