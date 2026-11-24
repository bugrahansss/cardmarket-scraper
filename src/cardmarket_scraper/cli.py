"""Command line:

    cardmarket-scraper set "Modern Horizons 3" --pages 2 -f csv -o mh3.csv
    cardmarket-scraper search "Sol Ring" --game magic
    cardmarket-scraper product URL [URL ...] --offers -f csv -o offers.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

from .client import Cardmarket
from .parser import CARD_FIELDS, OFFER_FIELDS, PRODUCT_FIELDS


def _write(rows, fields, fmt, path):
    out = open(path, "w", newline="", encoding="utf-8") if path else sys.stdout
    try:
        if fmt == "csv":
            writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        else:
            json.dump(rows, out, ensure_ascii=False, indent=2)
            out.write("\n")
    finally:
        if path:
            out.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="cardmarket-scraper",
                                description="Scrape Cardmarket through the Scrape.do API (token in SCRAPEDO_TOKEN).")
    p.add_argument("--token", help="Scrape.do token (default: SCRAPEDO_TOKEN)")
    p.add_argument("--super", action="store_true", help="Use Scrape.do residential proxies for every request")
    p.add_argument("-f", "--format", choices=["json", "csv"], default="json")
    p.add_argument("-o", "--output", help="Output file (default: stdout)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("set", help="Every single in an expansion (list view, 30 per page)")
    s.add_argument("expansion", help='Expansion name or slug, e.g. "Modern Horizons 3", or its URL')
    s.add_argument("--game", default="Magic", help="magic, pokemon, yugioh, lorcana, onepiece, ... (default: magic)")
    s.add_argument("--pages", type=int, default=1, help="Pages of 30 (0 = all)")
    s.add_argument("--sort", default="price_desc", help="price_desc (default), price_asc, name_asc, collectorsnumber_asc, ...")
    s.add_argument("--details", action="store_true", help="Open every card's page for the price guide (1 request per card)")

    q = sub.add_parser("search", help="Singles matching a card name")
    q.add_argument("query")
    q.add_argument("--game", default="Magic")
    q.add_argument("--pages", type=int, default=1)

    d = sub.add_parser("product", help="Price guide, price history and offers of product pages")
    d.add_argument("urls", nargs="+")
    d.add_argument("--offers", action="store_true", help="Output one row per offer instead of one per product")
    d.add_argument("--history", action="store_true", help="Output the 30-day average sell price history")

    args = p.parse_args(argv)
    cm = Cardmarket(token=args.token, super_proxy=args.super)

    if args.cmd in ("set", "search"):
        cards = list(cm.expansion(args.expansion, args.game, args.pages, args.sort) if args.cmd == "set"
                     else cm.search(args.query, args.game, args.pages))
        if args.cmd == "set" and args.details:
            rows = [cm.product(c.url).to_dict() for c in cards]
            fields = PRODUCT_FIELDS
        else:
            rows, fields = [c.to_dict() for c in cards], CARD_FIELDS
    else:
        products = cm.products(args.urls)
        if args.offers:
            rows = [dict(product=pr.name, expansion=pr.expansion, **o.to_dict()) for pr in products for o in pr.offers]
            fields = ["product", "expansion"] + OFFER_FIELDS
        elif args.history:
            rows = [dict(product=pr.name, expansion=pr.expansion, date=d_, avg_sell_price=v) for pr in products for d_, v in pr.history]
            fields = ["product", "expansion", "date", "avg_sell_price"]
        else:
            rows, fields = [pr.to_dict() for pr in products], PRODUCT_FIELDS

    _write(rows, fields, args.format, args.output)
    print(f"{len(rows)} rows, {cm.requests_made} pages, {cm.credits_used} Scrape.do credits", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
