"""Offers on a Cardmarket card that sit below its price trend, written to CSV.

    SCRAPEDO_TOKEN=... python examples/below_trend.py https://www.cardmarket.com/en/Magic/Products/Singles/The-Lord-of-the-Rings-Tales-of-Middle-earth/The-One-Ring
"""

import csv
import sys

from cardmarket_scraper import Cardmarket

url = sys.argv[1] if len(sys.argv) > 1 else \
    "https://www.cardmarket.com/en/Magic/Products/Singles/The-Lord-of-the-Rings-Tales-of-Middle-earth/The-One-Ring"

card = Cardmarket().product(url)
trend = card.price_trend
cheap = [o for o in card.offers if trend and o.price is not None and o.price < trend]

with open("below_trend.csv", "w", newline="", encoding="utf-8") as fh:
    writer = csv.writer(fh)
    writer.writerow(["price", "below_trend_pct", "condition", "language", "foil", "location", "quantity"])
    for o in cheap:
        writer.writerow([o.price, round(100 * (trend - o.price) / trend, 1), o.condition, o.language, o.foil, o.location, o.quantity])

print(f"{card.name}: trend {trend} EUR, from {card.from_price} EUR")
print(f"{len(cheap)} of the {len(card.offers)} cheapest offers are below the trend -> below_trend.csv")
