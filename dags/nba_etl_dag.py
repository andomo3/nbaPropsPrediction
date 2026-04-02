"""
dags/nba_etl_dag.py

NBA player props weekly ETL pipeline.

Simulates a weekly batch drop pattern: CSVs are placed in data/landing/,
validated, transformed by PySpark, written to PostgreSQL, then archived.

Schedule: Sundays at 03:00 UTC. Can be triggered manually at any time.
Max 1 concurrent run (prevents overlapping JDBC truncate writes).

Task graph:
    check_landing
        → validate_schema
        → spark_transform
        → recreate_final_features_view
        → export_model_ready_csv
        → archive_landing_files
        → log_pipeline_run
"""

from __future__ import annotations

import csv
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.utils.trigger_rule import TriggerRule

# -----------------------------------------------------------------------
# Path constants (volume-mounted inside the Airflow container)
# -----------------------------------------------------------------------
DATA_ROOT = Path("/opt/airflow/data")
LANDING_DIR = DATA_ROOT / "landing"
ARCHIVE_DIR = DATA_ROOT / "archive"
MODEL_READY_DIR = DATA_ROOT / "model_ready"
SPARK_SCRIPT = Path("/opt/airflow/scripts/spark_features.py")

# -----------------------------------------------------------------------
# Default DAG arguments
# -----------------------------------------------------------------------
DEFAULT_ARGS = {
    "owner": "nba_pipeline",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# Minimum required CSV files for the pipeline to proceed
REQUIRED_FILES = ["PlayerStatistics.csv", "Games.csv"]

# Expected column headers for schema validation
EXPECTED_SCHEMAS: dict[str, set[str]] = {
    "PlayerStatistics.csv": {
        "personId", "gameId", "gameDateTimeEst",
        "points", "reboundsTotal", "assists", "numMinutes",
        "fieldGoalsAttempted", "fieldGoalsMade",
        "playerteamCity", "playerteamName",
        "opponentteamCity", "opponentteamName", "home",
    },
    "Games.csv": {
        "gameId", "gameDateTimeEst",
        "hometeamCity", "hometeamName", "hometeamId",
        "awayteamCity", "awayteamName", "awayteamId",
        "homeScore", "awayScore",
    },
}


# -----------------------------------------------------------------------
# Task: check_landing
# ShortCircuitOperator — skips the entire run if landing/ is empty.
# -----------------------------------------------------------------------
def _check_landing_files(**context) -> bool:
    """
    Returns True (continue pipeline) if all required CSVs are present in
    data/landing/. Returns False (short-circuit, skip all downstream tasks)
    if any required file is missing.
    """
    LANDING_DIR.mkdir(parents=True, exist_ok=True)
    found = {f.name for f in LANDING_DIR.glob("*.csv")}
    missing = [r for r in REQUIRED_FILES if r not in found]

    if missing:
        print(f"[check_landing] Missing required files: {missing}. Found: {sorted(found)}")
        return False

    print(f"[check_landing] All required files present: {sorted(found)}")
    context["ti"].xcom_push(key="landing_files", value=sorted(found))
    return True


# -----------------------------------------------------------------------
# Task: validate_schema
# Checks CSV headers before Spark reads the files.
# -----------------------------------------------------------------------
def _validate_csv_schema(**context) -> None:
    """
    Reads the first line of each required CSV and confirms expected columns
    are present. Raises ValueError on mismatch — marks the task Failed and
    prevents corrupt data reaching the Spark job.
    """
    for filename, expected_cols in EXPECTED_SCHEMAS.items():
        path = LANDING_DIR / filename
        if not path.exists():
            continue

        with open(path, newline="", encoding="utf-8") as f:
            actual_cols = set(next(csv.reader(f)))

        missing_cols = expected_cols - actual_cols
        if missing_cols:
            raise ValueError(
                f"[validate_schema] Schema mismatch in {filename}. "
                f"Missing columns: {missing_cols}"
            )

    print("[validate_schema] All schema checks passed.")


# -----------------------------------------------------------------------
# Task: export_model_ready_csv
# Exports view_final_features to data/model_ready/ after Spark writes.
# -----------------------------------------------------------------------
def _export_model_ready_csv(**context) -> None:
    """
    Queries view_final_features from PostgreSQL and writes the result to
    data/model_ready/nba_model_ready.csv. This CSV is the input for
    python manage.py train_models (offline retraining).
    """
    import psycopg2

    MODEL_READY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MODEL_READY_DIR / "nba_model_ready.csv"

    conn = psycopg2.connect(
        host="db",
        port=5432,
        dbname="nba_props",
        user=os.environ.get("NBA_DB_USER", "postgres"),
        password=os.environ.get("NBA_DB_PASSWORD", "postgres"),
    )

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.view_final_features ORDER BY player_id, date"
            )
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            writer.writerows(rows)

        print(f"[export_model_ready_csv] Wrote {len(rows):,} rows to {out_path}")
    finally:
        conn.close()


