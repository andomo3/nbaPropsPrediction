from datetime import date

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..constants import (
    BACKTEST_MODELS,
    DEFAULT_SEASON,
    MODEL_LABELS,
    SEASON_DATES,
    SEASON_REPORT_PLAYERS,
)
from ..models import BacktestRun
from ..services.backtest import run_backtest
from ..utils.stats import pred_score_tier


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
                "hit_rate":           round(run.accuracy, 4),
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
