from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..constants import (
    DEFAULT_SEASON,
    SEASON_DATES,
    SEASON_REPORT_PLAYERS,
)
from ..models import BacktestRun
from ..services.simulator import run_simulation
from ..services.shap_analysis import compute_shap_analysis
from ..services.variance_decomp import compute_variance_decomposition
from ..services.edge_calibration import compute_edge_calibration
from ..services.statistical_validation import compute_statistical_validation
from ..services.floor_ceiling import compute_floor_ceiling
from ..services.opponent_analysis import compute_opponent_analysis
from ..services.player_fingerprint import compute_player_fingerprint
from ..utils.stats import pred_score_tier
from ._shared import _intelligence_cache_get, _intelligence_preamble, _make_cache_key


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


class EdgeCalibrationView(APIView):
    """GET /api/intelligence/edge/?player_name=...&stat=pts&season=2026"""

    def get(self, request):
        matched, stat, season, err = _intelligence_preamble(request)
        if err:
            return err
        try:
            result = _intelligence_cache_get(
                _make_cache_key("edge", matched, stat, season),
                lambda: compute_edge_calibration(matched, stat, season),
            )
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
            result = _intelligence_cache_get(
                _make_cache_key("floor_ceiling", matched, stat, season),
                lambda: compute_floor_ceiling(matched, stat, season),
            )
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
            result = _intelligence_cache_get(
                _make_cache_key("opponents", matched, stat, season),
                lambda: compute_opponent_analysis(matched, stat, season),
            )
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
            result = _intelligence_cache_get(
                _make_cache_key("fingerprint", matched, stat, season),
                lambda: compute_player_fingerprint(matched, stat, season),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({"detail": f"Fingerprint failed: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(result)


class StatisticalValidationView(APIView):
    """GET /api/intelligence/validation/?player_name=...&stat=pts&season=2026"""

    def get(self, request):
        matched, stat, season, err = _intelligence_preamble(request)
        if err:
            return err
        try:
            result = _intelligence_cache_get(
                _make_cache_key("validation", matched, stat, season),
                lambda: compute_statistical_validation(matched, stat, season),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({"detail": f"Validation failed: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(result)
