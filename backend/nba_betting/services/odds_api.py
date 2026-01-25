from datetime import timedelta
import os

import requests
from django.utils import timezone

from nba_betting.models import Bookmaker, Player, PlayerPropLine


ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports/basketball_nba"


def _recent_props(game_id, cutoff):
    return (
        PlayerPropLine.objects.filter(game_id=game_id, timestamp__gte=cutoff)
        .select_related("player", "bookmaker", "game")
        .order_by("-timestamp")
    )


def fetch_live_odds(game_id):
    """Fetch odds for a game on-demand and cache in DB.

    Returns a list of prop dicts sorted by edge (placeholder).
    """
    cutoff = timezone.now() - timedelta(minutes=15)
    cached = _recent_props(game_id, cutoff)
    if cached.exists():
        return [
            {
                "player": prop.player.nba_id,
                "player_name": f"{prop.player.first_name} {prop.player.last_name}".strip(),
                "prop_type": prop.prop_type,
                "period": prop.period,
                "line": prop.line,
                "odds_over": prop.odds_over,
                "odds_under": prop.odds_under,
                "timestamp": prop.timestamp,
            }
            for prop in cached
        ]

    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        return []

    url = f"{ODDS_API_BASE}/events/{game_id}/odds"
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "player_points,h2h",
        "oddsFormat": "american",
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    props = []
    for bookmaker_data in payload.get("bookmakers", []):
        bookmaker, _ = Bookmaker.objects.get_or_create(
            name=bookmaker_data.get("title", "Unknown"),
            defaults={"site_url": bookmaker_data.get("key", "")},
        )
        for market in bookmaker_data.get("markets", []):
            if market.get("key") != "player_points":
                continue

            outcomes = market.get("outcomes", [])
            grouped = {}
            for outcome in outcomes:
                side = (outcome.get("name") or "").lower()
                player_name = outcome.get("description") or outcome.get("name")
                if not player_name:
                    continue
                point = outcome.get("point")
                price = outcome.get("price")
                key = (player_name, point)
                grouped.setdefault(key, {})[side] = price

            for (player_name, point), sides in grouped.items():
                player = _find_player(player_name)
                if not player or point is None:
                    continue
                if "over" not in sides or "under" not in sides:
                    continue
                prop = PlayerPropLine.objects.create(
                    player=player,
                    game_id=game_id,
                    bookmaker=bookmaker,
                    prop_type="pts",
                    period=0,
                    line=float(point),
                    odds_over=int(sides["over"]),
                    odds_under=int(sides["under"]),
                    timestamp=timezone.now(),
                )
                props.append(
                    {
                        "player": player.nba_id,
                        "player_name": f"{player.first_name} {player.last_name}".strip(),
                        "prop_type": prop.prop_type,
                        "period": prop.period,
                        "line": prop.line,
                        "odds_over": prop.odds_over,
                        "odds_under": prop.odds_under,
                        "timestamp": prop.timestamp,
                    }
                )

    return props


def _find_player(player_name):
    if not player_name:
        return None
    parts = [part for part in player_name.split(" ") if part]
    if len(parts) >= 2:
        player = Player.objects.filter(
            first_name__iexact=parts[0],
            last_name__iexact=" ".join(parts[1:]),
        ).first()
        if player:
            return player
    return Player.objects.filter(first_name__icontains=player_name).first()
