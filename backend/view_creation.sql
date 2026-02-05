/*
NBA Two-View Architecture (Position-Agnostic)
=============================================

This SQL file defines the base view used by the Python feature engine.
The final consumption view (`view_final_features`) is recreated by the Python
script after it refreshes `derived_features_store`.
*/

DROP VIEW IF EXISTS public.view_base_data;

/*
view_base_data
--------------
Raw, denormalized full-game logs used for feature engineering.

Filters:
- period = 0 (full game only)
- season in [2020-21, 2024-25]
*/
CREATE VIEW public.view_base_data AS
SELECT
    ps.player_id,
    ps.game_id,
    g.date,
    g.season,
    p.first_name || ' ' || p.last_name AS player_name,
    CASE
        WHEN ps.team_id = g.home_team_id THEN g.away_team_id
        ELSE g.home_team_id
    END AS opponent_id,
    ps.min,
    ps.pts,
    ps.reb,
    ps.ast,
    ps.fga,
    ps.fgm
FROM public.nba_betting_playerstats ps
JOIN public.nba_betting_game g ON g.game_id = ps.game_id
JOIN public.nba_betting_player p ON p.nba_id = ps.player_id
WHERE ps.period = 0
  AND g.season BETWEEN '2020-21' AND '2024-25';
