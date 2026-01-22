## Data Ingestion Strategy
1. NBA stats
   - Use `BoxScoreTraditionalV3` with StartPeriod/EndPeriod for quarter slices.
   - Store per-quarter stats in PlayerStats with period=1-4.
   - Player identity fields come from `homeTeam.players` and `awayTeam.players`.
2. Betting lines
   - Use The Odds API for historical player prop lines.
   - Normalize prop_type names to a consistent set (points, rebounds, assists).
3. Team context
   - Keep Team data aligned to player/game records for matchup features.
