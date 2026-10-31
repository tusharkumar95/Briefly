"""Refresh daily unadjusted closes for Moves multi-buyer signal cohorts.

Price quotes are independent from disclosed execution prices. Never substitute
bulk/block trade prices for a missing exchange closing price.
"""
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

PATH = Path("moves-tracking.json")
data = json.loads(PATH.read_text(encoding="utf-8"))
quotes = data.setdefault("quotes", {})
quote_symbols = data.setdefault("quoteSymbols", {})
today = datetime.now(ZoneInfo("America/Toronto")).date()
active = {}
for track in data.get("tracks", []):
    market = track.get("market")
    symbol = track.get("symbol")
    if market not in ("India", "Canada") or not symbol:
        continue
    try:
        first = date.fromisoformat(track["day"])
    except (KeyError, ValueError):
        continue
    if 0 <= (today - first).days <= 45:
        key = f"{market}:{symbol}"
        active[key] = min(first, active.get(key, first))

updated, failures = 0, []
for key, begin in sorted(active.items()):
    market, symbol = key.split(":", 1)
    # NSE symbols are exchange-disambiguated. Canadian issuers must be
    # exchange-identified; a bare ticker can otherwise refer to another firm.
    if market == "India":
        candidates = [symbol + ".NS"]
    else:
        exchange = next((t.get("exchange") for t in data["tracks"]
                         if t.get("market") == market and t.get("symbol") == symbol and t.get("exchange")), None)
        if exchange == "TSXV":
            candidates = [symbol + ".V"]
        elif exchange == "TSX":
            candidates = [symbol + ".TO"]
        else:
            failures.append(key + ":exchange-unconfirmed")
            continue
    got = False
    for ticker in candidates:
        try:
            frame = yf.download(
                tickers=ticker, start=begin.isoformat(),
                end=(today + timedelta(days=2)).isoformat(),
                interval="1d", auto_adjust=False, progress=False, threads=False, timeout=20
            )
            if frame.empty:
                continue
            if isinstance(frame.columns, pd.MultiIndex):
                if ("Close", ticker) in frame.columns:
                    close = frame[("Close", ticker)]
                elif (ticker, "Close") in frame.columns:
                    close = frame[(ticker, "Close")]
                else:
                    continue
            else:
                close = frame["Close"]
            store = quotes.setdefault(key, {})
            for stamp, value in close.items():
                if pd.isna(value):
                    continue
                price = float(value)
                if not math.isfinite(price) or price <= 0:
                    continue
                day = pd.Timestamp(stamp).date()
                if begin <= day <= today:
                    iso = day.isoformat()
                    rounded = round(price, 4)
                    if store.get(iso) != rounded:
                        store[iso] = rounded
                        updated += 1
            quote_symbols[key] = ticker
            got = bool(store)
            if got:
                break
        except Exception as exc:
            print("Quote warning", key, ticker, str(exc)[:160])
    if not got:
        failures.append(key)

data["quotesUpdatedAt"] = datetime.now(timezone.utc).isoformat()
data["quoteFailures"] = failures
data["quoteSource"] = "Yahoo Finance via yfinance; unadjusted daily closes, possibly delayed"
PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Moves tracking:", len(active), "symbols,", updated, "quotes updated,", len(failures), "unavailable")
