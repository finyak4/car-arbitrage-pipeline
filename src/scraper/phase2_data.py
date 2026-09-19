import asyncio
import random
import sqlite3

from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from tqdm import tqdm

from src.database import get_resolved_db_path, save_data
from src.utils.logger import get_logger

logger = get_logger("scraper_ph2")


async def extract_data(page_url, page):
    try:
        await page.goto(page_url, timeout=60000)
    except Exception:
        logger.warning("Did not reach the page")
        return {"status": "error", "message": "Did not reach the page"}

    find_vehicle_locator = page.locator('img[alt="find-vehicle"]')
    if await find_vehicle_locator.is_visible():
        logger.info("Not Available")
        return {"status": "not_available"}

    page_data = await page.evaluate("""
        () => {
            const fields = ["model","version","color","door_count","nr_seats","year","date_registration","fuel_type","engine_capacity","engine_power","body_type","gearbox","transmission","mileage","registration","new_used","has_registration","electric_power_peak","system_performance_of_hybrid_driveline_in_hp","number_engines"];

            const result = {};

            fields.forEach(field => {
                const element = document.querySelector(
                    `div[data-testid="${field}"] p[class="font-normal ooa-18oj254"]`
                );

                result[field] = element?.textContent.trim() ?? null;
            });

            return result;
        }
    """)

    price_data = await page.evaluate("""
        () => {
            const price = document.querySelector('div[class*="grid-area:price"] h3'); 
            return price.ariaLabel ?? null;
        }
    """)

    seller_data = await page.evaluate("""
        () => {
            const seller_type = document.querySelector('div[id="content-seller-area-section"] li p');
            return seller_type?.textContent.trim() ?? null;
        }
    """)

    equipment_data = await page.evaluate("""
        () => {
            const featureNodes = document.querySelectorAll('div[data-testid="content-equipments-section"] div.n-accordionitem-content p'); 
            // Note: Inspect the page to confirm the exact tag (it might be 'li' or a specific class)

            const features = new Set();
            featureNodes.forEach(node => {
                const text = node.textContent.trim();
                if (text) {
                    features.add(text);
                }
            });
            
            return Array.from(features);
        }
    """)

    page_data["price"] = price_data
    page_data["seller_type"] = seller_data
    page_data["equipment"] = equipment_data

    return {"status": "success", "data": page_data}


async def extract_pages(limit: int, db_path="cars_data_pipeline.db"):
    conn = sqlite3.connect(get_resolved_db_path(db_path))
    cursor = conn.cursor()

    urls = [
        row[0]
        for row in cursor.execute(
            "SELECT url FROM cars WHERE status='pending' LIMIT ?", (limit,)
        ).fetchall()
    ]
    conn.close()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        page = await context.new_page()

        stealth = Stealth()

        await stealth.apply_stealth_async(page)
        logger.info("Start Scraping data")
        consecutive_errors = 0
        for url in tqdm(urls):
            try:
                result = await extract_data(url, page)
                if result["status"] == "success":
                    save_data(
                        data=result["data"], url=url, status="done", db_path=db_path
                    )
                    consecutive_errors = 0
                elif result["status"] == "not_available":
                    save_data(
                        data=None, url=url, status="not_available", db_path=db_path
                    )
                elif result["status"] == "error":
                    save_data(data=result, url=url, status="error", db_path=db_path)
                    consecutive_errors += 1

            except Exception as e:
                logger.exception(f"Unexpected error scraping {url}: {e}")
                save_data(data=None, url=url, status="error", db_path=db_path)
                consecutive_errors += 1
            finally:
                delay = random.uniform(3.0, 4.0)
                await asyncio.sleep(delay)
            if consecutive_errors >= 10:
                logger.error("Stopping scraper: 10 consecutive URLs failed.")
                break
        logger.info(f"Scraping of {len(urls)} finished")
