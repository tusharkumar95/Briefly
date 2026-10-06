import json, re, urllib.request, urllib.parse, http.cookiejar
from datetime import datetime, timezone

UA="Mozilla/5.0 (Briefly Moves; personal research)"
OUT={"testedAt":datetime.now(timezone.utc).isoformat(),"india":{},"canada":{}}

def fetch(url, opener=None, headers=None, data=None):
    req=urllib.request.Request(url,data=data,headers={"User-Agent":UA,"Accept-Language":"en-CA,en;q=0.9",**(headers or {})})
    with (opener or urllib.request).open(req,timeout=25) as r:
        return r.status,r.geturl(),r.headers.get("Content-Type",""),r.read(1500000)

# INDIA: inspect official NSE report HTML for the actual downloadable/API routes and
# try known NSE report API candidates. Save only parsed transaction-like rows.
try:
    status,url,ctype,body=fetch("https://www.nseindia.com/report-detail/display-bulk-and-block-deals")
    html=body.decode("utf-8","ignore")
    urls=sorted(set(re.findall(r'https?://[^"\'<> ]+|/api/[^"\'<> ]+|[^"\'<> ]+\.csv[^"\'<> ]*',html,re.I)))
    relevant=[u for u in urls if any(k in u.lower() for k in ("bulk","block","deal"))][:30]
    OUT["india"]["page"]={"ok":status==200,"candidateRoutes":relevant}
    # NSE's public equity bulk/block endpoint; cookies are primed by the report page.
    cj=http.cookiejar.CookieJar()
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    fetch("https://www.nseindia.com/",opener=op)
    candidates=[
      "https://www.nseindia.com/api/snapshot-capital-market-largedeal",
      "https://www.nseindia.com/api/historical/bulk-deals",
      "https://www.nseindia.com/api/historical/block-deals"
    ]
    attempts=[]
    for endpoint in candidates:
        try:
            s,u,c,b=fetch(endpoint,opener=op,headers={"Accept":"application/json,text/plain,*/*","Referer":"https://www.nseindia.com/report-detail/display-bulk-and-block-deals"})
            txt=b.decode("utf-8","ignore")
            parsed=None
            try: parsed=json.loads(txt)
            except: pass
            attempts.append({"url":endpoint,"status":s,"contentType":c,"bytes":len(b),"json":parsed is not None,
                             "sample":parsed if parsed is not None and len(txt)<20000 else txt[:500]})
        except Exception as e:
            attempts.append({"url":endpoint,"ok":False,"error":type(e).__name__+": "+str(e)})
    OUT["india"]["apiAttempts"]=attempts
except Exception as e:
    OUT["india"]["error"]=type(e).__name__+": "+str(e)

# CANADA: establish a cookie-backed public SEDI session and reach the live
# Insider Transaction Detail search controller. We do not fake a broad scrape.
try:
    cj=http.cookiejar.CookieJar()
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    s,u,c,b=fetch("https://www.sedi.ca/sedi/SVTWelcome?locale=en_CA",opener=op)
    s2,u2,c2,b2=fetch("https://www.sedi.ca/sedi/SVTReportsAccessController?menukey=15.03.00&locale=en_CA",opener=op,
                     headers={"Referer":"https://www.sedi.ca/sedi/SVTWelcome?locale=en_CA"})
    text=b2.decode("utf-8","ignore")
    forms=re.findall(r'<form[^>]+action=["\']?([^"\' >]+)',text,re.I)
    inputs=re.findall(r'<(?:input|select)[^>]+name=["\']?([^"\' >]+)',text,re.I)
    OUT["canada"]={"welcome":s==200,"reportsStatus":s2,"finalUrl":u2,"bytes":len(b2),
                   "hasInsiderTransactionDetail":"Insider transaction detail" in text,
                   "forms":forms[:10],"inputNames":sorted(set(inputs))[:80],
                   "blocked":"perfdrive" in u2.lower() or "shieldsquare" in text.lower()}
except Exception as e:
    OUT["canada"]={"error":type(e).__name__+": "+str(e)}

with open("moves-realdata-test.json","w",encoding="utf-8") as f:
    json.dump(OUT,f,indent=2,ensure_ascii=False)
print(json.dumps(OUT,indent=2,ensure_ascii=False))
