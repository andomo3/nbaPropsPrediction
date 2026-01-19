from django.contrib import admin

from .models import (
    Game,
    GameBettingLine,
    Player,
    PlayerGameStats,
    PlayerPropLine,
    PlayerQuarterStats,
    Prediction,
)

admin.site.register(
    [
        Player,
        Game,
        PlayerGameStats,
        PlayerQuarterStats,
        GameBettingLine,
        PlayerPropLine,
        Prediction,
    ]
)