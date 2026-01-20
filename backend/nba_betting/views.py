from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .ml.predictor import predict_scenario
from .models import Player


class PlayerListView(APIView):
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        queryset = Player.objects.all()
        if query:
            queryset = queryset.filter(name__icontains=query)

        players = queryset.order_by("name")[:25]
        payload = [
            {
                "id": player.id,
                "name": player.name,
                "team": player.team,
                "nba_id": player.nba_id,
            }
            for player in players
        ]
        return Response(payload)


class ManualPredictionView(APIView):
    def post(self, request):
        data = request.data or {}
        player_name = data.get("player")
        prop_type = data.get("prop")
        user_line = data.get("line")
        period = data.get("period")

        missing = [
            field
            for field, value in (
                ("player", player_name),
                ("prop", prop_type),
                ("line", user_line),
                ("period", period),
            )
            if value in (None, "")
        ]
        if missing:
            return Response(
                {"detail": f"Missing fields: {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            period_int = int(period)
        except (TypeError, ValueError):
            return Response(
                {"detail": "period must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            line_value = float(user_line)
        except (TypeError, ValueError):
            return Response(
                {"detail": "line must be a number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        player = Player.objects.filter(name__iexact=player_name).first()
        if not player:
            return Response(
                {"detail": "Player not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = predict_scenario(player.id, prop_type, period_int, line_value)
        except NotImplementedError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        return Response(result)
