import asyncio
import random

from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from tqdm import tqdm

from src.database import save_urls
from src.utils.logger import get_logger

logger = get_logger("scraper_ph1")

MAIN_URL_START = "https://www.otomoto.pl/osobowe/toyota/avensis--avensis-verso--c-hr--c-hr-plus--camry--corolla--corolla-cross--corolla-verso--land-cruiser--proace--proace-city--proace-city-verso--proace-verso"
MAIN_URL_END = "&search%5Bmake_model_generation%5D%5B0%5D=toyota%7Cavensis&search%5Bmake_model_generation%5D%5B10%5D=toyota%7Cproace-city&search%5Bmake_model_generation%5D%5B11%5D=toyota%7Cproace-city-verso&search%5Bmake_model_generation%5D%5B12%5D=toyota%7Cproace-verso&search%5Bmake_model_generation%5D%5B1%5D=toyota%7Cavensis-verso&search%5Bmake_model_generation%5D%5B2%5D=toyota%7Cc-hr&search%5Bmake_model_generation%5D%5B3%5D=toyota%7Cc-hr-plus&search%5Bmake_model_generation%5D%5B4%5D=toyota%7Ccamry&search%5Bmake_model_generation%5D%5B5%5D=toyota%7Ccorolla&search%5Bmake_model_generation%5D%5B6%5D=toyota%7Ccorolla-cross&search%5Bmake_model_generation%5D%5B7%5D=toyota%7Ccorolla-verso&search%5Bmake_model_generation%5D%5B8%5D=toyota%7Cland-cruiser&search%5Bmake_model_generation%5D%5B9%5D=toyota%7Cproace"


async def discover_selected(pages, db_path=None):
    total_found = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        page = await context.new_page()

        stealth = Stealth()

        await stealth.apply_stealth_async(page)

        # PAGINATION LOOP
        logger.info("Start Scraping urls")
        for current_page in tqdm(range(1, pages + 1)):
            try:
                target_url = f"{MAIN_URL_START}?page={current_page}{MAIN_URL_END}"

                # 60-second timeout just in case the network is slow
                await page.goto(target_url, timeout=60000)

                car_link_locator = page.locator('a[href*="/osobowe/oferta/"]')

                try:
                    await car_link_locator.first.wait_for(
                        state="attached", timeout=15000
                    )
                except Exception:
                    logger.warning("No cars found on page.")

                    await page.screenshot(path=f"error_page_{current_page}.png")
                    continue

                car_urls = await page.evaluate("""
                    () => {
                        const links = document.querySelectorAll('a[href*="/osobowe/oferta/"]');
                        const uniqueLinks = new Set();
                        links.forEach(a => {
                            if (a.href) {
                                const cleanUrl = a.href.split('?')[0];
                                uniqueLinks.add(cleanUrl);
                            }
                        });
                        return Array.from(uniqueLinks);
                    }
                """)

                if car_urls:
                    save_urls(urls=car_urls, db_path=db_path)
                    total_found += len(car_urls)

            except Exception as e:
                logger.warning(
                    f"ERROR on page {current_page}. Skipping to next page. Details: {e}"
                )

            finally:
                delay = random.uniform(3.5, 4.5)
                await asyncio.sleep(delay)

        await browser.close()
    logger.info(f"URL discovery finished. Found {total_found} URLs.")
