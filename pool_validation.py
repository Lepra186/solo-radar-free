"""Read-only pool identity checks from Mining Scan (no API key).

Pool export entries are pool-wide, NOT coin-specific hashrate or blocks. Matching
by ticker alone is never proof of the identity of a new GPU PoW coin. No TCP
Stratum probes or wallet operations are performed.
"""
import json
import math
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urlsplit

URL="https://mining-scan.com/api/export/pools"
CACHE=timedelta(hours=6)
FRESH=timedelta(hours=12)
DOMAIN=re.compile(r"^(?=.{4,150}$)[a-z0-9.-]+\.[a-z]{2,}$",re.I)

def parsed(raw):
    if not isinstance(raw,str):return None
    try:
        dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:return None

def bounded(value,maximum):
    if isinstance(value,bool) or not isinstance(value,(int,float)):return None
    if not math.isfinite(value) or not 0<=value<=maximum:return None
    return value

def parse_pool_directory(payload,now):
    if not isinstance(payload,dict) or not isinstance(payload.get("data"),list):
        raise ValueError("Invalid pool directory payload")
    meta=payload.get("meta") or {}
    if not isinstance(meta,dict) or meta.get("stale") is True or meta.get("state")=="down":
        raise ValueError("Pool directory stale or down")
    generated=parsed(meta.get("generated_at"))
    if not generated or not timedelta(0)<=now-generated<=FRESH:
        raise ValueError("Pool directory generation date stale or missing")
    pools=[]
    for row in payload["data"][:5000]:
        if not isinstance(row,dict):continue
        domain=str(row.get("domain") or "").lower().strip(".")
        identity=str(row.get("id") or "")
        if not DOMAIN.fullmatch(domain) or not identity or row.get("status")!="confirmed":
            continue
        seen=parsed(row.get("last_metric_at"))
        schemes=row.get("payout_schemes")
        if not isinstance(schemes,list):schemes=[]
        symbols=row.get("coins")
        if not isinstance(symbols,list):symbols=[]
        symbols=[str(x).upper() for x in symbols if isinstance(x,str) and re.fullmatch(r"[a-zA-Z0-9]{2,15}",x)]
        pools.append({
            "id":identity[:100],"domain":domain,"name":str(row.get("name") or domain)[:95],
            "coins":symbols,"fresh_metrics":bool(seen and timedelta(0)<=now-seen<=FRESH),
            "last_metric_at":row.get("last_metric_at"),
            "fee_percent_poolwide":bounded(row.get("fee"),100),
            "payout_schemes_poolwide":[str(s).upper()[:24] for s in schemes[:6]],
            "miners_poolwide":bounded(row.get("miners"),1e9),
            # Pool blocks/hashrate are aggregate across coins! Never use them
            # as proof of this coin's recent blocks or hashrate.
            "last_block_poolwide":row.get("last_block_at"),
        })
    return {"generated_at":meta["generated_at"],"fetched_at":now.isoformat(timespec="seconds"),
            "pools":pools,"source":URL}

def update(fetch,state,now):
    old=state.get("pool_directory") or {}
    t=parsed(old.get("fetched_at"))
    if t and timedelta(0)<=now-t<CACHE:
        return old,False
    try:
        payload=json.loads(fetch(URL))
        return parse_pool_directory(payload,now),True
    except Exception as exc:
        print("Pool directory unavailable:",type(exc).__name__)
        return old,False

def match_pools(topics,directory,now):
    generated=parsed(directory.get("generated_at"))
    if not generated or not timedelta(0)<=now-generated<=FRESH:return {}
    catalog=directory.get("pools") or []
    matches={}
    for key,item in topics.items():
        if not isinstance(item,dict) or item.get("coin_class")!="coin_candidate":continue
        existing=item.get("pool_evidence") or {}
        ticker=str(existing.get("symbol") or "").upper()
        name=str(existing.get("name") or "").lower()
        # Reliable coin name from an already matched coin directory is required
        # to avoid aliasing unrelated assets that share the same ticker.
        if not ticker or len(name)<5 or name not in str(item.get("title") or "").lower():
            continue
        rows=[p for p in catalog if ticker in p["coins"]]
        if not rows:continue
        matches[key]={
            "source":"Mining Scan pool directory",
            "checked_at":directory.get("generated_at"),
            "coin_name":existing.get("name"),"coin_symbol":ticker,
            "identity_limit":"Coin symbol cross-reference, not independent proof of identity",
            "pools":[{
                "id":p["id"],"name":p["name"],"domain":p["domain"],
                "pool_metrics_fresh":p["fresh_metrics"],
                "fee_percent_poolwide":p["fee_percent_poolwide"],
                "payout_schemes_poolwide":p["payout_schemes_poolwide"],
                "last_metric_at":p["last_metric_at"],
                "stratum":"не подтверждён",
                "note":"Комиссия и схема выплат указаны для пула в целом, не гарантированы для монеты"
            } for p in sorted(rows,key=lambda x:(not x["fresh_metrics"],x["domain"]))[:5]]
        }
    return matches

def stratum_by_coin(fetch,info,limit=2):
    """Find recorded endpoint only when a per-pool row matches the coin identity.

    The lookup domain comes exclusively from parsed directory entries.
    URL is constructed on fixed Mining Scan host (no arbitrary URL fetch).
    """
    symbol=info.get("coin_symbol")
    coinname=re.sub(r"[^a-z0-9]","",str(info.get("coin_name") or "").lower())
    fetched=0
    for pool in info.get("pools",[]):
        if fetched>=limit:break
        domain=pool.get("domain","")
        if not DOMAIN.fullmatch(domain):continue
        fetched+=1
        try:
            payload=json.loads(fetch("https://mining-scan.com/pools/"+quote(domain,safe="")+"/coins"))
            rows=payload.get("data") if isinstance(payload,dict) else payload
            if not isinstance(rows,list):continue
            for row in rows[:100]:
                if not isinstance(row,dict):continue
                current_symbol=str(row.get("symbol") or row.get("coin_symbol") or "").upper()
                name=re.sub(r"[^a-z0-9]","",str(row.get("coin_name") or row.get("name") or "").lower())
                if current_symbol!=symbol or name!=coinname:continue
                endpoints=[]
                for entry in (row.get("stratum_endpoints") or [])[:8]:
                    if not isinstance(entry,dict):continue
                    uri=str(entry.get("url") or "")
                    # Display only URI, no sockets or credentials. No trust
                    # in endpoint status; we never connect to these hosts.
                    parsed_uri=urlsplit(uri)
                    if parsed_uri.scheme not in ("stratum+tcp","stratum+ssl","stratum+tls"):
                        continue
                    try:valid_port=1<=parsed_uri.port<=65535
                    except ValueError:valid_port=False
                    if not valid_port or not parsed_uri.hostname or parsed_uri.username or parsed_uri.password:
                        continue
                    endpoints.append(uri[:200])
                if endpoints:
                    pool["stratum"]="опубликован, не проверен"
                    pool["stratum_endpoints"]=endpoints[:2]
                break
        except Exception as exc:
            print("Per-pool coin details unavailable:",type(exc).__name__)
    return fetched
