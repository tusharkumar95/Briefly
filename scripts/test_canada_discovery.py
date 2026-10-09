import json, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

queries=[
  '"early warning report" "acquired" "shares" Canada when:7d',
  '"early warning" "acquiror" "acquired" TSX when:7d',
  '"early warning report" "purchase" "shares" CSE when:7d'
]
results=[]
for query in queries:
    url="https://news.google.com/rss/search?q="+urllib.parse.quote(query)+"&hl=en-CA&gl=CA&ceid=CA:en"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=25) as response:
            data=response.read(1500000)
        root=ET.fromstring(data)
        items=[]
        for item in root.findall("./channel/item")[:15]:
            items.append({
                "title":item.findtext("title",""),
                "url":item.findtext("link",""),
                "published":item.findtext("pubDate",""),
                "source":item.findtext("source","")
            })
        results.append({"query":query,"ok":True,"count":len(items),"items":items})
    except Exception as e:
        results.append({"query":query,"ok":False,"error":str(e)})
with open("moves-canada-discovery-test.json","w",encoding="utf-8") as f:
    json.dump({"testedAt":datetime.now(timezone.utc).isoformat(),"note":"Discovery candidates only; not verified investor purchases","queries":results},f,indent=2)
print("Queries:",len(results),"Candidates:",sum(len(x.get("items",[])) for x in results))

# Preserve a separate shortlist of disclosure candidates; never label as verified trades.
shortlist=[]
seen=set()
for group in results:
    for item in group.get("items",[]):
        title=item["title"]
        key=title.lower().split(" - ")[0]
        if key in seen:
            continue
        seen.add(key)
        if any(term in key for term in ("early warning","reports participation","acquires shares","strategic investment")):
            shortlist.append({"headline":title,"published":item["published"],"source":item["source"],"discoveryUrl":item["url"],"verified":False,"status":"Needs original disclosure verification"})
# Retain previously discovered candidates for 30 days so daily RSS turnover
# does not erase a disclosure before it can be verified.
try:
    with open("moves-canada-candidates.json",encoding="utf-8") as previous_file:
        previous=json.load(previous_file).get("records",[])
except (FileNotFoundError,ValueError):
    previous=[]
cutoff=datetime.now(timezone.utc)-timedelta(days=30)
for item in previous:
    key=item.get("headline","").lower().split(" - ")[0]
    if not key or key in seen:
        continue
    try:
        published=parsedate_to_datetime(item["published"])
        if published < cutoff:
            continue
    except (ValueError,TypeError,KeyError):
        continue
    seen.add(key)
    shortlist.append(item)
shortlist.sort(key=lambda item: parsedate_to_datetime(item["published"]),reverse=True)
with open("moves-canada-candidates.json","w",encoding="utf-8") as f:
    json.dump({"updated":datetime.now(timezone.utc).isoformat(),"records":shortlist,"disclaimer":"Unverified discovery candidates; do not display as confirmed purchases"},f,indent=2)
print("Shortlisted:",len(shortlist))
