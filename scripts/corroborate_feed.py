import json
import re
import xml.etree.ElementTree as ET

from fetch_news import (
    fetch_xml,
    feed_url,
    candidate_from_item,
    similarity,
    tokens,
    fetch_article_text,
)

DATA_PATH = "data.json"
MAX_EXTRA_SOURCES = 2
MIN_SIMILARITY = 0.48


def norm(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def source_key(name, url):
    text = norm(name).lower()
    if text:
        return text
    match = re.search(r"https?://(?:www\.)?([^/]+)", str(url or ""), re.I)
    return (match.group(1) if match else str(url or "")).lower()


def search_query(title):
    words = []
    seen = set()
    for word in tokens(title):
        if word in seen:
            continue
        seen.add(word)
        words.append(word)
        if len(words) >= 7:
            break
    return " ".join(words) + " when:24h"


def shared_token_count(a, b):
    return len(set(tokens(a)) & set(tokens(b)))


def corroborate_story(story):
    title = norm(story.get("title"))
    category = story.get("cat") or "World"
    if not title:
        return 0

    existing = story.get("sources") or []
    seen = {source_key(row.get("name"), row.get("url")) for row in existing if isinstance(row, dict)}
    added = 0

    try:
        root = ET.fromstring(fetch_xml(feed_url(search_query(title))))
    except Exception as error:
        print("Corroboration search failed:", title, error)
        return 0

    for item in root.findall("./channel/item")[:24]:
        candidate = candidate_from_item(category, item, "Google News corroboration", direct=False)
        if not candidate:
            continue

        score = similarity(title, candidate.get("title", ""))
        shared = shared_token_count(title, candidate.get("title", ""))
        if score < MIN_SIMILARITY or shared < 3:
            continue

        key = source_key(candidate.get("source"), candidate.get("url"))
        if not key or key in seen:
            continue

        paragraphs = fetch_article_text(candidate.get("url", ""))
        if not paragraphs:
            continue

        existing.append({
            "name": candidate.get("source") or "Corroborating source",
            "url": candidate.get("url"),
            "publishedAt": candidate.get("published").isoformat() if candidate.get("published") else "",
        })
        seen.add(key)
        added += 1
        if added >= MAX_EXTRA_SOURCES:
            break

    if added:
        story["sources"] = existing
        story["sourceCount"] = len({source_key(row.get("name"), row.get("url")) for row in existing if isinstance(row, dict)})
        story["importanceScore"] = round(float(story.get("importanceScore", 0) or 0) + min(2.0, added * 0.8), 1)
        story["corroborated"] = True
        story["corroboratingSourcesAdded"] = added

    return added


def main():
    with open(DATA_PATH, encoding="utf-8") as handle:
        data = json.load(handle)

    total_added = 0
    corroborated = 0
    for story in data.get("stories", []):
        added = corroborate_story(story)
        total_added += added
        corroborated += int(added > 0)

    coverage = data.setdefault("coverage", {})
    coverage["corroboratedStories"] = corroborated
    coverage["addedCorroboratingSources"] = total_added

    with open(DATA_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)

    print("Corroborated", corroborated, "stories with", total_added, "additional readable sources")


if __name__ == "__main__":
    main()
