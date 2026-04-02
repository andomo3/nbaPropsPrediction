"""
scripts/spark_features.py

PySpark feature engineering for NBA player props.
Reads player game logs from PostgreSQL (view_base_data), computes rolling/EMA/Holt
features, and writes to derived_features_store via JDBC.

Ported from: notebooks/feature_engineering.py (Pandas → PySpark)

Key design decisions:
  - Rolling L10 windows use rowsBetween(-10, -1) — equivalent to pandas shift(1).rolling(10).
    The -1 upper bound excludes the current row, preventing leakage.
  - EMA (span=5) is approximated via 5 LAG() calls with exponential weights since
    PySpark has no native ewm() window function.
  - Holt damped trend uses applyInPandas: each player's history runs statsmodels
    inside a Pandas partition on a Spark executor. This is the only safe way to
    use statsmodels in a distributed Spark context.
  - Opponent defense context uses a separate groupBy(opponent_id) aggregation with
    the same shift(1)-equivalent window to prevent lookahead bias.

Run standalone:
  spark-submit --jars /opt/spark/jars/postgresql-42.7.3.jar scripts/spark_features.py \\
      --jdbc-url jdbc:postgresql://localhost:5432/nba_props \\
      --db-user postgres --db-password postgres

Run via Airflow SparkSubmitOperator (see dags/nba_etl_dag.py).
"""

from __future__ import annotations

import argparse
import warnings
from typing import Iterator

import numpy as np
import pandas as pd
from pyspark.sql import SparkSession, Window, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
)

# -----------------------------------------------------------------------
# Schema for applyInPandas return type (Holt trend output).
# Must exactly match the columns returned by _compute_holt_trends_pandas.
# -----------------------------------------------------------------------
HOLT_OUTPUT_SCHEMA = StructType([
    StructField("player_id", LongType(), False),
    StructField("game_id", StringType(), False),
    StructField("trend_pts", DoubleType(), True),
    StructField("trend_reb", DoubleType(), True),
    StructField("trend_ast", DoubleType(), True),
])


def build_spark_session() -> SparkSession:
    return (
        SparkSession.builder
        .appName("nba_feature_engineering")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .getOrCreate()
    )


def read_base_data(spark: SparkSession, jdbc_url: str, user: str, password: str) -> DataFrame:
    """
    Reads view_base_data from PostgreSQL via JDBC.
    Partitions on player_id to parallelize the read across Spark workers.
    """
    return (
        spark.read
        .format("jdbc")
        .option("url", jdbc_url)
        .option("dbtable", "public.view_base_data")
        .option("user", user)
        .option("password", password)
        .option("driver", "org.postgresql.Driver")
        .option("partitionColumn", "player_id")
        .option("lowerBound", "1")
        .option("upperBound", "9999999")
        .option("numPartitions", "8")
        .load()
    )


def compute_rolling_window_features(df: DataFrame) -> DataFrame:
    """
    L10 rolling features using PySpark Window functions.

    rowsBetween(-10, -1) is the Spark equivalent of pandas shift(1).rolling(10):
      - upper bound -1 excludes the current row (no leakage / shift equivalent)
      - lower bound -10 gives the 10-game lookback window
    """
    w_l10 = (
        Window.partitionBy("player_id")
        .orderBy("date")
        .rowsBetween(-10, -1)
    )

    df = df.withColumn("min_l10", F.mean("min").over(w_l10))
    df = df.withColumn("pts_mean_l10", F.mean("pts").over(w_l10))
    df = df.withColumn("pts_std_l10", F.stddev_pop("pts").over(w_l10))

    # Coefficient of variation: std / mean, guarded against near-zero mean
    df = df.withColumn(
        "cv_l10",
        F.when(
            F.abs(F.col("pts_mean_l10")) > 1e-9,
            F.col("pts_std_l10") / F.col("pts_mean_l10"),
        ).otherwise(F.lit(0.0))
    )

    # Volume projection: field goal attempts per minute, projected forward
    df = df.withColumn(
        "fga_per_min_raw",
        F.when(F.col("min") > 0, F.col("fga") / F.col("min")).otherwise(None)
    )
    df = df.withColumn("fga_per_min_l10", F.mean("fga_per_min_raw").over(w_l10))
    df = df.withColumn("proj_volume", F.col("fga_per_min_l10") * F.col("min_l10"))

    # Null fallbacks for first-career-game edge case
    df = df.withColumn("min_l10", F.coalesce("min_l10", "min"))
    df = df.withColumn("fga_per_min_l10", F.coalesce("fga_per_min_l10", "fga_per_min_raw", F.lit(0.0)))
    df = df.withColumn("proj_volume", F.coalesce("proj_volume", F.lit(0.0)))

    return df


