from django.contrib import admin

from .models import (
    Bookmaker,
    Game,
    Player,
    PlayerPropLine,
    PlayerStats,
    Prediction,
    Team,
)

admin.site.register(
    [
        Team,
        Bookmaker,
        Player,
        Game,
        PlayerStats,
        PlayerPropLine,
        Prediction,
    ]
)
