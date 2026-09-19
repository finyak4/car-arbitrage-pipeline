import os
import sqlite3
from datetime import date
from pathlib import Path

import mlflow
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger("predict")

DATA_DIR = Path(os.getenv("APP_DIR", "."), "data")
data_csv = DATA_DIR / "mock_data.csv"
DEALS_DB = DATA_DIR / "selected_deals.db"

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow-server:5000")


def score_and_filter_deals(mock_foreign_df: pd.DataFrame) -> pd.DataFrame:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    model_uri = "models:/car-price-xgb_v0.1/2"
    logger.info("Loading model from URI: %s", model_uri)
    model = mlflow.pyfunc.load_model(model_uri)

    logger.info("Predicting Polish market prices for %d rows", len(mock_foreign_df))
    mock_foreign_df["predicted_pln"] = model.predict(mock_foreign_df)

    mock_foreign_df["margin_pct"] = (
        mock_foreign_df["predicted_pln"] - mock_foreign_df["price"]
    ) / mock_foreign_df["price"]

    # Filter deals with > 15% profit margin
    great_deals = mock_foreign_df[mock_foreign_df["margin_pct"] > 0.15]
    logger.info(
        "Filtering complete — %d/%d deals exceed 15%% margin",
        len(great_deals),
        len(mock_foreign_df),
    )
    return great_deals


def save_deals_to_db(deals: pd.DataFrame, db_path: Path = DEALS_DB) -> int:
    """Upsert *deals* into the selected_deals SQLite table.

    Uses ``url`` as the PRIMARY KEY — re-running the script will update an
    existing row instead of inserting a duplicate. Each row is also stamped
    with ``date_added`` (today's ISO date).

    Returns the number of rows written.
    """
    if deals.empty:
        logger.warning(
            "save_deals_to_db called with an empty DataFrame — nothing saved"
        )
        return 0

    # Stamp today's date on every row
    deals = deals.copy()
    deals["date_added"] = date.today().isoformat()

    all_cols = list(deals.columns)
    non_url_cols = [c for c in all_cols if c != "url"]
    columns_def = ", ".join([f'"{c}" TEXT' for c in non_url_cols])

    with sqlite3.connect(db_path) as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS selected_deals (
                "url" TEXT PRIMARY KEY,
                {columns_def}
            )
        """)

        # Stage into temp table then upsert — handles schema mismatches gracefully
        deals.to_sql("_staging_deals", conn, if_exists="replace", index=False)

        cols_sql = ", ".join([f'"{c}"' for c in all_cols])
        conn.execute(f"""
            INSERT OR REPLACE INTO selected_deals ({cols_sql})
            SELECT {cols_sql} FROM _staging_deals
        """)  # nosec B608
        conn.execute("DROP TABLE _staging_deals")

    logger.info("Saved %d deal(s) to %s", len(deals), db_path)
    return len(deals)


def get_mock_data() -> pd.DataFrame:
    df = pd.read_csv(data_csv)

    selected_deals = score_and_filter_deals(df)
    save_deals_to_db(selected_deals)

    return selected_deals
