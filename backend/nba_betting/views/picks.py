from datetime import date

from django.conf import settings
from django.db.models import F, FloatField, Value
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Greatest
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import DailyPick
from ..utils.dates import et_today


class LitePicksView(APIView):
    """
    GET /api/picks/?date=YYYY-MM-DD&stat=pts
    Returns pre-generated daily picks for the LITE player list.
    Picks are generated each morning by generate_daily_picks management command.
    """

    def get(self, request):
        date_str = request.query_params.get("date")
        stat = request.query_params.get("stat", "pts").lower().strip()

        try:
            pick_date = date.fromisoformat(date_str) if date_str else et_today()
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if stat not in ("pts", "reb", "ast"):
            return Response(
                {"detail": "stat must be one of: pts, reb, ast"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Confidence is the probability of the RECOMMENDED side — filtering on
        # prob_over alone would silently discard every Under pick.
        min_conf = getattr(settings, "PICKS_MIN_CONFIDENCE", 0.55)
        picks_qs = (
            DailyPick.objects.filter(pick_date=pick_date, stat=stat)
            .annotate(
                confidence=Greatest(
                    F("prob_over"),
                    ExpressionWrapper(
                        Value(1.0) - F("prob_over"), output_field=FloatField()
                    ),
                )
            )
            .filter(confidence__gte=min_conf)
            .select_related("player", "player__current_team")
        )

        picks = []
        for p in picks_qs:
            player_name = f"{p.player.first_name} {p.player.last_name}".strip()
            team_abbr = p.player.current_team.abbreviation if p.player.current_team else ""
            picks.append({
                "player_name": player_name,
                "team": team_abbr,
                "opponent": p.opponent_abbr,
                "is_home": p.is_home,
                "stat": p.stat,
                "line": p.line,
                "prob_over": round(p.prob_over, 4),
                "prob_under": round(1.0 - p.prob_over, 4),
                "projection": p.projection,
                "edge": p.edge,
                "confidence_pct": round(max(p.prob_over, 1.0 - p.prob_over) * 100),
            })

        generated_at = (
            picks_qs.first().generated_at.isoformat() if picks_qs.exists() else None
        )

        return Response({
            "date": str(pick_date),
            "stat": stat,
            "picks": picks,
            "count": len(picks),
            "generated_at": generated_at,
        })
