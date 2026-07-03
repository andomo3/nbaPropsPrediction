> **ARCHIVED (2026-07-03):** this document describes a superseded design and is kept for historical reference only. Quarter-slice ingestion via `BoxScoreTraditionalV3` is no longer used; the live system ingests full-game box scores from the ESPN unofficial API (`sync_espn_games`) — see `docs/ARCHITECTURE.md`.

## Data Ingestion Strategy
1. NBA stats
   - Use `BoxScoreTraditionalV3` with StartPeriod/EndPeriod for quarter slices.
   - Store per-quarter stats in PlayerStats with period=1-4.
   - Player identity fields come from `homeTeam.players` and `awayTeam.players`.
   - Rate limit: jitter sleep (0.6s–1.2s) after every request.
   - Retry policy: exponential cool-down (30s, then 60s) on timeouts; skip after 3 failures.
   - Requests use explicit headers (User-Agent + Referer) to reduce soft-ban risk.
   - If a Game exists with 0 PlayerStats, treat it as incomplete and re-fetch.
2. Betting lines
   - Use The Odds API for historical player prop lines.
   - Normalize prop_type names to a consistent set (points, rebounds, assists).
3. Team context
   - Keep Team data aligned to player/game records for matchup features.
