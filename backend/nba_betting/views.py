from datetime import date

from django.conf import settings
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from scipy.stats import norm

from .constants import BACKTEST_MODELS, DEFAULT_SEASON, MODEL_LABELS, SEASON_DATES, SEASON_REPORT_PLAYERS
from .ml.predictor import get_predictor
from .models import BacktestRun, DailyPick, Player
from .services.backtest import run_backtest
from .services.features import get_model_inputs
from .services.simulator import run_simulation
from .services.shap_analysis import compute_shap_analysis
from .services.variance_decomp import compute_variance_decomposition
from .services.edge_calibration import compute_edge_calibration
from .services.floor_ceiling import compute_floor_ceiling
from .services.opponent_analysis import compute_opponent_analysis
from .services.player_fingerprint import compute_player_fingerprint
from .utils.stats import pred_score_tier
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


class ModelComparisonView(APIView):
    """
    GET /api/backtest/model-comparison/?player_name=...&stat=pts&season=2026

    Returns aggregate stats + per-game projections for all 4 models in one
    request, so the frontend can render the comparison table and overlay chart
    without multiple round trips.

    Response shape:
        {
            "player_name": "...",
            "stat": "pts",
            "season": "2025-26",
            "dates":   ["2026-02-06", ...],   // game dates (shared across models)
            "actuals": [34.0, 28.0, ...],     // actual values (shared)
            "models": [
                {
                    "model":    "xgb",
                    "label":    "XGBoost",
                    "available": true,
                    "summary":  {total_games, mae, bias, hit_rate, total_pnl, roi},
                    "projections": [29.1, 27.4, ...]   // parallel to dates/actuals
                },
                ...
            ]
        }
    """

    def get(self, request):
        player_name = request.query_params.get("player_name", "").strip()
        stat = request.query_params.get("stat", "").lower().strip()
        season_str = request.query_params.get("season", str(DEFAULT_SEASON))

        if not player_name:
            return Response({"detail": "player_name is required."}, status=status.HTTP_400_BAD_REQUEST)
        if stat not in ("pts", "reb", "ast"):
            return Response({"detail": "stat must be one of: pts, reb, ast"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            season_year = int(season_str)
        except ValueError:
            return Response({"detail": "season must be an integer year."}, status=status.HTTP_400_BAD_REQUEST)

        if season_year not in SEASON_DATES:
            return Response(
                {"detail": f"Season {season_year} not supported. Available: {sorted(SEASON_DATES.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        matched_name = next(
            (p for p in SEASON_REPORT_PLAYERS if p.lower() == player_name.lower()), None
        )
        if not matched_name:
            return Response(
                {"detail": f"{player_name!r} is not in the Season Report Card roster."},
                status=status.HTTP_404_NOT_FOUND,
            )

        date_from, date_to = SEASON_DATES[season_year]
        season_label = f"{season_year - 1}-{season_year % 100:02d}"

        # ── Fetch all 4 model runs in one query ───────────────────────────────
        runs = {
            run.model: run
            for run in BacktestRun.objects.filter(
                player_name=matched_name,
                stat=stat,
                date_from=date_from,
                date_to=date_to,
                total_bets__gt=0,
            ).prefetch_related("results")
        }

        # Use the xgb run to establish the canonical date/actual sequence
        anchor = runs.get("xgb") or next(iter(runs.values()), None)
        if anchor is None:
            return Response(
                {"detail": f"No seeded data found for {matched_name} / {stat} / {season_label}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        anchor_results = list(anchor.results.all())
        dates   = [str(r.game_date) for r in anchor_results]
        actuals = [r.actual for r in anchor_results]

        # ── Build per-model payload ───────────────────────────────────────────
        model_rows = []
        for model_key in BACKTEST_MODELS:
            run = runs.get(model_key)
            if run is None:
                model_rows.append({
                    "model":       model_key,
                    "label":       MODEL_LABELS.get(model_key, model_key),
                    "available":   False,
                    "summary":     None,
                    "projections": [],
                })
                continue

            results = list(run.results.all())
            abs_err = sum(abs(r.error) for r in results)
            err_sum = sum(r.error for r in results)
            n = len(results)

            model_rows.append({
                "model":       model_key,
                "label":       MODEL_LABELS.get(model_key, model_key),
                "available":   True,
                "summary": {
                    "total_games": run.total_bets,
                    "mae":         round(abs_err / n, 3) if n else 0.0,
                    "bias":        round(err_sum / n, 3) if n else 0.0,
                    "hit_rate":    round(run.accuracy, 4),
                    "total_pnl":   round(run.total_pnl, 2),
                    "roi":         round(run.roi, 2),
                },
                "projections": [round(r.prob_over, 1) for r in results],
            })

        return Response({
            "player_name": matched_name,
            "stat":        stat,
            "season":      season_label,
            "dates":       dates,
            "actuals":     actuals,
            "models":      model_rows,
        })


class LeaderboardView(APIView):
    """
    GET /api/backtest/leaderboard/?stat=pts&model=xgb&season=2026

    Returns all 10 seed players ranked by MAE ascending (most predictable first).
    Reads from already-seeded BacktestRun rows — no computation on request.

    Query params:
        stat    (required) — pts | reb | ast
        model   (optional) — xgb | rf | lr | naive  (default: xgb)
        season  (optional) — NBA season end-year     (default: 2026)

    Response:
        {
            "stat": "pts",
            "model": "xgb",
            "model_label": "XGBoost",
            "season": "2025-26",
            "rankings": [
                {
                    "rank": 1,
                    "player_name": "Nikola Jokic",
                    "total_games": 45,
                    "mae":      3.21,
                    "bias":    -0.14,
                    "hit_rate": 0.601,
                    "total_pnl": 4.20,
                    "roi":      5.1
                },
                ...
            ]
        }
    """

    def get(self, request):
        stat       = request.query_params.get("stat",   "pts").lower().strip()
        model      = request.query_params.get("model",  "xgb").lower().strip()
        season_str = request.query_params.get("season", str(DEFAULT_SEASON))

        if stat not in ("pts", "reb", "ast"):
            return Response(
                {"detail": "stat must be one of: pts, reb, ast"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if model not in BACKTEST_MODELS:
            return Response(
                {"detail": f"model must be one of: {BACKTEST_MODELS}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            season_year = int(season_str)
        except ValueError:
            return Response(
                {"detail": "season must be an integer year."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if season_year not in SEASON_DATES:
            return Response(
                {"detail": f"Season {season_year} not supported. Available: {sorted(SEASON_DATES.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        date_from, date_to = SEASON_DATES[season_year]
        season_label = f"{season_year - 1}-{season_year % 100:02d}"

        # ── Fetch all seeded runs for this stat/model/season in one query ─────
        runs = {
            run.player_name: run
            for run in BacktestRun.objects.filter(
                stat=stat,
                model=model,
                date_from=date_from,
                date_to=date_to,
                total_bets__gt=0,
                player_name__in=SEASON_REPORT_PLAYERS,
            ).prefetch_related("results")
        }

        rankings = []
        for player_name in SEASON_REPORT_PLAYERS:
            run = runs.get(player_name)
            if run is None:
                continue

            results  = list(run.results.all())
            n        = len(results)
            abs_err  = sum(abs(r.error) for r in results)
            err_sum  = sum(r.error for r in results)

            # ── Predictability score ──────────────────────────────────────────
            actuals    = [r.actual for r in results]
            errors     = [r.error  for r in results]
            pred_score, pred_tier = pred_score_tier(actuals, errors, run.accuracy)

            rankings.append({
                "player_name":        player_name,
                "total_games":        run.total_bets,
                "mae":                round(abs_err / n, 3) if n else 0.0,
                "bias":               round(err_sum / n, 3) if n else 0.0,
                "hit_rate":           round(hit_rate, 4),
                "total_pnl":          round(run.total_pnl, 2),
                "roi":                round(run.roi, 2),
                "predictability_score": pred_score,
                "predictability_tier":  pred_tier,
            })

        # Sort by MAE ascending — lowest error = most predictable = rank 1
        rankings.sort(key=lambda r: r["mae"])
        for i, row in enumerate(rankings):
            row["rank"] = i + 1

        return Response({
            "stat":        stat,
            "model":       model,
            "model_label": MODEL_LABELS.get(model, model),
            "season":      season_label,
            "rankings":    rankings,
        })


class SimulatorView(APIView):
    """
    GET /api/simulator/?player_name=Luka+Doncic&stat=pts&n_future=20

    Fits AR(1) to the player's 2025-26 game log and runs Monte Carlo
    simulation to project the next n_future games.

    Response:
        {
            "player_name": "Luka Doncic",
            "stat": "pts",
            "season": "2025-26",
            "season_avg": 28.4,
            "games_played": 47,
            "n_future": 20,
            "ar1_phi": 0.23,
            "ar1_sigma": 6.1,
            "actual": [
                {"game_num": 1, "date": "2025-10-22", "value": 31, "opponent": "OKC"},
                ...
            ],
            "projections": [
                {"game_num": 48, "p10": 16, "p25": 22, "p50": 28, "p75": 34, "p90": 40},
                ...
            ],
            "prop_table": [
                {"line": 20.5, "prob_over": 0.82},
                ...
            ]
        }
    """

    def get(self, request):
        player_name = request.query_params.get("player_name", "").strip()
        stat        = request.query_params.get("stat", "pts").lower().strip()
        n_future_str = request.query_params.get("n_future", "20")

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
            n_future = max(1, min(int(n_future_str), 82))
        except ValueError:
            n_future = 20

        matched_name = next(
            (p for p in SEASON_REPORT_PLAYERS if p.lower() == player_name.lower()),
            None,
        )
        if not matched_name:
            return Response(
                {"detail": (
                    f"{player_name!r} is not in the Season Report roster. "
                    f"Available: {SEASON_REPORT_PLAYERS}"
                )},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = run_simulation(matched_name, stat, n_future=n_future)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response(
                {"detail": f"Simulation failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result)


class ShapAnalysisView(APIView):
    """
    GET /api/analysis/shap/?player_name=LeBron+James&stat=pts

    Computes SHAP feature attributions for the XGBoost model on the player's
    2025-26 game log. Expensive on first call (~1-2s); no DB caching.

    Response:
        {
            "player_name": "LeBron James",
            "stat": "pts",
            "n_games": 68,
            "expected_value": 24.3,
            "feature_importance": [
                {
                    "feature": "pts_L5",
                    "label": "Pts avg (L5)",
                    "mean_abs_shap": 3.21,
                    "mean_shap": 2.84,
                    "direction": "positive",
                    "pct_contribution": 28.4
                },
                ...
            ],
            "per_game": [
                {
                    "game_num": 1,
                    "date": "2026-02-06",
                    "opponent": "GSW",
                    "actual": 31.0,
                    "projection": 27.4,
                    "top_driver": {"feature": "pts_L5", "label": "Pts avg (L5)", "shap_value": 4.1},
                    "shap_values": {"pts_L5": 4.1, "opp_pts_allowed_L10": -1.2, ...}
                },
                ...
            ],
            "group_importance": {
                "form": 42.1,
                "opponent": 12.3,
                "minutes": 8.4,
                "shooting": 11.2,
                "season_avg": 18.6,
                "context": 7.4
            },
            "insight": "LeBron's projected points output is most sensitive to..."
        }
    """

    def get(self, request):
        player_name = request.query_params.get("player_name", "").strip()
        stat        = request.query_params.get("stat", "pts").lower().strip()

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

        matched_name = next(
            (p for p in SEASON_REPORT_PLAYERS if p.lower() == player_name.lower()),
            None,
        )
        if not matched_name:
            return Response(
                {"detail": (
                    f"{player_name!r} is not in the Season Report roster. "
                    f"Available: {SEASON_REPORT_PLAYERS}"
                )},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = compute_shap_analysis(matched_name, stat)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response(
                {"detail": f"SHAP analysis failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result)


class VarianceDecompView(APIView):
    """
    GET /api/analysis/variance/?player_name=LeBron+James&stat=pts&season=2026

    Research-grade variance decomposition for player stat predictability.
    Reads from cached BacktestResult rows — no recomputation.

    Response:
        {
            "player_name": "LeBron James",
            "stat": "pts",
            "season": "2025-26",
            "n_games": 68,
            "distributional": {
                "mean": 24.3, "std": 6.1, "cv": 0.251, "mad": 4.5,
                "skewness": 0.21, "excess_kurtosis": -0.4,
                "normality_test": "dagostino-pearson", "normality_p": 0.14,
                "errors_normal": true
            },
            "variance_components": {
                "model_r2": 0.312,
                "opponent_eta2": 0.118,
                "opponent_delta": 0.054,
                "residual": 0.634
            },
            "icc": 0.082,
            "model_comparison": [
                {"model": "xgb", "label": "XGBoost", "available": true,
                 "mae": 4.21, "r2": 0.312, "bias": -0.34, "hit_rate": 0.632, "roi": 21.5},
                ...
            ],
            "predictability_score": 58.4,
            "predictability_tier": "Moderate",
            "insight": "LeBron's points output is Moderate predictability..."
        }
    """

    def get(self, request):
        player_name = request.query_params.get("player_name", "").strip()
        stat        = request.query_params.get("stat", "pts").lower().strip()
        season_str  = request.query_params.get("season", str(DEFAULT_SEASON))

        if not player_name:
            return Response({"detail": "player_name is required."}, status=status.HTTP_400_BAD_REQUEST)
        if stat not in ("pts", "reb", "ast"):
            return Response({"detail": "stat must be one of: pts, reb, ast"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            season = int(season_str)
        except ValueError:
            return Response({"detail": "season must be an integer year."}, status=status.HTTP_400_BAD_REQUEST)

        matched_name = next(
            (p for p in SEASON_REPORT_PLAYERS if p.lower() == player_name.lower()), None
        )
        if not matched_name:
            return Response(
                {"detail": f"{player_name!r} is not in the Season Report roster."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = compute_variance_decomposition(matched_name, stat, season)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response(
                {"detail": f"Variance decomposition failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result)


class LeaderboardComparisonView(APIView):
    """
    GET /api/backtest/leaderboard-comparison/?stat=pts&model=xgb

    Returns all players with predictability scores for both seasons side-by-side.
    """

    def get(self, request):
        stat    = request.query_params.get("stat",  "pts").lower().strip()
        model   = request.query_params.get("model", "xgb").lower().strip()
        seasons = [2025, 2026]

        if stat not in ("pts", "reb", "ast"):
            return Response({"detail": "stat must be one of: pts, reb, ast"},
                            status=status.HTTP_400_BAD_REQUEST)
        if model not in BACKTEST_MODELS:
            return Response({"detail": f"model must be one of: {BACKTEST_MODELS}"},
                            status=status.HTTP_400_BAD_REQUEST)

        all_runs = (
            BacktestRun.objects
            .filter(
                stat=stat,
                model=model,
                player_name__in=SEASON_REPORT_PLAYERS,
                total_bets__gt=0,
            )
            .prefetch_related("results")
        )

        run_index = {}
        for run in all_runs:
            for yr in seasons:
                date_from, date_to = SEASON_DATES[yr]
                if run.date_from == date_from and run.date_to == date_to:
                    run_index[(run.player_name, yr)] = run

        players = []
        for player_name in SEASON_REPORT_PLAYERS:
            season_data = {}
            scores = {}
            tiers  = {}

            for yr in seasons:
                run = run_index.get((player_name, yr))
                if run is None:
                    season_data[str(yr)] = {"available": False}
                    continue

                results  = list(run.results.all())
                n        = len(results)
                actuals  = [r.actual for r in results]
                errors   = [r.error  for r in results]
                abs_err  = sum(abs(e) for e in errors)
                err_sum  = sum(errors)

                score, tier   = pred_score_tier(actuals, errors, run.accuracy)
                scores[yr]    = score
                tiers[yr]     = tier

                season_data[str(yr)] = {
                    "available":            True,
                    "total_games":          run.total_bets,
                    "mae":                  round(abs_err / n, 3) if n else 0.0,
                    "bias":                 round(err_sum / n, 3) if n else 0.0,
                    "hit_rate":             round(run.accuracy, 4),
                    "roi":                  round(run.roi, 2),
                    "predictability_score": score,
                    "predictability_tier":  tier,
                }

            both        = all(scores.get(yr) is not None for yr in seasons)
            delta       = round(scores[2026] - scores[2025], 1) if both else None
            tier_changed = (tiers.get(2025) != tiers.get(2026)) if both else False

            players.append({
                "player_name":  player_name,
                "seasons":      season_data,
                "score_delta":  delta,
                "tier_changed": tier_changed,
            })

        players.sort(key=lambda p: (
            -(p["seasons"].get("2026", {}).get("predictability_score") or -999)
        ))

        return Response({
            "stat":    stat,
            "model":   model,
            "seasons": ["2024-25", "2025-26"],
            "players": players,
        })


class TierHistoryView(APIView):
    """
    GET /api/analysis/tier-history/?player_name=LeBron+James&stat=pts&season=2026&window=20

    Splits the season into rolling windows (50% overlap) and returns predictability
    score + tier per window, plus detected tier-change events.
    """

    def get(self, request):
        player_name = request.query_params.get("player_name", "").strip()
        stat        = request.query_params.get("stat", "pts").lower().strip()
        season_str  = request.query_params.get("season", str(DEFAULT_SEASON))
        window_str  = request.query_params.get("window", "20")

        if not player_name:
            return Response({"detail": "player_name is required."}, status=status.HTTP_400_BAD_REQUEST)
        if stat not in ("pts", "reb", "ast"):
            return Response({"detail": "stat must be one of: pts, reb, ast"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            season_year = int(season_str)
        except ValueError:
            return Response({"detail": "season must be an integer year."}, status=status.HTTP_400_BAD_REQUEST)
        if season_year not in SEASON_DATES:
            return Response({"detail": f"Season {season_year} not supported."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            window = max(10, min(int(window_str), 40))
        except ValueError:
            window = 20

        matched_name = next(
            (p for p in SEASON_REPORT_PLAYERS if p.lower() == player_name.lower()), None
        )
        if not matched_name:
            return Response(
                {"detail": f"{player_name!r} is not in the Season Report roster."},
                status=status.HTTP_404_NOT_FOUND,
            )

        date_from, date_to = SEASON_DATES[season_year]
        season_label = f"{season_year - 1}-{season_year % 100:02d}"

        run = (
            BacktestRun.objects
            .filter(
                player_name=matched_name,
                stat=stat,
                model="xgb",
                date_from=date_from,
                date_to=date_to,
                total_bets__gt=0,
            )
            .prefetch_related("results")
            .first()
        )
        if run is None:
            return Response(
                {"detail": f"No seeded data for {matched_name} / {stat} / {season_label}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        results = list(run.results.all())
        n_games  = len(results)

        if n_games < window:
            return Response(
                {"detail": f"Not enough games ({n_games}) for window size {window}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        step = max(1, window // 2)
        windows_out = []
        start = 0
        win_num = 1

        while start + window <= n_games:
            chunk    = results[start:start + window]
            actuals  = [r.actual for r in chunk]
            errors   = [r.error  for r in chunk]
            hits     = sum(1 for r in chunk if r.correct)
            hit_rate = hits / len(chunk)
            abs_err  = sum(abs(e) for e in errors) / len(chunk)

            score, tier = pred_score_tier(actuals, errors, hit_rate)
            windows_out.append({
                "window_num": win_num,
                "game_start": start + 1,
                "game_end":   start + window,
                "date_start": str(chunk[0].game_date),
                "date_end":   str(chunk[-1].game_date),
                "score":      score,
                "tier":       tier,
                "mae":        round(abs_err, 3),
                "hit_rate":   round(hit_rate, 4),
            })
            start   += step
            win_num += 1

        tier_changes = []
        for i in range(1, len(windows_out)):
            prev = windows_out[i - 1]
            curr = windows_out[i]
            if prev["tier"] != curr["tier"]:
                tier_changes.append({
                    "at_game":     curr["game_start"],
                    "date":        curr["date_start"],
                    "from_tier":   prev["tier"],
                    "to_tier":     curr["tier"],
                    "score_before": prev["score"],
                    "score_after":  curr["score"],
                })

        last = windows_out[-1] if windows_out else {}

        return Response({
            "player_name":  matched_name,
            "stat":         stat,
            "season":       season_label,
            "window":       window,
            "n_games":      n_games,
            "windows":      windows_out,
            "tier_changes": tier_changes,
            "current_score": last.get("score"),
            "current_tier":  last.get("tier"),
        })


# ── Sprint 5: Player Intelligence Suite ──────────────────────────────────────

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


class EdgeCalibrationView(APIView):
    """GET /api/intelligence/edge/?player_name=...&stat=pts&season=2026"""

    def get(self, request):
        matched, stat, season, err = _intelligence_preamble(request)
        if err:
            return err
        try:
            result = compute_edge_calibration(matched, stat, season)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({"detail": f"Edge calibration failed: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(result)


class FloorCeilingView(APIView):
    """GET /api/intelligence/floor-ceiling/?player_name=...&stat=pts&season=2026"""

    def get(self, request):
        matched, stat, season, err = _intelligence_preamble(request)
        if err:
            return err
        try:
            result = compute_floor_ceiling(matched, stat, season)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({"detail": f"Floor/ceiling analysis failed: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(result)


class OpponentAnalysisView(APIView):
    """GET /api/intelligence/opponents/?player_name=...&stat=pts&season=2026"""

    def get(self, request):
        matched, stat, season, err = _intelligence_preamble(request)
        if err:
            return err
        try:
            result = compute_opponent_analysis(matched, stat, season)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({"detail": f"Opponent analysis failed: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(result)


class PlayerFingerprintView(APIView):
    """GET /api/intelligence/fingerprint/?player_name=...&stat=pts&season=2026"""

    def get(self, request):
        matched, stat, season, err = _intelligence_preamble(request)
        if err:
            return err
        try:
            result = compute_player_fingerprint(matched, stat, season)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({"detail": f"Fingerprint failed: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(result)
