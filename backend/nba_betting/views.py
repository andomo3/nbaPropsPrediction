import os

import xgboost as xgb
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Player
from .services.features import get_model_inputs
from .services.probability import calculate_probability


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
        stat = data.get("stat")
        user_line = data.get("line")
        opponent = data.get("opponent")
        is_home = data.get("is_home", True)
        days_rest = data.get("days_rest", 2)

        missing = [
            field
            for field, value in (
                ("player_name", player_name),
                ("stat", stat),
                ("line", user_line),
                ("opponent", opponent),
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

        try:
            days_rest = float(days_rest)
        except (TypeError, ValueError):
            days_rest = 2

        player, feature_row_or_error = get_model_inputs(
            player_name=player_name,
            opponent=opponent,
            is_home=is_home,
            days_rest=days_rest,
        )
        if player is None:
            return Response(
                {"detail": feature_row_or_error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        model = _load_model(stat)
        if model is None:
            return Response(
                {"detail": "Model not found for requested stat."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        projection = _predict_projection(model, feature_row_or_error)
        probability_over = calculate_probability(stat, projection, line_value)
        probability_under = float(1.0 - probability_over)
        edge = "Over" if probability_over >= 0.5 else "Under"

        return Response(
            {
                "player": f"{player.first_name} {player.last_name}".strip(),
                "stat": stat,
                "line": line_value,
                "projection": float(projection),
                "probability_over": probability_over,
                "probability_under": probability_under,
                "edge": edge,
            }
        )


def _load_model(stat):
    stat_key = (stat or "").lower().strip()
    if not stat_key:
        return None

    model_dir = os.getenv("MODEL_DIR") or os.path.join("data", "models")
    candidates = [
        os.path.join(model_dir, f"{stat_key}_xgb.json"),
        os.path.join(model_dir, f"{stat_key}.json"),
    ]
    model_path = next((path for path in candidates if os.path.exists(path)), None)
    if not model_path:
        return None

    model = xgb.Booster()
    model.load_model(model_path)
    return model


def _predict_projection(model, feature_row):
    dmatrix = xgb.DMatrix(feature_row, feature_names=feature_row.columns.tolist())
    prediction = model.predict(dmatrix)
    return float(prediction[0])
