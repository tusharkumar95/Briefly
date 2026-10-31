import csv, io, json, os, re, urllib.request, hashlib, math
from datetime import datetime, timezone

UA="Mozilla/5.0 (Briefly Moves Intelligence; personal research)"
INDIA_SOURCES={
    "Bulk Deal":("https://nsearchives.nseindia.com/content/equities/bulk.csv","NSE Bulk Deals"),
    "Block Deal":("https://nsearchives.nseindia.com/content/equities/block.csv","NSE Block Deals"),
}
HISTORY="moves-history.json"
OUTPUT="moves.json"
INTELLIGENCE_OUTPUT="moves-intelligence.json"
CANADA_VERIFIED="moves-canada-verified.json"
CANADA_SEDI="moves-canada-sedi.json"


def fetch_csv(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/csv,*/*","Referer":"https://www.nseindia.com/all-reports"})
    with urllib.request.urlopen(req,timeout=25) as r:
        return r.read(2500000).decode("utf-8-sig","ignore")


def num(v):
    try:return float(str(v).replace(",","").strip())
    except:return 0.0


def field(row,*names):
    for name in names:
        if name in row and str(row.get(name) or "").strip(): return str(row.get(name) or "").strip()
    return ""


def load_json(path,default):
    if not os.path.exists(path): return default
    try:
        with open(path,encoding="utf-8") as f:return json.load(f)
    except Exception:return default


def load_history():
    data=load_json(HISTORY,{})
    return data.get("records",[]) if isinstance(data,dict) else []


def actor_type(name):
    text=(name or "").upper()
    if re.search(r"\b(BROKING|SECURITIES|STOCK BROK|ARBITRAGE|MARKET MAK|TRADING|FINTRADE)\b",text): return "Market intermediary"
    if re.search(r"\b(FUND|MUTUAL|ASSET MANAGEMENT|AMC|INVESTMENT FUND|PORTFOLIO)\b",text): return "Fund / investment manager"
    if re.search(r"\b(BANK|INSURANCE)\b",text): return "Financial institution"
    if re.search(r"\b(LIMITED|PRIVATE|PVT|LLP|CORP|CORPORATION|CAPITAL)\b",text): return "Corporate investor"
    return "Investor"


def strength(score):
    if score>=78:return "Exceptional"
    if score>=62:return "Strong"
    if score>=45:return "Worth watching"
    return "Low signal"


def score_move(value_inr,repeat_days,net_ratio,deal_type,actor,direction="BUY",official=True):
    crore=max(0.0,value_inr/10000000)
    score=18
    if crore>=100:score+=30
    elif crore>=25:score+=25
    elif crore>=10:score+=20
    elif crore>=2:score+=13
    elif crore>=0.5:score+=7
    score+=min(24,max(0,repeat_days-1)*7)
    if net_ratio>=0.85:score+=10
    elif net_ratio>=0.55:score+=6
    elif net_ratio<0.35:score-=8
    if deal_type=="Block Deal":score+=8
    if official:score+=8
    if actor=="Market intermediary":score-=12
    if direction=="SELL":score-=2
    return max(0,min(100,int(round(score))))


def why_india(record):
    value=record["valueCr"]
    repeat=record["observedDays"]
    deal=record["dealType"].lower()
    direction=record["direction"].lower()
    pieces=[]
    if repeat>=3: pieces.append(f"This is the {repeat}th observed {direction} day for the same investor/company pair in Briefly's history")
    elif repeat==2: pieces.append(f"This is a repeat {direction}, not a one-off disclosure")
    else: pieces.append(f"The disclosed net {direction} is about ₹{value:.2f} Cr")
    if record["dealType"]=="Block Deal": pieces.append("it was reported in NSE's block-deal disclosure")
    if record["actorType"]=="Market intermediary": pieces.append("the participant appears to be a market intermediary, so conviction is discounted")
    return "; ".join(pieces)+"."


def parse_india():
    raw=[]
    source_status={}
    for deal_type,(url,source_name) in INDIA_SOURCES.items():
        try:
            text=fetch_csv(url)
            rows=list(csv.DictReader(io.StringIO(text)))
            source_status[deal_type]={"ok":True,"rows":len(rows),"url":url}
        except Exception as exc:
            rows=[]
            source_status[deal_type]={"ok":False,"error":str(exc)[:160],"url":url}
        for row in rows:
            date=field(row,"Date","DATE")
            if date.upper()=="NO RECORDS": continue
            side=field(row,"Buy/Sell","BUY/SELL","Buy / Sell","BUY / SELL").upper()
            if side not in ("BUY","SELL"): continue
            qty=num(field(row,"Quantity Traded","Quantity","QUANTITY TRADED","Qty"))
            price=num(field(row,"Trade Price / Wght. Avg. Price","Trade Price","Price","TRADE PRICE / WGHT. AVG. PRICE"))
            if qty<=0 or price<=0: continue
            symbol=field(row,"Symbol","SYMBOL")
            if not symbol or symbol.endswith("-RE"): continue
            raw.append({
                "date":date,"symbol":symbol,
                "company":field(row,"Security Name","SECURITY NAME","SecurityName") or symbol,
                "investor":re.sub(r"\s+"," ",field(row,"Client Name","CLIENT NAME","ClientName")),
                "side":side,"quantity":int(qty),"price":round(price,2),"valueINR":round(qty*price,2),
                "dealType":deal_type,"source":source_name,"sourceUrl":url
            })
    return raw,source_status


def group_india(raw):
    groups={}
    for r in raw:
        k=(r["date"],r["symbol"],r["investor"],r["dealType"])
        g=groups.setdefault(k,{"date":r["date"],"symbol":r["symbol"],"company":r["company"],"investor":r["investor"],"dealType":r["dealType"],"source":r["source"],"sourceUrl":r["sourceUrl"],"buyQty":0,"sellQty":0,"buyValue":0.0,"sellValue":0.0})
        if r["side"]=="BUY":g["buyQty"]+=r["quantity"];g["buyValue"]+=r["valueINR"]
        else:g["sellQty"]+=r["quantity"];g["sellValue"]+=r["valueINR"]
    records=[]
    for g in groups.values():
        net=g["buyQty"]-g["sellQty"]
        gross=max(g["buyQty"],g["sellQty"],1)
        ratio=abs(net)/gross
        if not net or ratio<0.20: continue
        direction="BUY" if net>0 else "SELL"
        qty=abs(net)
        relevant_qty=g["buyQty"] if direction=="BUY" else g["sellQty"]
        relevant_value=g["buyValue"] if direction=="BUY" else g["sellValue"]
        avg=(relevant_value/relevant_qty) if relevant_qty else 0
        value=qty*avg
        if value<500000: continue
        rid=hashlib.sha256(f'{g["date"]}|{g["symbol"]}|{g["investor"]}|{g["dealType"]}|{direction}'.encode()).hexdigest()[:18]
        records.append({**g,"id":rid,"market":"India","direction":direction,"netQty":qty,"netBuyQty":qty if direction=="BUY" else 0,"avgPrice":round(avg,2),"avgBuyPrice":round(avg,2) if direction=="BUY" else 0,"valueINR":round(value,2),"netBuyValueINR":round(value,2) if direction=="BUY" else 0,"valueCr":round(value/10000000,2),"netBuyValueCr":round(value/10000000,2) if direction=="BUY" else 0,"netRatio":round(ratio,3),"actorType":actor_type(g["investor"]),"verified":True,"sourceQuality":"Official exchange disclosure"})
    return records


def add_india_history(records,history):
    combined=[]
    for old in history:
        if old.get("market") in (None,"India") and old.get("symbol") and old.get("investor"):
            combined.append(old)
    existing={r.get("id"):r for r in combined if r.get("id")}
    for r in records:existing[r["id"]]=r
    india_history=list(existing.values())[-6500:]
    pair_stats={}
    for r in india_history:
        direction=r.get("direction") or ("BUY" if r.get("netBuyQty",0)>0 else "SELL")
        pair=(r.get("symbol"),r.get("investor"),direction)
        s=pair_stats.setdefault(pair,{"days":set(),"value":0.0})
        if r.get("date"):s["days"].add(r.get("date"))
        s["value"]+=float(r.get("valueINR") or r.get("netBuyValueINR") or 0)
    for r in records:
        stats=pair_stats.get((r["symbol"],r["investor"],r["direction"]),{"days":{r["date"]},"value":r["valueINR"]})
        r["observedDays"]=len(stats["days"])
        r["observedBuyDays"]=r["observedDays"] if r["direction"]=="BUY" else 0
        r["observedNetValueINR"]=round(stats["value"],2)
        r["observedNetValueCr"]=round(stats["value"]/10000000,2)
        r["moveScore"]=score_move(r["valueINR"],r["observedDays"],r["netRatio"],r["dealType"],r["actorType"],r["direction"])
        r["strength"]=strength(r["moveScore"])
        if r["direction"]=="SELL":r["signal"]="Repeated Selling" if r["observedDays"]>=2 else "Large Sale"
        elif r["observedDays"]>=2:r["signal"]="Accumulating"
        elif r["dealType"]=="Block Deal":r["signal"]="Block Purchase"
        elif r["valueCr"]>=10:r["signal"]="Large Purchase"
        else:r["signal"]="Net Purchase"
        tags=["notable"] if r["moveScore"]>=45 else []
        if r["direction"]=="SELL":tags.append("selling")
        if r["direction"]=="BUY" and r["observedDays"]>=2:tags.append("accumulating")
        r["tags"]=tags
        r["whyNotable"]=why_india(r)
    return india_history


def canada_records():
    records=[]
    verified=load_json(CANADA_VERIFIED,{}).get("records",[])
    sedi=load_json(CANADA_SEDI,{}).get("records",[])
    automated=load_json("moves-canada-auto.json",{}).get("records",[])
    unique={}
    for item in [*automated,*sedi,*verified]:
        unique[item.get("sourceUrl") or item.get("id") or str(item)]=item
    for r in unique.values():
        direction=str(r.get("direction") or "BUY").upper()
        value=float(r.get("valueCAD") or 0)
        role=str(r.get("role") or r.get("insiderRole") or "Significant shareholder / disclosed acquiror")
        is_insider=bool(re.search(r"\b(CEO|CFO|COO|CHIEF|DIRECTOR|OFFICER|PRESIDENT|EXECUTIVE|INSIDER)\b",role,re.I))
        transaction_type=str(r.get("type") or r.get("transactionType") or "Disclosed acquisition")
        score=24
        if value>=5000000:score+=24
        elif value>=1000000:score+=18
        elif value>=250000:score+=11
        if is_insider and direction=="BUY":score+=22
        if "open-market" in transaction_type.lower():score+=12
        score=min(100,score)
        rid=r.get("id") or hashlib.sha256(f'CA|{r.get("transactionDate")}|{r.get("company")}|{r.get("investor")}|{direction}'.encode()).hexdigest()[:18]
        tags=["notable"] if score>=45 else []
        if is_insider and direction=="BUY":tags.append("insider buying")
        if direction=="SELL":tags.append("selling")
        records.append({
            "id":rid,"market":"Canada","direction":direction,"company":r.get("company") or "","symbol":r.get("symbol") or "","investor":r.get("investor") or "","actorType":"Corporate insider" if is_insider else "Significant shareholder / disclosed acquiror","role":role,
            "date":r.get("transactionDate") or r.get("disclosureDate") or "","transactionDate":r.get("transactionDate"),"disclosureDate":r.get("disclosureDate"),"dealType":transaction_type,
            "quantity":int(r.get("shares") or r.get("quantity") or 0),"netQty":int(r.get("shares") or r.get("quantity") or 0),"avgPrice":round(float(r.get("priceCAD") or r.get("avgPrice") or 0),4),"valueCAD":round(value,2),"currency":"CAD",
            "moveScore":score,"strength":strength(score),"signal":"Insider Purchase" if is_insider and direction=="BUY" else ("Verified Acquisition" if direction=="BUY" else "Insider / holder sale"),"tags":tags,
            "observedDays":int(r.get("observedDays") or 1),"whyNotable":r.get("whyNotable") or ("A disclosed insider open-market purchase can be a stronger ownership signal than a grant or option exercise." if is_insider and direction=="BUY" else "This is a verified ownership change from a public disclosure; it is not treated as insider buying unless the filer role establishes that."),
            "verified":True,"source":r.get("sourceName") or "Public disclosure","sourceUrl":r.get("sourceUrl") or "https://www.sedi.ca/","sourceQuality":"SEDI / primary public disclosure" if r in sedi else "Primary/public disclosure",
            "notes":r.get("notes") or ""
        })
    return records


def main():
    raw,source_status=parse_india()
    india=group_india(raw)
    old_history=load_history()
    india_history=add_india_history(india,old_history)
    canada=canada_records()
    combined=sorted([*india,*canada],key=lambda r:(int(r.get("moveScore") or 0),float(r.get("valueINR") or r.get("valueCAD") or 0)),reverse=True)
    now=datetime.now(timezone.utc).isoformat()

    # Backward-compatible India buy feed for older clients.
    legacy=[r for r in india if r["direction"]=="BUY"]
    legacy.sort(key=lambda r:r["valueINR"],reverse=True)
    with open(OUTPUT,"w",encoding="utf-8") as f:json.dump({"updated":now,"country":"India","source":"NSE official Bulk + Block Deals","freshness":"End-of-day disclosure data","records":legacy[:120]},f,indent=2,ensure_ascii=False)

    # Preserve both directions and deal types in history for pattern detection.
    byid={r.get("id"):r for r in old_history if r.get("id")}
    for r in india_history:byid[r.get("id")]=r
    with open(HISTORY,"w",encoding="utf-8") as f:json.dump({"updated":now,"records":list(byid.values())[-7000:]},f,indent=2,ensure_ascii=False)

    with open(INTELLIGENCE_OUTPUT,"w",encoding="utf-8") as f:json.dump({
        "updated":now,"engine":"Moves Intelligence v2",
        "policy":"Rank disclosed ownership activity by size, repetition, transaction type, participant type and source quality. This is research context, not a buy/sell recommendation.",
        "sources":{"India":{"name":"NSE official Bulk + Block Deals","status":source_status},"Canada":{"name":"SEDI / verified public disclosures","automation":"SEDI blocks automated access; only independently verified public records are published, with SEDI-ready records accepted from moves-canada-sedi.json."}},
        "filters":["Notable","Accumulating","Insider Buying","Selling"],
        "records":combined[:160]
    },f,indent=2,ensure_ascii=False)
    print("India raw:",len(raw),"India intelligence:",len(india),"Canada verified:",len(canada),"Combined:",len(combined))

if __name__=="__main__":main()
