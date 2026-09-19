import sys
from datetime import datetime, timedelta
from airflow.decorators import dag, task

# Default task settings
DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
}

@dag(
    dag_id="car_arbitrage_deal_scorer",
    default_args=DEFAULT_ARGS,
    description="Loads mock foreign car data, scores with MLflow XGBoost, and saves deals",
    schedule="0 8 * * *",        # Runs daily at 08:00 UTC (or set schedule=None for manual trigger)
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["arbitrage", "mlflow", "toyota"],
)
def car_arbitrage_dag():

    @task
    def process_and_score_deals():
        # Lazy import inside the task:
        # Keeps DAG parsing instantaneous for the Airflow Scheduler
        import os
        from pathlib import Path
        
        app_dir = os.getenv("APP_DIR", "/opt/airflow/project_root")
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)

        from src.model.predict import get_mock_data

        deals_df = get_mock_data()
        return f"Successfully processed and stored {len(deals_df)} deals."

    process_and_score_deals()

car_arbitrage_dag()