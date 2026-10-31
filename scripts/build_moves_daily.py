"""Build durable seven-day Moves views and immutable multi-buyer tracking cohorts.

Canada filing candidates are deliberately NOT labeled as trades.
"""
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(".")
TODAY = datetime.now(ZoneInfo("America/Toronto")).date()
NOW = datetime.now(timezone.utc).isoformat()
DAYS = 7


def read(name, fallback):
    p = HERE / name
    if not p.exists():
        return fallback
    with p.open(encoding="utf-8") as file:
        return json.load(file)


def write(name, value):
    with (HERE / name).open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")


def iso(value):
    if not value:
        return None
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return None


def in_window(day):
    return day and (TODAY - timedelta(days=DAYS)) <= date.fromisoformat(day) <= TODAY


def normalized_india(r):
    row = dict(r)
    row["market"] = "India"
    row["direction"] = str(row.get("direction") or ("BUY" if float(row.get("netBuyQty") or 0) else "SELL")).upper()
    row["day"] = iso(row.get("date"))
    row["netQty"] = int(row.get("netQty") or row.get("netBuyQty") or 0)
    row["avgPrice"] = float(row.get("avgPrice") or row.get("avgBuyPrice") or 0)
    row["valueINR"] = float(row.get("valueINR") or row.get("netBuyValueINR") or 0)
    row["valueCr"] = round(float(row.get("valueCr") or row.get("netBuyValueCr") or row["valueINR"] / 1e7), 2)
    row["moveScore"] = int(row.get("moveScore") or min(80, 45 + row["valueCr"] / 5))
    row["tags"] = row.get("tags") or (["notable"] if row["moveScore"] >= 45 else [])
    row["sourceUrl"] = row.get("sourceUrl") or "https://www.nseindia.com/report-detail/display-bulk-and-block-deals"
    row["verified"] = True
    row["id"] = str(row.get("id") or ":".join([row["day"] or "", row.get("symbol", ""), row.get("investor", ""), row.get("dealType", ""), row["direction"]]))
    return row


def normalized_canada(r):
    row = dict(r)
    row["market"] = "Canada"
    # Disclosures are indexed by filing date, NOT implied trade date.
    row["day"] = iso(row.get("disclosureDate") or row.get("date"))
    row["verified"] = True
    return row


def canadian_leads():
    candidates = read("moves-canada-candidates.json", {}).get("records", [])
    results = []
    seen = set()
    for r in candidates:
        day = iso(r.get("published"))
        headline = str(r.get("headline") or "").strip()
        key = (day, headline.lower().split(" - ")[0])
        if not day or not in_window(day) or not headline or key in seen:
            continue
        seen.add(key)
        results.append({
            "id": "lead:" + day + ":" + str(len(results)),
            "day": day,
            "headline": headline,
            "source": r.get("source", "Canadian disclosure discovery"),
            "url": r.get("discoveryUrl") or "",
            "verification": "Unverified — open original filing before acting",
        })
    return results


