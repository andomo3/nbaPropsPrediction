from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q

from .ml.predictor import predict_scenario
from .models import Player


class PlayerListView(APIView):
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        queryset = Player.objects.all()
        if query:
            queryset = queryset.filter(name__icontains=query)

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

        player = None
        if player_name:
            parts = [part for part in player_name.split(" ") if part]
            if len(parts) >= 2:
                player = Player.objects.filter(
                    first_name__iexact=parts[0],
                    last_name__iexact=" ".join(parts[1:]),
                ).first()
            if not player:
                player = Player.objects.filter(
                    Q(first_name__icontains=player_name)
                    | Q(last_name__icontains=player_name)
                ).first()
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
