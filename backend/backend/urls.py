from django.contrib import admin
from django.urls import path

from nba_betting import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/players/", views.PlayerListView.as_view(), name="player-list"),
    path(
        "api/predict/manual/",
        views.ManualPredictionView.as_view(),
        name="manual-prediction",
    ),
]
