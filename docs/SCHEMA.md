# Schema Reference

![EERD Diagram](erdplus.png)

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

---

# Schema Specification (Source of Truth)

This section defines the target schema at a high level. Use it as a reference
when aligning models to the EERD.

## Core Reference Models

### Team
- Primary key: `id`
- Fields: `city`, `nickname`, `abbreviation`

### Bookmaker
- Primary key: `id`
- Fields: `name` (ex: DraftKings)

### Player
- Primary key: `nba_id` (from NBA API)
- Fields: `first_name`, `last_name`, `position`, `is_active`
- Foreign keys: `current_team` (nullable)

### Game
- Primary key: `game_id` (NBA API ID)
- Fields: `date`, `season`, `home_score`, `away_score`
- Foreign keys: `home_team`, `away_team`

## Data Models (Weak Entities)

### PlayerStats (Collapsed Supertype)
- Foreign keys: `player`, `game`, `team` (team at time of game)
- Fields: `period` (0=Full, 1-4=Quarter), `pts`, `reb`, `ast`, `min`, `fga`, `fgm`
- Constraints: `unique_together = ['player', 'game', 'period']`

### PlayerPropLine (Market)
- Foreign keys: `player`, `game`, `bookmaker`
- Fields: `prop_type`, `period`, `line`, `odds_over`, `odds_under`, `timestamp`
- Constraints: `unique_together = ['player', 'game', 'bookmaker', 'prop_type', 'period']`
  (include timestamp if tracking history)

### Prediction (ML Output)
- Foreign keys: `prop_line`
- Fields: `model_version`, `prediction_timestamp`, `prob_over`, `recommendation`

---

# Agent-Ready Prompt: Schema Integrity Audit

**Role:** Senior Django Architect & Database Designer  
**Project:** NBA Period Predictor (Backend)  
**Current Task:** Verify `core/models.py` against the "Target Schema Specification".

## Context

We have finalized the Enhanced Entity Relationship Diagram (EERD) for the
application. We need to ensure the actual Django code (`models.py`) matches this
design exactly before we run migrations.

## The Target Schema Specification

### 1. Strong Entities

**Team**: Needs `team_id` (PK), `city`, `nickname`, `abbreviation`.  
**Bookmaker**: Needs `name`, `site_url`.  
**Player**: Needs `nba_id` (PK), `first_name`, `last_name` (Composite split),
`position`, `is_active`.  
Relationship: `current_team` (FK to Team, nullable).  

**Game**: Needs `game_id` (PK), `date`, `season`, `home_score`, `away_score`.  
Relationship: `home_team` (FK to Team), `away_team` (FK to Team).  

### 2. Weak Entities & Logic

**PlayerStats**:
Logic: Collapsed Supertype. Uses `period` field (0=Full Game, 1-4=Quarter).  
Relationships: Must link to `Player`, `Game`, AND `Team`
(to track historical team at time of game).  
Constraint: `unique_together = ['player', 'game', 'period']`.  

**PlayerPropLine**:
Logic: Represents a betting line offered by a specific bookmaker.  
Relationships: Must link to `Player`, `Game`, and `Bookmaker`.  
Constraint: `unique_together` on player, game, bookmaker, prop_type, and period.  

**Prediction**:
Logic: A child of the Prop Line.  
Relationship: FK to `PlayerPropLine` (NOT Player).  

## Instructions

1. Read: Analyze the current contents of `core/models.py`.
2. Compare: Check for the following specific gaps:
- Does the `Bookmaker` model exist?
- Does `Player` have `first_name`/`last_name` split?
- Does `PlayerStats` have the `team` Foreign Key (to track historical context)?
- Is `Prediction` correctly linked to `PlayerPropLine` (instead of Player)?
- Are `unique_together` constraints present on Stats and PropLines?

3. Report:
- List every discrepancy found.
- Ask me: "Shall I refactor `models.py` to match the Target Schema?"
