import csv, io, json, urllib.request
from datetime import datetime, timezone

UA = "Mozilla/5.0 (Briefly Moves source test; personal project)"
OUT = {"testedAt": datetime.now(timezone.utc).isoformat(), "sources": {}}

def get(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json,text/csv,*/*",
        "Accept-Language": "en-CA,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read(750000)
        return r.status, r.geturl(), r.headers.get("Content-Type", ""), body

# India: first prove GitHub Actions can reach official NSE public report surfaces.
# We deliberately don't wire this into the app yet.
for key, url in {
    "nse_bulk_block_page": "https://www.nseindia.com/report-detail/display-bulk-and-block-deals",
    "nse_all_reports": "https://www.nseindia.com/all-reports",
}.items():
    try:
        status, final_url, ctype, body = get(url)
        text = body.decode("utf-8", "ignore")
        OUT["sources"][key] = {
            "ok": status == 200,
            "status": status,
            "finalUrl": final_url,
            "contentType": ctype,
            "bytes": len(body),
            "signals": {
                "bulk": "Bulk" in text or "bulk" in text,
                "block": "Block" in text or "block" in text,
                "csv": ".csv" in text.lower() or "download" in text.lower(),
            },
        }
    except Exception as e:
        OUT["sources"][key] = {"ok": False, "error": type(e).__name__ + ": " + str(e)}

# Canada: prove GitHub Actions can reach SEDI's public site and public-report help.
for key, url in {
    "sedi_public": "https://www.sedi.ca/sedi/SVTWelcome?locale=en_CA",
    "sedi_public_reports_help": "https://www.sedi.ca/sedi/new_help/english/public/Access_Public_Information/access_public_filings.htm",
}.items():
    try:
        status, final_url, ctype, body = get(url)
        text = body.decode("utf-8", "ignore")
        OUT["sources"][key] = {
            "ok": status == 200,
            "status": status,
            "finalUrl": final_url,
            "contentType": ctype,
            "bytes": len(body),
            "signals": {
                "insider": "insider" in text.lower(),
                "transaction": "transaction" in text.lower(),
                "public": "public" in text.lower(),
            },
        }
    except Exception as e:
        OUT["sources"][key] = {"ok": False, "error": type(e).__name__ + ": " + str(e)}

OUT["summary"] = {
    "allReachable": all(x.get("ok") for x in OUT["sources"].values()),
    "note": "Connectivity proof only. No Briefly UI/data files are changed by this test."
}

with open("moves-source-test.json", "w", encoding="utf-8") as f:
    json.dump(OUT, f, indent=2, ensure_ascii=False)

print(json.dumps(OUT, indent=2))
