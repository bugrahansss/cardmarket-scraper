from pathlib import Path

import pytest

from cardmarket_scraper import (Cardmarket, ScrapeError, expansion_url, game_name, parse_list, parse_product, price,
                                product_url, search_url, slugify)

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_urls_and_helpers():
    assert slugify("Modern Horizons 3") == "Modern-Horizons-3"
    assert slugify("The Lord of the Rings: Tales of Middle-earth") == "The-Lord-of-the-Rings-Tales-of-Middle-earth"
    assert expansion_url("Modern Horizons 3") == \
        "https://www.cardmarket.com/en/Magic/Products/Singles/Modern-Horizons-3?mode=list&sortBy=price_desc"
    assert expansion_url("Prismatic-Evolutions", "pokemon", 3).endswith("/en/Pokemon/Products/Singles/Prismatic-Evolutions?mode=list&sortBy=price_desc&site=3")
    assert search_url("Sol Ring") == "https://www.cardmarket.com/en/Magic/Products/Search?searchString=Sol%20Ring&category=1&mode=list"
    assert game_name("yu-gi-oh") == "YuGiOh" and game_name("Lorcana") == "Lorcana"
    assert product_url("/en/Magic/Products/Singles/X/Y?language=1") == "https://www.cardmarket.com/en/Magic/Products/Singles/X/Y"
    assert price("1.234,56 €") == 1234.56 and price("0,02 €") == 0.02 and price("N/A") is None
    with pytest.raises(ValueError):
        expansion_url("Modern Horizons 3", sort="cheapest")
    with pytest.raises(ValueError):
        product_url("not a url")


def test_list_page():
    page = parse_list(load("list.html"))
    assert page.total == 47 and page.page == 1 and page.pages == 2
    assert [c.id for c in page.cards] == ["900001", "900002", "900003"]  # duplicate row dropped
    a, b, c = page.cards
    assert (a.name, a.expansion, a.rarity, a.number) == ("Example Dragon", "Example Set", "Mythic", "7")
    assert (a.available, a.from_price, a.available_foils, a.from_price_foil) == (1204, 1234.5, 12, 1500.0)
    assert a.url == "https://www.cardmarket.com/en/Magic/Products/Singles/Example-Set/Example-Dragon"
    assert b.name == "Sample & Ring" and b.available_foils == 0 and b.from_price_foil is None
    assert c.from_price == 0.02 and c.rarity == "Common"


def test_product_page():
    p = parse_product(load("product.html"), "https://www.cardmarket.com/en/Magic/Products/Singles/Example-Set/Sample-Ring")
    assert (p.id, p.name, p.expansion, p.category, p.rarity, p.number) == ("900002", "Sample Ring", "Example Set", "Singles", "Rare", "88")
    assert (p.available, p.from_price, p.price_trend, p.avg_30, p.avg_7, p.avg_1) == (45, 88.0, 1105.62, 102.65, 103.15, None)
    assert p.versions == 3 and p.rules_text == "Indestructible\nWhen Sample Ring enters, draw a card."
    assert p.history == [("2026-11-01", 100.0), ("2026-11-02", 96.75), ("2026-11-03", 102.5)]
    assert len(p.offers) == 3
    a, b, c = p.offers
    assert (a.seller, a.seller_type, a.seller_sales, a.location) == ("ExampleCards", "Professional", 1204, "Exampleland")
    assert (a.condition, a.language, a.foil, a.price, a.quantity) == ("NM", "English", False, 88.0, 2)
    assert b.foil and b.specials == ["Foil"] and b.comment == "Sleeved & top-loaded" and b.condition == "EX"
    assert c.seller_type == "Powerseller" and c.specials == ["Signed", "Altered"] and c.price == 1050.0
    row = p.to_dict()
    assert row["offers_listed"] == 3 and "offers" not in row and "history" not in row
    assert c.to_dict()["specials"] == "Signed, Altered"


def test_missing():
    assert parse_list("<html></html>") is None
    assert parse_product(load("list.html")) is None
    assert parse_product("<html></html>") is None


class FakeResponse:
    def __init__(self, text, status=200):
        self.text, self.status_code, self.headers = text, status, {}


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = responses, []

    def get(self, url, params=None, timeout=None):
        self.calls.append(dict(params))
        r = self.responses(params, len(self.calls))
        return FakeResponse(*r) if isinstance(r, tuple) else FakeResponse(r)


def test_expansion_walks_pages_and_dedupes(monkeypatch):
    monkeypatch.setattr("cardmarket_scraper.client.time.sleep", lambda s: None)
    s = FakeSession(lambda p, n: load("list.html"))
    cm = Cardmarket(token="t", session=s)
    cards = list(cm.expansion("Example Set", pages=0))
    assert len(cards) == 3  # page 2 repeats page 1, so the walk stops
    assert [c["url"].split("?")[1] for c in s.calls] == ["mode=list&sortBy=price_desc", "mode=list&sortBy=price_desc&site=2"]
    assert cm.credits_used == 2


def test_retries_502_then_cloudflare_then_ok(monkeypatch):
    monkeypatch.setattr("cardmarket_scraper.client.time.sleep", lambda s: None)
    seq = {1: ('{"ErrorType":"ROTATION_FAILED"}', 502), 2: load("blocked.html"), 3: load("product.html")}
    s = FakeSession(lambda p, n: seq[n])
    cm = Cardmarket(token="t", session=s)
    assert cm.product("https://www.cardmarket.com/en/Magic/Products/Singles/Example-Set/Sample-Ring").name == "Sample Ring"
    assert len(s.calls) == 3 and cm.requests_made == 2


def test_fallback_to_super(monkeypatch):
    monkeypatch.setattr("cardmarket_scraper.client.time.sleep", lambda s: None)
    s = FakeSession(lambda p, n: load("product.html") if p.get("super") == "true" else ("bad gateway", 502))
    cm = Cardmarket(token="t", retries=1, fallback_to_super=True, session=s)
    assert cm.product("/en/Magic/Products/Singles/Example-Set/Sample-Ring").id == "900002"
    assert [c.get("super") for c in s.calls] == [None, None, "true"]
    assert cm.credits_used == 10


def test_401_stops(monkeypatch):
    monkeypatch.setattr("cardmarket_scraper.client.time.sleep", lambda s: None)
    s = FakeSession(lambda p, n: ("Unauthorized", 401))
    with pytest.raises(ScrapeError) as err:
        Cardmarket(token="bad", session=s).product("/en/Magic/Products/Singles/X/Y")
    assert err.value.status_code == 401 and len(s.calls) == 1


def test_token_required(monkeypatch):
    monkeypatch.delenv("SCRAPEDO_TOKEN", raising=False)
    with pytest.raises(ValueError):
        Cardmarket()
