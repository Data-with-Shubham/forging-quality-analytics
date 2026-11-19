"""Airflow DAG: nightly forging quality pipeline.
Copy this file into your Airflow `dags/` folder and set PROJECT_DIR below."""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = "/opt/airflow/forging-quality-analytics"  # <- change to your path

default_args = {
    "owner": "data-qms",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="forging_quality_pipeline",
    description="Validate and load forging inspection data, then refresh KPI exports",
    default_args=default_args,
    start_date=datetime(2025, 10, 1),
    schedule="0 1 * * *",  # every night at 01:00
    catchup=False,
    tags=["qms", "forging"],
) as dag:

    etl = BashOperator(
        task_id="validate_and_load",
        bash_command=f"cd {PROJECT_DIR}/src && python etl.py",
    )

    kpis = BashOperator(
        task_id="refresh_kpi_exports",
        bash_command=f"cd {PROJECT_DIR}/src && python kpis.py",
    )

    etl >> kpis
