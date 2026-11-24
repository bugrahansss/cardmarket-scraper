"""Parse Cardmarket's server-rendered pages.

* Set (expansion) pages in list mode, ``/en/<Game>/Products/Singles/<Expansion>?mode=list``: 30 cards per page,
  each row with name, rarity, collector number, items available and the lowest price (normal and foil).
* Product pages, ``/en/<Game>/Products/Singles/<Expansion>/<Card>``: the price guide (from, trend, 30/7/1-day
  averages), a 30-day average sell price chart and the first 50 offers (seller country, condition, language,
  foil, price, quantity).
"""

from __future__ import annotations

import html as htmllib
import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urlencode

BASE = "https://www.cardmarket.com"
PAGE_SIZE = 30

GAMES = {
    "magic": "Magic", "mtg": "Magic", "pokemon": "Pokemon", "yugioh": "YuGiOh", "yu-gi-oh": "YuGiOh",
    "lorcana": "Lorcana", "onepiece": "OnePiece", "one-piece": "OnePiece", "fab": "FleshAndBlood",
    "fleshandblood": "FleshAndBlood", "digimon": "Digimon", "dragonball": "DragonBallSuper",
    "starwars": "StarWarsUnlimited", "riftbound": "Riftbound",
}
SORTS = {"price_desc", "price_asc", "name_asc", "name_desc", "collectorsnumber_asc", "collectorsnumber_desc",
         "idRarity_asc", "idRarity_desc"}
SPECIALS = ("Foil", "Signed", "Altered", "Playset", "First Edition", "Reverse Holo")


# ---- URLs -------------------------------------------------------------------------------------------------

def game_name(game: str) -> str:
    """``"pokemon"`` -> ``"Pokemon"``. Unknown names pass through as given (Cardmarket's own spelling)."""
    key = re.sub(r"[\s_]+", "", (game or "Magic").strip().lower())
    return GAMES.get(key, (game or "Magic").strip())


def slugify(text: str) -> str:
    """Cardmarket slugs: ``"Modern Horizons 3"`` -> ``"Modern-Horizons-3"``."""
    text = re.sub(r"[’'`:,.!?()\[\]]", "", text.strip())
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")


def expansion_url(expansion: str, game: str = "Magic", page: int = 1, sort: str = "price_desc") -> str:
    """List view of every single in an expansion, 30 per page."""
    if expansion.startswith("http"):
        base = expansion.split("?")[0]
    else:
        base = f"{BASE}/en/{game_name(game)}/Products/Singles/{expansion if '-' in expansion else slugify(expansion)}"
    params = {"mode": "list"}
    if sort:
        if sort not in SORTS:
            raise ValueError(f"sort must be one of {sorted(SORTS)}")
        params["sortBy"] = sort
    if page > 1:
        params["site"] = page
    return f"{base}?{urlencode(params)}"


def search_url(query: str, game: str = "Magic", page: int = 1) -> str:
    """Singles search by card name, list view."""
    params = {"searchString": query, "category": 1, "mode": "list"}
    if page > 1:
        params["site"] = page
    return f"{BASE}/en/{game_name(game)}/Products/Search?{urlencode(params, quote_via=quote)}"


def product_url(value: str) -> str:
    """A full product URL, or a path like ``/en/Magic/Products/Singles/...``. Query strings are dropped."""
    v = value.strip()
    if v.startswith("http"):
        return v.split("?")[0].split("#")[0]
    if v.startswith("/"):
        return BASE + v.split("?")[0]
    raise ValueError("Give a Cardmarket product URL, e.g. https://www.cardmarket.com/en/Magic/Products/Singles/...")


# ---- helpers ----------------------------------------------------------------------------------------------

def text(fragment: Optional[str]) -> str:
    if not fragment:
        return ""
    t = re.sub(r"<br\s*/?>", "\n", fragment)
    t = htmllib.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\s*\n\s*", "\n", t).strip()


def price(value: Optional[str]) -> Optional[float]:
    """``"1.234,56 €"`` -> ``1234.56``. ``None`` for N/A or empty."""
    if not value:
        return None
    v = re.sub(r"[^\d,.\-]", "", text(value))
    if not v or not re.search(r"\d", v):
        return None
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def integer(value: Optional[str]) -> Optional[int]:
    v = re.sub(r"[^\d]", "", text(value))
    return int(v) if v else None


def _testid(row: str, name: str) -> str:
    m = re.search(rf'data-testid="{name}"[^>]*>(.*?)</div>', row, re.S)
    return m.group(1) if m else ""


