import os
import warnings
import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.holtwinters import Holt

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
EXPORTS_DIR = ROOT / "exports"
OUTPUT_PATH = EXPORTS_DIR / "nba_model_ready.csv"

# Runtime diagnostics for trend feature quality.
TREND_DIAGNOSTICS = {}
FAST_MODE = False


CREATE_VIEW_FINAL_FEATURES_SQL = """
CREATE OR REPLACE VIEW public.view_final_features AS
SELECT
    b.*,
    d.trend_pts,
    d.trend_reb,
    d.trend_ast,
    d.min_l10,
    d.fga_per_min_l10,
    d.proj_volume,
    d.pts_std_l10,
    d.pts_mean_l10,
    d.cv_l10,
    d.opp_avg_pts_allowed_l10,
    d.opp_avg_reb_allowed_l10,
    d.opp_avg_ast_allowed_l10
FROM public.view_base_data b
JOIN public.derived_features_store d
  ON b.player_id = d.player_id
 AND b.game_id = d.game_id;
"""


def get_db_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Example: postgres://postgres:postgres@db:5432/nba_props"
        )
    return db_url


def get_connection():
    return psycopg2.connect(get_db_url())


def get_sqlalchemy_engine():
    # SQLAlchemy v2 expects postgresql+psycopg2 scheme.
    url = get_db_url().replace("postgres://", "postgresql+psycopg2://", 1)
    return create_engine(url)


def load_base_data() -> pd.DataFrame:
    query = """
        SELECT
            player_id,
            game_id,
            date,
            season,
            player_name,
            opponent_id,
            min,
            pts,
            reb,
            ast,
            fga,
            fgm
        FROM public.view_base_data
        ORDER BY player_id, date, game_id
    """
    with get_connection() as conn:
        df = pd.read_sql_query(query, conn)

    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["player_id", "date", "game_id"]).reset_index(drop=True)


def filter_single_season(df: pd.DataFrame, season: str | None) -> pd.DataFrame:
    """Optionally scope pipeline to one season."""
    if not season:
        return df
    return df[df["season"] == season].copy()


