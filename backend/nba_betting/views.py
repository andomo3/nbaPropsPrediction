from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from scipy.stats import norm

from .ml.predictor import get_predictor
from .models import Player
from .services.features import get_model_inputs


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

        # Get classification probability (P of beating rolling average)
        # Change xgb to catboost for the model type if needed
        predictor = get_predictor()
        base_prob = predictor.predict_probability(feature_row_or_error, stat, "xgb")
        
        if base_prob is None:
            return Response(
                {"detail": "Model not found for requested stat."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        # Get the player's rolling average for this stat (the baseline)
        stat_key = stat.lower().strip()
        rolling_avg_col = f"{stat_key}_L5"
        if rolling_avg_col in feature_row_or_error.columns:
            rolling_avg = float(feature_row_or_error[rolling_avg_col].iloc[0])
        else:
            rolling_avg = line_value  # Fallback

        # Get standard deviation for adjustment
        std_col = f"{stat_key}_std_L10" if stat_key == "pts" else None
        if std_col and std_col in feature_row_or_error.columns:
            std_dev = float(feature_row_or_error[std_col].iloc[0])
        else:
            # Default std dev estimates based on stat type
            std_dev = {"pts": 8.0, "reb": 3.0, "ast": 2.5}.get(stat_key, 5.0)

        # Adjust probability based on line difference from rolling average
        # If user_line > rolling_avg, probability of over decreases
        # If user_line < rolling_avg, probability of over increases
        probability_over = _adjust_probability_for_line(
            base_prob, rolling_avg, line_value, std_dev
        )
        probability_under = float(1.0 - probability_over)
        edge = "Over" if probability_over >= 0.5 else "Under"

        # Use rolling average as the projection (expected value)
        projection = rolling_avg

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


def _adjust_probability_for_line(base_prob, rolling_avg, user_line, std_dev):
    """
    Adjust the base probability based on the difference between
    the user's line and the player's rolling average.

    The model predicts P(actual > rolling_avg). We need P(actual > user_line).

    Uses a normal distribution adjustment:
    - If user_line == rolling_avg, return base_prob
    - If user_line > rolling_avg, return lower probability
    - If user_line < rolling_avg, return higher probability

    Args:
        base_prob: Model's P(over rolling_avg)
        rolling_avg: Player's rolling average (the model's baseline)
        user_line: The user's betting line
        std_dev: Estimated standard deviation of the stat

    Returns:
        Adjusted probability of going over the user's line
    """
    if std_dev <= 0:
        std_dev = 1.0

    # Calculate the line difference in standard deviations
    line_diff = user_line - rolling_avg
    z_adjustment = line_diff / std_dev

    # Convert base probability to z-score, adjust, and convert back
    # base_prob = P(X > rolling_avg) = 1 - Phi(0) if centered
    # We need P(X > user_line) = 1 - Phi(z_adjustment)

    # Use the base probability to infer the player's "form factor"
    # Then adjust for the line difference
    if base_prob >= 0.9999:
        base_z = 3.5
    elif base_prob <= 0.0001:
        base_z = -3.5
    else:
        # base_prob = P(X > avg) = P(Z > 0 + form_factor)
        # So form_factor = inverse_norm(base_prob) for the "over" side
        base_z = norm.ppf(base_prob)

    # Adjusted z-score accounts for line being different from average
    adjusted_z = base_z - z_adjustment

    # Convert back to probability
    adjusted_prob = float(norm.cdf(adjusted_z))

    # Clamp to valid probability range
    return max(0.01, min(0.99, adjusted_prob))