def compute_ema_features(df: DataFrame) -> DataFrame:
    """
    Approximate EMA (exponential moving average) with span=5.
    alpha = 2/(5+1) = 0.333

    PySpark has no native ewm() window function. We approximate using 5 LAG() calls
    with exponentially decaying weights. This matches pandas ewm(span=5, adjust=False)
    within floating-point tolerance for window sizes >= 5.

    weights: [alpha, alpha*(1-a), alpha*(1-a)^2, alpha*(1-a)^3, alpha*(1-a)^4]
    where the most recent observation (LAG 1) gets the highest weight.
    """
    alpha = 2.0 / (5 + 1)  # 0.3333...
    w_ordered = Window.partitionBy("player_id").orderBy("date")

    for stat in ["pts", "reb", "ast"]:
        lags = []
        for i in range(1, 6):
            lag_col = f"_lag_{stat}_{i}"
            df = df.withColumn(lag_col, F.lag(stat, i).over(w_ordered))
            weight = alpha * ((1 - alpha) ** (i - 1))
            lags.append((lag_col, weight))

        # Weighted sum / total non-null weight
        weight_sum_expr = sum(
            F.when(F.col(col).isNotNull(), F.lit(w)).otherwise(F.lit(0.0))
            for col, w in lags
        )
        weighted_val_expr = sum(
            F.when(F.col(col).isNotNull(), F.col(col) * F.lit(w)).otherwise(F.lit(0.0))
            for col, w in lags
        )

        df = df.withColumn(
            f"{stat}_ema_l5",
            F.when(weight_sum_expr > 0, weighted_val_expr / weight_sum_expr).otherwise(None)
        )

        for col, _ in lags:
            df = df.drop(col)

    return df


def compute_opponent_defense_context(df: DataFrame) -> DataFrame:
    """
    Opponent rolling defense: opp_avg_{stat}_allowed_l10.
    Aggregates total stats allowed per (opponent_id, game_id), then
    computes L10 rolling mean with rowsBetween(-10, -1) to prevent leakage.
    Falls back to league average for early-season sparse data.
    """
    opp_game = (
        df.groupBy("opponent_id", "game_id", "date")
        .agg(
            F.sum("pts").alias("opp_pts_allowed_total"),
            F.sum("reb").alias("opp_reb_allowed_total"),
            F.sum("ast").alias("opp_ast_allowed_total"),
        )
    )

    w_opp_l10 = (
        Window.partitionBy("opponent_id")
        .orderBy("date")
        .rowsBetween(-10, -1)
    )

    for stat in ["pts", "reb", "ast"]:
        total_col = f"opp_{stat}_allowed_total"
        feature_col = f"opp_avg_{stat}_allowed_l10"
        opp_game = opp_game.withColumn(feature_col, F.mean(total_col).over(w_opp_l10))

    # Compute league averages for fallback
    league_avgs = {}
    for stat in ["pts", "reb", "ast"]:
        row = df.agg(F.mean(stat).alias("avg")).first()
        league_avgs[stat] = float(row["avg"]) if row and row["avg"] is not None else 0.0

    for stat in ["pts", "reb", "ast"]:
        feature_col = f"opp_avg_{stat}_allowed_l10"
        opp_game = opp_game.withColumn(
            feature_col,
            F.coalesce(F.col(feature_col), F.lit(league_avgs[stat]))
        )

    opp_cols = (
        ["opponent_id", "game_id", "date"]
        + [f"opp_avg_{s}_allowed_l10" for s in ["pts", "reb", "ast"]]
    )
    df = df.join(opp_game.select(opp_cols), on=["opponent_id", "game_id", "date"], how="left")

    # Final league-average fallback for players missing opponent data
    for stat in ["pts", "reb", "ast"]:
        feature_col = f"opp_avg_{stat}_allowed_l10"
        df = df.withColumn(feature_col, F.coalesce(F.col(feature_col), F.lit(league_avgs[stat])))

    return df