def calculate_holt_trend(series: pd.Series, window: int = 10, stat_key: str = "unknown") -> pd.Series:
    """Uses Holt-Winters Damped Trend.

    Parameters are optimized via MSE for players with >10 games history;
    fixed parameters are used for sparse data to ensure stability.
    """
    shifted = series.shift(1)
    TREND_DIAGNOSTICS.setdefault(
        stat_key,
        {
            "rows_total": 0,
            "rows_non_null": 0,
            "optimized_rows": 0,
            "fixed_rows": 0,
            "fallback_rows": 0,
            "nan_rows": 0,
        },
    )
    diag = TREND_DIAGNOSTICS[stat_key]

    def _holt(values: np.ndarray) -> float:
        y = pd.Series(values).dropna().to_numpy(dtype=float)
        diag["rows_total"] += 1
        if y.size == 0:
            diag["nan_rows"] += 1
            return np.nan
        if y.size == 1:
            # Holt needs at least 2 points to initialize trend.
            diag["fixed_rows"] += 1
            diag["rows_non_null"] += 1
            return float(y[0])

        try:
            model = Holt(y, damped_trend=True, initialization_method="estimated")
            if FAST_MODE or y.size < 10:
                fitted = model.fit(
                    smoothing_level=0.3,
                    smoothing_trend=0.2,
                    damping_trend=0.9,
                    optimized=False,
                )
                diag["fixed_rows"] += 1
            else:
                # Treat convergence warnings as errors so we can fallback cleanly.
                with warnings.catch_warnings():
                    warnings.simplefilter("error", ConvergenceWarning)
                    fitted = model.fit(optimized=True)
                diag["optimized_rows"] += 1
            diag["rows_non_null"] += 1
            return float(np.asarray(fitted.trend)[-1])
        except Exception:
            # Fallback for noisy windows where optimization fails to converge.
            try:
                model = Holt(y, damped_trend=True, initialization_method="estimated")
                fallback = model.fit(
                    smoothing_level=0.3,
                    smoothing_trend=0.2,
                    damping_trend=0.9,
                    optimized=False,
                )
                diag["fallback_rows"] += 1
                diag["rows_non_null"] += 1
                return float(np.asarray(fallback.trend)[-1])
            except Exception:
                diag["nan_rows"] += 1
                return np.nan

    return shifted.rolling(window=window, min_periods=1).apply(_holt, raw=True)


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    total_players = out["player_id"].nunique()
    print(f"  Players in scope: {total_players:,}")

    # Basic rolling window stats.
    print("  Computing rolling windows (L10 stats)...")
    out["min_l10"] = out.groupby("player_id")["min"].transform(
        lambda x: x.shift(1).rolling(window=10, min_periods=1).mean()
    )
    out["min_l10"] = out["min_l10"].fillna(out["min"])
    out["pts_std_l10"] = out.groupby("player_id")["pts"].transform(
        lambda x: x.shift(1).rolling(window=10, min_periods=2).std()
    )
    out["pts_mean_l10"] = out.groupby("player_id")["pts"].transform(
        lambda x: x.shift(1).rolling(window=10, min_periods=1).mean()
    )
    out["cv_l10"] = np.where(
        out["pts_mean_l10"].abs() > 1e-9,
        out["pts_std_l10"] / out["pts_mean_l10"],
        np.nan,
    )
    out["cv_l10"] = out["cv_l10"].fillna(0.0)

    # Volume: proj_volume = (fga_per_min_L10) * (min_L10)
    print("  Computing volume features...")
    out["fga_per_min_raw"] = np.where(out["min"] > 0, out["fga"] / out["min"], np.nan)
    out["fga_per_min_l10"] = out.groupby("player_id")["fga_per_min_raw"].transform(
        lambda x: x.shift(1).rolling(window=10, min_periods=3).mean()
    )
    out["fga_per_min_l10"] = out["fga_per_min_l10"].fillna(out["fga_per_min_raw"]).fillna(0.0)
    out["proj_volume"] = out["fga_per_min_l10"] * out["min_l10"]

    # Holt damped trends (trajectory).
    print(f"  Computing Holt damped trend features (FAST_MODE={FAST_MODE})...")
    for stat, out_col in [("pts", "trend_pts"), ("reb", "trend_reb"), ("ast", "trend_ast")]:
        out[out_col] = np.nan
        grouped = out.groupby("player_id")[stat]
        t0 = time.perf_counter()
        for i, (_pid, series) in enumerate(grouped, start=1):
            out.loc[series.index, out_col] = calculate_holt_trend(
                series, window=10, stat_key=stat
            ).to_numpy()
            if i % 250 == 0 or i == total_players:
                elapsed = time.perf_counter() - t0
                pct = (i / total_players) * 100 if total_players else 100
                print(
                    f"    {stat.upper()} trend: {i:,}/{total_players:,} players "
                    f"({pct:.1f}%) in {elapsed:.1f}s"
                )

    # Team-level context (no leakage): rolling(10).mean().shift(1) by opponent.
    print("  Computing opponent rolling defense context...")
    opp_game = (
        out.groupby(["opponent_id", "game_id", "date"], as_index=False)[["pts", "reb", "ast"]]
        .sum()
        .rename(
            columns={
                "pts": "opp_pts_allowed_total",
                "reb": "opp_reb_allowed_total",
                "ast": "opp_ast_allowed_total",
            }
        )
        .sort_values(["opponent_id", "date", "game_id"])
    )
    for stat in ["pts", "reb", "ast"]:
        total_col = f"opp_{stat}_allowed_total"
        feature_col = f"opp_avg_{stat}_allowed_l10"
        print(f"    Opponent context for {stat.upper()}...")
        opp_game[feature_col] = opp_game.groupby("opponent_id")[total_col].transform(
            lambda x: x.shift(1).rolling(window=10, min_periods=3).mean()
        )
        league_col = f"league_avg_{stat}_allowed_l10"
        opp_game[league_col] = opp_game[total_col].shift(1).rolling(window=10, min_periods=1).mean()

    out = out.merge(
        opp_game[
            [
                "opponent_id",
                "game_id",
                "date",
                "opp_avg_pts_allowed_l10",
                "opp_avg_reb_allowed_l10",
                "opp_avg_ast_allowed_l10",
                "league_avg_pts_allowed_l10",
                "league_avg_reb_allowed_l10",
                "league_avg_ast_allowed_l10",
            ]
        ],
        on=["opponent_id", "game_id", "date"],
        how="left",
    )

    out["opp_avg_pts_allowed_l10"] = out["opp_avg_pts_allowed_l10"].fillna(out["league_avg_pts_allowed_l10"])
    out["opp_avg_reb_allowed_l10"] = out["opp_avg_reb_allowed_l10"].fillna(out["league_avg_reb_allowed_l10"])
    out["opp_avg_ast_allowed_l10"] = out["opp_avg_ast_allowed_l10"].fillna(out["league_avg_ast_allowed_l10"])

    # Sparse-slice hard fallbacks (e.g., very early season runs).
    out["trend_pts"] = out["trend_pts"].fillna(0.0)
    out["trend_reb"] = out["trend_reb"].fillna(0.0)
    out["trend_ast"] = out["trend_ast"].fillna(0.0)
    out["opp_avg_pts_allowed_l10"] = out["opp_avg_pts_allowed_l10"].fillna(float(out["pts"].mean()))
    out["opp_avg_reb_allowed_l10"] = out["opp_avg_reb_allowed_l10"].fillna(float(out["reb"].mean()))
    out["opp_avg_ast_allowed_l10"] = out["opp_avg_ast_allowed_l10"].fillna(float(out["ast"].mean()))

    # Keep only keys + engineered columns in the derived store.
    derived_cols = [
        "player_id",
        "game_id",
        "date",
        "trend_pts",
        "trend_reb",
        "trend_ast",
        "min_l10",
        "fga_per_min_l10",
        "proj_volume",
        "pts_std_l10",
        "pts_mean_l10",
        "cv_l10",
        "opp_avg_pts_allowed_l10",
        "opp_avg_reb_allowed_l10",
        "opp_avg_ast_allowed_l10",
    ]
    derived = out[derived_cols].copy()

    # Final training-clean filter (no DNP rows, no null engineered values).
    derived = derived[out["min"] > 0]
    derived = derived.dropna(
        subset=[
            "proj_volume",
            "cv_l10",
            "opp_avg_pts_allowed_l10",
            "opp_avg_reb_allowed_l10",
            "opp_avg_ast_allowed_l10",
        ]
    )
    return derived


