from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from django.core.management.base import BaseCommand
from django.db import transaction

from nba_betting.models import Game, Player, PlayerStats, Team


@dataclass
class TeamMap:
    id_to_abbrev: Dict[str, str]
    name_to_abbrev: Dict[Tuple[str, str], str]


def parse_date(value: str) -> Optional[date]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(value.split(" ")[0])
    except ValueError:
        return None


def season_label(game_date: date) -> str:
    start_year = game_date.year if game_date.month >= 10 else game_date.year - 1
    end_year = (start_year + 1) % 100
    return f"{start_year}-{end_year:02d}"


def normalize_abbrev(value: str) -> str:
    return (value or "").strip().upper()


def fallback_abbrev(team_name: str) -> str:
    name = (team_name or "").strip().upper()
    return name[:3] if len(name) >= 3 else name


def load_team_histories(path: Path) -> TeamMap:
    id_to_abbrev: Dict[str, str] = {}
    name_to_abbrev: Dict[Tuple[str, str], str] = {}

    if not path.exists():
        return TeamMap(id_to_abbrev, name_to_abbrev)

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            team_id = (row.get("teamId") or "").strip()
            team_city = (row.get("teamCity") or "").strip()
            team_name = (row.get("teamName") or "").strip()
            team_abbrev = normalize_abbrev(row.get("teamAbbrev") or "")
            if not team_abbrev:
                continue

            if team_id:
                id_to_abbrev[team_id] = team_abbrev
            if team_city and team_name:
                name_to_abbrev[(team_city, team_name)] = team_abbrev

            Team.objects.update_or_create(
                abbreviation=team_abbrev,
                defaults={"city": team_city or team_abbrev, "nickname": team_name or team_abbrev},
            )

    return TeamMap(id_to_abbrev, name_to_abbrev)


def resolve_team(
    city: str,
    name: str,
    team_id: Optional[str],
    team_map: TeamMap,
) -> Team:
    team_abbrev = ""
    if team_id and team_id in team_map.id_to_abbrev:
        team_abbrev = team_map.id_to_abbrev[team_id]
    elif (city, name) in team_map.name_to_abbrev:
        team_abbrev = team_map.name_to_abbrev[(city, name)]
    else:
        team_abbrev = fallback_abbrev(name) or fallback_abbrev(city)

    team_abbrev = normalize_abbrev(team_abbrev)
    return Team.objects.update_or_create(
        abbreviation=team_abbrev,
        defaults={
            "city": city or team_abbrev,
            "nickname": name or team_abbrev,
        },
    )[0]


