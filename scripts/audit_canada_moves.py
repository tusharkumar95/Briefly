"""Audit Canada disclosure candidates without treating headlines as verified trades."""
import json
import re
from datetime import datetime, timezone

def normalize(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()

def audit():
    with open("moves-canada-candidates.json", encoding="utf-8") as f:
        candidates = json.load(f).get("records", [])
    with open("moves-canada-verified.json", encoding="utf-8") as f:
        verified = json.load(f).get("records", [])
    rows = []
    for item in candidates:
        headline = item.get("headline", "")
        title = normalize(headline.split(" - ")[0])
        matches = []
        for record in verified:
            investor = normalize(record.get("investor", ""))
            company = normalize(record.get("company", ""))
            # Conservative matching: full company name + meaningful investor token.
            company_words = [w for w in company.split() if w not in {"corp", "corporation", "inc", "ltd", "limited", "energy", "gold", "materials"}]
            investor_words = [w for w in investor.split() if len(w) >= 6 and w not in {"capital", "corporation", "minerals", "resources", "limited"}]
            if company_words and investor_words and any(w in title.split() for w in company_words) and any(w in title.split() for w in investor_words):
                matches.append({"investor": record.get("investor"), "company": record.get("company")})
        rows.append({
            "headline": headline,
            "published": item.get("published"),
            "discoveryUrl": item.get("discoveryUrl"),
            "reviewStatus": "possible_already_published" if matches else "needs_original_source_review",
            "possibleMatches": matches,
            "verified": False,
            "note": "Headline matching is only a review hint, not transaction verification."
        })
    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "candidateCount": len(rows),
        "needsReview": sum(row["reviewStatus"] == "needs_original_source_review" for row in rows),
        "possibleDuplicates": sum(row["reviewStatus"] == "possible_already_published" for row in rows),
        "records": rows,
        "policy": "Do not publish audit candidates to Moves; verify original announcements manually."
    }
    with open("moves-canada-audit.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print("Audited", len(rows), "candidates;", output["possibleDuplicates"], "possible duplicates")

if __name__ == "__main__":
    audit()
