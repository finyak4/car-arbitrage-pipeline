import asyncio
from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from src.config import settings
from src.data.clean import run_cleaning_pipeline
from src.database import get_resolved_db_path
from src.database import init_db as db_init
from src.scraper.phase1_urls import discover_selected
from src.scraper.phase2_data import extract_pages
from src.utils.logger import get_logger

logger = get_logger("cli")

app = typer.Typer(
    help="CLI tool for Otomoto scraper and ML data pipeline.",
    add_completion=False,
)


@app.command(name="init_db")
def init_db(
    db_path: Annotated[
        Path, typer.Option("--db-name", "-d", help="SQLite database file name")
    ] = settings.db_path,
):
    """Initializes the SQLite database tables."""
    logger.info(f"🔧 Initializing database '{db_path}'...")
    db_init(db_path=db_path)
    logger.info("Database initialized and ready!")


@app.command(name="discover")
def discover(
    pages: Annotated[
        int, typer.Option("--pages", "-p", min=1, max=500, help="Total pages to scrape")
    ] = settings.discovery_pages,
    db_path: Annotated[
        Path, typer.Option("--db-name", "-d", help="Database to store discovered URLs")
    ] = settings.db_path,
):
    """Phase 1: Discover car listing URLs and save them to SQLite."""
    logger.info(f"🚀 Starting Phase 1 Discovery: across {pages} pages...")

    asyncio.run(discover_selected(pages=pages, db_path=db_path))
    logger.info("🎉 Discovery phase finished!")


@app.command(name="retrieve_data")
def retrieve_data(
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", min=1, max=10000, help="Total URLs to scrape"),
    ] = settings.retrieve_pages,
    db_path: Annotated[
        Path, typer.Option("--db-name", "-d", help="Database to store discovered URLs")
    ] = settings.db_path,
):
    """Phase 2: Retrieve car listing data from discovered URLs and save it to SQLite."""
    logger.info(f"🚀 Starting Phase 2 Retrieval: across {limit} URLs...")

    asyncio.run(extract_pages(limit=limit, db_path=db_path))
    logger.info("🎉 Retreival phase finished!")


@app.command(name="clean_data")
def clean_data(
    db_path: Annotated[
        Path, typer.Option("--db-name", "-d", help="Database to store discovered URLs")
    ] = settings.db_path,
    output_db: Annotated[
        Path, typer.Option("--db-store", "-ds", help="Database to store cleaned Data")
    ] = settings.db_out_path,
    date_for_data: Annotated[
        str | None,
        typer.Option(
            "--date",
            help="Filter by scrape date (YYYY-MM-DD). If omitted, processes all 'done' cars.",
        ),
    ] = settings.date_for_data,
):
    """Clean raw JSON records into structured tabular format."""
    logger.info("Cleaning data ...")
    filter_date: date | None = (
        date.fromisoformat(date_for_data) if date_for_data else None
    )

    resolved_in = get_resolved_db_path(db_path)
    resolved_out = get_resolved_db_path(output_db)

    run_cleaning_pipeline(resolved_in, resolved_out, filter_date)
    logger.info("Cleaning Finished")


if __name__ == "__main__":
    app()
