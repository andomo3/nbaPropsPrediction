# Schema Reference

This document highlights the core tables that power quarter-level prop
predictions. Types below align with the Django models in `backend/nba_betting/models.py`.

## Player
Represents an NBA player.

Primary key:
- id (BigAutoField)

Foreign keys:
- None

Constraints/indexes:
- Unique: nba_id

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| name | string | Yes | Full name. |
| team | string | Yes | Team abbreviation or name. |
| nba_id | int | Yes | Unique NBA ID. |

## Game
Represents a single NBA game.

Primary key:
- id (BigAutoField)

Foreign keys:
- None

Constraints/indexes:
- Unique: game_id

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| game_id | string | Yes | Unique game identifier. |
| date | date | Yes | Game date (UTC). |
| home_team | string | Yes | Home team. |
| away_team | string | Yes | Away team. |

## PlayerGameStats
Full-game stat line for a player.

Primary key:
- id (BigAutoField)

Foreign keys:
- player -> Player.id
- game -> Game.id

Constraints/indexes:
- FK indexes on player, game (implicit)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| player | FK -> Player | Yes | Links to the player record. |
| game | FK -> Game | Yes | Links to the game record. |
| min | decimal | Yes | Minutes played in game. |
| pts | int | Yes | Points. |
| reb | int | Yes | Rebounds. |
| ast | int | Yes | Assists. |

## PlayerQuarterStats
Represents a single player's box score stats for one quarter of a game.

Primary key:
- id (BigAutoField)

Foreign keys:
- player -> Player.id
- game -> Game.id

Constraints/indexes:
- Unique: (player, game, quarter)
- FK indexes on player, game (implicit)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| player | FK -> Player | Yes | Links to the player record. |
| game | FK -> Game | Yes | Links to the game record. |
| quarter | int (1-4) | Yes | Regulation quarters only. |
| pts | int | Yes | Points scored in the quarter. |
| reb | int | Yes | Rebounds in the quarter. |
| ast | int | Yes | Assists in the quarter. |
| fga | int | Yes | Field goal attempts. |
| fgm | int | Yes | Field goals made. |
| min | float | Yes | Minutes played in the quarter. |
| fouls | int | Yes | Personal fouls. |

Example record:
- player: 203507 (Giannis Antetokounmpo)
- game: 0022300111
- quarter: 1
- pts: 8
- reb: 4
- ast: 2
- fga: 6
- fgm: 3
- min: 10.5
- fouls: 1

## PlayerPropLine
Represents a sportsbook line for a player's stat in a specific period.

Primary key:
- id (BigAutoField)

Foreign keys:
- player -> Player.id
- game -> Game.id

Constraints/indexes:
- FK indexes on player, game (implicit)

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

## GameBettingLine
Game-level market context.

Primary key:
- id (BigAutoField)

Foreign keys:
- game -> Game.id

Constraints/indexes:
- FK indexes on game (implicit)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| game | FK -> Game | Yes | Links to the game record. |
| home_spread | float | Yes | Home spread. |
| over_under | float | Yes | Total points line. |
| favorite | string | Yes | Market favorite. |

## Prediction
Stores model predictions for tracking and auditing.

Primary key:
- id (BigAutoField)

Foreign keys:
- player -> Player.id
- game -> Game.id

Constraints/indexes:
- FK indexes on player, game (implicit)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| player | FK -> Player | Yes | Links to the player record. |
| game | FK -> Game | Yes | Links to the game record. |
| stat_type | string | Yes | Example: points, rebounds. |
| period | int | Yes | Quarter 1-4. |
| threshold | float | Yes | Line value. |
| predicted_prob | float | Yes | Model probability. |
| is_over_recommended | bool | Yes | True for Over recommendation. |