def _rarity(fragment: str) -> str:
    m = re.search(r'<svg[^>]*title="([^"]+)"', fragment) or re.search(r'title="([^"]+)"', fragment)
    return htmllib.unescape(m.group(1)) if m else ""


# ---- set / search pages -----------------------------------------------------------------------------------

@dataclass
class Card:
    id: str
    name: str
    expansion: str
    rarity: str
    number: str
    available: Optional[int]
    from_price: Optional[float]
    available_foils: Optional[int]
    from_price_foil: Optional[float]
    url: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CardPage:
    cards: List[Card]
    total: Optional[int]
    page: int
    pages: int


CARD_FIELDS = list(Card.__dataclass_fields__)


def parse_list(html: str) -> Optional[CardPage]:
    """A list-view page of singles (set page or search). ``None`` when the page has no product table."""
    starts = [m.start() for m in re.finditer(r'<div id="productRow\d+"', html)]
    if not starts and "productRow" not in html:
        return None
    cards, seen = [], set()
    for i, s in enumerate(starts):
        row = html[s:starts[i + 1] if i + 1 < len(starts) else s + 6000]
        pid = re.match(r'<div id="productRow(\d+)"', row).group(1)
        if pid in seen:
            continue
        seen.add(pid)
        name = re.search(r'data-testid="name"[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', row, re.S)
        exp = re.search(r'data-testid="expansion".*?title="([^"]+)"', row, re.S)
        cards.append(Card(
            id=pid,
            name=text(name.group(2)) if name else "",
            expansion=htmllib.unescape(exp.group(1)) if exp else "",
            rarity=_rarity(_testid(row, "rarity")),
            number=text(_testid(row, "collector_number")),
            available=integer(_testid(row, "availability")),
            from_price=price(_testid(row, "from_price")),
            available_foils=integer(_testid(row, "available_foils")),
            from_price_foil=price(_testid(row, "price_from_foils")),
            url=(BASE + name.group(1)) if name else "",
        ))
    hits = re.search(r"([\d.,]+)\s+Hits", html)
    pages = re.search(r"Page\s+(\d+)\s+of\s+(\d+)", html)
    total = integer(hits.group(1)) if hits else None
    page_no = int(pages.group(1)) if pages else 1
    n_pages = int(pages.group(2)) if pages else (max(1, -(-total // PAGE_SIZE)) if total else 1)
    return CardPage(cards=cards, total=total, page=page_no, pages=n_pages)


# ---- product pages ----------------------------------------------------------------------------------------

@dataclass
class Offer:
    id: str
    seller: str
    seller_type: str
    seller_sales: Optional[int]
    location: str
    condition: str
    language: str
    foil: bool
    specials: List[str]
    price: Optional[float]
    quantity: Optional[int]
    comment: str

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["specials"] = ", ".join(self.specials)
        return d


@dataclass
class Product:
    id: str
    name: str
    expansion: str
    category: str
    rarity: str
    number: str
    available: Optional[int]
    from_price: Optional[float]
    price_trend: Optional[float]
    avg_30: Optional[float]
    avg_7: Optional[float]
    avg_1: Optional[float]
    versions: Optional[int]
    rules_text: str
    image: str
    url: str
    history: List[Tuple[str, float]] = field(default_factory=list)
    offers: List[Offer] = field(default_factory=list)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d.pop("history")
        d.pop("offers")
        d["offers_listed"] = len(self.offers)
        return d


PRODUCT_FIELDS = [f for f in Product.__dataclass_fields__ if f not in ("history", "offers")] + ["offers_listed"]
OFFER_FIELDS = list(Offer.__dataclass_fields__)


def _info(html: str) -> Dict[str, str]:
    dl = re.search(r'<dl class="labeled[^"]*"[^>]*>(.*?)</dl>', html, re.S)
    if not dl:
        return {}
    pairs = re.findall(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", dl.group(1), re.S)
    return {text(k): v for k, v in pairs}


def _history(html: str) -> List[Tuple[str, float]]:
    m = re.search(r'new Chart\(\w+,\{"type":"line","data":\{"labels":(\[[^\]]*\]),"datasets":\[\{"label":"Avg\. Sell Price","data":(\[[^\]]*\])', html)
    if not m:
        return []
    labels = re.findall(r'"(\d{2})\.(\d{2})\.(\d{4})"', m.group(1))
    values = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", m.group(2))]
    return [(f"{y}-{mo}-{d}", v) for (d, mo, y), v in zip(labels, values)]


def _offers(html: str) -> List[Offer]:
    starts = [m.start() for m in re.finditer(r'<div id="articleRow\d+"', html)]
    out = []
    for i, s in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else html.find("</section", s)
        row = html[s:end if end > s else s + 6000]
        oid = re.match(r'<div id="articleRow(\d+)"', row).group(1)
        seller = re.search(r'<a href="/en/\w+/Users/[^"]+">(.*?)</a>', row, re.S)
        stype = re.search(r'title="(Professional|Powerseller)"', row)
        sales = re.search(r'class="[^"]*sell-count[^"]*">([\d.,]+)<', row)
        loc = re.search(r'title="Item location: ([^"]+)"', row)
        cond = re.search(r'title="([^"]+)" data-bs-toggle="tooltip"[^>]*class="article-condition', row)
        cond_short = re.search(r'class="article-condition[^"]*"[^>]*><span class="badge ?">(\w+)<', row)
        attrs = re.search(r'class="product-attributes[^"]*">(.*?)<div class="(?:mobile-offer-container|product-comments)', row, re.S)
        attr = attrs.group(1) if attrs else row
        lang = re.search(r'title="([^"]+)" data-bs-toggle="tooltip" data-bs-html="true" data-bs-placement="bottom" class="icon me-2"', attr)
        specials = [s for s in SPECIALS if f'title="{s}"' in attr]
        comment = re.search(r'class="product-comments[^"]*">.*?<span class="d-block[^"]*">(.*?)</span>', row, re.S)
        prices = re.search(r'class="price-container.*?<span class="[^"]*fw-bold[^"]*">(.*?)</span>', row, re.S) \
            or re.search(r'<span class="color-primary[^"]*fw-bold[^"]*">(.*?)</span>', row, re.S)
        qty = re.search(r'class="amount-container d-none[^"]*">\s*<span class="item-count[^"]*">(\d+)<', row) \
            or re.search(r'class="item-count[^"]*">(\d+)<', row)
        out.append(Offer(
            id=oid,
            seller=text(seller.group(1)) if seller else "",
            seller_type=stype.group(1) if stype else "",
            seller_sales=integer(sales.group(1)) if sales else None,
            location=htmllib.unescape(loc.group(1)) if loc else "",
            condition=cond_short.group(1) if cond_short else (htmllib.unescape(cond.group(1)) if cond else ""),
            language=htmllib.unescape(lang.group(1)) if lang else "",
            foil="Foil" in specials,
            specials=specials,
            price=price(prices.group(1)) if prices else None,
            quantity=int(qty.group(1)) if qty else None,
            comment=text(comment.group(1)) if comment else "",
        ))
    return out


def parse_product(html: str, url: str = "") -> Optional[Product]:
    """A product page. ``None`` when the page has no price guide (not a product page)."""
    info = _info(html)
    if "Available items" not in info and "From" not in info:
        return None
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    name, category = "", ""
    if h1:
        sub = re.search(r"<span[^>]*>(.*?)</span>", h1.group(1), re.S)
        name = text(h1.group(1)[:sub.start()] if sub else h1.group(1))
        category = text(sub.group(1)).split(" - ")[-1] if sub else ""
    printed = info.get("Printed in", "")
    exp = re.findall(r"<a [^>]*>([^<]+)</a>", printed)
    versions = re.search(r"Show Versions \((\d+)\)", info.get("Reprints", ""))
    pid = re.search(r"idProduct=(\d+)", html)
    image = re.search(r'<img src="(https://product-images\.s3\.cardmarket\.com/[^"]+)"', html)
    rules = re.search(r'<span class="h4">Rules Text</span>\s*<p>(.*?)</p>', html, re.S)
    canonical = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return Product(
        id=pid.group(1) if pid else "",
        name=name,
        expansion=text(exp[-1]) if exp else text(printed),
        category=category,
        rarity=_rarity(info.get("Rarity", "")),
        number=text(info.get("Number", "")),
        available=integer(info.get("Available items")),
        from_price=price(info.get("From")),
        price_trend=price(info.get("Price Trend")),
        avg_30=price(info.get("30-days average price")),
        avg_7=price(info.get("7-days average price")),
        avg_1=price(info.get("1-day average price")),
        versions=int(versions.group(1)) if versions else None,
        rules_text=text(rules.group(1)) if rules else "",
        image=image.group(1) if image else "",
        url=url or (canonical.group(1) if canonical else ""),
        history=_history(html),
        offers=_offers(html),
    )
