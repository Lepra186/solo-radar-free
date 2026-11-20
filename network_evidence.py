"""Public, keyless BackPoW network-data corroboration.

Only use canonical coin IDs from the provider's sitemap, never generate IDs from
untrusted titles. Never infer GPU feasibility or profitability from a lone
difficulty value. Missing source fields remain null.
"""
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
from coin_filter import is_coin

SITEMAP="https://backpow.com/sitemap-coins.xml"
BASE="https://backpow.com/coins-data/"
CACHE_INTERVAL=timedelta(hours=24)
MAX_COINS=3

def parse_utc(value):
    try:
        if not isinstance(value,str): return None
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:
        return None

def normalized(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())

def coin_ids(xml):
    root=ET.fromstring(xml)
    found={}
    for elem in root.iter():
        if not elem.tag.endswith("loc") or not elem.text:continue
        p=urlsplit(elem.text.strip())
        if p.netloc not in ("backpow.com","www.backpow.com"):continue
        bits=[v for v in p.path.split("/") if v]
        if len(bits)!=1 or not re.fullmatch(r"[A-Za-z0-9_-]{2,70}",bits[0]):continue
        name=bits[0]
        found.setdefault(normalized(name),name)
    return found

def known_coins(topics,ids):
    candidates=[]
    seen=set()
    for key,item in topics.items():
        if not isinstance(item,dict) or not is_coin(key,item):continue
        # Coins with a catalog-verifiable name only: no ticker-only guessing.
        evidence=item.get("pool_evidence") or {}
        name=evidence.get("name")
        if not name:
            # Resolve from explicit "Coin Name:" or the first ANN title, not a
            # GitHub repository name and never a generic GPU/PoW string.
            raw=str(item.get("title") or "")
            m=re.search(r"\bcoin\s*name\s*:\s*([A-Za-z][A-Za-z0-9 _-]{2,32})",raw,re.I)
            if m:name=m.group(1).split("|")[0].strip()
            else:
                m=re.match(r"^\[(?:pre-)?ann\]\s*([A-Za-z][A-Za-z0-9_-]{2,32})\s*(?:\(|\||-)",raw,re.I)
                if m:name=m.group(1)
        identifier=ids.get(normalized(name)) if name else None
        if identifier and identifier.lower() not in seen:
            seen.add(identifier.lower())
            candidates.append((key,identifier))
    return candidates[:MAX_COINS]

def numeric(value):
    if isinstance(value,bool) or value is None:return None
    try:
        n=float(str(value).replace(",",""))
        return n if 0<=n<1e60 and n==n else None
    except (ValueError,TypeError):
        return None

def extract_data(payload):
    if not isinstance(payload,dict):raise ValueError("not a BackPoW object")
    def pick(*names):
        for k in names:
            if k in payload and payload[k] is not None:return payload[k]
        return None
    return {
        "algorithm":str(pick("Algorithm","algorithm") or "")[:60] or None,
        "network_hashrate_hs":numeric(pick("Nethash","nethash","network_hashrate")),
        "difficulty":numeric(pick("Difficulty","difficulty")),
        "block_time_seconds":numeric(pick("Block time","block_time","block_time_seconds")),
        "block_reward":numeric(pick("Bl. reward","block_reward")),
        "last_block_height":numeric(pick("Last block","last_block","height")),
        "note":"BackPoW — публичная оценка сети; не проверка добычи RTX 5070 Ti"
    }

def update(fetch,topics,state,now):
    previous=state.get("backpow") or {}
    last=parse_utc(previous.get("checked_at"))
    if last and timedelta(0)<=now-last<CACHE_INTERVAL:
        return previous,False
    result={"checked_at":now.isoformat(timespec="seconds"),"source":"https://backpow.com/api",
            "verified":{},"attempted":0,"successful":0}
    try:
        ids=coin_ids(fetch(SITEMAP))
        for key,coin_id in known_coins(topics,ids):
            result["attempted"]+=1
            try:
                payload=json.loads(fetch(BASE+coin_id+".json"))
                network=extract_data(payload)
                if not any(network.get(x) is not None for x in
                           ("network_hashrate_hs","difficulty","last_block_height")):
                    continue
                result["verified"][key]={"coin_id":coin_id,"fetched_at":result["checked_at"],**network}
                result["successful"]+=1
            except Exception as exc:
                print("BackPoW coin data unavailable:",type(exc).__name__)
    except Exception as exc:
        print("BackPoW sitemap unavailable:",type(exc).__name__)
        return previous,False
    return result,True
