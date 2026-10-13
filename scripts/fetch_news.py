import json
import re
import html
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import hashlib

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser


UA = "Mozilla/5.0 (Briefly personal news app)"

feeds = [
    ("India", "🇮🇳", "India economy business companies technology launches investments when:24h -politics -election -sports"),
    ("Canada", "🇨🇦", "Canada economy business companies technology investments when:24h -politics -election -sports"),
    ("Indian Markets", "📈", "NSE BSE Nifty Sensex earnings stocks market today when:24h -stock-price -quote"),
    ("Canadian Markets", "📈", "TSX Canadian stocks earnings acquisitions markets today when:24h -stock-price -quote"),
    ("AI", "🤖", "artificial intelligence AI OpenAI Google Anthropic Meta Nvidia models agents chips research when:24h")
]

bad = re.compile(r"\\b(politic|election|party|minister|parliament|bollywood|hollywood|celebrity|gossip|sports|cricket|football)\\b", re.I)
IRRELEVANT = re.compile(r"(?i)\\b(loafers|fashion|outfit|wardrobe|shopping guide|worth buying|celebrity|bollywood|hollywood|reality tv|horoscope|recipe|travel tips|watch:|news hour at|live stream|cockroach|viral video|movie|film|red carpet|best dressed|sports highlights)\\b")
BOILERPLATE = re.compile(r"(?i)(leave a comment|share (this|on|via|to)|facebook|whatsapp|see more sharing options|submit search|quick search|trending now|add .* to home|read on app|newsletter|sign up|subscribe|related stories|more stories|click here|follow us|comments? section|previous close|trending tickers|cloudfront|request id:|we can.t connect|cookie policy|privacy policy|all rights reserved|advertisement)")
IMPORTANT = re.compile(r"(?i)\\b(economy|economic|inflation|interest rate|central bank|bank of canada|rbi|investment|investor|earnings|revenue|profit|loss|stock|market|tsx|nifty|sensex|nse|bse|business|company|companies|corporate|technology|artificial intelligence|\\bai\\b|semiconductor|chip|trade|tariff|energy|oil|gas|manufactur|industry|employment|jobs|layoffs|merger|acquisition|funding|startup|research|policy|regulation|climate|infrastructure|housing|gdp|exports|imports|supply chain|geopolitic|security|war|conflict|breakthrough)\\b")


def relevant(title, category):
    if IRRELEVANT.search(title):
        return False
    if category in ("Canada", "India") and bad.search(title):
        return False
    return bool(IMPORTANT.search(title))

now = datetime.now(timezone.utc)
cutoff = now - timedelta(hours=24)


