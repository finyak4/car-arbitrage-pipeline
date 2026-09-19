import json
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(os.getenv("APP_DIR", "."), "data")


def get_resolved_db_path(db_name: str | Path) -> Path:
    """Resolve a relative DB path inside the configured data directory."""
    provided_path = Path(db_name)

    if provided_path.is_absolute():
        return provided_path
    else:
        return DATA_DIR / provided_path


def init_db(db_path="cars_data_pipeline.db"):
    """Creates the SQLite database and tables."""
    resolved_path = get_resolved_db_path(db_path)

    conn = sqlite3.connect(resolved_path)
    cursor = conn.cursor()

    # Create the table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cars (
        id INTEGER PRIMARY KEY,
        url TEXT UNIQUE,
        raw_json TEXT,
        status TEXT DEFAULT 'pending',
        date DATE DEFAULT CURRENT_DATE
    );
    """)

    conn.commit()
    conn.close()


def save_urls(urls: list[str], db_path="cars_data_pipeline.db"):
    """Saves discovered URLs to the database."""
    resolved_path = get_resolved_db_path(db_path)

    conn = sqlite3.connect(resolved_path)
    cursor = conn.cursor()

    # 'INSERT OR IGNORE' prevents duplicates automatically
    formatted_urls = [(url,) for url in urls]

    # SQL SYNTAX FIX: Added parentheses around (url)
    cursor.executemany("INSERT OR IGNORE INTO cars (url) VALUES (?)", formatted_urls)

    conn.commit()
    conn.close()


def save_data(
    data: dict | None, url: str, status: str = "Done", db_path="cars_data_pipeline.db"
):
    resolved_path = get_resolved_db_path(db_path)
    with sqlite3.connect(resolved_path) as conn:
        if data is None:
            conn.execute(
                """
                UPDATE cars
                SET status = ?,
                date = CURRENT_DATE
                WHERE url = ?
            """,
                (status, url),
            )
        else:
            conn.execute(
                """
                UPDATE cars
                SET raw_json = ?, status = ?, date = CURRENT_DATE
                WHERE url = ?
            """,
                (json.dumps(data), status, url),
            )
