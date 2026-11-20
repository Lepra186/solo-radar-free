"""Mining Scan public pool-directory verification, not new-coin discovery.

The directory's data is only corroboration for pre-existing candidates.
Respect source freshness and rate limit with a 6-hour project-wide cache.
"""
import json
from datetime import datetime,timezone,timedelta
from coin_filter import is_coin

URL="https://mining-scan.com/api/export/coins"
REFRESH=timedelta(hours=6)
ALGORITHMS={"kawpow","ethash","etchash","progpow","fishhash","autolykos",
            "equihash","octopus","verthash","firopow","zelhash","cuckoocycle","ubqhash"}

def timestamp(s):
    if not isinstance(s,str):return None
    try:
        t=datetime.fromisoformat(s.replace("Z","+00:00"))
        return t.astimezone(timezone.utc) if t.tzinfo else None
    except ValueError:
        return None

def parse_directory(payload):
    if not isinstance(payload,dict):raise ValueError("Invalid directory object")
    meta=payload.get("meta") or {}
    if not isinstance(meta,dict) or meta.get("stale") is True or meta.get("state")=="down":
        raise ValueError("Mining Scan source is stale or down")
    rows=payload.get("data")
    if not isinstance(rows,list):raise ValueError("Coin directory has no data")
    coins=[]
    for raw in rows[:1000]:
        if not isinstance(raw,dict):continue
        algorithm=str(raw.get("algorithm") or "").lower()
        symbol=str(raw.get("symbol") or "").upper()
        name=str(raw.get("coin_name") or "")
        if not symbol or not name or not any(a in algorithm for a in ALGORITHMS):
            continue
        coins.append({
          "symbol":symbol[:16],"name":name[:90],
          "algorithm":str(raw.get("algorithm") or "")[:40],
          "pools":raw.get("pool_count"),
          "blocks_48h":raw.get("blocks_48h"),
          "last_block_at":raw.get("last_block_at"),
          "slug":str(raw.get("slug") or "")[:100]
        })
    return {"checked_at":meta.get("generated_at"),"stale":False,
            "source":URL,"coins":coins[:400]}

def matches_for(topics,listing):
    # Both ticker AND coin-name matching needed; tickers can collide across coins.
    found={}
    catalog=listing.get("coins") or []
    for key,item in topics.items():
        if not isinstance(item,dict) or not is_coin(key,item):continue
        facts=item.get("facts") or {}
        ticker=str(facts.get("ticker") or "").upper()
        title=str(item.get("title") or "").lower()
        for coin in catalog:
            name=coin["name"].lower()
            if ticker and ticker!=coin["symbol"]:continue
            if len(name)<5 or name not in title:continue
            found[key]={"source":"Mining Scan","checked_at":listing.get("checked_at"),
                        "symbol":coin["symbol"],"name":coin["name"],
                        "algorithm":coin["algorithm"],"pools_reported":coin["pools"],
                        "blocks_48h_reported":coin["blocks_48h"],
                        "last_block_at":coin["last_block_at"],
                        "note":"Каталог пулов, не независимая проверка mainnet или выплат"}
            break
    return found

def refresh(fetch,state,now):
    previous=state.get("mining_scan")
    checked=timestamp((previous or {}).get("fetched_at"))
    if checked and now-checked<REFRESH:return previous,False
    try:
        raw=json.loads(fetch(URL))
        listing=parse_directory(raw)
        listing["fetched_at"]=now.isoformat(timespec="seconds")
        return listing,True
    except Exception as exc:
        print("Mining Scan evidence unavailable:",type(exc).__name__)
        return (previous or {}),False
