import json
from datetime import datetime, timezone, timedelta

DATA_PATH = "data.json"
HISTORY_PATH = "history.json"
SNAPSHOT_RETENTION_HOURS = 72
EVENT_RETENTION_DAYS = 7
MAX_EVENT_SNAPSHOTS = 24


def load(path, default):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def parse_dt(value):
    try:
        text = str(value or "")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def compact_story(story):
    return {
        "id": story.get("id"),
        "cat": story.get("cat"),
        "title": story.get("title"),
        "summary": story.get("summary"),
        "why": story.get("why"),
        "publishedAt": story.get("publishedAt"),
        "firstSeen": story.get("firstSeen"),
        "importanceScore": story.get("importanceScore"),
        "sourceCount": story.get("sourceCount"),
        "sourceQuality": story.get("sourceQuality"),
        "verified": bool(story.get("verified")),
        "confidence": story.get("confidence"),
        "lifecycle": story.get("lifecycle"),
        "changed": bool(story.get("changed")),
        "change": story.get("change"),
        "url": story.get("url"),
    }


def main():
    now = datetime.now(timezone.utc)
    current = load(DATA_PATH, {})
    history = load(HISTORY_PATH, {
        "retentionHours": SNAPSHOT_RETENTION_HOURS,
        "eventRetentionDays": EVENT_RETENTION_DAYS,
        "snapshots": [],
        "events": {}
    })

    at = current.get("updated") or now.isoformat()
    stories = [compact_story(story) for story in current.get("stories", []) if story.get("id")]

    snapshots = history.get("snapshots") or []
    snapshots = [row for row in snapshots if row.get("at") != at]
    snapshots.append({
        "at": at,
        "changeSummary": current.get("changeSummary") or {},
        "stories": stories,
    })

    snapshot_cutoff = now - timedelta(hours=SNAPSHOT_RETENTION_HOURS)
    snapshots = [
        row for row in snapshots
        if (parse_dt(row.get("at")) or now) >= snapshot_cutoff
    ]
    snapshots.sort(key=lambda row: row.get("at", ""))
    history["snapshots"] = snapshots[-SNAPSHOT_RETENTION_HOURS:]

    events = history.get("events") or {}
    event_cutoff = now - timedelta(days=EVENT_RETENTION_DAYS)

    for story in stories:
        event_id = story["id"]
        event = events.get(event_id) or {
            "id": event_id,
            "firstSeen": story.get("firstSeen") or story.get("publishedAt") or at,
            "snapshots": []
        }
        event["lastSeen"] = at
        event["cat"] = story.get("cat")
        event["latestTitle"] = story.get("title")
        event["latestSummary"] = story.get("summary")
        event["why"] = story.get("why")
        event["url"] = story.get("url")
        event_snaps = event.get("snapshots") or []
        event_snaps = [row for row in event_snaps if row.get("at") != at]
        event_snaps.append({
            "at": at,
            "title": story.get("title"),
            "summary": story.get("summary"),
            "importanceScore": story.get("importanceScore"),
            "sourceCount": story.get("sourceCount"),
            "sourceQuality": story.get("sourceQuality"),
            "verified": story.get("verified"),
            "confidence": story.get("confidence"),
            "lifecycle": story.get("lifecycle"),
            "changed": story.get("changed"),
            "change": story.get("change"),
        })
        event["snapshots"] = event_snaps[-MAX_EVENT_SNAPSHOTS:]
        events[event_id] = event

    kept_events = {}
    for event_id, event in events.items():
        last_seen = parse_dt(event.get("lastSeen"))
        if last_seen and last_seen >= event_cutoff:
            kept_events[event_id] = event

    history["events"] = kept_events
    history["updated"] = at
    history["retentionHours"] = SNAPSHOT_RETENTION_HOURS
    history["eventRetentionDays"] = EVENT_RETENTION_DAYS

    available_from = snapshots[0]["at"] if snapshots else at
    current["history"] = {
        "availableFrom": available_from,
        "updated": at,
        "snapshotCount": len(snapshots),
        "eventCount": len(kept_events),
        "retentionHours": SNAPSHOT_RETENTION_HOURS,
    }

    with open(HISTORY_PATH, "w", encoding="utf-8") as handle:
        json.dump(history, handle, ensure_ascii=False, indent=2)

    with open(DATA_PATH, "w", encoding="utf-8") as handle:
        json.dump(current, handle, ensure_ascii=False, indent=2)

    print("History snapshots:", len(snapshots), "events:", len(kept_events), "available from:", available_from)


if __name__ == "__main__":
    main()
