"""Cross-scan Blockscout height trends, with explicit uncertain coin identity.

Never confuse a linked explorer's indexed height with verified native PoW
network activity. Source URL and timestamps must match between observations.
"""
from datetime import datetime,timezone,timedelta
import math

MIN_GAP=timedelta(minutes=10)
MAX_GAP=timedelta(hours=36)

def as_time(s):
    if not isinstance(s,str):return None
    try:
        t=datetime.fromisoformat(s.replace("Z","+00:00"))
        return t.astimezone(timezone.utc) if t.tzinfo else None
    except ValueError:return None

def measure(item,now):
    e=item.get("explorer_evidence") or {}
    domain=e.get("explorer")
    checked=as_time(e.get("checked_at"))
    block_time=as_time(e.get("last_block_time"))
    h=e.get("last_block_height")
    if not isinstance(domain,str) or not domain.startswith("https://") or len(domain)>110:return None
    if isinstance(h,bool) or not isinstance(h,int) or h<=0:return None
    if not checked or not block_time or not timedelta(0)<=now-checked<timedelta(hours=6):return None
    if not timedelta(0)<=now-block_time<timedelta(hours=48):return None
    if block_time>checked+timedelta(minutes=5):return None
    return {"source":domain,"height":h,"observed_at":checked.isoformat(timespec="seconds"),
            "block_time":block_time.isoformat(timespec="seconds")}

def update(topics,history,now):
    history=history if isinstance(history,dict) else {}
    updated={};counts={"eligible":0,"baselines":0,"increased":0,"stalled":0}
    for key,item in topics.items():
        if not isinstance(item,dict) or item.get("coin_class")!="coin_candidate":continue
        new=measure(item,now)
        if not new:continue
        counts["eligible"]+=1
        old=(history.get(key) or {}).get("baseline")
        updated[key]={"baseline":new}
        if not isinstance(old,dict) or old.get("source")!=new["source"]:
            counts["baselines"]+=1
            continue
        old_at=as_time(old.get("observed_at"))
        delta=as_time(new["observed_at"])-old_at if old_at else timedelta(0)
        old_height=old.get("height")
        if isinstance(old_height,bool) or not isinstance(old_height,int) or old_height<=0:
            counts["baselines"]+=1
            continue
        if not MIN_GAP<=delta<=MAX_GAP or new["height"]<old_height:
            continue
        if new["height"]==old_height:
            counts["stalled"]+=1
            continue
        # Index catch-up or a misleading index height is not evidence of
        # newly produced blocks unless the explorer's block timestamp advances.
        old_block_time=as_time(old.get("block_time"))
        new_block_time=as_time(new.get("block_time"))
        if not old_block_time or not new_block_time or new_block_time<=old_block_time:
            counts["stalled"]+=1
            continue
        counts["increased"]+=1
        item["explorer_progress"]={
            "source":new["source"],"first_height":old_height,"last_height":new["height"],
            "delta_blocks":new["height"]-old_height,
            "first_checked":old["observed_at"],"last_checked":new["observed_at"],
            "identity_verified":False,
            "note":"Рост индекса обозревателя, совпадение с целевой PoW-монетой не доказано"}
    return updated,counts
