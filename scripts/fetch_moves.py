import csv, io, json, os, re, urllib.request, hashlib
from datetime import datetime, timezone

SOURCE="https://nsearchives.nseindia.com/content/equities/bulk.csv"
UA="Mozilla/5.0 (Briefly Moves; personal research)"
HISTORY="moves-history.json"
OUTPUT="moves.json"

def fetch_csv():
    req=urllib.request.Request(SOURCE,headers={"User-Agent":UA,"Accept":"text/csv,*/*","Referer":"https://www.nseindia.com/all-reports"})
    with urllib.request.urlopen(req,timeout=25) as r:
        return r.read(2500000).decode("utf-8-sig","ignore")

def num(v):
    try:return float(str(v).replace(",","").strip())
    except:return 0.0

def load_history():
    if not os.path.exists(HISTORY): return []
    try:
        with open(HISTORY,encoding="utf-8") as f:return json.load(f).get("records",[])
    except:return []

rows=list(csv.DictReader(io.StringIO(fetch_csv())))
raw=[]
for r in rows:
    if (r.get("Date") or "").upper()=="NO RECORDS": continue
    side=(r.get("Buy/Sell") or "").strip().upper()
    if side not in ("BUY","SELL"): continue
    qty=num(r.get("Quantity Traded"))
    price=num(r.get("Trade Price / Wght. Avg. Price"))
    if qty<=0 or price<=0: continue
    raw.append({
      "date":(r.get("Date") or "").strip(),
      "symbol":(r.get("Symbol") or "").strip(),
      "company":(r.get("Security Name") or "").strip(),
      "investor":re.sub(r"\s+"," ",(r.get("Client Name") or "").strip()),
      "side":side,"quantity":int(qty),"price":round(price,2),"valueINR":round(qty*price,2)
    })

# Net same-day activity by investor/company. This suppresses firms that buy and
# sell essentially the same position during the day.
groups={}
for r in raw:
    k=(r["date"],r["symbol"],r["investor"])
    g=groups.setdefault(k,{"date":r["date"],"symbol":r["symbol"],"company":r["company"],"investor":r["investor"],
                           "buyQty":0,"sellQty":0,"buyValue":0.0,"sellValue":0.0})
    if r["side"]=="BUY":
        g["buyQty"]+=r["quantity"]; g["buyValue"]+=r["valueINR"]
    else:
        g["sellQty"]+=r["quantity"]; g["sellValue"]+=r["valueINR"]

today=[]
for g in groups.values():
    net=g["buyQty"]-g["sellQty"]
    gross=max(g["buyQty"],g["sellQty"],1)
    # Keep only meaningful net accumulation; discard near-round trips.
    if net<=0 or net/gross<0.20: continue
    # Skip rights-entitlement symbols and immaterial net purchases.
    if g["symbol"].endswith("-RE"): continue
    if net * (g["buyValue"]/g["buyQty"] if g["buyQty"] else 0) < 500000: continue
    avg=(g["buyValue"]/g["buyQty"]) if g["buyQty"] else 0
    value=net*avg
    rec={**g,"netBuyQty":net,"avgBuyPrice":round(avg,2),"netBuyValueINR":round(value,2),
         "netBuyValueCr":round(value/10000000,2),"source":"NSE Bulk Deals","sourceUrl":SOURCE}
    rec["id"]=hashlib.sha256(f'{g["date"]}|{g["symbol"]}|{g["investor"]}'.encode()).hexdigest()[:16]
    today.append(rec)

history=load_history()
byid={r.get("id"):r for r in history if r.get("id")}
for r in today: byid[r["id"]]=r
history=list(byid.values())[-5000:]

# Accumulation count is based only on our collected history; don't imply older
# ownership we haven't observed.
pair_counts={}
for r in history:
    pair=(r.get("symbol"),r.get("investor"))
    pair_counts[pair]=pair_counts.get(pair,0)+1

for r in today:
    r["observedBuyDays"]=pair_counts.get((r["symbol"],r["investor"]),1)
    r["signal"]="Accumulating" if r["observedBuyDays"]>=2 else ("Large Purchase" if r["netBuyValueCr"]>=10 else "Net Purchase")

today.sort(key=lambda x:x["netBuyValueINR"],reverse=True)
now=datetime.now(timezone.utc).isoformat()
with open(HISTORY,"w",encoding="utf-8") as f:json.dump({"updated":now,"records":history},f,indent=2,ensure_ascii=False)
with open(OUTPUT,"w",encoding="utf-8") as f:json.dump({
 "updated":now,"country":"India","source":"NSE official Bulk Deals",
 "freshness":"End-of-day disclosure data","records":today[:100]
},f,indent=2,ensure_ascii=False)
print("Raw:",len(raw),"Net purchase records:",len(today),"History:",len(history))
