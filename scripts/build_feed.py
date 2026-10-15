import json
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

from fetch_news import (
    NOW,
    BOILERPLATE,
    DIRECT_FEEDS,
    SEARCH_FEEDS,
    fetch_xml,
    feed_url,
    candidate_from_item,
    hostname,
    enrich_candidate,
    cluster_candidates,
    build_events,
    select_events,
    fallback_summary,
    carry_event_history,
)

SPORTS = re.compile(r"(?i)\b(hockey|nhl|nba|nfl|mlb|cfl|soccer|football|cricket|tennis|golf|playoffs?|season opener|road win|home win|senators|maple leafs|leafs|canadiens|oilers|flames|canucks|blue jays|raptors|argonauts)\b|\b\d{1,2}-\d{1,2}\b")
ENTERTAINMENT = re.compile(r"(?i)\b(celebrity|bollywood|hollywood|gossip|red carpet|movie|film|trailer|reality tv|fashion|outfit|horoscope|viral video)\b")
LOCAL_INCIDENT = re.compile(r"(?i)\b(local residents?|vehicle owners?|fuel tanks?|stolen car|car theft|rollercoaster|amusement park|house fire|apartment fire|missing person|police search|charged with|arrested after|fatal crash|road crash|shooting investigation)\b")
ROUTINE_MARKET = re.compile(r"(?i)\b(shares? (?:soar|surge|jump|rise|gain|fall|drop|slip)|q[1-4].*(?:profit|revenue|earnings)|profit (?:rises?|jumps?|falls?|drops?))\b")
MAJOR_COMPANY = re.compile(r"(?i)\b(reliance|tata|infosys|hdfc|icici|sbi|adani|bharti airtel|larsen|microsoft|apple|google|alphabet|amazon|meta|nvidia|openai|anthropic|tesla|bank of america|jpmorgan|goldman sachs)\b")
MATERIAL = re.compile(r"(?i)\b(war|conflict|ceasefire|sanctions|missile|invasion|attack|earthquake|hurricane|flood|wildfire|disaster|emergency|outbreak|cyberattack|major outage|recession|default|bankruptcy|tariff|trade deal|trade war|rate cut|rate hike|interest rates?|inflation|gdp|unemployment|mass layoffs?|merger|acquisition|takeover|ipo|regulation|antitrust|court ruling|ban|approval|breakthrough|semiconductor|chips?|nuclear|energy crisis|supply chain|housing|mortgage|imf|world bank|central bank|bank of canada|rbi|money laundering|billion|trillion)\b")
CANADA_SIGNAL = re.compile(r"(?i)\b(canada|canadian|toronto|ontario|quebec|alberta|vancouver|ottawa|montreal|tsx|loonie|bank of canada)\b")
INDIA_SIGNAL = re.compile(r"(?i)\b(india|indian|delhi|mumbai|bengaluru|hyderabad|rupee|rbi|nse|bse|nifty|sensex|reliance|tata|infosys|hdfc|adani)\b")
AI_SOFT_STORY = re.compile(r"(?i)\b(pitches?|betting on|demo(?:s|ed)?|showcases?|explains?|shares? how|sends? ai agents?|new labels?|music labels?|creator tools?|tips?|interview|podcast)\b")
AI_MATERIAL = re.compile(r"(?i)\b(regulation|law|ban|court ruling|copyright|antitrust|acquisition|merger|bankruptcy|security breach|cyberattack|major outage|export controls?|semiconductor|chips?|data cent(?:er|re)|compute|billion|breakthrough|benchmark record|launches?.*(?:model|chip|agent)|releases?.*(?:model|chip|agent)|rolls? out.*(?:model|chip|agent))\b")

TRUSTED_SOURCE = re.compile(
    r"(?i)\b(reuters|associated press|ap news|bbc|cbc|the globe and mail|financial times|bloomberg|bnnbloomberg|"
    r"bank of canada|statistics canada|statcan|reserve bank of india|rbi|sebi|international monetary fund|imf|"
    r"world bank|world health organization|who|government of canada|government of india)\b"
)

PRIMARY_SOURCE = re.compile(
    r"(?i)\b(bank of canada|statistics canada|statcan|reserve bank of india|rbi|sebi|international monetary fund|imf|"
    r"world bank|world health organization|who|government of canada|government of india|openai|anthropic|deepmind)\b"
)

OFFICIAL_SEARCH_FEEDS = [
    ("World", "(site:imf.org OR site:worldbank.org OR site:who.int) global economy growth health emergency when:24h"),
    ("Canada", "(site:bankofcanada.ca OR site:statcan.gc.ca OR site:canada.ca) Canada economy inflation jobs housing trade when:24h"),
    ("India", "(site:rbi.org.in OR site:sebi.gov.in OR site:pib.gov.in) India economy banking markets trade regulation when:24h"),
    ("AI", "(site:openai.com OR site:anthropic.com OR site:deepmind.google) artificial intelligence model research safety platform when:24h"),
]


def source_boost(candidate, official_hint=False):
    text = f"{candidate.get('source','')} {hostname(candidate.get('url',''))}"
    boost = 0.0
    if TRUSTED_SOURCE.search(text):
        boost += 1.6
    if PRIMARY_SOURCE.search(text):
        boost += 1.4
    if official_hint:
        boost += 1.5
    return boost


def accept_region_candidate(candidate):
    title = candidate.get("title", "")
    category = candidate.get("category")
    if category == "Canada" and not CANADA_SIGNAL.search(title):
        return False
    if category == "India" and not INDIA_SIGNAL.search(title):
        return False
    return True


