"""Scrape Cardmarket card prices, price guides and offers with Python."""

from .client import Cardmarket, ScrapeError
from .parser import (
    CARD_FIELDS,
    OFFER_FIELDS,
    PRODUCT_FIELDS,
    Card,
    CardPage,
    Offer,
    Product,
    expansion_url,
    game_name,
    parse_list,
    parse_product,
    price,
    product_url,
    search_url,
    slugify,
)

__version__ = "0.1.0"
__all__ = [
    "Cardmarket", "ScrapeError", "Card", "CardPage", "Offer", "Product", "parse_list", "parse_product",
    "expansion_url", "search_url", "product_url", "game_name", "slugify", "price",
    "CARD_FIELDS", "PRODUCT_FIELDS", "OFFER_FIELDS",
]
