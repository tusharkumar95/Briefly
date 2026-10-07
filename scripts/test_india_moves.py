import csv, io, json, re, urllib.request
from datetime import datetime, timezone

UA="Mozilla/5.0 (Briefly Moves; personal research)"
OUT={"updated":datetime.now(timezone.utc).isoformat(),"country":"India","source":"NSE","records":[],"diagnostics":[]}

def grab(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/csv,text/plain,*/*","Referer":"https://www.nseindia.com/all-reports"})
    with urllib.request.urlopen(req,timeout=20) as r:
        return r.geturl(),r.headers.get("Content-Type",""),r.read(2500000)

# NSE's All Reports publishes daily bulk.csv/block.csv report names. Try the
# official report-download surfaces rather than the protected JSON APIs.
candidates=[
 "https://nsearchives.nseindia.com/content/equities/bulk.csv",
 "https://nsearchives.nseindia.com/content/equities/block.csv",
 "https://archives.nseindia.com/content/equities/bulk.csv",
 "https://archives.nseindia.com/content/equities/block.csv",
]
for url in candidates:
    try:
        final,ctype,raw=grab(url)
        text=raw.decode("utf-8-sig","ignore")
        first=text[:300].replace("\n"," | ")
        OUT["diagnostics"].append({"url":url,"ok":True,"finalUrl":final,"contentType":ctype,"bytes":len(raw),"sample":first})
        rows=list(csv.reader(io.StringIO(text)))
        if len(rows)<2: continue
        headers=[re.sub(r"\s+"," ",x).strip() for x in rows[0]]
        low=[x.lower() for x in headers]
        # Only accept files that actually look like deal data.
        if not any("client" in x for x in low) or not any("quantity" in x or "qty" in x for x in low):
            continue
        for row in rows[1:]:
            if len(row)!=len(headers): continue
            d=dict(zip(headers,row))
            OUT["records"].append({"report":url.rsplit("/",1)[-1],"raw":d})
    except Exception as e:
        OUT["diagnostics"].append({"url":url,"ok":False,"error":type(e).__name__+": "+str(e)})

OUT["recordCount"]=len(OUT["records"])
with open("moves-india-test.json","w",encoding="utf-8") as f:
    json.dump(OUT,f,indent=2,ensure_ascii=False)
print("India records:",OUT["recordCount"])
print(json.dumps(OUT["diagnostics"],indent=2))
