from datetime import date

from django.conf import settings
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from scipy.stats import norm

from .constants import DEFAULT_SEASON, SEASON_DATES, SEASON_REPORT_PLAYERS
from .ml.predictor import get_predictor
from .models import BacktestRun, DailyPick, Player
from .services.backtest import run_backtest
from .services.features import get_model_inputs
from .utils.dates import et_today


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

        # ── Derive probability from edge + player std dev ─────────────────────
        # P(actual > line) ≈ 1 − Φ((line − projection) / std_dev)
        std_col = f"{stat_key}_std_L10"
        if std_col in feature_row_or_error.columns:
            std_dev = float(feature_row_or_error[std_col].iloc[0])
        else:
            std_dev = {"pts": 6.0, "reb": 2.5, "ast": 2.0}.get(stat_key, 4.0)
        std_dev = max(std_dev, 0.5)  # guard against zero

        z = (line_value - projection) / std_dev
        prob_over  = float(max(0.01, min(0.99, 1 - norm.cdf(z))))
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

        min_conf = getattr(settings, "PICKS_MIN_CONFIDENCE", 0.55)
        picks_qs = (
            DailyPick.objects.filter(pick_date=pick_date, stat=stat)
            .filter(prob_over__gte=min_conf)
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
                "confidence_pct": round(p.prob_over * 100),
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


class BacktestView(APIView):
    """
    POST /api/backtest/
    Run a per-game backtest for one player + stat over a date range.
    Results are cached in BacktestRun/BacktestResult on first run.
    """

    def post(self, request):
        data = request.data or {}
        player_name = data.get("player_name", "").strip()
        stat = data.get("stat", "").lower().strip()
        date_from_str = data.get("date_from", "")
        date_to_str = data.get("date_to", "")

        missing = [
            f for f, v in [
                ("player_name", player_name),
                ("stat", stat),
                ("date_from", date_from_str),
                ("date_to", date_to_str),
            ] if not v
        ]
        if missing:
            return Response(
                {"detail": f"Missing fields: {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if stat not in ("pts", "reb", "ast"):
            return Response(
                {"detail": "stat must be one of: pts, reb, ast"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            date_from = date.fromisoformat(date_from_str)
            date_to = date.fromisoformat(date_to_str)
        except ValueError:
            return Response(
                {"detail": "Dates must be in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if date_from >= date_to:
            return Response(
                {"detail": "date_from must be before date_to."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = run_backtest(player_name, stat, date_from, date_to)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response(
                {"detail": f"Backtest failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result)


class SeasonSummaryView(APIView):
    """
    GET /api/backtest/season-summary/?player_name=Nikola+Jokic&stat=pts&season=2024

    Returns pre-seeded Season Report Card data for one player + stat.
    Data must exist in the DB (run seed_season_backtest first).

    Query params:
        player_name  (required) — must be one of the 10 seed players
        stat         (required) — pts | reb | ast
        season       (optional) — NBA season end-year, default 2024

    Response shape:
        {
            "player_name": "Nikola Jokic",
            "stat": "pts",
            "season": "2023-24",
            "date_from": "2023-10-24",
            "date_to": "2024-06-17",
            "summary": {
                "total_games": 74,
                "mae": 4.21,        // mean absolute error
                "bias": -0.34,      // mean signed error (+ = under-projected)
                "hit_rate": 0.568,  // fraction of games where over/under was correct
                "total_pnl": 2.40,
                "roi": 2.9          // % return on investment at -110 odds
            },
            "per_game": [
                {
                    "date": "2023-10-25",
                    "opponent": "PHX",
                    "actual": 34.0,
                    "line": 27.2,
                    "projection": 29.1,
                    "error": 4.9,
                    "correct": true,
                    "pnl": 1.0,
                    "cumulative_pnl": 1.0
                },
                ...
            ]
        }
    """

    def get(self, request):
        player_name = request.query_params.get("player_name", "").strip()
        stat = request.query_params.get("stat", "").lower().strip()
        season_str = request.query_params.get("season", str(DEFAULT_SEASON))

        # ── Validate inputs ───────────────────────────────────────────────────
        if not player_name:
            return Response(
                {"detail": "player_name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if stat not in ("pts", "reb", "ast"):
            return Response(
                {"detail": "stat must be one of: pts, reb, ast"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            season_year = int(season_str)
        except ValueError:
            return Response(
                {"detail": "season must be an integer year (e.g. 2024)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if season_year not in SEASON_DATES:
            return Response(
                {
                    "detail": (
                        f"Season {season_year} is not supported. "
                        f"Available: {sorted(SEASON_DATES.keys())}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate player is one of the seed list (case-insensitive match)
        matched_name = next(
            (p for p in SEASON_REPORT_PLAYERS if p.lower() == player_name.lower()),
            None,
        )
        if not matched_name:
            return Response(
                {
                    "detail": (
                        f"{player_name!r} is not in the Season Report Card roster. "
                        f"Available players: {SEASON_REPORT_PLAYERS}"
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        date_from, date_to = SEASON_DATES[season_year]
        season_label = f"{season_year - 1}-{season_year % 100:02d}"

        # ── Fetch cached run ──────────────────────────────────────────────────
        run = (
            BacktestRun.objects.filter(
                player_name=matched_name,
                stat=stat,
                date_from=date_from,
                date_to=date_to,
                total_bets__gt=0,
            )
            .prefetch_related("results")
            .first()
        )

        if run is None:
            return Response(
                {
                    "detail": (
                        f"No seeded data found for {matched_name} / {stat} / {season_label}. "
                        "Run: python manage.py seed_season_backtest"
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Build per-game array + compute derived stats ──────────────────────
        results = list(run.results.all())   # already ordered by game_date

        per_game = []
        cumulative_pnl = 0.0
        error_sum = 0.0
        abs_error_sum = 0.0

        for r in results:
            cumulative_pnl = round(cumulative_pnl + r.pnl, 2)
            error_sum += r.error
            abs_error_sum += abs(r.error)
            per_game.append({
                "date":           str(r.game_date),
                "opponent":       r.opponent,
                "actual":         r.actual,
                "line":           r.line,
                "projection":     r.prob_over,   # stored in prob_over for backward compat
                "error":          round(r.error, 2),
                "correct":        r.correct,
                "pnl":            r.pnl,
                "cumulative_pnl": cumulative_pnl,
            })

        n = len(results)
        mae  = round(abs_error_sum / n, 3) if n else 0.0
        bias = round(error_sum / n, 3) if n else 0.0

        return Response({
            "player_name": matched_name,
            "stat":        stat,
            "season":      season_label,
            "date_from":   str(date_from),
            "date_to":     str(date_to),
            "summary": {
                "total_games": run.total_bets,
                "mae":         mae,
                "bias":        bias,
                "hit_rate":    round(run.accuracy, 4),
                "total_pnl":   round(run.total_pnl, 2),
                "roi":         round(run.roi, 2),
            },
            "per_game": per_game,
        })


