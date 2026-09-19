import json
import re
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger("clean_pipeline")

NUMERIC_CONVERT_COLS = ["number_engines", "year", "nr_seats", "door_count"]
NUMERIC_CLEAN_COLS = [
    "price",
    "system_performance_of_hybrid_driveline_in_hp",
    "electric_power_peak",
    "mileage",
    "engine_power",
    "engine_capacity",
]


def clean_numeric_strings(df: pd.DataFrame, feature_list: list[str]) -> pd.DataFrame:
    """Strips currency symbols, spaces, and text, converting to numeric."""
    for col in feature_list:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r"[^\d]", "", regex=True)
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def convert_to_numeric(df: pd.DataFrame, feature_list: list[str]) -> pd.DataFrame:
    """Converts string numbers ('5', '2018') into integer/float types."""
    for col in feature_list:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


TOYOTA_TRIMS_ORDERED = [
    # Special / Performance editions
    "GR SPORT",
    "GR-SPORT",
    "ADVENTURE",
    "CROSS",
    "PREMIERE EDITION",
    # High trims & packages
    "SELECTION VIP",
    "SELECTION STYLE",
    "SELECTION CHROME",
    "SELECTION",
    "EXECUTIVE",
    "PRESTIGE",
    "DYNAMIC",
    "PLATINUM",
    # Mid trims
    "STYLE",
    "COMFORT",
    "BUSINESS",
    "PREMIUM",
    # Entry / Legacy trims
    "ACTIVE",
    "LIFE",
    "LUNA",
    "SOL",
    "TERRA",
]


def extract_trim(version_str: str) -> str:
    """
    Extracts standardized Toyota trim level from unstructured version string.
    Returns 'Standard/Unknown' if no matching trim keyword is found.
    """
    if pd.isna(version_str):
        return "Standard/Unknown"

    # Normalize: uppercase and collapse repeated whitespace
    text = re.sub(r"\s+", " ", str(version_str).upper()).strip()

    for trim in TOYOTA_TRIMS_ORDERED:
        pattern = r"\b" + re.escape(trim) + r"\b"
        if re.search(pattern, text):
            # Normalize variations like GR-SPORT -> GR Sport
            if trim in ["GR-SPORT", "GR SPORT"]:
                return "GR Sport"
            return trim.title()

    return "Standard/Unknown"


def filter_toyota_models(df: pd.DataFrame) -> pd.DataFrame:
    # strict list of allowed Toyota models
    allowed_toyotas = settings.allowed_toyotas

    df = df[df["model"].isin(allowed_toyotas)].reset_index(drop=True)

    return df


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Master cleaning function (Stateless).
    Turns raw bronze data into cleaned silver data.
    """
    df = filter_toyota_models(df)

    df = clean_numeric_strings(df, NUMERIC_CLEAN_COLS)
    df = convert_to_numeric(df, NUMERIC_CONVERT_COLS)

    # Drop rows without a target price
    df = df.dropna(subset=["price", "mileage"]).reset_index(drop=True)

    # Drop non-generalizable metadata
    cols_to_drop = [c for c in ["registration", "date_registration"] if c in df.columns]
    df = df.drop(columns=cols_to_drop)

    # Create model_trim instead of messy model, version
    df["trim"] = df["version"].apply(extract_trim)
    df["model_trim"] = df["model"].astype(str) + "_" + df["trim"].astype(str)

    df = df.drop(columns=["version", "trim"])

    return df


def run_cleaning_pipeline(
    db_in_path: Path, db_out_path: Path, filter_date: date | None = None
):
    """ETL Pipeline: Extracts raw data, cleans it, and upserts it into the silver database."""

    logger.info(f"Reading raw data from '{db_in_path}'...")

    with sqlite3.connect(db_in_path) as conn:
        cursor = conn.cursor()

        query = "SELECT url, raw_json FROM cars WHERE status = 'done'"
        params = []
        if filter_date:
            query += " AND DATE(date) = ?"
            params.append(filter_date)
            logger.info(f"Applying filter: date = '{filter_date}'")

        rows = cursor.execute(query, tuple(params)).fetchall()

    if not rows:
        logger.error("⚠️ No matching scraped cars found in database!")
        return

    data = []
    for row in rows:
        car_url = row[0]
        car_dict = json.loads(row[1])
        car_dict["url"] = car_url
        data.append(car_dict)

    df_raw = pd.DataFrame(data)

    df = clean_dataframe(df_raw)

    if "equipment" in df.columns:
        df["equipment"] = df["equipment"].apply(
            lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else x
        )

    UNIQUE_ID_COLUMN = "url"

    with sqlite3.connect(db_out_path) as output_conn:
        output_cursor = output_conn.cursor()

        # Dynamically build the table schema based on Pandas columns
        columns_def = ", ".join(
            [f'"{col}" TEXT' for col in df.columns if col != UNIQUE_ID_COLUMN]
        )
        create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS cars_cleaned (
                "{UNIQUE_ID_COLUMN}" TEXT PRIMARY KEY,
                {columns_def}
            )
        """
        output_cursor.execute(create_table_sql)

        # Write to staging
        df.to_sql("staging_cars", output_conn, if_exists="replace", index=False)

        # Upsert into main table
        columns_list = ", ".join([f'"{col}"' for col in df.columns])
        upsert_sql = f"""
            INSERT OR REPLACE INTO cars_cleaned ({columns_list})
            SELECT {columns_list} FROM staging_cars
        """  # nosec B608
        output_cursor.execute(upsert_sql)
        output_cursor.execute("DROP TABLE staging_cars")
        output_conn.commit()

    logger.info(f"✅ Cleaned {len(df)} rows successfully saved to '{db_out_path}'.")