def safe_write_back(derived_df: pd.DataFrame) -> None:
    """Drop dependent view, write table, then recreate final view."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP VIEW IF EXISTS public.view_final_features;")
        conn.commit()

    engine = get_sqlalchemy_engine()
    derived_df.to_sql(
        "derived_features_store",
        engine,
        schema="public",
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=5000,
    )

    with engine.begin() as conn:
        conn.execute(text(CREATE_VIEW_FINAL_FEATURES_SQL))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build derived NBA features.")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use fixed-parameter Holt only (faster, less adaptive).",
    )
    parser.add_argument(
        "--season",
        type=str,
        default=None,
        help="Optional single season filter, e.g. 2024-25.",
    )
    args = parser.parse_args()

    global FAST_MODE
    FAST_MODE = bool(args.fast)

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading view_base_data...")
    base_df = load_base_data()
    # IMPORTANT: compute features on full history, then filter output season.
    # This preserves pre-season context for early-season rows.
    scoped_df = filter_single_season(base_df, args.season)
    if args.season:
        print(f"Target season {args.season}: {len(scoped_df):,} rows (features computed on full history)")

    print("Calculating derived features...")
    derived_df = add_derived_features(base_df)
    derived_to_write = derived_df
    if args.season:
        derived_to_write = derived_df.merge(
            base_df[["player_id", "game_id", "date", "season"]],
            on=["player_id", "game_id", "date"],
            how="left",
        )
        derived_to_write = derived_to_write[derived_to_write["season"] == args.season].drop(columns=["season"])

    print("Writing derived_features_store and recreating view_final_features...")
    safe_write_back(derived_to_write)

    # Optional local CSV export for model training scripts.
    merged = base_df.merge(
        derived_df,
        on=["player_id", "game_id", "date"],
        how="inner",
    )
    if args.season:
        merged = merged[merged["season"] == args.season].copy()
    merged.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(merged)} rows to {OUTPUT_PATH}")

    print("Sample trend columns:")
    print(
        merged[
            ["player_id", "game_id", "date", "trend_pts", "trend_reb", "trend_ast"]
        ]
        .head(10)
        .to_string(index=False)
    )

    print("\nTrend feature diagnostics:")
    for stat_key in ["pts", "reb", "ast"]:
        d = TREND_DIAGNOSTICS.get(stat_key, {})
        if not d:
            continue
        print(
            f"  {stat_key}: non_null={d.get('rows_non_null', 0):,}/{d.get('rows_total', 0):,}, "
            f"optimized={d.get('optimized_rows', 0):,}, fixed={d.get('fixed_rows', 0):,}, "
            f"fallback={d.get('fallback_rows', 0):,}, nan={d.get('nan_rows', 0):,}"
        )


if __name__ == "__main__":
    main()
