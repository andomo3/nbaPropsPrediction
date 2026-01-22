import json
import time
from datetime import date

from django.core.management.base import BaseCommand

from nba_api.stats.endpoints import boxscoretraditionalv3, leaguegamelog

from nba_betting.models import Game, Player, PlayerStats, Team


def current_season_label():
    today = date.today()
    start_year = today.year if today.month >= 10 else today.year - 1
    end_year = (start_year + 1) % 100
    return f"{start_year}-{end_year:02d}"


def split_player_name(full_name):
    if not full_name:
        return "", ""
    parts = full_name.split(" ")
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def split_team_name(team_name, abbreviation):
    if not team_name:
        return "", abbreviation
    parts = team_name.split(" ")
    if len(parts) == 1:
        return "", parts[0]
    return " ".join(parts[:-1]), parts[-1]


def parse_minutes(value):
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and ":" in value:
        minutes, seconds = value.split(":", maxsplit=1)
        return float(minutes) + float(seconds) / 60.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_game_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def find_result_set(data, name):
    for result in data.get("resultSets", []):
        if result.get("name") == name:
            return result
    return None


def extract_player_rows(data):
    preferred = ("boxScoreTraditional", "PlayerStats", "playerStats")
    result_set = None
    for name in preferred:
        result_set = find_result_set(data, name)
        if result_set:
            break
    if not result_set:
        for candidate in data.get("resultSets", []):
            headers = candidate.get("headers") or []
            if "PLAYER_ID" in headers and "TEAM_ID" in headers:
                result_set = candidate
                break
    if not result_set:
        return [], []
    return result_set.get("headers", []), result_set.get("rowSet", [])


def get_value(row, header_map, key, default=None):
    index = header_map.get(key)
    if index is None:
        return default
    return row[index]


def extract_team_players(data):
    boxscore = (
        data.get("boxScoreTraditional")
        or data.get("boxScoreTraditionalV3")
        or data.get("boxscoretraditional")
        or {}
    )
    players = []
    for side in ("homeTeam", "awayTeam"):
        team = boxscore.get(side) or {}
        team_abbrev = (
            team.get("teamTricode")
            or team.get("teamCode")
            or team.get("teamAbbreviation")
        )
        team_city = team.get("teamCity") or team.get("city") or ""
        team_name = team.get("teamName") or team.get("nickname") or ""
        for player in team.get("players", []):
            players.append(
                {
                    "player": player,
                    "team_abbrev": team_abbrev,
                    "team_city": team_city,
                    "team_name": team_name,
                }
            )
    return players


def get_stat(player_data, stats, *keys, default=0):
    for key in keys:
        if stats and key in stats:
            return stats.get(key)
        if key in player_data:
            return player_data.get(key)
    return default


