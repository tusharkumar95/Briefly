import json,re,html,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from datetime import datetime,timezone
UA="Mozilla/5.0 (Briefly personal news app)"
feeds=[("India","🇮🇳","India economy business corporate technology -politics -election -bollywood -celebrity -sports"),("Canada","🇨🇦","Canada economy business corporate technology -politics -election -celebrity -sports"),("Indian Markets","📈","India Nifty Sensex stock market NSE BSE earnings companies"),("Canadian Markets","📈","Canada TSX stock market banks energy mining earnings companies"),("AI","🤖","artificial intelligence AI OpenAI Google Anthropic Meta Nvidia models agents chips research")]
bad=re.compile(r'\b(politic|election|party|minister|parliament|bollywood|hollywood|celebrity|gossip|sports|cricket|football)\b',re.I)
def clean(s):
 s=html.unescape(re.sub(r'<[^>]+>',' ',s or ''));return re.sub(r'\s+',' ',s).strip()
def feed_url(q):return "https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":q,"hl":"en-CA","gl":"CA","ceid":"CA:en"})
items=[]
for cat,icon,q in feeds:
 try:
  req=urllib.request.Request(feed_url(q),headers={"User-Agent":UA});root=ET.fromstring(urllib.request.urlopen(req,timeout=20).read())
  for it in root.findall("./channel/item")[:12]:
   title=clean(it.findtext("title"));desc=clean(it.findtext("description"));url=it.findtext("link") or "";pub=it.findtext("pubDate") or "";se=it.find("source");source=clean(se.text if se is not None else "Google News")
   if cat in ("India","Canada") and bad.search(title):continue
   summary=desc or title
   if len(summary)>360:summary=summary[:357].rsplit(" ",1)[0]+"..."
   items.append({"id":str(abs(hash(url))),"cat":cat,"icon":icon,"title":title,"summary":summary,"why":"Selected for your Briefly topics; routine political, celebrity and sports coverage is filtered out.","importance":"Important","source":source,"url":url,"published":pub})
 except Exception as e: print("feed error",cat,e)
seen=set();out=[]
for x in items:
 key=" ".join(re.sub(r'[^a-z0-9 ]','',x["title"].lower()).split()[:12])
 if key and key not in seen:seen.add(key);out.append(x)
with open("data.json","w",encoding="utf-8") as f:json.dump({"updated":datetime.now(timezone.utc).isoformat(),"stories":out[:45]},f,ensure_ascii=False,indent=2)
print("Wrote",len(out),"stories")
