import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

def get_tcgplayer_data(card_name, set_name, language="English"):
    """
    Retrieves price data for a Pokémon card from TCGPlayer using Selenium.

    Args:
    card_name (str): The name of the card.
    set_name (str): The name of the set.
    language (str): The language of the card (English or Japanese)

    Returns:
        dict: A dictionary containing the card name, set, and prices in the given rarities
             or None if an error occurs
    """
    # Define headers for the request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    # Define base URL for TCGPlayer search
    base_url = "https://www.tcgplayer.com/search/pokemon"

    # Set up the language based on the parameters
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
    
    # Set up Selenium webdriver options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu") # Disable gpu for headless mode
    chrome_options.add_argument("--no-sandbox")  # Bypass OS security model
    
    # Set up web driver service
    # TODO: CHANGE THIS TO THE CORRECT PATH OF YOUR WEB DRIVER
    webdriver_service = Service('C:/Users/ASUS/Downloads/IT-STUFF/self-learn/chromedriver.exe')
    
    
    for rarity in rarities:
        # Construct the URL based on the language
        if language == "English":
            url = f"{base_url}/{set_name.replace(' ','-').lower()}?view=grid&productLineName=pokemon&setName={set_name.replace(' ','-').lower()}&Rarity={rarity.replace(' ','+')}&page=1"
        else:
            url = f"{base_url}-japan/{set_name.replace(' ','-').lower()}?view=grid&productLineName=pokemon-japan&page=1&setName={set_name.replace(' ','-').lower()}&Rarity={rarity.replace(' ','+')}"

        try:
            print(f"Fetching URL with Selenium: {url}")
            driver = webdriver.Chrome(service=webdriver_service, options=chrome_options)
            driver.get(url)

             # Wait for the search results to load (adjust timeout if needed)
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'search-result')))


            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # Find all product listings
            card_elements = soup.find_all('div', class_='search-result')
            
            if not card_elements:
                print(f"Could not find card elements for {url}")
                driver.quit()
                continue

            print(f"Found {len(card_elements)} card elements for {url}")
            
            for card in card_elements:
                #get the card title. The CSS selector might need to change in the future
                card_title_element = card.find('span', class_='product-card__title')
                card_title = card_title_element.text.strip() if card_title_element else None

                #get the card price. The CSS selector might need to change in the future
                price_element = card.find('span', class_='product-card__market-price--value')
                price_text = price_element.text.strip() if price_element else None

                set_name_element = card.find('h4', class_='product-card__set-name')
                set_name = set_name_element.text.strip() if set_name_element else None

                try:
                    price = float(price_text.replace('$', '')) if price_text else None
                except (ValueError, AttributeError):
                     price = None


                print(f"Card Title: {card_title}, Price: {price}")
                if card_title and price and card_name.lower() in card_title.lower():
                  all_card_data.append({
                      "card_name": card_title,
                      "set_name": set_name,
                      "language": language,
                      "rarity": rarity,
                      "tcgplayer_price": price
                    })

        except TimeoutException as e:
            print(f"Timeout waiting for search results for {url}: {e}")
        except Exception as e:
            print(f"Unexpected error fetching data from TCGPlayer: {e}")
        finally:
            if 'driver' in locals() and driver:
              driver.quit() # Close the webdriver after completing
            time.sleep(random.uniform(0.5, 1.5))

    return all_card_data if all_card_data else None
    
def get_ebay_psa10_price(card_name, set_name):
    """
    Retrieves the average price of a PSA 10 graded Pokémon card from eBay sold listings.

    Args:
    card_name (str): The name of the card.
    set_name (str): The name of the set.

    Returns:
        float: The average sold price of the card in PSA 10 condition, or None if not found.
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
        print(f"Fetching eBay URL: {base_url} with params: {params}")
        response = requests.get(base_url, params=params)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Find the list of sold items (this may change)
        sold_items = soup.find_all("li", class_="s-item s-item__pl-on-bottom")
        
        prices = []
        for item in sold_items:
            price_span = item.find("span", class_="s-item__price")
            
            if price_span:
                price_text = price_span.text.strip()
                # Extract the numeric part of the price (remove the $ sign)
                price_match = re.search(r'\$([\d.]+)', price_text)
                if price_match:
                    price = float(price_match.group(1))
                    prices.append(price)

        if prices:
            average_price = sum(prices) / len(prices)  # Calculate the average
            print(f"Average PSA 10 price found on eBay for {card_name} {set_name}: ${average_price}")
            return average_price
        else:
            print(f"Could not find PSA 10 prices for {card_name} {set_name}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from eBay: {e}")
        return None
    time.sleep(random.uniform(0.5, 1.5))  # Respectful delay


def calculate_profit(tcgplayer_data, ebay_price):
    """
    Calculates the profit potential of grading a card.

    Args:
        tcgplayer_data: A list of dictionaries of TCGPlayer data.
        ebay_price (float): The average PSA 10 price from eBay.

    Returns:
        list: A list of dictionaries with profit data
    """
    all_profit_data = []
    for card in tcgplayer_data:
      ungraded_price = card.get("tcgplayer_price")

      if ungraded_price and ebay_price:
        price_delta = ebay_price - ungraded_price
        profit_potential = (price_delta) / ungraded_price - 1
        card["psa_10_price"] = ebay_price
        card["price_delta"] = price_delta
        card["profit_potential"] = profit_potential
        all_profit_data.append(card)
      else:
        print(f"Could not get ebay price, or tcgplayer price for {card.get('card_name')}")

    return all_profit_data
  

if __name__ == '__main__':
    # Example usage:
    # English example
    card_name_en = "Charizard ex"
    set_name_en = "Obsidian Flames"
    
    #japanese example
    card_name_jp = "Mew ex"
    set_name_jp = "Pokemon Card 151"

    #English
    tcgplayer_data_en = get_tcgplayer_data(card_name_en, set_name_en)
    if tcgplayer_data_en:
       for card in tcgplayer_data_en:
            ebay_price_en = get_ebay_psa10_price(card.get("card_name"), card.get("set_name"))
            if ebay_price_en:
                profit_data = calculate_profit([card], ebay_price_en)
                print("ENGLISH DATA")
                for item in profit_data:
                    print(item)
    else:
        print("Could not get TCG Player Data")

    #Japanese
    tcgplayer_data_jp = get_tcgplayer_data(card_name_jp, set_name_jp, language = "Japanese")
    if tcgplayer_data_jp:
        for card in tcgplayer_data_jp:
            ebay_price_jp = get_ebay_psa10_price(card.get("card_name"), card.get("set_name"))
            if ebay_price_jp:
                profit_data = calculate_profit([card], ebay_price_jp)
                print("JAPANESE DATA")
                for item in profit_data:
                    print(item)

    else:
        print("Could not get TCG Player Data")