class Command(BaseCommand):
    help = "Ingest historical NBA player stats (period 0-4) with rate limiting."

    def add_arguments(self, parser):
        parser.add_argument("--season", default=current_season_label())
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--max-games", type=int, default=None)

    def handle(self, *args, **options):
        season = options["season"]
        dry_run = options["dry_run"]
        max_games = options["max_games"]

        log = leaguegamelog.LeagueGameLog(season=season)
        log_data = log.get_dict()
        log_set = find_result_set(log_data, "LeagueGameLog")
        if not log_set:
            self.stdout.write("No game log data found.")
            return

        headers = log_set.get("headers", [])
        rows = log_set.get("rowSet", [])
        header_index = {header: idx for idx, header in enumerate(headers)}

        game_index = {}
        for row in rows:
            game_id = get_value(row, header_index, "GAME_ID")
            matchup = get_value(row, header_index, "MATCHUP", "")
            team_abbrev = get_value(row, header_index, "TEAM_ABBREVIATION")
            team_name = get_value(row, header_index, "TEAM_NAME")
            game_date = get_value(row, header_index, "GAME_DATE")
            pts = get_value(row, header_index, "PTS")

            if not game_id or not team_abbrev:
                continue

            entry = {
                "team_abbrev": team_abbrev,
                "team_name": team_name,
                "game_date": game_date,
                "pts": pts,
                "is_home": "vs." in matchup or "vs" in matchup,
            }

            game_index.setdefault(game_id, {"entries": []})
            game_index[game_id]["entries"].append(entry)

        game_ids = list(game_index.keys())
        if max_games:
            game_ids = game_ids[:max_games]

        if dry_run and game_ids:
            sample_game = game_ids[0]
            sample = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=sample_game)
            time.sleep(0.6)
            self.stdout.write(json.dumps(sample.get_dict(), indent=2))
            return

        for game_id in game_ids:
            entries = game_index[game_id]["entries"]
            home_entry = next((e for e in entries if e["is_home"]), None)
            away_entry = next((e for e in entries if not e["is_home"]), None)
            if not home_entry or not away_entry:
                self.stdout.write(f"Skipping {game_id}: missing home/away rows.")
                continue

            home_city, home_nickname = split_team_name(
                home_entry["team_name"], home_entry["team_abbrev"]
            )
            away_city, away_nickname = split_team_name(
                away_entry["team_name"], away_entry["team_abbrev"]
            )

            home_team, _ = Team.objects.get_or_create(
                abbreviation=home_entry["team_abbrev"],
                defaults={"city": home_city, "nickname": home_nickname},
            )
            away_team, _ = Team.objects.get_or_create(
                abbreviation=away_entry["team_abbrev"],
                defaults={"city": away_city, "nickname": away_nickname},
            )

            game, _ = Game.objects.update_or_create(
                game_id=game_id,
                defaults={
                    "date": parse_game_date(home_entry["game_date"]) or date.today(),
                    "season": season,
                    "home_score": home_entry["pts"] or 0,
                    "away_score": away_entry["pts"] or 0,
                    "home_team": home_team,
                    "away_team": away_team,
                },
            )

            periods_done = []
            for period in [0, 1, 2, 3, 4]:
                if period == 0:
                    boxscore = boxscoretraditionalv3.BoxScoreTraditionalV3(
                        game_id=game_id
                    )
                else:
                    boxscore = boxscoretraditionalv3.BoxScoreTraditionalV3(
                        game_id=game_id,
                        start_period=period,
                        end_period=period,
                    )
                time.sleep(0.6)

                data = boxscore.get_dict()
                player_entries = extract_team_players(data)

                for entry in player_entries:
                    player_data = entry["player"]
                    player_id = player_data.get("personId") or player_data.get("playerId")
                    first_name = player_data.get("firstName") or ""
                    last_name = player_data.get("familyName") or player_data.get(
                        "lastName", ""
                    )
                    position = player_data.get("position") or "UNK"
                    team_abbrev = entry["team_abbrev"] or player_data.get("teamTricode")
                    team_city = entry["team_city"]
                    team_name = entry["team_name"]

                    if not player_id or not team_abbrev:
                        continue

                    if not first_name or not last_name:
                        full_name = player_data.get("name") or ""
                        first_name, last_name = split_player_name(full_name)

                    city, nickname = split_team_name(team_name, team_abbrev)
                    if team_city:
                        city = team_city
                    team, _ = Team.objects.get_or_create(
                        abbreviation=team_abbrev,
                        defaults={"city": city, "nickname": nickname},
                    )

                    player, _ = Player.objects.update_or_create(
                        nba_id=player_id,
                        defaults={
                            "first_name": first_name,
                            "last_name": last_name,
                            "position": position or "UNK",
                            "is_active": True,
                            "current_team": team,
                        },
                    )

                    stats = player_data.get("statistics") or player_data.get("stats") or {}
                    try:
                        PlayerStats.objects.update_or_create(
                            player=player,
                            game=game,
                            period=period,
                            defaults={
                                "team": team,
                                "pts": get_stat(player_data, stats, "points", "PTS", default=0) or 0,
                                "reb": get_stat(
                                    player_data, stats, "reboundsTotal", "rebounds", "REB", default=0
                                )
                                or 0,
                                "ast": get_stat(
                                    player_data, stats, "assists", "AST", default=0
                                )
                                or 0,
                                "min": parse_minutes(
                                    get_stat(player_data, stats, "minutes", "MIN")
                                ),
                                "fga": get_stat(
                                    player_data,
                                    stats,
                                    "fieldGoalsAttempted",
                                    "FGA",
                                    default=0,
                                )
                                or 0,
                                "fgm": get_stat(
                                    player_data,
                                    stats,
                                    "fieldGoalsMade",
                                    "FGM",
                                    default=0,
                                )
                                or 0,
                            },
                        )
                    except Exception as exc:
                        self.stdout.write(
                            self.style.ERROR(f"Stats Error: {exc}")
                        )

                periods_done.append(f"P{period}")

            self.stdout.write(
                f"Processed Game {game_id} [{' '.join(periods_done)}] - OK"
            )
