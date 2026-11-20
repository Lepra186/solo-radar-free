"""Public Blockscout explorer checks for early GPU PoW candidates.

Only use explicitly supplied explorer URLs on *.blockscout.com. A random
project URL or blockchain ticker never authorizes probing a third-party API.
Blockscout data demonstrates reported indexed chain height, NOT PoW consensus
or accepted shares. No arbitrary URL fetch, RPC write, wallet or payout tests.
"""
import base64
import json
import re
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit
from coin_filter import is_coin

CHECK_INTERVAL=timedelta(minutes=25)
MAX_EXPLORERS=3
MAX_READMES=2
URL_PATTERN=re.compile(r"https://[^\s<>\)\]\"']{5,220}",re.I)

def date(raw):
    if not isinstance(raw,str):return None
    try:
        dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:return None

def official_blockscout(url):
    if not isinstance(url,str) or len(url)>250:return None
    try:
        p=urlsplit(url)
        host=(p.hostname or "").lower().rstrip(".")
        if p.scheme!="https" or not host.endswith(".blockscout.com"):
            return None
        if p.username or p.password or p.port not in (None,443) or "\\" in url:return None
        # Single dot-separated subdomain, no localhost or IP aliases.
        if not re.fullmatch(r"[a-z0-9-]{2,55}\.blockscout\.com",host):return None
        return "https://"+host
    except ValueError:return None

def candidate_from_readme(text):
    if not isinstance(text,str):return None
    lines=text.splitlines()
    for line in lines[:2500]:
        if not re.search(r"\b(explorer|block.?scout|обозреватель|scan)\b",line,re.I):continue
        for u in URL_PATTERN.findall(line):
            address=official_blockscout(u.rstrip(".,;"))
            if address:return address
    return None

def repo(item):
    p=urlsplit(str(item.get("url") or ""))
    if p.hostname not in ("github.com","www.github.com"):return None
    parts=[s for s in p.path.strip("/").split("/") if s]
    if len(parts)<2 or not all(re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}",s) for s in parts[:2]):return None
    return "/".join(parts[:2])

def readme_link(fetch,repo_name):
    payload=json.loads(fetch("https://api.github.com/repos/"+repo_name+"/readme"))
    if not isinstance(payload,dict) or payload.get("encoding")!="base64":return None
    raw=payload.get("content")
    if not isinstance(raw,str) or len(raw)>150000:return None
    decoded=base64.b64decode(raw.replace("\n",""),validate=True)
    if len(decoded)>100000:return None
    return candidate_from_readme(decoded.decode("utf-8",errors="replace"))

def latest_blocks(payload,now):
    blocks=payload.get("items") if isinstance(payload,dict) else payload
    if not isinstance(blocks,list) or not 1<=len(blocks)<=60:
        raise ValueError("Unexpected Blockscout recent-block response")
    valid=[]
    for block in blocks[:30]:
        if not isinstance(block,dict) or block.get("type") not in (None,"block"):continue
        h=block.get("height")
        when=date(block.get("timestamp"))
        if isinstance(h,bool) or not isinstance(h,int) or h<=0 or not when:continue
        if not timedelta(0)<=now-when<=timedelta(hours=48):continue
        valid.append((h,when,block))
    if not valid:raise ValueError("No recent canonical block in explorer response")
    max_height,max_time,detail=max(valid,key=lambda x:x[0])
    return {"last_block_height":max_height,"last_block_time":max_time.isoformat(timespec="seconds"),
            "last_block_hash":str(detail.get("hash") or "")[:90],
            "blocks_in_response":len(valid)}

def verify(fetch,topics,state,now):
    stats={"readmes_checked":0,"api_checked":0,"explorers_reporting_recent_blocks":0,
           "unverified_identity":0,"source":"Blockscout public explorer"}
    seen=set()
    for key,item in topics.items():
        if not isinstance(item,dict) or not is_coin(key,item):continue
        if not key.startswith(("gh:","gh-")):continue
        repo_name=repo(item)
        if not repo_name or repo_name.lower() in seen:continue
        seen.add(repo_name.lower())
        # For source transparency, let existing copies retain the same
        # source URL only when explicitly present in that candidate's links.
        found=(item.get("links") or {}).get("explorer")
        candidate=official_blockscout(found) or official_blockscout((item.get("explorer_origin") or {}).get("url"))
        if not candidate and stats["readmes_checked"]<MAX_READMES:
            last=date(item.get("explorer_checked_at"))
            if not last or now-last>=timedelta(days=1):
                stats["readmes_checked"]+=1
                try:candidate=readme_link(fetch,repo_name)
                except Exception as exc:
                    print("Official README explorer discovery failed:",type(exc).__name__)
                item["explorer_checked_at"]=now.isoformat(timespec="seconds")
        if candidate:
            item["explorer_origin"]={"url":candidate,"source":"GitHub project README or explicit explorer link",
                "identity_verified":False}
    for key,item in topics.items():
        if not isinstance(item,dict) or not is_coin(key,item):continue
        origin=item.get("explorer_origin") or {}
        base=official_blockscout(origin.get("url"))
        if not base:continue
        # Blockscout is often deployed for PoS and L2 networks too.
        # Current block number by itself cannot prove this is the coin's PoW chain.
        old=item.get("explorer_evidence") or {}
        previous=date(old.get("checked_at"))
        if previous and timedelta(0)<=now-previous<CHECK_INTERVAL:continue
        if stats["api_checked"]>=MAX_EXPLORERS:break
        stats["api_checked"]+=1
        try:
            details=latest_blocks(json.loads(fetch(base+"/api/v2/blocks")),now)
            item["explorer_evidence"]={
                "source":"Blockscout","explorer":base,"checked_at":now.isoformat(timespec="seconds"),
                **details,"identity_verified":False,
                "note":"Данные обозревателя, связь с указанной PoW-сетью независимо не доказана"}
            stats["explorers_reporting_recent_blocks"]+=1
            stats["unverified_identity"]+=1
        except Exception as exc:
            print("Project Blockscout unavailable:",type(exc).__name__)
    return stats
