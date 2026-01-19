# Schema Reference

This document focuses on the period-specific tables that power quarter-level prop
predictions. Types below align with the Django models in `backend/nba_betting/models.py`.

## PlayerQuarterStats
Represents a single player's box score stats for one quarter of a game.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| player | FK -> Player | Yes | Links to the player record. |
| game | FK -> Game | Yes | Links to the game record. |
| quarter | int (1-4) | Yes | Regulation quarters only. |
| pts | int | Yes | Points scored in the quarter. |
| reb | int | Yes | Rebounds in the quarter. |
| ast | int | Yes | Assists in the quarter. |
| min | decimal | Yes | Minutes played in the quarter. |

Constraints and indexes:
- Unique constraint on (player, game, quarter).
- Implicit FK indexes via Django.

Example record:
- player: 203507 (Giannis Antetokounmpo)
- game: 0022300111
- quarter: 1
- pts: 8
- reb: 4
- ast: 2
- min: 10.5

## PlayerPropLine
Represents a sportsbook line for a player's stat in a specific period.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| player | FK -> Player | Yes | Links to the player record. |
| game | FK -> Game | Yes | Links to the game record. |
| stat_type | string | Yes | Example: rebounds, points, assists. |
| period | int (1-4) | Yes | Quarter the line applies to. |
| threshold | float | Yes | Example: 2.5. |
| odds | int | Yes | American odds (ex: -110, +130). |
| bookmaker | string | Yes | Example: FanDuel, DraftKings. |

Example record:
- player: 203507
- game: 0022300111
- stat_type: rebounds
- period: 1
- threshold: 2.5
- odds: -115
- bookmaker: DraftKings
