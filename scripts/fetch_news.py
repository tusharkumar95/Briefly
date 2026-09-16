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
    ("India", "🇮🇳", "India economy business corporate technology -politics -election -bollywood -celebrity -sports when:6h"),
    ("Canada", "🇨🇦", "Canada economy business corporate technology -politics -election -celebrity -sports when:6h"),
    ("Indian Markets", "📈", "India Nifty Sensex stock market NSE BSE earnings companies when:6h"),
    ("Canadian Markets", "📈", "Canada TSX stock market banks energy mining earnings companies when:6h"),
    ("AI", "🤖", "artificial intelligence AI OpenAI Google Anthropic Meta Nvidia models agents chips research when:6h")
]

bad = re.compile(r"\b(politic|election|party|minister|parliament|bollywood|hollywood|celebrity|gossip|sports|cricket|football)\b", re.I)
now = datetime.now(timezone.utc)
cutoff = now - timedelta(hours=6)


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
    # Google News RSS links often do not redirect cleanly when fetched by urllib.
    # Jina Reader follows the article link and returns readable publisher text.
    candidates = [
        "https://r.jina.ai/" + url,
        url
    ]
    for target in candidates:
        try:
            request = urllib.request.Request(target, headers={"User-Agent": UA})
            response = urllib.request.urlopen(request, timeout=12)
            raw = response.read(500000).decode("utf-8", errors="ignore")
            if not raw:
                continue

            parser = ArticleParser()
            parser.feed(raw)
            paragraphs = []
            for paragraph in parser.paragraphs:
                lower = paragraph.lower()
                if any(x in lower for x in ("cookie policy", "privacy policy", "subscribe to", "sign up for", "all rights reserved", "advertisement")):
                    continue
                if paragraph not in paragraphs:
                    paragraphs.append(paragraph)

            meta = next(iter(parser.meta.values()), "")
            text = " ".join(paragraphs[:12])
            if len(meta) > len(text):
                text = meta + " " + text
            if len(text) >= 120:
                return text
        except Exception:
            continue
    return ""


def make_summary(title, description, url):
    text = strip_title(description, title)
    article_text = fetch_article_text(url) if len(text) < 180 else ""
    if article_text:
        text = strip_title(article_text, title)

    sentences = re.split(r"(?<=[.!?])\s+", text)
    title_words = set(re.findall(r"[a-z0-9]+", title.lower()))
    selected = []

    for sentence in sentences:
        sentence = clean(sentence)
        if len(sentence) < 45:
            continue
        words = set(re.findall(r"[a-z0-9]+", sentence.lower()))
        overlap = len(words & title_words) / max(1, len(title_words))
        if overlap > 0.70 and len(sentence) < len(title) + 60:
            continue
        selected.append(sentence)
        if len(selected) >= 5:
            break

    summary = " ".join(selected)
    if not summary:
        summary = text

    if len(summary) > 700:
        summary = summary[:697].rsplit(" ", 1)[0] + "..."
    return summary.strip()


def feed_url(query):
    params = {"q": query, "hl": "en-CA", "gl": "CA", "ceid": "CA:en"}
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(params)


def parse_pub(value):
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except Exception:
        return None


items = []

for category, icon, query in feeds:
    try:
        request = urllib.request.Request(feed_url(query), headers={"User-Agent": UA})
        response = urllib.request.urlopen(request, timeout=20)
        root = ET.fromstring(response.read())

        for item in root.findall("./channel/item")[:20]:
            title = clean(item.findtext("title"))
            description = clean(item.findtext("description"))
            url = item.findtext("link") or ""
            published_raw = item.findtext("pubDate") or ""
            published = parse_pub(published_raw)

            if not published or published < cutoff or published > now + timedelta(minutes=5):
                continue
            if category in ("India", "Canada") and bad.search(title):
                continue

            summary = make_summary(title, description, url)
            source_element = item.find("source")
            source = clean(source_element.text or "Google News") if source_element is not None else "Google News"
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

with open("data.json", "w", encoding="utf-8") as file:
    json.dump({"updated": now.isoformat(), "stories": output[:50]}, file, ensure_ascii=False, indent=2)

print("Wrote", len(output), "stories newer than 6 hours")
