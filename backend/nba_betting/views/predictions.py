from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..constants import STD_DEFAULTS
from ..ml.predictor import get_predictor
from ..models import Player
from ..services.features import get_model_inputs
from ..services.probability import calculate_probability


class PlayerListView(APIView):
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        queryset = Player.objects.all()
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query) | Q(last_name__icontains=query)
            )

        players = queryset.order_by("last_name", "first_name")[:25]
        payload = [
            {
                "id": player.nba_id,
                "first_name": player.first_name,
                "last_name": player.last_name,
                "full_name": f"{player.first_name} {player.last_name}",
                "team": player.current_team.abbreviation if player.current_team else None,
            }
            for player in players
        ]
        return Response(payload)


class MetadataView(APIView):
    def get(self, request):
        players = (
            Player.objects.order_by("last_name", "first_name")
            .values_list("first_name", "last_name")
        )
        player_names = [
            f"{first} {last}".strip()
            for first, last in players
            if first or last
        ]

        teams = (
            Player.objects.filter(current_team__isnull=False)
            .values_list("current_team__abbreviation", flat=True)
            .distinct()
            .order_by("current_team__abbreviation")
        )

        return Response({"players": player_names, "teams": list(teams)})


class ManualPredictionView(APIView):
    def post(self, request):
        data = request.data or {}
        player_name = data.get("player_name")
        stat = data.get("stat") or "pts"
        user_line = data.get("line")
        opponent = data.get("opponent_ticker") or data.get("opponent")
        is_home = data.get("is_home", True)

        missing = [
            field
            for field, value in (
                ("player_name", player_name),
                ("line", user_line),
                ("opponent_ticker", opponent),
            )
            if value in (None, "")
        ]
        if missing:
            return Response(
                {"detail": f"Missing fields: {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            line_value = float(user_line)
        except (TypeError, ValueError):
            return Response(
                {"detail": "line must be a number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if isinstance(is_home, str):
            is_home = is_home.lower() in {"true", "1", "yes", "y"}

        stat_key = stat.lower().strip()

        player, feature_row_or_error = get_model_inputs(
            player_name=player_name,
            opponent=opponent,
            stat=stat_key,
            is_home=is_home,
        )
        if player is None:
            return Response(
                {"detail": feature_row_or_error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Regression projection ─────────────────────────────────────────────
        predictor = get_predictor()
        projection = predictor.predict_projection(feature_row_or_error, stat_key, "xgb")

        if projection is None:
            return Response(
                {"detail": "Model not found for requested stat."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        projection = round(float(projection), 1)
        edge_value = round(projection - line_value, 2)
        recommendation = "OVER" if edge_value > 0 else "UNDER"

        # ── Derive probability (services/probability.py: Poisson for
        #    low-count stats, Normal otherwise; clamped) ─────────────────────
        std_col = f"{stat_key}_std_L10"
        if std_col in feature_row_or_error.columns:
            std_dev = float(feature_row_or_error[std_col].iloc[0])
        else:
            std_dev = STD_DEFAULTS.get(stat_key, 4.0)

        prob_over  = calculate_probability(stat_key, projection, line_value, std_dev)
        prob_under = round(1.0 - prob_over, 4)
        prob_over  = round(prob_over, 4)

        return Response(
            {
                "player":         f"{player.first_name} {player.last_name}".strip(),
                "stat":           stat_key,
                "line":           line_value,
                "projection":     projection,
                "edge":           edge_value,
                "recommendation": recommendation,
                "prob_over":      prob_over,
                "prob_under":     prob_under,
            }
        )
