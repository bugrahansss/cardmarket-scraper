# Cardmarket Scraper

[![PyPI](https://img.shields.io/pypi/v/cardmarket-scraper)](https://pypi.org/project/cardmarket-scraper/)
[![Python](https://img.shields.io/pypi/pyversions/cardmarket-scraper)](https://pypi.org/project/cardmarket-scraper/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Scrape [Cardmarket](https://www.cardmarket.com), Europe's biggest trading card marketplace, into structured data. List **every card in a set** (Magic, Pokémon, Yu-Gi-Oh!, Lorcana, One Piece, ...) with its **rarity, collector number, items available, lowest price and lowest foil price**. Open a card for its **price guide** (from, price trend, 30/7/1-day averages), the **30-day average sell price history** and the **50 cheapest offers** with condition, language, foil, seller country, price and quantity. JSON or CSV.

```bash
pip install cardmarket-scraper
export SCRAPEDO_TOKEN=your_token
cardmarket-scraper -f csv -o mh3.csv set "Modern Horizons 3" --pages 0          # all 300 singles, 10 credits
cardmarket-scraper -f csv -o mh3_top.csv set "Modern Horizons 3" --details      # price guide of the 30 most expensive
cardmarket-scraper -f csv -o ring.csv product --offers \
  https://www.cardmarket.com/en/Magic/Products/Singles/The-Lord-of-the-Rings-Tales-of-Middle-earth/The-One-Ring
cardmarket-scraper set "Prismatic Evolutions" --game pokemon
```

## Why plain requests fail

```python
import requests

r = requests.get("https://www.cardmarket.com/en/Magic/Products/Singles/Modern-Horizons-3")
print(r.status_code)   # 403
print(r.text[:200])    # ... <title>Attention Required! | Cloudflare</title> ...
```

Cardmarket sits behind Cloudflare, which blocks scripts with `403`. This package sends each request through [Scrape.do](https://scrape.do/?utm_source=github&utm_medium=readme&utm_campaign=cardmarket-scraper), which returns the real server-rendered page: **1 credit per page**. Cloudflare sometimes refuses Scrape.do's datacenter IPs for a while; Scrape.do then answers `502`, doesn't charge it, and the client retries with backoff. Pass `fallback_to_super=True` (or `--super` on the CLI) to switch to residential proxies when that happens.

## Where the data is

* **Set pages**: `/en/<Game>/Products/Singles/<Expansion>?mode=list&sortBy=price_desc&site=N`. The list view has 30 rows per page, each cell tagged with `data-testid` (`name`, `rarity`, `collector_number`, `availability`, `from_price`, `available_foils`, `price_from_foils`), and a "300 Hits" / "Page 1 of 10" header.
* **Product pages**: `/en/<Game>/Products/Singles/<Expansion>/<Card>`. The price guide is a `<dl class="labeled">` (Available items, From, Price Trend, 30/7/1-day averages), the price chart is a Chart.js config with 30 days of average sell prices, and the offers are `div#articleRow…` rows.

In a live test, The One Ring from *The Lord of the Rings: Tales of Middle-earth* had 467 copies listed from €88.00 against a price trend of €105.62. All 50 cheapest offers were below the trend; 43 were Near Mint and they shipped from 9 countries, led by the United Kingdom (17) and France (13). Its 30-day average sell price ranged from €90.50 to €116.75. *Modern Horizons 3* has 300 singles on 10 list pages: the whole set's lowest prices cost 10 credits.

## Python

```python
from cardmarket_scraper import Cardmarket

cm = Cardmarket(token="YOUR_SCRAPEDO_TOKEN")   # or set SCRAPEDO_TOKEN

for card in cm.expansion("Modern Horizons 3", pages=1):          # 30 most expensive first
    print(card.name, card.rarity, card.available, card.from_price, card.from_price_foil)

ring = cm.product("https://www.cardmarket.com/en/Magic/Products/Singles/The-Lord-of-the-Rings-Tales-of-Middle-earth/The-One-Ring")
print(ring.from_price, ring.price_trend, ring.avg_30, ring.avg_7, ring.avg_1)
print(ring.history[-3:])                                         # [("2026-11-21", 115.7), ...]
for offer in ring.offers[:5]:
    print(offer.price, offer.condition, offer.language, offer.location, offer.foil)
print(cm.credits_used)
```

`examples/below_trend.py` lists the offers on a card that sit below its price trend.

## Fields

**Card (set and search pages):** `id`, `name`, `expansion`, `rarity`, `number`, `available`, `from_price`, `available_foils`, `from_price_foil`, `url`.

**Product:** `id`, `name`, `expansion`, `category`, `rarity`, `number`, `available`, `from_price`, `price_trend`, `avg_30`, `avg_7`, `avg_1`, `versions`, `rules_text`, `image`, `url`, `history` (date, average sell price), `offers`.

**Offer:** `id`, `seller`, `seller_type` (`Professional`, `Powerseller` or empty), `seller_sales`, `location`, `condition` (`MT`, `NM`, `EX`, `GD`, `LP`, `PL`, `PO`), `language`, `foil`, `specials` (Foil, Signed, Altered, Playset, First Edition, Reverse Holo), `price`, `quantity`, `comment`.

Prices are in euros. Logged-out product pages show the 50 cheapest offers; filters such as language or condition are Cardmarket URL parameters you can add to the product URL.

## Use it responsibly

Cardmarket's prices are public, but respect its terms, keep request rates low, and don't republish seller data. Sellers' usernames are in the `seller` field for analysis; leave them out of anything you publish. This is not legal advice.

## Tests

```bash
pip install pytest
PYTHONPATH=src pytest
```

The fixtures are fictional ("Example Set", "ExampleCards", "Exampleland").

## License

MIT
