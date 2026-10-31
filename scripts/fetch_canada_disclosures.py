"""Conservative acquisition extraction from original Canada NewsWire releases.

Only a completed exchange-market purchase, with price, shares, issuer and a
Canadian exchange ticker, is eligible. Other announcements stay in the
unverified discovery queue and are NEVER promoted by headline alone.
"""
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

LISTING = "https://www.newswire.ca/news-releases/financial-services-latest-news/acquisitions-mergers-and-takeovers-list/?page=1&pagesize=100"
OUTPUT = Path("moves-canada-auto.json")
NOW = datetime.now(timezone.utc)
UA = "Mozilla/5.0 (compatible; Briefly personal financial research)"
HEADLINE = re.compile(r"\b(EARLY WARNING|ACQUIRES? (?:COMMON )?SHARES)\b", re.I)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href", "")
            self.current = [href, []]

    def handle_data(self, data):
        if self.current:
            self.current[1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current:
            self.links.append((self.current[0], " ".join(self.current[1]).strip()))
            self.current = None


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=17) as response:
        return response.read(1800000).decode("utf-8", "ignore")


def day(value):
    try:
        return datetime.strptime(value, "%B %d, %Y").date().isoformat()
    except (TypeError, ValueError):
        return None


def candidate_urls(raw):
    parser = Links()
    parser.feed(raw)
    selected = []
    for path, title in parser.links:
        if not HEADLINE.search(title):
            continue
        url = urllib.parse.urljoin("https://www.newswire.ca", html.unescape(path))
        parsed = urllib.parse.urlparse(url)
        if parsed.hostname not in ("www.newswire.ca", "newswire.ca") or not re.match(r"^/news-releases/.*\.html$", parsed.path):
            continue
        if url not in selected:
            selected.append(url)
    return selected[:14]


def extract(raw, url):
    parser = Text()
    parser.feed(raw)
    text = re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts)))
    match = re.search(r"/CNW/\s*-{0,2}\s*(.{0,2600})", text, re.I)
    if not match:
        return None
    paragraph = match.group(1)
    headline = re.search(r"News Releases (.+?)(?:News provided by|Oct \d|NEW YORK,)", text, re.I)
    # Only pick up on-market completed buying. Grants, warrants, financing,
    # debt settlements and a stake change by dilution are not evidence of a
    # share purchase and must remain unverified.
    if not re.search(r"\b(?:had )?acquired\b", paragraph, re.I):
        return None
    if not re.search(r"\b(open.market|through the facilities of (?:the )?(?:Toronto Stock Exchange|TSX Venture Exchange|TSX|TSXV))\b", paragraph, re.I):
        return None
    trade = re.search(
        r"acquired\s+(?:an aggregate of\s+)?([\d,]+)\s+common shares\b.{0,120}?\bof\s+([A-Z][A-Za-z0-9&.'’\- ]{3,90}?(?:Corp\.|Corporation|Inc\.|Limited|Ltd\.))",
        paragraph, re.I)
    if not trade:
        return None
    quantity = int(trade.group(1).replace(",", ""))
    issuer = trade.group(2).strip()
    if quantity < 1:
        return None
    listing = re.search(r"\b(TSX|TSXV|TSX-V|CSE)\s*:\s*([A-Z][A-Z0-9.]{0,10})\b", paragraph, re.I)
    if not listing:
        return None
    exchange = listing.group(1).upper().replace("TSX-V", "TSXV")
    ticker = listing.group(2).upper()
    price_match = re.search(r"(?:\bat a price of\b|\bpurchase price of\b)\s*(?:Cdn|CAD|C)?\s*\$\s*([\d,.]+)\s+per\s+(?:common\s+)?share", paragraph, re.I)
    if not price_match:
        return None
    price = float(price_match.group(1).replace(",", ""))
    if not 0.0001 <= price <= 100000:
        return None
    # Named acquirer must be grounded in the publisher's "SOURCE" line, not
    # inferred from a trading company's press release.
    source_match = re.search(r"\bSOURCE\s+(.{3,85}?)(?:\s+For further|\s+Image|\s+Contact|$)", text, re.I)
    if not source_match:
        return None
    investor = re.sub(r"\s+", " ", source_match.group(1)).strip()
    if any(x in investor.lower() for x in ("copyright", "newswire", "stock exchange")):
        return None
    article_day = re.search(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},\s+20\d\d,\s+\d\d:\d\d\s+ET", text)
    disclosure = None
    if article_day:
        try:
            disclosure = datetime.strptime(article_day.group(0).rsplit(",", 1)[0].replace(".", ""), "%b %d, %Y").date().isoformat()
        except ValueError:
            pass
    if not disclosure:
        short = re.search(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d\d\b", paragraph, re.I)
        disclosure = day(short.group(0)) if short else None
    if not disclosure or (NOW.date() - datetime.fromisoformat(disclosure).date()).days not in range(-1, 15):
        return None
    transaction_date = None
    before = re.search(r"\bon\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:,\s*(20\d\d))?\b.{0,45}\bacquired", paragraph, re.I)
    after = re.search(r"\bacquired\b.{0,300}?\bon\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s*(20\d\d)?", paragraph, re.I)
    matched = before or after
    if matched:
        y = matched.group(3) or disclosure[:4]
        transaction_date = day(matched.group(1) + " " + matched.group(2) + ", " + y)
    if not transaction_date:
        return None
    value = round(quantity * price, 2)
    return {
        "id": "newswire:" + hashlib.sha1(url.encode()).hexdigest()[:17],
        "market": "Canada", "direction": "BUY",
        "investor": investor, "company": issuer, "symbol": ticker,
        "exchange": exchange, "transactionDate": transaction_date,
        "disclosureDate": disclosure, "shares": quantity,
        "priceCAD": price, "valueCAD": value,
        "type": "Open-market acquisition", "status": "Completed; source article automatically parsed",
        "sourceUrl": url, "sourceName": "Canada NewsWire — original acquiror announcement",
        "notes": "Machine-extracted from original public release; verify the source before trading. Distinct from SEDI insider filings.",
        "extraction": "primary_release_structured",
    }


def main():
    existing = {}
    if OUTPUT.exists():
        try:
            existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            existing = {}
    archive = {r["sourceUrl"]: r for r in existing.get("records", []) if r.get("sourceUrl")}
    status = {"listing": LISTING, "ok": False, "candidates": 0, "parsed": 0, "errors": []}
    try:
        raw = fetch(LISTING)
        urls = candidate_urls(raw)
        status["ok"] = True
        status["candidates"] = len(urls)
        for url in urls:
            try:
                row = extract(fetch(url), url)
                if row:
                    archive[url] = row
                    status["parsed"] += 1
            except Exception as exc:
                status["errors"].append(str(exc)[:130])
    except Exception as exc:
        status["errors"].append(str(exc)[:130])
    cutoff = (NOW - timedelta(days=60)).date().isoformat()
    rows = [r for r in archive.values() if r.get("disclosureDate", "") >= cutoff]
    rows.sort(key=lambda r: r.get("disclosureDate", ""), reverse=True)
    output = {"updated": NOW.isoformat(), "source": "Original Canada NewsWire", "status": status, "records": rows}
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Canada primary releases:", status["candidates"], "candidates,", status["parsed"], "parsed,", len(rows), "retained", status["errors"][:2])


if __name__ == "__main__":
    main()
