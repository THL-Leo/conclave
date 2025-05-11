import requests
from bs4 import BeautifulSoup
import json
from pathlib import Path
from typing import List, Dict
import re

def extract_cardinals_from_wiki() -> List[Dict]:
    """
    Extract cardinal information from the Wikipedia article about the 2025 papal conclave.
    """
    url = "https://en.wikipedia.org/wiki/Cardinal_electors_in_the_2025_papal_conclave"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the main table containing cardinal information
        tables = soup.find_all('table', {'class': 'wikitable'})
        cardinals = []
        
        for table in tables:
            rows = table.find_all('tr')[1:]  # Skip header row
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 7:  # Ensure we have enough cells
                    # Extract name and link
                    name_cell = cells[1]
                    name_link = name_cell.find('a')
                    if name_link:
                        name = name_link.get_text(strip=True)
                        wiki_url = f"https://en.wikipedia.org{name_link['href']}"
                        
                        # Extract country
                        country_cell = cells[2]
                        country_link = country_cell.find('a')
                        country = country_link.get_text(strip=True) if country_link else country_cell.get_text(strip=True)
                        
                        # Extract role/office
                        role = cells[6].get_text(strip=True)
                        
                        # Extract order (CB, CP, or CD)
                        order_cell = cells[4]
                        order_link = order_cell.find('a')
                        order = order_link.get_text(strip=True) if order_link else order_cell.get_text(strip=True)
                        
                        cardinal_data = {
                            "name": name,
                            "country": country,
                            "role": role,
                            "order": order,
                            "wiki_url": wiki_url
                        }
                        
                        cardinals.append(cardinal_data)
        
        return cardinals
        
    except Exception as e:
        print(f"Error extracting cardinals from Wikipedia: {e}")
        return []

def save_cardinal_list(cardinals: List[Dict], output_file: str = "data/cardinal_list.json"):
    """
    Save the extracted cardinal list to a JSON file.
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cardinals, f, indent=2)
    
    print(f"Saved {len(cardinals)} cardinals to {output_file}")

def main():
    # Extract cardinals from Wikipedia
    cardinals = extract_cardinals_from_wiki()
    
    if cardinals:
        # Save the cardinal list
        save_cardinal_list(cardinals)
        
        # Print summary
        print("\nCardinal Summary:")
        print(f"Total cardinals extracted: {len(cardinals)}")
        
        # Count by order
        orders = {}
        for cardinal in cardinals:
            order = cardinal['order']
            orders[order] = orders.get(order, 0) + 1
        
        print("\nCardinals by order:")
        for order, count in orders.items():
            print(f"{order}: {count}")
        
        # Count by country
        countries = {}
        for cardinal in cardinals:
            country = cardinal['country']
            countries[country] = countries.get(country, 0) + 1
        
        print("\nTop 10 countries by number of cardinals:")
        sorted_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)
        for country, count in sorted_countries[:10]:
            print(f"{country}: {count}")
    
if __name__ == "__main__":
    main() 