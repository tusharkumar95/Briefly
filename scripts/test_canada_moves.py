import json, urllib.request, urllib.parse, re
from datetime import datetime, timezone

OUT={"testedAt":datetime.now(timezone.utc).isoformat(),"source":"SEDAR+","tests":[]}
UA="Mozilla/5.0 (Briefly Moves; personal research)"

# Public SEDAR+ document pages are accessible without login. This test checks
# official discovery/search surfaces only; it does not use or bypass SEDI.
urls=[
 "https://www.sedarplus.ca/",
 "https://www.sedarplus.ca/csa-party/records/document.html?id=7cdddbe18836f1c8aa72645b0e63695fe73cb0b6e59ad7f1fcb63bd94178ffc2"
]
for url in urls:
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,*/*"})
        with urllib.request.urlopen(req,timeout=25) as r:
            raw=r.read(1500000)
            text=raw.decode("utf-8","ignore")
            OUT["tests"].append({
              "url":url,"ok":True,"status":r.status,"finalUrl":r.geturl(),
              "contentType":r.headers.get("Content-Type",""),"bytes":len(raw),
              "signals":{
                "earlyWarning":bool(re.search(r"early warning",text,re.I)),
                "acquisition":bool(re.search(r"acqui",text,re.I)),
                "acquiror":bool(re.search(r"acquiror|acquirer",text,re.I)),
                "shares":bool(re.search(r"shares|units",text,re.I))
              },
              "sample":re.sub(r"\\s+"," ",text[:700])[:700]
            })
    except Exception as e:
        OUT["tests"].append({"url":url,"ok":False,"error":type(e).__name__+": "+str(e)})

with open("moves-canada-source-test.json","w",encoding="utf-8") as f:
    json.dump(OUT,f,indent=2,ensure_ascii=False)
print(json.dumps(OUT,indent=2))
