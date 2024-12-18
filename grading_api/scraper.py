from playwright.async_api import async_playwright
import asyncio
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import aiohttp
from ratelimit import limits, sleep_and_retry
import functools
import logging
import time


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

ONE_MINUTE = 60
MAX_REQUESTS_PER_MINUTE_TCG = 30
MAX_REQUESTS_PER_MINUTE_EBAY = 20  # Add rate limiting for eBay

def cache_results(func):
    cache = {}

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        key = str(args) + str(kwargs)
        now = datetime.now()

        if key in cache:
            result, timestamp = cache[key]
            if now - timestamp < timedelta(hours=24):
                logging.info(f"Returning cached result for {key}")
                return result

        result = await func(*args, **kwargs)
        if result:
            cache[key] = (result, now)
        return result

    return wrapper

@sleep_and_retry
@limits(calls=MAX_REQUESTS_PER_MINUTE_TCG, period=ONE_MINUTE)
async def fetch_tcgplayer_data(card_name, set_name, language="English", context=None):
    """
    Retrieves price data for a card from TCGPlayer using Playwright.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }

    if language == "English":
        rarities = [
            "Special Illustration Rare",
            "Illustration Rare",
            "Hyper Rare"
        ]
    elif language == "Japanese":
        rarities = [
            "Art Rare",
            "Super Rare",
            "Special Art Rare",
            "Ultra Rare"
        ]
    else:
        raise ValueError("Language must be English or Japanese")

    base_url = "https://www.tcgplayer.com/search/pokemon"
    all_card_data = []

    page = await context.new_page()

    await page.route("**/*.{png,jpg,jpeg}", lambda route: route.abort())

    for rarity in rarities:
        try:
            if language == "English":
                url = f"{base_url}/product?productLineName=pokemon&q={card_name.replace(' ', '+')}&view=grid&page=1&ProductTypeName=Cards&Rarity={rarity.replace(' ', '+')}"
                if set_name and set_name.lower() != card_name.lower():
                    url += f"&setName={set_name.replace(' ', '-').lower()}"
            else:
                url = f"{base_url}-japan/product?productLineName=pokemon-japan&q={card_name.replace(' ', '+')}&view=grid&page=1&ProductTypeName=Cards&Rarity={rarity.replace(' ', '+')}"
                if set_name and set_name.lower() != card_name.lower():
                    url += f"&setName={set_name.replace(' ', '-').lower()}"

            retries = 0
            max_retries = 3
            while retries < max_retries:
                try:
                    logging.info(f"Attempt {retries + 1}/{max_retries}: Fetching URL: {url}")
                    await page.goto(url, timeout=20000, wait_until="domcontentloaded")

                    try:
                        await asyncio.wait_for(
                            page.wait_for_selector(
                                ".search-result, .blank-slate", state="visible", timeout=10000
                            ),
                            timeout=10,
                        )
                    except asyncio.TimeoutError:
                        logging.warning("Neither .search-result nor .blank-slate found within timeout")

                    if await page.query_selector('.search-result'):
                        break
                    else:
                        logging.warning("No results found on page")
                        break

                except Exception as e:
                    logging.error(f"Error during page navigation: {e}")

                retries += 1
                if retries < max_retries:
                    await asyncio.sleep(2**(retries + 1))  # Exponential backoff
                else:
                    logging.error("Max retries reached. Stopping.")
                    return []

            html = await page.content()
            soup = BeautifulSoup(html, 'lxml')  # Use lxml parser
            card_elements = soup.find_all('div', class_='search-result')

            for card in card_elements:
                try:
                    card_title_element = card.find('span', class_='product-card__title')
                    card_title = card_title_element.text.strip() if card_title_element else None

                    price_element = card.find('span', class_='product-card__market-price--value')
                    price_text = price_element.text.strip() if price_element else None

                    set_name_element = card.find('div', class_='product-card__set-name__variant')
                    set_name = set_name_element.text.strip() if set_name_element else None

                    rarity_element = card.find('div', class_="product-card__rarity__variant")
                    rarity_spans = rarity_element.find_all('span') if rarity_element else None
                    rarity = rarity_spans[0].text.strip().replace(",", "") if rarity_spans and len(rarity_spans) > 0 else None

                    try:
                        price = float(price_text.replace('$', '')) if price_text else None
                    except (ValueError, AttributeError):
                        price = None

                    if card_title and price and card_name.lower() in card_title.lower() and rarity in rarities:
                        all_card_data.append({
                            "card_name": card_title,
                            "set_name": set_name,
                            "language": language,
                            "rarity": rarity,
                            "tcgplayer_price": price
                        })
                except Exception as e:
                    logging.error(f"Error processing card element: {e}")
                    continue

        except Exception as e:
            logging.error(f"Error fetching data for rarity {rarity}: {e}")

    await page.close()
    return all_card_data

@sleep_and_retry
@limits(calls=MAX_REQUESTS_PER_MINUTE_EBAY, period=ONE_MINUTE)
async def get_ebay_psa10_price_async(session, card_name, set_name):
    """
    Asynchronous eBay price fetching with rate limiting.
    """
    base_url = "https://www.ebay.com/sch/i.html"
    search_query = f"{card_name} {set_name} psa 10"
    params = {
        "_nkw": search_query,
        "_sacat": 0,
        "_from": "R40",
        "rt": "nc",
        "LH_Sold": 1,
        "LH_Complete": 1
    }

    try:
        async with session.get(base_url, params=params) as response:
            html = await response.text()
            soup = BeautifulSoup(html, "lxml")

            sold_items = soup.find_all("li", class_="s-item s-item__pl-on-bottom")
            prices = []

            for item in sold_items:
                price_span = item.find("span", class_="s-item__price")
                if price_span:
                    price_text = price_span.text.strip()
                    price_match = re.search(r'\$([\d.]+)', price_text)
                    if price_match:
                        price = float(price_match.group(1))
                        prices.append(price)

            if prices:
                average_price = sum(prices) / len(prices)
                logging.info(f"Average PSA 10 price on eBay for {card_name} {set_name}: ${average_price}")
                return average_price
            return None

    except Exception as e:
        logging.error(f"Error fetching eBay data: {e}")
        return None

async def get_ebay_prices_async(session, cards):
    """
    Fetches eBay prices concurrently with a shared session.
    """
    tasks = [
        get_ebay_psa10_price_async(session, card['card_name'], card['set_name'])
        for card in cards
    ]
    return await asyncio.gather(*tasks)

def calculate_profit(tcgplayer_data, ebay_price):
    """
    Calculates profit potential for grading cards.
    """
    all_profit_data = []
    for card in tcgplayer_data:
        ungraded_price = card.get("tcgplayer_price")

        if ungraded_price and ebay_price:
            price_delta = ebay_price - ungraded_price
            profit_potential = (price_delta) / ungraded_price
            card["psa_10_price"] = ebay_price
            card["price_delta"] = price_delta
            card["profit_potential"] = profit_potential * 100
            all_profit_data.append(card)
        else:
            logging.warning(f"Could not get eBay price or TCGPlayer price for {card.get('card_name')}")

    return all_profit_data

async def main_scrape(card_name, set_name, language="English"):
    start_time = time.perf_counter()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=15)) as session:  # Add connection pooling
            tcgplayer_results = await fetch_tcgplayer_data(card_name, set_name, language, context)
            ebay_prices = await get_ebay_prices_async(session, tcgplayer_results)

            all_profit_data = []
            for card_data, ebay_price in zip(tcgplayer_results, ebay_prices):
                if ebay_price:
                    profit_data = calculate_profit([card_data], ebay_price)
                    if profit_data:
                        all_profit_data.extend(profit_data)

            await browser.close()
            end_time = time.perf_counter()  # Get the ending time
            elapsed_time = end_time - start_time

            print(f"Scraping completed in {elapsed_time:.2f} seconds")
            return all_profit_data

if __name__ == "__main__":
    cards_to_fetch = [
        {'name': 'Charizard ex', 'set': 'Obsidian Flames', 'language': 'English'},
        {'name': 'Mew ex', 'set': 'Pokemon Card 151', 'language': 'Japanese'}
    ]

    async def run_main():
        results = []
        for card in cards_to_fetch:
            result = await main_scrape(card['name'], card['set'], card['language'])
            results.append(result)
        
        # Flatten the list of lists if needed
        flat_results = [item for sublist in results for item in sublist]
        print(flat_results)

    asyncio.run(run_main())