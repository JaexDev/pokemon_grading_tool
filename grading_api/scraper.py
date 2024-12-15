from bs4 import BeautifulSoup
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from concurrent.futures import ThreadPoolExecutor, as_completed
import functools
from datetime import datetime, timedelta
import aiohttp
import asyncio
from ratelimit import limits, sleep_and_retry

ONE_MINUTE = 60
MAX_REQUESTS_PER_MINUTE = 30

# Cache decorator
def cache_results(func):
    cache = {}
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key = str(args) + str(kwargs)
        now = datetime.now()
        
        if key in cache:
            result, timestamp = cache[key]
            if now - timestamp < timedelta(hours=24): 
                return result
                
        result = func(*args, **kwargs)
        if result:
            cache[key] = (result, now)
        return result
        
    return wrapper

@sleep_and_retry
@limits(calls=MAX_REQUESTS_PER_MINUTE, period=ONE_MINUTE)
@cache_results
def get_tcgplayer_data(card_name, set_name, language="English", driver=None, max_retries=3):
    """
    Retrieves price data for a Pokémon card from TCGPlayer using Selenium.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
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
        raise ValueError("language needs to be English or Japanese")

    all_card_data = []
    
    base_url = "https://www.tcgplayer.com/search/pokemon"

    should_quit_driver = False
    if driver is None:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        webdriver_service = Service('C:/Users/ASUS/Downloads/IT-STUFF/self-learn/chromedriver.exe')
        driver = webdriver.Chrome(service=webdriver_service, options=chrome_options)
        should_quit_driver = True

    try:
        for rarity in rarities:
            retry_count = 0
            while retry_count < max_retries:
                try:
                    if language == "English":
                        url = f"{base_url}/product?productLineName=pokemon&q={card_name.replace(' ', '+')}&view=grid&page=1&ProductTypeName=Cards&Rarity={rarity.replace(' ', '+')}"
                        if set_name:
                            url = f"{base_url}/{set_name.replace(' ','-').lower()}?productLineName=pokemon&q={card_name.replace(' ', '+')}&view=grid&page=1&ProductTypeName=Cards&Rarity={rarity.replace(' ', '+')}&setName={set_name.replace(' ','-').lower()}"
                    else:
                        url = f"{base_url}-japan/product?productLineName=pokemon-japan&q={card_name.replace(' ', '+')}&view=grid&page=1&ProductTypeName=Cards&Rarity={rarity.replace(' ', '+')}"
                        if set_name:
                            url = f"{base_url}-japan/{set_name.replace(' ','-').lower()}?productLineName=pokemon-japan&q={card_name.replace(' ', '+')}&view=grid&page=1&Rarity={rarity.replace(' ', '+')}&setName={set_name.replace(' ','-').lower()}"

                    print(f"Fetching URL with Selenium: {url}")
                    driver.get(url)
                    wait = WebDriverWait(driver, 10)
                    wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'search-result')))

                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    card_elements = soup.find_all('div', class_='search-result')
                    
                    if not card_elements:
                        print(f"Could not find card elements for {url}")
                        retry_count += 1
                        if retry_count == max_retries:
                            print(f"Max retries reached for rarity {rarity}")
                        continue

                    print(f"Found {len(card_elements)} card elements for {url}")
                    
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
                            rarity = rarity_spans[0].text.strip().replace(",", "") if rarity_spans and len(rarity_spans)>0 else None
                            
                            try:
                                price = float(price_text.replace('$', '')) if price_text else None
                            except (ValueError, AttributeError):
                                price = None

                            print(f"Card Title: {card_title}, Price: {price}, Rarity: {rarity}")
                            if card_title and price and card_name.lower() in card_title.lower() and rarity in rarities:
                                all_card_data.append({
                                    "card_name": card_title,
                                    "set_name": set_name,
                                    "language": language,
                                    "rarity": rarity,
                                    "tcgplayer_price": price
                                })
                        except Exception as e:
                            print(f"Error processing card element: {e}")
                            continue
                            
                    break

                except TimeoutException as e:
                    print(f"Timeout waiting for search results for {url}: {e}")
                    retry_count += 1
                    if retry_count == max_retries:
                        print(f"Max retries reached for rarity {rarity}")
                except Exception as e:
                    print(f"Unexpected error fetching data from TCGPlayer: {e}")
                    retry_count += 1
                    if retry_count == max_retries:
                        print(f"Max retries reached for rarity {rarity}")
                
    finally:
        if should_quit_driver and driver:
            driver.quit()
    
    return all_card_data if all_card_data else None

async def get_ebay_psa10_price_async(session, card_name, set_name):
    """
    Asynchronous version of eBay price fetching
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
            soup = BeautifulSoup(html, "html.parser")
            
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
                print(f"Average PSA 10 price found on eBay for {card_name} {set_name}: ${average_price}")
                return average_price
            return None

    except Exception as e:
        print(f"Error fetching data from eBay: {e}")
        return None

async def get_ebay_prices_async(cards):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for card in cards:
            task = asyncio.ensure_future(
                get_ebay_psa10_price_async(
                    session, 
                    card['card_name'], 
                    card['set_name']
                )
            )
            tasks.append(task)
        return await asyncio.gather(*tasks)

def calculate_profit(tcgplayer_data, ebay_price):
    """
    Calculates the profit potential of grading a card.
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
            print(f"Could not get ebay price, or tcgplayer price for {card.get('card_name')}")

    return all_profit_data

def fetch_all_data_concurrent(cards_to_fetch):
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_card = {
            executor.submit(get_tcgplayer_data, card['name'], card['set'], card.get('language', 'English')): card 
            for card in cards_to_fetch
        }
        
        results = []
        for future in as_completed(future_to_card):
            card = future_to_card[future]
            try:
                data = future.result()
                if data:
                    results.extend(data)
            except Exception as e:
                print(f"Error processing {card}: {e}")
    return results

def main_scrape(card_name, set_name, language="English"):
    cards_to_fetch = []
    cards_to_fetch.append({'name': card_name, 'set': set_name, 'language': language})
    
    tcgplayer_results = fetch_all_data_concurrent(cards_to_fetch)
    
    loop = asyncio.get_event_loop()
    ebay_prices = loop.run_until_complete(get_ebay_prices_async(tcgplayer_results))
    
    all_profit_data = []
    for card_data, ebay_price in zip(tcgplayer_results, ebay_prices):
        if ebay_price:
            profit_data = calculate_profit([card_data], ebay_price)
            if profit_data:
              for item in profit_data:
                 all_profit_data.append(item)
    return all_profit_data

if __name__ == '__main__':
    cards_to_fetch = [
        {'name': 'Charizard ex', 'set': 'Obsidian Flames', 'language': 'English'},
        {'name': 'Mew ex', 'set': 'Pokemon Card 151', 'language': 'Japanese'}
    ]
    
    tcgplayer_results = fetch_all_data_concurrent(cards_to_fetch)
    
    loop = asyncio.get_event_loop()
    ebay_prices = loop.run_until_complete(get_ebay_prices_async(tcgplayer_results))
    
    for card_data, ebay_price in zip(tcgplayer_results, ebay_prices):
        if ebay_price:
            profit_data = calculate_profit([card_data], ebay_price)
            print(f"{card_data['language']} DATA")
            for item in profit_data:
                print(item)