def clean(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def strip_title(text, title):
    text = clean(text)
    title = clean(title)
    if not text:
        return ""
    if title:
        text = re.sub(r"^\s*(?:[-|:—–]+\s*)?" + re.escape(title) + r"\s*", "", text, count=1, flags=re.I)
        text = re.sub(r"\s*(?:[-|:—–]+\s*)?" + re.escape(title) + r"\s*$", "", text, count=1, flags=re.I)
    return text.strip(" -|:—–")


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.in_p = False
        self.current = []
        self.paragraphs = []
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style", "noscript", "svg", "nav", "footer", "header"):
            self.skip_depth += 1
        elif tag == "p" and self.skip_depth == 0:
            self.in_p = True
            self.current = []
        elif tag == "meta":
            key = attrs.get("name") or attrs.get("property")
            value = attrs.get("content")
            if key and value and key.lower() in ("description", "og:description", "twitter:description"):
                self.meta[key.lower()] = clean(value)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg", "nav", "footer", "header") and self.skip_depth:
            self.skip_depth -= 1
        elif tag == "p" and self.in_p:
            text = clean(" ".join(self.current))
            if len(text) >= 45:
                self.paragraphs.append(text)
            self.in_p = False
            self.current = []

    def handle_data(self, data):
        if self.in_p and self.skip_depth == 0:
            self.current.append(data)


def fetch_article_text(url):
    """Extract readable article paragraphs from free public sources."""
    targets = ["https://r.jina.ai/" + url, url]
    for target in targets:
        try:
            request = urllib.request.Request(target, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read(350000).decode("utf-8", errors="ignore")
            if not raw:
                continue
            if target.startswith("https://r.jina.ai/"):
                marker = re.search(r"Markdown Content:\s*\n", raw, re.I)
                if not marker:
                    continue
                raw = raw[marker.end():]
                raw = re.sub(r"!\[[^]]*\]\([^)]*\)", " ", raw)
                raw = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", raw)
                raw = re.sub(r"(?m)^\s*(?:#{1,6}\s+|>\s*|[-*]\s+)", "", raw)
                paragraphs = [clean(p) for p in re.split(r"\n\s*\n", raw)]
            else:
                parser = ArticleParser()
                parser.feed(raw)
                paragraphs = [clean(p) for p in parser.paragraphs]
                paragraphs.extend(clean(p) for p in parser.meta.values())
            usable = []
            for p in paragraphs:
                low = p.lower()
                if not (85 <= len(p) <= 2400):
                    continue
                if BOILERPLATE.search(p):
                    continue
                if any(x in low for x in (
                    "cookie policy", "privacy policy", "subscribe to",
                    "all rights reserved", "advertisement", "enable javascript",
                    "sign up for", "related articles", "accept cookies",
                    "terms of use", "newsletters", "click here to",
                    "cloudfront", "request id:", "we can\u0027t connect to the server",
                    "access denied", "403 forbidden", "404 not found",
                    "trending tickers", "previous close", "market cap (intraday)",
                    "please verify you are human", "enable cookies"
                )):
                    continue
                usable.append(p)
            if usable:
                return usable[:12]
        except Exception:
            continue
    return []


def words(value):
    return re.findall(r"[a-z0-9]+", clean(value).lower())


def headline_duplicate(sentence, title, source=""):
    title_tokens = words(title)
    sentence_tokens = words(sentence)
    if not title_tokens or not sentence_tokens:
        return True
    if source:
        sentence_tokens = words(re.sub(re.escape(source), "", sentence, flags=re.I))
    if sentence_tokens == title_tokens:
        return True
    overlap = len(set(sentence_tokens) & set(title_tokens)) / max(1, len(set(sentence_tokens)))
    return overlap > .78 and len(sentence_tokens) <= len(title_tokens) + 10


def make_summary(title, description, url, source=""):
    """Extract 2 distinct, informative sentences; never recycle the RSS snippet."""
    paragraphs = fetch_article_text(url)
    if not paragraphs:
        return ""
    sentences = []
    for paragraph in paragraphs:
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            sentence = clean(sentence).strip(" -|:—–")
            if not (65 <= len(sentence) <= 310):
                continue
            if BOILERPLATE.search(sentence):
                continue
            if headline_duplicate(sentence, title, source):
                continue
            if re.search(r"\b(cookie|privacy|copyright|newsletter|subscribe|login|sign in|read more|follow us|terms of use|advertisement)\b", sentence, re.I):
                continue
            if sentence.endswith("?"):
                continue
            if re.search(r"(?i)(read on app|key points:|stock market crash:|related news|top stories|click to read|generated by cloudfront)", sentence):
                continue
            sentences.append(sentence)
    if not sentences:
        return ""
    # Favor facts (numbers, dates, named entities) and the beginning of the article.
    def score(pair):
        index, sentence = pair
        fact = bool(re.search(r"\d|%|\$|₹|million|billion|announced|said|reported|according to", sentence, re.I))
        overlap = len(set(words(sentence)) & set(words(title)))
        return (2 if fact else 0) + min(overlap, 4) * .35 - index * .12
    ranked = sorted(enumerate(sentences[:18]), key=score, reverse=True)
    selected = []
    for _, sentence in ranked:
        if any(len(set(words(sentence)) & set(words(prev))) / max(1, len(set(words(sentence)))) > .70 for prev in selected):
            continue
        selected.append(sentence)
        if len(selected) == 2:
            break
    if not selected:
        return ""
    # Put selected facts in article order so the result reads coherently.
    chosen = set(selected)
    selected = [sentence for sentence in sentences if sentence in chosen][:2]
    summary = " ".join(selected)
    if len(summary) < 100:
        return ""
    if BOILERPLATE.search(summary) or re.search(r"(?i)(stock price, news, quote|access denied|click to read|key points:)", summary):
        return ""
    # Never publish chopped-off statements; preserve complete sentences.
    if len(summary) > 420:
        if len(selected[0]) <= 420:
            return selected[0] if len(selected[0]) >= 100 else ""
        return ""
    return summary



def feed_url(query):
    params = {"q": query, "hl": "en-CA", "gl": "CA", "ceid": "CA:en"}
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(params)


def parse_pub(value):
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except Exception:
        return None


items = []

# Direct publisher RSS feeds provide original article links, avoiding Google News redirects.
direct_feeds = [
    ("Canada", "🇨🇦", "https://www.cbc.ca/cmlink/rss-business"),
    ("Canada", "🇨🇦", "https://globalnews.ca/feed/"),
    ("Indian Markets", "📈", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("India", "🇮🇳", "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms"),
    ("AI", "🤖", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("AI", "🤖", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
]

for category, icon, rss_url in direct_feeds:
    try:
        req = urllib.request.Request(rss_url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=12) as response:
            root = ET.fromstring(response.read(1000000))
        channel_items = root.findall("./channel/item")
        for item in channel_items[:18]:
            title = clean(item.findtext("title"))
            url = (item.findtext("link") or "").strip()
            published_raw = item.findtext("pubDate") or ""
            published = parse_pub(published_raw)
            if not title or not url or not published or published < cutoff or published > now + timedelta(minutes=5):
                continue
            if not relevant(title, category):
                continue
            description = clean(item.findtext("description"))
            source = urllib.parse.urlparse(rss_url).hostname or "Publisher"
            summary = make_summary(title, description, url, source)
            if not summary:
                continue
            items.append({
                "id": hashlib.sha256(url.encode("utf-8")).hexdigest()[:16],
                "cat": category, "icon": icon, "title": title,
                "summary": summary,
                "why": "Recent coverage selected for Briefly.",
                "importance": "Important", "source": source,
                "url": url, "published": published_raw, "publishedAt": published.isoformat()
            })
    except Exception as error:
        print("Direct RSS error:", category, rss_url, error)

for category, icon, query in feeds:
    try:
        request = urllib.request.Request(feed_url(query), headers={"User-Agent": UA})
        response = urllib.request.urlopen(request, timeout=20)
        root = ET.fromstring(response.read())

        for item in root.findall("./channel/item")[:25]:
            title = clean(item.findtext("title"))
            description = clean(item.findtext("description"))
            url = item.findtext("link") or ""
            published_raw = item.findtext("pubDate") or ""
            published = parse_pub(published_raw)

            if not published or published < cutoff or published > now + timedelta(minutes=5):
                continue
            if not relevant(title, category):
                continue

            # Google News searches occasionally return unrelated countries.
            if category == "India" and not re.search(r"(?i)\b(india|indian|delhi|mumbai|bengaluru|hyderabad|rupee|reliance|tata|infosys|hdfc|adani|nse|bse)\b", title):
                continue
            if category == "Canada" and not re.search(r"(?i)\b(canada|canadian|toronto|ontario|quebec|alberta|vancouver|ottawa|montreal|tsx|loonie)\b", title):
                continue
            if re.search(r"(?i)(stock price, news, quote|quote & history|historical data|live stock price|top 10 stocks rated|stocks to buy today)", title):
                continue
            source_element = item.find("source")
            source = clean(source_element.text or "Google News") if source_element is not None else "Google News"
            summary = make_summary(title, description, url, source)
            if not summary:
                continue
            story_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

            items.append({
                "id": story_id,
                "cat": category,
                "icon": icon,
                "title": title,
                "summary": summary,
                "why": "Selected for your Briefly topics; routine political, celebrity and sports coverage is filtered out.",
                "importance": "Important",
                "source": source,
                "url": url,
                "published": published_raw,
                "publishedAt": published.isoformat()
            })
    except Exception as error:
        print("Feed error:", category, error)

items.sort(key=lambda story: story["publishedAt"], reverse=True)
seen = set()
output = []

for story in items:
    key = " ".join(re.sub(r"[^a-z0-9 ]", "", story["title"].lower()).split()[:14])
    if not key or key in seen:
        continue
    seen.add(key)
    output.append(story)

if not output:
    raise RuntimeError("No fresh substantive news extracted; previous feed preserved")
else:
    with open("data.json", "w", encoding="utf-8") as file:
        json.dump({"updated": now.isoformat(), "stories": output[:50]}, file, ensure_ascii=False, indent=2)

print("Wrote", len(output), "stories newer than 24 hours with substantive summaries")