def create():
    existing = read("moves-tracking.json", {"schema": 1, "tracks": [], "quotes": {}})
    if not isinstance(existing.get("tracks"), list) or not isinstance(existing.get("quotes"), dict):
        raise ValueError("Invalid existing Moves tracking file; refusing to overwrite")
    history = read("moves-history.json", {}).get("records", [])
    intelligence = read("moves-intelligence.json", {}).get("records", [])
    verified = read("moves-canada-verified.json", {}).get("records", [])
    sedi = read("moves-canada-sedi.json", {}).get("records", [])
    automated = read("moves-canada-auto.json", {}).get("records", [])
    by_id = {}
    for raw in history:
        if raw.get("market") not in ("India", None):
            continue
        row = normalized_india(raw)
        if in_window(row["day"]):
            by_id[row["id"]] = row
    # Live intelligence records override historical versions with fresher scoring.
    for raw in intelligence:
        if raw.get("market") != "India":
            continue
        row = normalized_india(raw)
        if in_window(row["day"]):
            by_id[row["id"]] = row
    india = sorted(by_id.values(), key=lambda r: (r["day"], int(r.get("moveScore") or 0)), reverse=True)

    # Canada records are always verified, and are displayed by DISCLOSURE date.
    ca_by_id = {}
    for raw in [*automated, *verified, *sedi]:
        row = normalized_canada(raw)
        if row.get("company") and row.get("sourceUrl") and row.get("day"):
            key = str(row.get("sourceUrl") or row.get("id") or (row["day"], row["company"], row.get("investor")))
            ca_by_id[key] = row
    canada = sorted(ca_by_id.values(), key=lambda r: r["day"], reverse=True)
    leads = canadian_leads()

    dates = sorted({
        x["day"] for x in [*india, *canada, *leads] if in_window(x.get("day"))
    }, reverse=True)

    # A multiple-buyer event must contain distinct named buyers. A duplicate
    # bulk/block filing from one participant counts as ONE buyer.
    groups = defaultdict(dict)
    for r in [*india, *canada]:
        if r.get("direction", "BUY") != "BUY" or not in_window(r.get("day")):
            continue
        symbol = str(r.get("symbol") or "").upper().strip()
        investor = " ".join(str(r.get("investor") or "").upper().split())
        if not symbol or not investor:
            continue
        key = (r["day"], r["market"], symbol)
        previous = groups[key].get(investor)
        # Prefer a block-deal row, otherwise the higher-value record, to prevent
        # counting the same disclosed transaction twice.
        if previous is None or ("Block" in str(r.get("dealType")) and "Block" not in str(previous.get("dealType"))) or (float(r.get("valueINR") or r.get("valueCAD") or 0) > float(previous.get("valueINR") or previous.get("valueCAD") or 0)):
            groups[key][investor] = r

    tracks = {t["id"]: t for t in existing["tracks"] if t.get("id")}
    alerts = []
    for (day, market, symbol), buyers in sorted(groups.items(), reverse=True):
        if len(buyers) < 2:
            continue
        records = list(buyers.values())
        value = sum(float(r.get("valueINR") or r.get("valueCAD") or 0) for r in records)
        if value < (1_000_000 if market == "India" else 100_000):
            continue
        event_id = f"{day}:{market}:{symbol}"
        buyer_names = sorted(r.get("investor", "") for r in records)
        company = next((r.get("company") for r in records if r.get("company")), symbol)
        alert = {
            "id": event_id, "day": day, "market": market, "symbol": symbol,
            "company": company, "buyers": len(buyers), "investors": buyer_names,
            "value": round(value, 2), "currency": "INR" if market == "India" else "CAD",
            "disclosedAvgPrice": round(sum(float(r.get("avgPrice") or r.get("priceCAD") or 0) for r in records) / len(records), 4),
            "source": "Verified exchange/public disclosures", "status": "Multiple buyers disclosed; not an investment recommendation"
        }
        if market == "Canada":
            alert["exchange"] = next((r.get("exchange") for r in records if r.get("exchange")), None)
        alerts.append(alert)
        if event_id not in tracks:
            tracks[event_id] = {
                **alert, "firstDetectedAt": NOW, "firstBuyerCount": len(buyers),
                "trackingSource": "Daily market closing prices (unadjusted)",
            }
        # Keep original snapshot unchanged; never overwrite the first buyers/date.
    saved = sorted(tracks.values(), key=lambda a: a.get("day", ""), reverse=True)
    existing["schema"] = 1
    existing["updatedAt"] = NOW
    existing["tracks"] = saved[:1000]
    write("moves-tracking.json", existing)

    daily = {
        "schema": 1, "updated": NOW,
        "retentionDays": DAYS,
        "dates": dates,
        "days": [{
            "date": day,
            "india": [r for r in india if r["day"] == day],
            "canada": [r for r in canada if r["day"] == day],
            "canadaLeads": [r for r in leads if r["day"] == day],
            "alerts": [a for a in alerts if a["day"] == day],
        } for day in dates],
        "alerts": alerts,
        "canadaArchive": canada[:20],
        "sourceInfo": {
            "india": "NSE bulk/block disclosed transaction activity",
            "canada": "Verified Canadian deals and separately labeled unverified disclosure leads",
            "canadaDiscoveryUpdated": read("moves-canada-candidates.json", {}).get("updated"),
            "lastSevenDays": "Includes disclosure days in the previous seven calendar days, not just the current refresh",
        },
    }
    write("moves-daily.json", daily)
    print("Moves days:", len(dates), "India:", len(india), "Canada verified:", len(canada), "Canadian leads:", len(leads), "alerts:", len(alerts), "stored tracks:", len(saved))


if __name__ == "__main__":
    create()
