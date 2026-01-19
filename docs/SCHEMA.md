# Schema Reference

## PlayerQuarterStats
- player (FK -> Player)
- game (FK -> Game)
- quarter (int, 1-4)
- pts (int)
- reb (int)
- ast (int)
- min (decimal)
- unique constraint: player + game + quarter

## PlayerPropLine
- player (FK -> Player)
- game (FK -> Game)
- stat_type (string, e.g., rebounds)
- period (int, 1-4)
- threshold (float, e.g., 2.5)
- odds (int)
- bookmaker (string)