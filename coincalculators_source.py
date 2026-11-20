"""Free CoinCalculators public network statistics as cross-reference, not proof.

API does not guarantee per-coin field timestamps. observed_at is retrieval
time and MUST NOT be interpreted as network observation freshness. Never use
ticker-only matching or feed data to silently assert RTX hashrate or profits.
"""
import json
import math
import re
from datetime import datetime,timezone,timedelta

URL="https://coincalculators.io/api/coins.json"
CACHE=timedelta(hours=6)
KNOWN_ALGOS={"ethash","etchash","kawpow","progpow","fishhash",
 "autolykos","autolykos2","equihash","octopus","verthash","firopow"}

def norm(x):
    return re.sub(r"[^a-z0-9]","",str(x or "").lower())

def time_value(x):
    if not isinstance(x,str):return None
    try:
        t=datetime.fromisoformat(x.replace("Z","+00:00"))
        return t.astimezone(timezone.utc) if t.tzinfo else None
    except ValueError:return None

def number(x):
    if isinstance(x,bool):return None
    try:
        v=float(x)
        return v if math.isfinite(v) and 0<v<1e60 else None
    except (ValueError,TypeError):return None

def directory(payload,now):
    if not isinstance(payload,dict) or not isinstance(payload.get("coins"),dict):
        raise ValueError("CoinCalculators coins catalog missing")
    records=[]
    for name,raw in list(payload["coins"].items())[:1000]:
        if not isinstance(raw,dict):continue
        ticker=str(raw.get("tag") or "").upper()
        algo=norm(raw.get("algorithm"))
        if (not ticker or not re.fullmatch(r"[A-Z0-9]{2,14}",ticker)
            or algo not in KNOWN_ALGOS or not norm(name)):
            continue
        records.append({
            "name":str(name)[:95],"ticker":ticker,"algorithm":str(raw.get("algorithm"))[:50],
            "nethash_hs_reported":number(raw.get("nethash")),
            "block_time_seconds_reported":number(raw.get("block_time")),
            "block_reward_reported":number(raw.get("block_reward")),
            "difficulty_text":str(raw.get("difficulty") or "")[:30],
            # Prices are not used for income: markets, spreads and exit venues
            # need independent verification.
            "source":URL
        })
    return {"observed_at":now.isoformat(timespec="seconds"),
            "provider_update_time":"not_provided","source":URL,"coins":records[:500]}

def update(fetch,state,now):
    old=state.get("coin_calculators") or {}
    previous=time_value(old.get("observed_at"))
    if previous and timedelta(0)<=now-previous<CACHE:return old,False
    try:
        result=directory(json.loads(fetch(URL)),now)
        return result,True
    except Exception as exc:
        print("CoinCalculators unavailable:",type(exc).__name__,str(exc)[:90])
        return old,False

def matched(topics,catalog,now):
    seen=time_value(catalog.get("observed_at"))
    if not seen or not timedelta(0)<=now-seen<timedelta(hours=12):return {}
    by_key={}
    for raw in catalog.get("coins") or []:
        if not isinstance(raw,dict):continue
        by_key.setdefault((norm(raw.get("name")),str(raw.get("ticker") or "").upper()),
                          []).append(raw)
    matches={}
    for key,item in topics.items():
        if not isinstance(item,dict) or item.get("coin_class")!="coin_candidate":continue
        known=item.get("pool_evidence") or {}
        name=str(known.get("name") or "")
        ticker=str(known.get("symbol") or "").upper()
        if not name or not ticker:continue
        matches_for_name=by_key.get((norm(name),ticker),[])
        fact_alg=norm((item.get("facts") or {}).get("algorithm"))
        fitting=[x for x in matches_for_name if norm(x.get("algorithm"))==fact_alg]
        if len(fitting)!=1:continue
        p=fitting[0]
        matches[key]={
          "name":p["name"],"ticker":ticker,"algorithm":p["algorithm"],
          "observed_at":catalog["observed_at"],"source":URL,
          "network_hashrate_hs_reported":p["nethash_hs_reported"],
          "block_reward_reported":p["block_reward_reported"],
          "block_time_seconds_reported":p["block_time_seconds_reported"],
          "difficulty_text":p["difficulty_text"],
          "provider_time_unknown":True,
          "note":"Агрегатор не указал время показателей; это не подтверждение их актуальности"
        }
    return matches