# -----------------------------------------------------------------------
# Task: archive_landing_files
# Moves processed CSVs to data/archive/ with a timestamp suffix.
# -----------------------------------------------------------------------
def _archive_landing_files(**context) -> None:
    """
    Moves all CSVs from data/landing/ to data/archive/, appending the
    Airflow run timestamp (ts_nodash) to each filename.
    E.g.: PlayerStatistics.csv → archive/PlayerStatistics_20260601T030000.csv
    """
    run_ts = context["ts_nodash"]  # e.g. "20260601T030000"
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    for csv_path in sorted(LANDING_DIR.glob("*.csv")):
        dest = ARCHIVE_DIR / f"{csv_path.stem}_{run_ts}{csv_path.suffix}"
        shutil.move(str(csv_path), str(dest))
        print(f"[archive_landing_files] {csv_path.name} → {dest.name}")


# -----------------------------------------------------------------------
# DAG definition
# -----------------------------------------------------------------------
with DAG(
    dag_id="nba_etl_weekly",
    default_args=DEFAULT_ARGS,
    description="NBA props weekly ETL: CSV landing → Spark features → PostgreSQL",
    schedule_interval="0 3 * * 0",  # Sundays at 03:00 UTC
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["nba", "etl", "spark"],
) as dag:

    # ------------------------------------------------------------------
    # T1: Gate — skip the run if landing/ is empty
    # ------------------------------------------------------------------
    check_landing = ShortCircuitOperator(
        task_id="check_landing_files",
        python_callable=_check_landing_files,
    )

    # ------------------------------------------------------------------
    # T2: Validate CSV column headers before touching Spark
    # ------------------------------------------------------------------
    validate_schema = PythonOperator(
        task_id="validate_csv_schema",
        python_callable=_validate_csv_schema,
    )

    # ------------------------------------------------------------------
    # T3: Run PySpark feature engineering
    # conn_id="spark_default" must point to spark://spark-master:7077
    # (configured via Airflow UI or airflow-init command)
    # ------------------------------------------------------------------
    spark_transform = SparkSubmitOperator(
        task_id="spark_feature_transform",
        application=str(SPARK_SCRIPT),
        conn_id="spark_default",
        conf={
            "spark.executor.memory": "2g",
            "spark.driver.memory": "1g",
            "spark.sql.shuffle.partitions": "8",
            # apache/spark image places Spark home at /opt/spark
            "spark.driver.extraClassPath": "/opt/spark/jars/postgresql-42.7.3.jar",
            "spark.executor.extraClassPath": "/opt/spark/jars/postgresql-42.7.3.jar",
        },
        application_args=[
            "--jdbc-url",
            "jdbc:postgresql://db:5432/nba_props",
            "--db-user",
            "postgres",
            "--db-password",
            "postgres",
        ],
        verbose=True,
    )

    # ------------------------------------------------------------------
    # T4: Recreate view_final_features (joins base data + derived store)
    # The Spark job truncates derived_features_store; the view is
    # refreshed here so downstream queries see up-to-date data.
    # ------------------------------------------------------------------
    recreate_view = PostgresOperator(
        task_id="recreate_final_features_view",
        postgres_conn_id="nba_postgres",
        sql="""
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
            FROM  public.view_base_data          b
            JOIN  public.derived_features_store  d
               ON b.player_id = d.player_id
              AND b.game_id   = d.game_id;
        """,
    )

    # ------------------------------------------------------------------
    # T5: Export joined features to data/model_ready/ for retraining
    # ------------------------------------------------------------------
    export_csv = PythonOperator(
        task_id="export_model_ready_csv",
        python_callable=_export_model_ready_csv,
    )

    # ------------------------------------------------------------------
    # T6: Archive processed landing CSVs (only on full success)
    # ------------------------------------------------------------------
    archive_files = PythonOperator(
        task_id="archive_landing_files",
        python_callable=_archive_landing_files,
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    # ------------------------------------------------------------------
    # T7: Write audit record to pipeline_runs table
    # Runs regardless of success/failure (ALL_DONE) for observability.
    # ------------------------------------------------------------------
    log_run = PostgresOperator(
        task_id="log_pipeline_run",
        postgres_conn_id="nba_postgres",
        sql="""
            INSERT INTO public.pipeline_runs (dag_id, run_id, status, finished_at)
            VALUES (
                '{{ dag.dag_id }}',
                '{{ run_id }}',
                'SUCCESS',
                NOW()
            )
            ON CONFLICT (run_id)
            DO UPDATE SET status = 'SUCCESS', finished_at = NOW();
        """,
        trigger_rule=TriggerRule.ALL_DONE,
    )

    # ------------------------------------------------------------------
    # Dependency chain
    # ------------------------------------------------------------------
    (
        check_landing
        >> validate_schema
        >> spark_transform
        >> recreate_view
        >> export_csv
        >> archive_files
        >> log_run
    )