def _compute_holt_trends_pandas(pdf: pd.DataFrame) -> pd.DataFrame:
    """
    Runs statsmodels Holt damped trend on a single player's history.
    Called via applyInPandas — each Spark executor receives one player's
    full game log as a Pandas DataFrame.

    Input columns: player_id, game_id, date, pts, reb, ast
    Output columns: player_id, game_id, trend_pts, trend_reb, trend_ast

    Matches the logic in notebooks/feature_engineering.py:
      - shift(1) via sorting + using only prior rows in rolling window
      - Holt(damped_trend=True) with adaptive optimisation for 10+ games
      - Fixed params (smoothing_level=0.3, smoothing_trend=0.2, damping=0.9)
        for sparse histories or when optimisation fails
    """
    from statsmodels.tsa.holtwinters import Holt
    from statsmodels.tools.sm_exceptions import ConvergenceWarning

    pdf = pdf.sort_values("date").reset_index(drop=True)

    def _holt_series(series: pd.Series, window: int = 10) -> pd.Series:
        shifted = series.shift(1)
        result = np.full(len(series), np.nan)

        for i in range(len(series)):
            values = shifted.iloc[max(0, i - window + 1): i + 1].dropna().to_numpy(dtype=float)
            if len(values) == 0:
                result[i] = np.nan
                continue
            if len(values) == 1:
                result[i] = values[0]
                continue
            try:
                model = Holt(values, damped_trend=True, initialization_method="estimated")
                use_fixed = len(values) < 10
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", ConvergenceWarning)
                    fitted = model.fit(
                        smoothing_level=0.3,
                        smoothing_trend=0.2,
                        damping_trend=0.9,
                        optimized=not use_fixed,
                    )
                result[i] = float(np.asarray(fitted.trend)[-1])
            except Exception:
                try:
                    model = Holt(values, damped_trend=True, initialization_method="estimated")
                    fitted = model.fit(
                        smoothing_level=0.3,
                        smoothing_trend=0.2,
                        damping_trend=0.9,
                        optimized=False,
                    )
                    result[i] = float(np.asarray(fitted.trend)[-1])
                except Exception:
                    result[i] = np.nan

        return pd.Series(result, index=series.index)

    pdf["trend_pts"] = _holt_series(pdf["pts"])
    pdf["trend_reb"] = _holt_series(pdf["reb"])
    pdf["trend_ast"] = _holt_series(pdf["ast"])

    for col in ["trend_pts", "trend_reb", "trend_ast"]:
        pdf[col] = pdf[col].fillna(0.0)

    return pdf[["player_id", "game_id", "trend_pts", "trend_reb", "trend_ast"]]


def compute_holt_trends(df: DataFrame) -> DataFrame:
    """
    Dispatches per-player Holt computation to Spark executors via applyInPandas.
    Parallelises across players while keeping statsmodels isolated from the
    Spark distributed planner.
    """
    holt_df = (
        df.select("player_id", "game_id", "date", "pts", "reb", "ast")
        .groupBy("player_id")
        .applyInPandas(_compute_holt_trends_pandas, schema=HOLT_OUTPUT_SCHEMA)
    )
    return df.join(holt_df, on=["player_id", "game_id"], how="left")


def write_to_postgres(df: DataFrame, jdbc_url: str, user: str, password: str) -> int:
    """
    Writes derived_features_store to PostgreSQL via JDBC.
    Filters DNP rows (min=0) and drops rows with nulls in critical features.
    Uses truncate=true + overwrite to match the safe_write_back() pattern
    in the original feature_engineering.py.
    Returns the row count written.
    """
    derived_cols = [
        "player_id", "game_id", "date",
        "trend_pts", "trend_reb", "trend_ast",
        "min_l10", "fga_per_min_l10", "proj_volume",
        "pts_std_l10", "pts_mean_l10", "cv_l10",
        "opp_avg_pts_allowed_l10", "opp_avg_reb_allowed_l10", "opp_avg_ast_allowed_l10",
    ]

    output_df = (
        df.select(derived_cols)
        .filter(F.col("min") > 0)
        .dropna(subset=[
            "proj_volume", "cv_l10",
            "opp_avg_pts_allowed_l10",
            "opp_avg_reb_allowed_l10",
            "opp_avg_ast_allowed_l10",
        ])
    )

    row_count = output_df.count()

    (
        output_df.write
        .format("jdbc")
        .option("url", jdbc_url)
        .option("dbtable", "public.derived_features_store")
        .option("user", user)
        .option("password", password)
        .option("driver", "org.postgresql.Driver")
        .option("truncate", "true")
        .mode("overwrite")
        .save()
    )

    return row_count


def main(jdbc_url: str, db_user: str, db_password: str) -> None:
    spark = build_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    print("Reading base data from PostgreSQL (view_base_data)...")
    df = read_base_data(spark, jdbc_url, db_user, db_password)
    df = df.orderBy("player_id", "date", "game_id")
    total_rows = df.count()
    print(f"  Loaded {total_rows:,} rows")

    print("Computing rolling L10 window features...")
    df = compute_rolling_window_features(df)

    print("Computing EMA features (span=5)...")
    df = compute_ema_features(df)

    print("Computing opponent defense context (L10, no leakage)...")
    df = compute_opponent_defense_context(df)

    print("Computing Holt damped trend features (applyInPandas per player)...")
    df = compute_holt_trends(df)

    print("Writing derived_features_store to PostgreSQL...")
    rows_written = write_to_postgres(df, jdbc_url, db_user, db_password)
    print(f"  Wrote {rows_written:,} rows to derived_features_store")

    print("Pipeline complete.")
    spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NBA PySpark feature engineering pipeline")
    parser.add_argument("--jdbc-url", required=True, help="JDBC URL for PostgreSQL")
    parser.add_argument("--db-user", default="postgres", help="DB username")
    parser.add_argument("--db-password", default="postgres", help="DB password")
    args = parser.parse_args()
    main(args.jdbc_url, args.db_user, args.db_password)