def load_players(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            player_id = (row.get("personId") or "").strip()
            if not player_id:
                continue
            first_name = (row.get("firstName") or "").strip()
            last_name = (row.get("lastName") or "").strip()
            guard = (row.get("guard") or "").strip() == "1"
            forward = (row.get("forward") or "").strip() == "1"
            center = (row.get("center") or "").strip() == "1"

            position_parts = []
            if guard:
                position_parts.append("G")
            if forward:
                position_parts.append("F")
            if center:
                position_parts.append("C")
            position = "-".join(position_parts) if position_parts else "UNK"

            Player.objects.update_or_create(
                nba_id=int(player_id),
                defaults={
                    "first_name": first_name or "Unknown",
                    "last_name": last_name or "",
                    "position": position,
                    "is_active": True,
                },
            )
            count += 1
    return count


def load_games(path: Path, team_map: TeamMap, allowed_seasons: Optional[set] = None) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            game_id = (row.get("gameId") or "").strip()
            if not game_id:
                continue
            game_date = parse_date((row.get("gameDateTimeEst") or "").strip())
            if not game_date:
                continue

            home_city = (row.get("hometeamCity") or "").strip()
            home_name = (row.get("hometeamName") or "").strip()
            home_id = (row.get("hometeamId") or "").strip()
            away_city = (row.get("awayteamCity") or "").strip()
            away_name = (row.get("awayteamName") or "").strip()
            away_id = (row.get("awayteamId") or "").strip()

            home_team = resolve_team(home_city, home_name, home_id, team_map)
            away_team = resolve_team(away_city, away_name, away_id, team_map)

            home_score = int(float(row.get("homeScore") or 0))
            away_score = int(float(row.get("awayScore") or 0))

            if allowed_seasons and season_label(game_date) not in allowed_seasons:
                continue

            Game.objects.update_or_create(
                game_id=game_id,
                defaults={
                    "date": game_date,
                    "season": season_label(game_date),
                    "home_score": home_score,
                    "away_score": away_score,
                    "home_team": home_team,
                    "away_team": away_team,
                },
            )
            count += 1
    return count


def load_player_stats(
    path: Path,
    team_map: TeamMap,
    skip_existing: bool = False,
    allowed_seasons: Optional[set] = None,
    log_every: int = 5000,
    log_fn=None,
) -> int:
    if not path.exists():
        return 0
    count = 0
    processed = 0
    started_at = time.monotonic()
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            processed += 1
            game_id = (row.get("gameId") or "").strip()
            player_id = (row.get("personId") or "").strip()
            if not game_id or not player_id:
                continue

            game_date = parse_date((row.get("gameDateTimeEst") or "").strip())
            if not game_date:
                continue
            if allowed_seasons and season_label(game_date) not in allowed_seasons:
                continue

            player_team_city = (row.get("playerteamCity") or "").strip()
            player_team_name = (row.get("playerteamName") or "").strip()
            opponent_team_city = (row.get("opponentteamCity") or "").strip()
            opponent_team_name = (row.get("opponentteamName") or "").strip()

            player_team = resolve_team(player_team_city, player_team_name, None, team_map)
            opponent_team = resolve_team(opponent_team_city, opponent_team_name, None, team_map)

            is_home = (row.get("home") or "").strip() == "1"

            game = Game.objects.filter(game_id=game_id).first()
            if not game:
                home_team = player_team if is_home else opponent_team
                away_team = opponent_team if is_home else player_team
                game = Game.objects.create(
                    game_id=game_id,
                    date=game_date,
                    season=season_label(game_date),
                    home_score=int(float(row.get("teamScore") or row.get("points") or 0)),
                    away_score=int(float(row.get("opponentScore") or 0)),
                    home_team=home_team,
                    away_team=away_team,
                )

            player = Player.objects.filter(nba_id=int(player_id)).first()
            if not player:
                first_name = (row.get("firstName") or "").strip() or "Unknown"
                last_name = (row.get("lastName") or "").strip()
                player = Player.objects.create(
                    nba_id=int(player_id),
                    first_name=first_name,
                    last_name=last_name,
                    position="UNK",
                    is_active=True,
                    current_team=player_team,
                )

            if skip_existing and PlayerStats.objects.filter(player=player, game=game, period=0).exists():
                continue

            PlayerStats.objects.update_or_create(
                player=player,
                game=game,
                period=0,
                defaults={
                    "team": player_team,
                    "pts": int(float(row.get("points") or 0)),
                    "reb": int(float(row.get("reboundsTotal") or 0)),
                    "ast": int(float(row.get("assists") or 0)),
                    "min": float(row.get("numMinutes") or 0),
                    "fga": int(float(row.get("fieldGoalsAttempted") or 0)),
                    "fgm": int(float(row.get("fieldGoalsMade") or 0)),
                },
            )
            player.current_team = player_team
            player.save(update_fields=["current_team"])
            count += 1

            if log_fn and log_every and count % log_every == 0:
                elapsed = time.monotonic() - started_at
                rate = count / elapsed if elapsed > 0 else 0
                log_fn(f"PlayerStats progress: {count:,} rows saved ({rate:,.1f} rows/sec)")

    return count


class Command(BaseCommand):
    help = "Load raw CSV files into existing Django tables (Option A: ORM upserts)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--raw-dir",
            default=str(Path.cwd() / "data" / "raw"),
            help="Directory containing raw CSV files (default: data/raw)",
        )
        parser.add_argument(
            "--skip-playerstats",
            action="store_true",
            help="Skip loading PlayerStatistics.csv",
        )
        parser.add_argument(
            "--only-playerstats",
            action="store_true",
            help="Only load PlayerStatistics.csv (skip Teams/Players/Games).",
        )
        parser.add_argument(
            "--skip-existing-stats",
            action="store_true",
            help="Skip PlayerStats rows that already exist (player, game, period=0).",
        )
        parser.add_argument(
            "--season-start",
            default="2019-20",
            help="Earliest season label to import (default: 2019-20).",
        )
        parser.add_argument(
            "--season-end",
            default="2024-25",
            help="Latest season label to import (default: 2024-25).",
        )
        parser.add_argument(
            "--log-every",
            type=int,
            default=5000,
            help="Log progress every N PlayerStats rows (default: 5000). Use 0 to disable.",
        )

    def handle(self, *args, **options):
        raw_dir = Path(options["raw_dir"]).resolve()
        team_histories = raw_dir / "TeamHistories.csv"
        players_csv = raw_dir / "Players.csv"
        games_csv = raw_dir / "Games.csv"
        player_stats_csv = raw_dir / "PlayerStatistics.csv"

        if not raw_dir.exists():
            self.stdout.write(self.style.ERROR(f"Raw dir not found: {raw_dir}"))
            return

        only_playerstats = options.get("only_playerstats")
        season_start = options.get("season_start")
        season_end = options.get("season_end")
        allowed_seasons = None
        try:
            start_year = int(season_start.split("-")[0])
            end_year = int(season_end.split("-")[0])
            allowed_seasons = {f"{year}-{(year + 1) % 100:02d}" for year in range(start_year, end_year + 1)}
        except Exception:
            allowed_seasons = None

        if not only_playerstats:
            with transaction.atomic():
                team_map = load_team_histories(team_histories)
                team_count = len(team_map.name_to_abbrev)
                self.stdout.write(f"Teams loaded/updated: {team_count}")

            with transaction.atomic():
                player_count = load_players(players_csv)
                self.stdout.write(f"Players loaded/updated: {player_count}")

            with transaction.atomic():
                game_count = load_games(games_csv, team_map, allowed_seasons=allowed_seasons)
                self.stdout.write(f"Games loaded/updated: {game_count}")
        else:
            team_map = load_team_histories(team_histories)

        if options.get("skip_playerstats"):
            self.stdout.write("Skipping PlayerStatistics.csv")
            return

        with transaction.atomic():
            stats_count = load_player_stats(
                player_stats_csv,
                team_map,
                skip_existing=options.get("skip_existing_stats"),
                allowed_seasons=allowed_seasons,
                log_every=options.get("log_every") or 0,
                log_fn=self.stdout.write,
            )
            self.stdout.write(f"PlayerStats loaded/updated: {stats_count}")
