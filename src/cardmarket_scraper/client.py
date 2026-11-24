"""Fetch Cardmarket pages through the Scrape.do API.

cardmarket.com sits behind Cloudflare: a plain ``requests.get`` from a script gets ``403`` and an
"Attention Required! | Cloudflare" page. Sent through Scrape.do, the request returns the real
server-rendered page. A plain request costs 1 credit; when Cloudflare refuses the datacenter IP
Scrape.do answers 502 (not charged) and the client retries, then optionally falls back to
residential proxies (``super_proxy=True``, more credits per request).
"""

from __future__ import annotations

import os
import time
from typing import Iterator, List, Optional

import requests

from .parser import Card, CardPage, Product, expansion_url, parse_list, parse_product, product_url, search_url

API_URL = "https://api.scrape.do/"
TOKEN_ENV = "SCRAPEDO_TOKEN"
BLOCK_MARKERS = ("Attention Required! | Cloudflare", "Just a moment...", "cf-error-details")


class ScrapeError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class Cardmarket:
    """Read Cardmarket set pages, searches and product pages.

    >>> cm = Cardmarket(token="YOUR_SCRAPEDO_TOKEN")
    >>> for card in cm.expansion("Modern Horizons 3", pages=2):
    ...     print(card.name, card.rarity, card.from_price)
    >>> ring = cm.product("https://www.cardmarket.com/en/Magic/Products/Singles/The-Lord-of-the-Rings-Tales-of-Middle-earth/The-One-Ring")
    >>> print(ring.price_trend, ring.avg_30, len(ring.offers))
    """

    def __init__(self, token: Optional[str] = None, timeout: float = 90.0, retries: int = 3,
                 super_proxy: bool = False, fallback_to_super: bool = False,
                 session: Optional[requests.Session] = None):
        self.token = token or os.environ.get(TOKEN_ENV, "")
        if not self.token:
            raise ValueError(f"A Scrape.do API token is required. Pass token=... or set {TOKEN_ENV}.")
        self.timeout = timeout
        self.retries = max(0, retries)
        self.super_proxy = super_proxy
        self.fallback_to_super = fallback_to_super
        self.session = session or requests.Session()
        self.requests_made = 0
        self.credits = 0

    def _get(self, url: str, use_super: bool):
        params = {"token": self.token, "url": url}
        if use_super:
            params["super"] = "true"
        return self.session.get(API_URL, params=params, timeout=self.timeout)

    def fetch(self, url: str) -> str:
        last: Optional[ScrapeError] = None
        plans = [self.super_proxy] * (self.retries + 1)
        if self.fallback_to_super and not self.super_proxy:
            plans.append(True)
        for attempt, use_super in enumerate(plans):
            try:
                response = self._get(url, use_super)
            except requests.RequestException as exc:
                last = ScrapeError(f"Request failed: {exc}")
            else:
                status = response.status_code
                if status == 200:
                    self.requests_made += 1
                    cost = response.headers.get("Scrape.do-Request-Cost")
                    self.credits += int(float(cost)) if cost else (10 if use_super else 1)
                    if not any(m in response.text for m in BLOCK_MARKERS):
                        return response.text
                    last = ScrapeError(f"Cloudflare page for {url}", 200)
                else:
                    last = ScrapeError(f"Request for {url} failed with status {status}", status)
                    if status in (400, 401, 404, 410):
                        break
            if attempt < len(plans) - 1:
                time.sleep(3 * (attempt + 1))
        assert last is not None
        raise last

    # ---- lists --------------------------------------------------------------------------------------

    def _list(self, url: str) -> CardPage:
        page = parse_list(self.fetch(url))
        if page is None:
            raise ScrapeError(f"No product list on {url}")
        return page

    def _walk(self, make_url, pages: int) -> Iterator[Card]:
        seen = set()
        page, last = 1, None
        while not ((pages and page > pages) or (last is not None and page > last)):
            result = self._list(make_url(page))
            last = result.pages
            fresh = [c for c in result.cards if c.id not in seen]
            if not fresh:
                break
            for card in fresh:
                seen.add(card.id)
                yield card
            page += 1

    def expansion_page(self, expansion: str, game: str = "Magic", page: int = 1, sort: str = "price_desc") -> CardPage:
        return self._list(expansion_url(expansion, game, page, sort))

    def expansion(self, expansion: str, game: str = "Magic", pages: int = 1, sort: str = "price_desc") -> Iterator[Card]:
        """Every single in an expansion, 30 per page, most expensive first by default. ``pages=0`` = all."""
        return self._walk(lambda p: expansion_url(expansion, game, p, sort), pages)

    def search(self, query: str, game: str = "Magic", pages: int = 1) -> Iterator[Card]:
        """Singles whose name matches ``query``."""
        return self._walk(lambda p: search_url(query, game, p), pages)

    # ---- products -----------------------------------------------------------------------------------

    def product(self, url: str) -> Product:
        """Price guide, 30-day price history and the first 50 offers of one product."""
        url = product_url(url)
        product = parse_product(self.fetch(url), url)
        if product is None:
            raise ScrapeError(f"No price guide on {url} (is it a product page?)")
        return product

    def products(self, urls: List[str]) -> List[Product]:
        return [self.product(u) for u in urls]

    @property
    def credits_used(self) -> int:
        return self.credits
