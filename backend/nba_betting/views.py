import os

import numpy as np
import pandas as pd
import xgboost as xgb
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Player, PlayerStats
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


class ManualPredictionView(APIView):
    def post(self, request):
        data = request.data or {}
        player_name = data.get("player_name")
        stat = data.get("stat")
        user_line = data.get("line")

        missing = [
            field
            for field, value in (
                ("player_name", player_name),
                ("stat", stat),
                ("line", user_line),
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

        feature_row = _build_latest_features(player)
        if feature_row is None:
            return Response(
                {"detail": "Not enough data to build features."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        model = _load_model(stat)
        if model is None:
            return Response(
                {"detail": "Model not found for requested stat."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        projection = _predict_projection(model, feature_row)
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


def _build_latest_features(player):
    stats_qs = (
        PlayerStats.objects.filter(player=player, period=0)
        .select_related("game", "team", "game__home_team", "game__away_team")
        .order_by("game__date")
    )
    if not stats_qs.exists():
        return None

    rows = []
    for row in stats_qs:
        game = row.game
        fg_pct = (row.fgm / row.fga) if row.fga else 0.0
        rows.append(
            {
                "date": game.date,
                "game_id": game.game_id,
                "player_name": f"{player.first_name} {player.last_name}".strip(),
                "player_team": row.team.abbreviation if row.team else None,
                "home_team": game.home_team.abbreviation if game.home_team else None,
                "away_team": game.away_team.abbreviation if game.away_team else None,
                "pts": row.pts,
                "reb": row.reb,
                "ast": row.ast,
                "min": row.min,
                "fg_pct": fg_pct,
            }
        )

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["player_name", "date"]).reset_index(drop=True)

    df["is_home"] = (df["player_team"] == df["home_team"]).astype(int)
    df["opponent"] = np.where(df["is_home"] == 1, df["away_team"], df["home_team"])
    df["days_rest"] = df.groupby("player_name")["date"].diff().dt.days
    df["days_rest"] = df["days_rest"].fillna(3)

    calc_df = df.copy()
    mask = calc_df["min"] < 10
    calc_df.loc[mask, ["pts", "reb", "ast", "min", "fg_pct"]] = np.nan

    stats = ["pts", "reb", "ast", "min", "fg_pct"]
    windows = [5, 10]
    for stat in stats:
        for window in windows:
            df[f"{stat}_L{window}"] = calc_df.groupby("player_name")[stat].transform(
                lambda x: x.shift(1).rolling(window=window, min_periods=1).mean()
            )

    for stat in ["pts", "reb", "ast"]:
        df[f"{stat}_ema_L5"] = calc_df.groupby("player_name")[stat].transform(
            lambda x: x.shift(1).ewm(span=5, adjust=False).mean()
        )

    df["pts_std_L10"] = calc_df.groupby("player_name")["pts"].transform(
        lambda x: x.shift(1).rolling(window=10, min_periods=5).std()
    )

    defense = (
        df.groupby(["game_id", "date", "opponent"])["pts"]
        .sum()
        .reset_index()
        .rename(columns={"pts": "total_pts_allowed"})
        .sort_values(["opponent", "date"])
    )
    defense["opp_pts_allowed_L10"] = defense.groupby("opponent")[
        "total_pts_allowed"
    ].transform(lambda x: x.shift(1).rolling(window=10, min_periods=1).mean())

    df = df.merge(
        defense[["game_id", "opponent", "opp_pts_allowed_L10"]],
        on=["game_id", "opponent"],
        how="left",
    )

    df = df[df["min"] > 0]
    df = df.dropna()
    if df.empty:
        return None

    latest = df.iloc[-1]
    feature_columns = [
        "is_home",
        "days_rest",
        "opp_pts_allowed_L10",
        "pts_L5",
        "pts_L10",
        "pts_ema_L5",
        "pts_std_L10",
        "reb_L5",
        "reb_L10",
        "reb_ema_L5",
        "ast_L5",
        "ast_L10",
        "ast_ema_L5",
        "min_L5",
        "min_L10",
        "fg_pct_L5",
        "fg_pct_L10",
    ]
    feature_row = latest[feature_columns].astype(float).to_frame().T
    return feature_row


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
