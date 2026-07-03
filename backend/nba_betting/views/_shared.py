import logging

from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger(__name__)

from ..constants import (
    DEFAULT_SEASON,
    SEASON_DATES,
    SEASON_REPORT_PLAYERS,
)


# ── Sprint 5: Player Intelligence Suite ──────────────────────────────────────

def _make_cache_key(endpoint, player, stat, season):
    slug = player.lower().replace(" ", "_")
    return f"intel:{endpoint}:{slug}:{stat}:{season}"


def _intelligence_cache_get(key, fn, ttl=86400):
    """
    Try Redis; fall back to calling fn() directly if Redis is unavailable.
    Logs cache hits so response-time differences are observable in server logs.
    """
    try:
        cached = cache.get(key)
        if cached is not None:
            logger.info("cache HIT  %s", key)
            return cached
        result = fn()
        cache.set(key, result, ttl)
        logger.info("cache MISS %s (stored)", key)
        return result
    except Exception as exc:
        logger.warning("cache error (%s) — running uncached: %s", key, exc)
        return fn()


def _intelligence_preamble(request):
    """Shared validation for all intelligence endpoints. Returns (matched_name, stat, season, err_response)."""
    player_name = request.query_params.get("player_name", "").strip()
    stat        = request.query_params.get("stat", "pts").lower().strip()
    season_str  = request.query_params.get("season", str(DEFAULT_SEASON))

    if not player_name:
        return None, None, None, Response({"detail": "player_name is required."}, status=status.HTTP_400_BAD_REQUEST)
    if stat not in ("pts", "reb", "ast"):
        return None, None, None, Response({"detail": "stat must be one of: pts, reb, ast"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        season = int(season_str)
    except ValueError:
        return None, None, None, Response({"detail": "season must be an integer year."}, status=status.HTTP_400_BAD_REQUEST)
    if season not in SEASON_DATES:
        return None, None, None, Response({"detail": f"Season {season} not supported."}, status=status.HTTP_400_BAD_REQUEST)

    matched = next((p for p in SEASON_REPORT_PLAYERS if p.lower() == player_name.lower()), None)
    if not matched:
        return None, None, None, Response(
            {"detail": f"{player_name!r} not in roster. Available: {SEASON_REPORT_PLAYERS}"},
            status=status.HTTP_404_NOT_FOUND,
        )
    return matched, stat, season, None
