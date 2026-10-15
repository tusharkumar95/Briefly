import json
import re
from urllib.parse import urlparse

from fetch_news import similarity

PREVIOUS_PATH = "previous-data.json"
CURRENT_PATH = "data.json"

PRIMARY_PATTERNS = (
    "bank of canada", "statistics canada", "statcan", "government of canada", "canada.ca",
    "reserve bank of india", "rbi", "sebi", "pib", "government of india",
    "imf", "international monetary fund", "world bank", "who", "world health organization",
    "sec.gov", "securities and exchange commission", "federal reserve", "ecb", "european central bank",
)

TIER_ONE_PATTERNS = (
    "reuters", "associated press", "ap news", "bbc", "cbc", "the globe and mail",
    "financial times", "bloomberg", "bnnbloomberg", "wall street journal", "new york times",
)

TIER_TWO_PATTERNS = (
    "global news", "economic times", "business standard", "livemint", "the hindu",
    "techcrunch", "the verge", "cnbc", "forbes", "fortune",
)


def norm(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def host(url):
    try:
        return (urlparse(str(url or "")).hostname or "").lower().removeprefix("www.")
    except Exception:
        return ""


def source_text(source):
    return (norm(source.get("name", "")) + " " + host(source.get("url", ""))).lower()


def source_tier(source):
    text = source_text(source)
    if any(pattern in text for pattern in PRIMARY_PATTERNS):
        return "primary", 4
    if any(pattern in text for pattern in TIER_ONE_PATTERNS):
        return "tier-1", 3
    if any(pattern in text for pattern in TIER_TWO_PATTERNS):
        return "tier-2", 2
    return "general", 1


def source_quality(story):
    sources = story.get("sources") or []
    tiers = [source_tier(source) for source in sources if isinstance(source, dict)]
    if not tiers:
        return {"label": "general", "bestRank": 1, "trustedCount": 0, "primaryCount": 0}
    best = max(rank for _, rank in tiers)
    label = {4: "primary", 3: "tier-1", 2: "tier-2", 1: "general"}[best]
    trusted = sum(1 for _, rank in tiers if rank >= 3)
    primary = sum(1 for _, rank in tiers if rank == 4)
    return {"label": label, "bestRank": best, "trustedCount": trusted, "primaryCount": primary}


def load(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def best_previous_match(story, previous_stories):
    exact = next((old for old in previous_stories if old.get("id") and old.get("id") == story.get("id")), None)
    if exact:
        return exact, 1.0
    best_story = None
    best_score = 0.0
    for old in previous_stories:
        score = similarity(story.get("title", ""), old.get("title", ""))
        if score > best_score:
            best_story, best_score = old, score
    return (best_story, best_score) if best_score >= 0.50 else (None, best_score)


def material_change(story, previous, title_similarity):
    if previous is None:
        return True, "New high-signal event entered the brief."

    current_summary = norm(story.get("summary", ""))
    old_summary = norm(previous.get("summary", ""))
    summary_similarity = similarity(current_summary[:650], old_summary[:650]) if current_summary and old_summary else 1.0
    source_delta = int(story.get("sourceCount", 1) or 1) - int(previous.get("sourceCount", 1) or 1)
    score_delta = float(story.get("importanceScore", 0) or 0) - float(previous.get("importanceScore", 0) or 0)
    verification_upgraded = bool(story.get("verified")) and not bool(previous.get("verified"))

    if title_similarity < 0.70 or summary_similarity < 0.56:
        return True, "Material details changed since the previous brief."
    if source_delta > 0:
        return True, f"{source_delta} additional source{'s' if source_delta != 1 else ''} now support this event."
    if verification_upgraded:
        return True, "Jarvis verification is now available for this event."
    if abs(score_delta) >= 2.0:
        direction = "rose" if score_delta > 0 else "fell"
        return True, f"Its significance score {direction} as the evidence changed."
    return False, "No material change since the previous brief."


def main():
    current = load(CURRENT_PATH)
    previous = load(PREVIOUS_PATH)
    current_stories = current.get("stories") or []
    previous_stories = previous.get("stories") or []

    counts = {"new": 0, "updated": 0, "continuing": 0}

    for story in current_stories:
        quality = source_quality(story)
        story["sourceQuality"] = quality["label"]
        story["trustedSourceCount"] = quality["trustedCount"]
        story["primarySourceCount"] = quality["primaryCount"]

        old, match_score = best_previous_match(story, previous_stories)
        if old:
            # Stable IDs make an event remain the same event even as headlines evolve.
            if old.get("id"):
                story["id"] = old["id"]
            story["firstSeen"] = old.get("firstSeen") or old.get("publishedAt") or story.get("firstSeen") or story.get("publishedAt")
            story["previousTitle"] = norm(old.get("title", ""))[:180]
            story["previousSummary"] = norm(old.get("summary", ""))[:700]
            story["previousPublishedAt"] = old.get("publishedAt", "")
            story["previousSourceCount"] = int(old.get("sourceCount", 1) or 1)
            story["previousImportanceScore"] = float(old.get("importanceScore", 0) or 0)
            changed, note = material_change(story, old, match_score)
            story["changed"] = changed
            story["change"] = note
            story["lifecycle"] = "Updated" if changed else "Continuing"
            # Keep the existing status vocabulary for current clients while exposing
            # a more precise lifecycle field to Jarvis and newer clients.
            story["status"] = "Updated"
            counts["updated" if changed else "continuing"] += 1
        else:
            story["changed"] = True
            story["change"] = "New high-signal event entered the brief."
            story["lifecycle"] = "New"
            story["status"] = "New"
            counts["new"] += 1

    current["previousUpdated"] = previous.get("updated", "")
    current["changeSummary"] = counts
    current["sourceQualityModel"] = "primary / tier-1 / tier-2 / general"

    with open(CURRENT_PATH, "w", encoding="utf-8") as handle:
        json.dump(current, handle, ensure_ascii=False, indent=2)

    print("Event memory:", counts)
    print("Trusted-source stories:", sum(1 for story in current_stories if int(story.get("trustedSourceCount", 0)) > 0))
    print("Primary-source stories:", sum(1 for story in current_stories if int(story.get("primarySourceCount", 0)) > 0))


if __name__ == "__main__":
    main()
