import json
import sqlite3
import time

import pandas as pd
import pytest

from src.data.clean import run_cleaning_pipeline
from src.database import get_resolved_db_path, init_db
from src.scraper.phase1_urls import discover_selected
from src.scraper.phase2_data import extract_pages
from src.utils.logger import get_logger

logger = get_logger("tests")


@pytest.fixture(scope="class")
def shared_db(request):
    """Creates a DB once per test class, yields it, then deletes it at the very end."""
    db_file = "test.db"

    resolved_path = get_resolved_db_path(db_file)

    # Clean up before starting just in case a previous test crashed
    if resolved_path.exists():
        resolved_path.unlink()

    init_db(db_path=db_file)

    conn = sqlite3.connect(resolved_path)
    request.cls.conn = conn

    yield db_file

    try:
        request.cls.conn.close()
    except Exception:
        pass

    for _ in range(5):
        time.sleep(0.2)
        try:
            resolved_path.unlink(missing_ok=True)
            break
        except PermissionError:
            pass


@pytest.mark.smoke
class TestScraperPhase:
    @pytest.mark.asyncio
    async def test_1_scrape_and_save_urls(self, shared_db):
        """Test 1: Actually scrape the site and populate the DB."""
        await discover_selected(pages=1, db_path=shared_db)

        cursor = self.conn.cursor()
        cursor.execute("SELECT url FROM cars")
        url = cursor.fetchone()[0]

        assert url.startswith("https://"), f"URL does not start with https://: {url}"

        assert "otomoto.pl/osobowe/oferta/" in url, (
            f"URL is not a valid Otomoto offer: {url}"
        )

    @pytest.mark.asyncio
    async def test_2_scrape_data_from_urls(self, shared_db):
        await extract_pages(limit=1, db_path=shared_db)
        cursor = self.conn.cursor()
        cursor.execute("SELECT raw_json, status FROM cars")
        row = cursor.fetchone()

        data = json.loads(row[0])
        status = row[1]

        assert data.get("price") is not None
        assert data.get("year") is not None
        assert status == "done"

    def test_clean_cars(self, tmp_path, shared_db):
        db_path = tmp_path / "test_cars_clean.db"

        resolved_in = get_resolved_db_path(shared_db)
        resolved_out = get_resolved_db_path(db_path)

        run_cleaning_pipeline(resolved_in, resolved_out)

        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql("SELECT price FROM cars_cleaned", conn)

        price_numeric = pd.to_numeric(df["price"], errors="coerce")
        assert price_numeric.notna().all(), (
            f"Some price values could not be converted to numeric: "
            f"{df['price'][price_numeric.isna()].tolist()}"
        )
