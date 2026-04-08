"""
management/commands/sync_espn_games.py

Replaces the banned nba_api ingestion with ESPN's free unofficial API.
No API key or auth required.

Usage:
    # Sync today's games
    python manage.py sync_espn_games

    # Sync a specific date
    python manage.py sync_espn_games --date 20260101

    # Backfill the last 60 days
    python manage.py sync_espn_games --days 60

ESPN endpoints:
    Scoreboard: https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD
    Box score:  https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={id}
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import requests
from django.core.management.base import BaseCommand, CommandError

from nba_betting.models import Game, Player, PlayerStats, Team

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"

# Fallback stats array indices (used only if ESPN response has no "names" labels)
IDX_MIN = 0
IDX_FG  = 1
IDX_REB = 6
IDX_AST = 7
IDX_PTS = 13

REQUEST_DELAY = 0.4  # seconds between requests (courteous to ESPN servers)


class Command(BaseCommand):
    help = "Sync NBA game data from ESPN unofficial API into Django DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            help="Date to sync in YYYYMMDD format (default: today)",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=1,
            help="Number of days to backfill ending on --date (default: 1 = just --date)",
        )

    def handle(self, *args, **options):
        end_date = (
            datetime.strptime(options["date"], "%Y%m%d").date()
            if options["date"]
            else date.today()
        )
        days = max(1, options["days"])
        dates = [end_date - timedelta(days=i) for i in range(days - 1, -1, -1)]

        total_games = 0
        total_stats = 0

        for d in dates:
            games, stats = self._sync_date(d)
            total_games += games
            total_stats += stats

        self.stdout.write(
            self.style.SUCCESS(
                f"Sync complete: {total_games} games, {total_stats} player-stat rows"
            )
        )

    # ------------------------------------------------------------------
    # Date-level sync
    # ------------------------------------------------------------------

    def _sync_date(self, game_date: date) -> tuple[int, int]:
        date_str = game_date.strftime("%Y%m%d")
        self.stdout.write(f"Syncing {date_str}...")

        try:
            resp = requests.get(SCOREBOARD_URL, params={"dates": date_str}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            self.stderr.write(f"  Scoreboard fetch failed for {date_str}: {exc}")
            return 0, 0

        events = data.get("events", [])
        if not events:
            self.stdout.write(f"  No games on {date_str}")
            return 0, 0

        game_count = 0
        stat_count = 0

        for event in events:
            g, s = self._sync_event(event, game_date)
            game_count += g
            stat_count += s
            time.sleep(REQUEST_DELAY)

        return game_count, stat_count

    # ------------------------------------------------------------------
    # Event-level sync
    # ------------------------------------------------------------------

    def _sync_event(self, event: dict, game_date: date) -> tuple[int, int]:
        event_id = event.get("id", "")
        if not event_id:
            return 0, 0

        try:
            competition = event["competitions"][0]
        except (KeyError, IndexError):
            return 0, 0

        competitors = competition.get("competitors", [])
        if len(competitors) < 2:
            return 0, 0

        # Identify home and away teams
        home_comp = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away_comp = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        home_team = self._upsert_team(home_comp.get("team", {}))
        away_team = self._upsert_team(away_comp.get("team", {}))
        if not home_team or not away_team:
            return 0, 0

        # Scores (None if game not yet completed)
        completed = event.get("status", {}).get("type", {}).get("completed", False)
        home_score = None
        away_score = None
        if completed:
            try:
                home_score = int(home_comp.get("score", 0))
                away_score = int(away_comp.get("score", 0))
            except (ValueError, TypeError):
                pass

        season = _derive_season(game_date)

        game, _ = Game.objects.update_or_create(
            game_id=event_id,
            defaults={
                "date": game_date,
                "season": season,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
            },
        )

        stat_count = 0
        if completed:
            stat_count = self._sync_box_score(event_id, game)

        return 1, stat_count

    # ------------------------------------------------------------------
    # Box score sync (completed games only)
    # ------------------------------------------------------------------

    def _sync_box_score(self, event_id: str, game: Game) -> int:
        try:
            resp = requests.get(SUMMARY_URL, params={"event": event_id}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            self.stderr.write(f"  Box score fetch failed for event {event_id}: {exc}")
            return 0

        box = data.get("boxscore", {})
        player_groups = box.get("players", [])
        count = 0

        for group in player_groups:
            team_info = group.get("team", {})
            team = self._upsert_team(team_info)
            if not team:
                continue

            statistics = group.get("statistics", [])
            if not statistics:
                continue

            stat_group = _find_full_game_group(statistics)
            if stat_group is None:
                continue

            # Build a name→index map from the ESPN response so we never rely
            # on hardcoded positions that can shift between API versions.
            names = stat_group.get("names", [])
            idx = {n.upper(): i for i, n in enumerate(names)}

            athletes = stat_group.get("athletes", [])
            for athlete_entry in athletes:
                if self._sync_player_stats(athlete_entry, game, team, idx):
                    count += 1

        return count

    def _sync_player_stats(self, entry: dict, game: Game, team: Team, idx: dict | None = None) -> bool:
        athlete = entry.get("athlete", {})
        stats = entry.get("stats", [])

        if not athlete or not stats:
            return False

        if idx is None:
            idx = {}

        # Resolve column positions: prefer label-based lookup, fall back to
        # hardcoded constants so old data formats still work.
        i_min = idx.get("MIN", IDX_MIN)
        i_fg  = idx.get("FG",  IDX_FG)
        i_reb = idx.get("REB", IDX_REB)
        i_ast = idx.get("AST", IDX_AST)
        i_pts = idx.get("PTS", IDX_PTS)

        min_needed = max(i_min, i_fg, i_reb, i_ast, i_pts) + 1
        if len(stats) < min_needed:
            return False

        # Parse minutes: "34:56" → 34.93
        try:
            minutes = _parse_minutes(stats[i_min])
        except (ValueError, IndexError):
            return False

        if minutes <= 0:
            return False  # Did not play

        # Parse FG: "9-18" → (9, 18)
        try:
            fgm, fga = _parse_made_attempted(stats[i_fg])
        except (ValueError, IndexError):
            fgm, fga = 0, 0

        try:
            pts = int(stats[i_pts])
            reb = int(stats[i_reb])
            ast = int(stats[i_ast])
        except (ValueError, IndexError):
            return False

        # Upsert Player
        athlete_id = athlete.get("id")
        if not athlete_id:
            return False

        try:
            nba_id = int(athlete_id)
        except ValueError:
            return False

        display_name = athlete.get("displayName", "")
        first_name, last_name = _split_name(display_name)

        player, _ = Player.objects.update_or_create(
            nba_id=nba_id,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "position": athlete.get("position", {}).get("abbreviation", ""),
                "is_active": True,
                "current_team": team,
            },
        )

        # Upsert PlayerStats (period=0 = full game)
        PlayerStats.objects.update_or_create(
            player=player,
            game=game,
            period=0,
            defaults={
                "team": team,
                "pts": pts,
                "reb": reb,
                "ast": ast,
                "min": round(minutes, 2),
                "fga": fga,
                "fgm": fgm,
            },
        )
        return True

    # ------------------------------------------------------------------
    # Team upsert
    # ------------------------------------------------------------------

    def _upsert_team(self, team_info: dict) -> Team | None:
        abbrev = team_info.get("abbreviation", "").upper()
        if not abbrev:
            return None

        display_name = team_info.get("displayName", abbrev)
        # Split "Los Angeles Lakers" → city="Los Angeles", nickname="Lakers"
        parts = display_name.rsplit(" ", 1)
        city = parts[0] if len(parts) == 2 else display_name
        nickname = parts[1] if len(parts) == 2 else ""

        team, _ = Team.objects.update_or_create(
            abbreviation=abbrev,
            defaults={"city": city, "nickname": nickname},
        )
        return team


# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------

def _find_full_game_group(statistics: list) -> dict | None:
    """
    Return the statistics group that contains full-game player stats.

    ESPN may return multiple groups (e.g. per-quarter + totals). We want the
    group whose "names" array includes PTS, REB, and AST — that is the
    full-game totals group. Falls back to statistics[0] if none qualify.
    """
    required = {"PTS", "REB", "AST"}
    for group in statistics:
        names = {n.upper() for n in group.get("names", [])}
        if required.issubset(names):
            return group
    # Fallback: return the first group and let index-based lookup handle it
    return statistics[0] if statistics else None


def _derive_season(game_date: date) -> str:
    """Convert a game date to NBA season label, e.g. 2024-01-15 → '2023-24'."""
    year = game_date.year
    month = game_date.month
    if month >= 10:
        return f"{year}-{(year + 1) % 100:02d}"
    return f"{year - 1}-{year % 100:02d}"


def _parse_minutes(raw: str) -> float:
    """Parse '34:56' → 34.933..."""
    if not raw or raw in ("--", ""):
        return 0.0
    if ":" in raw:
        parts = raw.split(":")
        return int(parts[0]) + int(parts[1]) / 60.0
    return float(raw)


def _parse_made_attempted(raw: str) -> tuple[int, int]:
    """Parse '9-18' → (9, 18)."""
    if not raw or "-" not in raw:
        return 0, 0
    parts = raw.split("-")
    return int(parts[0]), int(parts[1])


def _split_name(display_name: str) -> tuple[str, str]:
    """Split 'LeBron James' → ('LeBron', 'James'); handles multi-word last names."""
    parts = display_name.strip().split(" ", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return display_name, ""
