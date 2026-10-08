import json, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone
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
