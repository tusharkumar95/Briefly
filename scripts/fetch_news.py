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
    ("India", "🇮🇳", "India economy business corporate technology -politics -election -bollywood -celebrity -sports when:12h"),
    ("Canada", "🇨🇦", "Canada economy business corporate technology -politics -election -celebrity -sports when:12h"),
    ("Indian Markets", "📈", "India Nifty Sensex stock market NSE BSE earnings companies when:12h"),
    ("Canadian Markets", "📈", "Canada TSX stock market banks energy mining earnings companies when:12h"),
    ("AI", "🤖", "artificial intelligence AI OpenAI Google Anthropic Meta Nvidia models agents chips research when:12h")
]

bad = re.compile(r"\b(politic|election|party|minister|parliament|bollywood|hollywood|celebrity|gossip|sports|cricket|football)\b", re.I)
now = datetime.now(timezone.utc)
cutoff = now - timedelta(hours=12)


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
    """Get readable article content, never mistake an RSS headline for an article."""
    candidates = ["https://r.jina.ai/" + url, url]
    for target in candidates:
        try:
            request = urllib.request.Request(target, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=12) as response:
                raw = response.read(500000).decode("utf-8", errors="ignore")
            if not raw:
                continue
            if target.startswith("https://r.jina.ai/"):
                # Jina Reader returns markdown/plain text, NOT HTML.
                match = re.search(r"Markdown Content:\\s*\\n", raw, re.I)
                raw = raw[match.end():] if match else raw
                raw = re.sub(r"!\\[[^]]*\\]\\([^)]*\\)", " ", raw)
                raw = re.sub(r"\\[([^]]+)\\]\\([^)]*\\)", r"\\1", raw)
                raw = re.sub(r"(?m)^\\s*(?:#{1,6}\\s+|>\\s*|[-*]\\s+)", "", raw)
                raw = re.sub(r"(?m)^\\s*(?:Title:|URL Source:|Published Time:|Content type:).*?$", "", raw)
                paragraphs = [clean(p) for p in re.split(r"\\n\\s*\\n", raw)]
            else:
                parser = ArticleParser()
                parser.feed(raw)
                paragraphs = [clean(p) for p in parser.paragraphs]
                paragraphs += [clean(p) for p in parser.meta.values()]
            usable = []
            for paragraph in paragraphs:
                lower = paragraph.lower()
                if len(paragraph) < 90 or len(paragraph) > 3000:
                    continue
                if any(x in lower for x in ("cookie policy", "privacy policy", "subscribe to", "sign up for", "all rights reserved", "advertisement", "javascript is disabled", "enable javascript", "google news", "related articles")):
                    continue
                usable.append(paragraph)
            if usable:
                return " ".join(usable[:8])[:6000]
        except Exception:
            continue
    return ""


def normalized_words(value):
    return re.findall(r"[a-z0-9]+", clean(value).lower())


def is_repeated_headline(sentence, title, source=""):
    sentence_words = normalized_words(sentence)
    title_words = normalized_words(title)
    if not sentence_words or not title_words:
        return True
    # Google RSS descriptions often contain only the headline and publisher.
    stripped = re.sub(re.escape(source), "", sentence, flags=re.I) if source else sentence
    stripped_words = normalized_words(stripped)
    if stripped_words == title_words or stripped_words == title_words[:len(stripped_words)]:
        return True
    a, b = set(sentence_words), set(title_words)
    overlap = len(a & b) / max(1, len(a))
    return overlap >= .82 and len(sentence_words) <= len(title_words) + 8


def make_summary(title, description, url, source=""):
    # RSS descriptions are often just the title. Never use them as fallback.
    article_text = fetch_article_text(url)
    if not article_text:
        return ""
    candidates = re.split(r"(?<=[.!?])\\s+|\\n+", article_text)
    selected = []
    for sentence in candidates:
        sentence = clean(sentence).strip(" -|:—–")
        if len(sentence) < 65 or len(sentence) > 500:
            continue
        if is_repeated_headline(sentence, title, source):
            continue
        if re.search(r"(?i)\\b(privacy|copyright|sign in|newsletter|cookies|subscribe|read more|follow us|terms of use|related stories)\\b", sentence):
            continue
        if any(sentence.lower() in previous.lower() or previous.lower() in sentence.lower() for previous in selected):
            continue
        selected.append(sentence)
        if len(selected) == 2:
            break
    # Two substantive sentences provide an actual 2–3 line explanation.
    if len(selected) < 2:
        return ""
    summary = " ".join(selected)
    return summary[:420].rsplit(" ", 1)[0] + "…" if len(summary) > 420 else summary



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

with open("data.json", "w", encoding="utf-8") as file:
    json.dump({"updated": now.isoformat(), "stories": output[:50]}, file, ensure_ascii=False, indent=2)

print("Wrote", len(output), "stories newer than 12 hours with substantive summaries")
