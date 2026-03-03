from app.logic.scraper import parse_scraped_bill
from bs4 import BeautifulSoup

with open("mepco_result.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

data = parse_scraped_bill(soup, "05151280432603")
print("Parsed data:", data)