def append_candidate(candidates, seen_urls, candidate, official_hint=False):
    if not candidate or not accept_region_candidate(candidate):
        return
    if candidate["url"] in seen_urls:
        return
    seen_urls.add(candidate["url"])
    candidate["preScore"] += source_boost(candidate, official_hint=official_hint)
    candidate["officialHint"] = bool(official_hint or PRIMARY_SOURCE.search(f"{candidate.get('source','')} {hostname(candidate.get('url',''))}"))
    candidates.append(candidate)


def collect_candidates_v2():
    candidates = []
    seen_urls = set()

    for category, rss_url in DIRECT_FEEDS:
        try:
            root = ET.fromstring(fetch_xml(rss_url))
            for item in root.findall("./channel/item")[:24]:
                append_candidate(candidates, seen_urls, candidate_from_item(category, item, hostname(rss_url), direct=True))
        except Exception as error:
            print("Direct feed error:", category, rss_url, error)

    for category, query in SEARCH_FEEDS:
        try:
            root = ET.fromstring(fetch_xml(feed_url(query)))
            for item in root.findall("./channel/item")[:36]:
                append_candidate(candidates, seen_urls, candidate_from_item(category, item, "Google News", direct=False))
        except Exception as error:
            print("Search feed error:", category, error)

    for category, query in OFFICIAL_SEARCH_FEEDS:
        try:
            root = ET.fromstring(fetch_xml(feed_url(query)))
            for item in root.findall("./channel/item")[:18]:
                append_candidate(candidates, seen_urls, candidate_from_item(category, item, "Official search", direct=False), official_hint=True)
        except Exception as error:
            print("Official-source search error:", category, error)

    candidates.sort(key=lambda item: item["preScore"], reverse=True)
    return candidates[:80]


def materially_useful(event):
    title = event.get("title", "")
    if SPORTS.search(title) or ENTERTAINMENT.search(title) or LOCAL_INCIDENT.search(title):
        return False
    source_count = int(event.get("sourceCount", 1) or 1)
    category = event.get("cat")
    if category in ("Canadian Markets", "Indian Markets") and ROUTINE_MARKET.search(title):
        if source_count < 2 and not MAJOR_COMPANY.search(title):
            return False
    if category in ("World", "Canada", "India") and not MATERIAL.search(title) and source_count < 2:
        return False
    if category == "AI":
        if source_count < 2 and AI_SOFT_STORY.search(title):
            return False
        if source_count >= 2:
            return bool(AI_MATERIAL.search(title) or MATERIAL.search(title) or MAJOR_COMPANY.search(title))
        return bool(AI_MATERIAL.search(title) or (MAJOR_COMPANY.search(title) and re.search(r"(?i)\b(launch|release|acquire|buy|invest|fund|regulat|ban|lawsuit|court|outage|breach|chip|model)\b", title)))
    return True


def seed_story(event):
    summary = fallback_summary(event)
    if len(summary) < 80 or BOILERPLATE.search(summary):
        return None
    sources = [{key: source[key] for key in ("name", "url", "publishedAt")} for source in event.get("sources", [])]
    if not sources:
        return None
    return {
        **{key: value for key, value in event.items() if key != "sources"},
        "summary": summary,
        "why": "Pending final editorial review.",
        "confidence": "medium" if event.get("sourceCount", 1) > 1 else "low",
        "verified": False,
        "editor": "Source extraction",
        "sources": sources,
    }


def main():
    raw_candidates = collect_candidates_v2()
    candidates = [candidate for candidate in raw_candidates if not SPORTS.search(candidate.get("title", "")) and not ENTERTAINMENT.search(candidate.get("title", "")) and not LOCAL_INCIDENT.search(candidate.get("title", ""))]
    official_count = sum(1 for candidate in candidates if candidate.get("officialHint"))
    print("Collected", len(candidates), "non-noise candidates while preserving corroboration")
    print("Official/primary candidates:", official_count)

    enriched = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        future_map = {pool.submit(enrich_candidate, candidate): candidate for candidate in candidates}
        for future in as_completed(future_map):
            try:
                item = future.result()
                evidence_head = (item.get("evidence") or "")[:260]
                combined = item.get("title", "") + " " + evidence_head
                if SPORTS.search(combined) or ENTERTAINMENT.search(combined) or LOCAL_INCIDENT.search(combined):
                    continue
                enriched.append(item)
            except Exception as error:
                print("Article enrichment error:", error)

    readable_count = sum(1 for item in enriched if item.get("readable"))
    print("Readable candidates:", readable_count, "/", len(enriched))
    events = build_events(cluster_candidates(enriched))
    material_events = [event for event in events if materially_useful(event)]
    selected = select_events(material_events)
    print("Material events:", len(material_events), "from", len(events), "publishable clusters")
    print("Selected events:", len(selected))

    stories = []
    for event in selected:
        story = seed_story(event)
        if story:
            stories.append(story)
    stories = carry_event_history(stories)
    if not stories:
        raise RuntimeError("No reliable high-signal stories produced; previous feed preserved")

    coverage = {
        "rawCandidates": len(raw_candidates),
        "nonNoiseCandidates": len(candidates),
        "officialOrPrimaryCandidates": official_count,
        "enrichedCandidates": len(enriched),
        "readableCandidates": readable_count,
        "eventClusters": len(events),
        "materialEvents": len(material_events),
        "selectedEvents": len(selected),
        "seededStories": len(stories),
    }

    with open("data.json", "w", encoding="utf-8") as handle:
        json.dump({
            "updated": NOW.isoformat(),
            "engine": "Briefly Intelligence v2",
            "editor": "Awaiting Jarvis editorial gate",
            "windowHours": 24,
            "coverage": coverage,
            "stories": stories[:10],
        }, handle, ensure_ascii=False, indent=2)

    print("Coverage telemetry:", coverage)
    print("Prepared", len(stories[:10]), "material events for editorial review")


if __name__ == "__main__":
    main()
