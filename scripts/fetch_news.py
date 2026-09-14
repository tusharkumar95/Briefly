import json
import re
import html
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import hashlib

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime


UA = "Mozilla/5.0 (Briefly personal news app)"

feeds = [
    (
        "India",
        "🇮🇳",
        "India economy business corporate technology "
        "-politics -election -bollywood -celebrity -sports when:6h"
    ),

    (
        "Canada",
        "🇨🇦",
        "Canada economy business corporate technology "
        "-politics -election -celebrity -sports when:6h"
    ),

    (
        "Indian Markets",
        "📈",
        "India Nifty Sensex stock market NSE BSE earnings "
        "companies when:6h"
    ),

    (
        "Canadian Markets",
        "📈",
        "Canada TSX stock market banks energy mining earnings "
        "companies when:6h"
    ),

    (
        "AI",
        "🤖",
        "artificial intelligence AI OpenAI Google Anthropic "
        "Meta Nvidia models agents chips research when:6h"
    )
]


bad = re.compile(
    r"\b("
    r"politic|election|party|minister|parliament|"
    r"bollywood|hollywood|celebrity|gossip|"
    r"sports|cricket|football"
    r")\b",
    re.I
)


now = datetime.now(timezone.utc)

cutoff = now - timedelta(hours=6)


def clean(text):
    text = html.unescape(
        re.sub(r"<[^>]+>", " ", text or "")
    )

    return re.sub(r"\s+", " ", text).strip()


def feed_url(query):
    params = {
        "q": query,
        "hl": "en-CA",
        "gl": "CA",
        "ceid": "CA:en"
    }

    return (
        "https://news.google.com/rss/search?"
        + urllib.parse.urlencode(params)
    )


def parse_pub(value):
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)

    except Exception:
        return None


items = []


for category, icon, query in feeds:

    try:

        request = urllib.request.Request(
            feed_url(query),
            headers={"User-Agent": UA}
        )

        response = urllib.request.urlopen(
            request,
            timeout=20
        )

        root = ET.fromstring(
            response.read()
        )

        for item in root.findall("./channel/item")[:20]:

            title = clean(
                item.findtext("title")
            )

            description = clean(
                item.findtext("description")
            )

            url = (
                item.findtext("link")
                or ""
            )

            published_raw = (
                item.findtext("pubDate")
                or ""
            )

            published = parse_pub(
                published_raw
            )

            # Only accept properly dated stories.
            if not published:
                continue

            # Remove anything older than 6 hours.
            if published < cutoff:
                continue

            # Ignore strange future timestamps.
            if published > now + timedelta(minutes=5):
                continue

            # Additional political / entertainment /
            # sports filtering for India and Canada.
            if category in ("India", "Canada"):

                if bad.search(title):
                    continue

            summary = (
                description
                or title
            )

            if len(summary) > 360:

                summary = (
                    summary[:357]
                    .rsplit(" ", 1)[0]
                    + "..."
                )

            source_element = item.find("source")

            if source_element is not None:

                source = clean(
                    source_element.text
                    or "Google News"
                )

            else:

                source = "Google News"


            story_id = hashlib.sha256(
                url.encode("utf-8")
            ).hexdigest()[:16]


            items.append({
                "id": story_id,
                "cat": category,
                "icon": icon,
                "title": title,
                "summary": summary,
                "why": (
                    "Selected for your Briefly topics; "
                    "routine political, celebrity and "
                    "sports coverage is filtered out."
                ),
                "importance": "Important",
                "source": source,
                "url": url,
                "published": published_raw,
                "publishedAt": published.isoformat()
            })


    except Exception as error:

        print(
            "Feed error:",
            category,
            error
        )


# Newest first.
items.sort(
    key=lambda story: story["publishedAt"],
    reverse=True
)


# Remove duplicate headlines.
seen = set()

output = []


for story in items:

    key = " ".join(
        re.sub(
            r"[^a-z0-9 ]",
            "",
            story["title"].lower()
        ).split()[:14]
    )

    if not key:
        continue

    if key in seen:
        continue

    seen.add(key)

    output.append(story)


with open(
    "data.json",
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        {
            "updated": now.isoformat(),
            "stories": output[:50]
        },
        file,
        ensure_ascii=False,
        indent=2
    )


print(
    "Wrote",
    len(output),
    "stories newer than 6 hours"
)
