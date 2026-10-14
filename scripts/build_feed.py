import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from fetch_news import (
    NOW,
    BOILERPLATE,
    collect_candidates,
    enrich_candidate,
    cluster_candidates,
    build_events,
    select_events,
    fallback_summary,
    carry_event_history,
)

SPORTS = re.compile(r"(?i)\b(hockey|nhl|nba|nfl|mlb|cfl|soccer|football|cricket|tennis|golf|playoffs?|season opener|road win|home win|senators|maple leafs|leafs|canadiens|oilers|flames|canucks|blue jays|raptors|argonauts)\b|\b\d{1,2}-\d{1,2}\b")
ENTERTAINMENT = re.compile(r"(?i)\b(celebrity|bollywood|hollywood|gossip|red carpet|movie|film|trailer|reality tv|fashion|outfit|horoscope|viral video)\b")


def seed_story(event):
    summary = fallback_summary(event)
    if len(summary) < 80 or BOILERPLATE.search(summary):
        return None
    sources = [
        {key: source[key] for key in ("name", "url", "publishedAt")}
        for source in event.get("sources", [])
    ]
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
    candidates = [
        candidate for candidate in collect_candidates()
        if not SPORTS.search(candidate.get("title", ""))
        and not ENTERTAINMENT.search(candidate.get("title", ""))
    ]
    print("Collected", len(candidates), "non-noise high-signal candidates")

    enriched = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        future_map = {pool.submit(enrich_candidate, candidate): candidate for candidate in candidates}
        for future in as_completed(future_map):
            try:
                item = future.result()
                evidence_head = (item.get("evidence") or "")[:260]
                if SPORTS.search(item.get("title", "") + " " + evidence_head):
                    continue
                if ENTERTAINMENT.search(item.get("title", "") + " " + evidence_head):
                    continue
                enriched.append(item)
            except Exception as error:
                print("Article enrichment error:", error)

    print("Readable candidates:", sum(1 for item in enriched if item.get("readable")), "/", len(enriched))
    events = build_events(cluster_candidates(enriched))
    selected = select_events(events)
    print("Selected events:", len(selected), "from", len(events), "publishable clusters")

    stories = []
    for event in selected:
        story = seed_story(event)
        if story:
            stories.append(story)
    stories = carry_event_history(stories)

    if not stories:
        raise RuntimeError("No reliable high-signal stories produced; previous feed preserved")

    with open("data.json", "w", encoding="utf-8") as handle:
        json.dump({
            "updated": NOW.isoformat(),
            "engine": "Briefly Intelligence v2",
            "editor": "Awaiting Jarvis editorial gate",
            "windowHours": 24,
            "stories": stories[:10],
        }, handle, ensure_ascii=False, indent=2)

    print("Prepared", len(stories[:10]), "events for editorial review")


if __name__ == "__main__":
    main()
