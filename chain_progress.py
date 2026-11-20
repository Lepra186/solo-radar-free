"""Check longitudinal proof-of-work chain growth from independent public snapshots.

Requires two distinct observed heights at least ten minutes apart, same
provider-specific coin identity, and valid source timestamps. A single height
or pool marketing copy is never independent proof of active block production.
"""
from datetime import datetime,timezone,timedelta
import math

MIN_GAP=timedelta(minutes=10)
MAX_GAP=timedelta(hours=36)
SNAPSHOT_TTL=timedelta(hours=48)

def parsed(value):
    if not isinstance(value,str):return None
    try:
        ts=datetime.fromisoformat(value.replace("Z","+00:00"))
        return ts.astimezone(timezone.utc) if ts.tzinfo else None
    except ValueError:return None

def height(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        return None
    if value<=0 or value!=int(value):return None
    return int(value)

def record(network):
    """Trust only canonical, provider-identified BackPoW records."""
    if not isinstance(network,dict):return None
    coin_id=str(network.get("coin_id") or "")
    if not coin_id or len(coin_id)>80:return None
    observed=parsed(network.get("fetched_at"))
    h=height(network.get("last_block_height"))
    if not observed or h is None:return None
    return {"provider":"BackPoW","coin_id":coin_id,
            "height":h,"observed_at":observed.isoformat(timespec="seconds")}

def reconcile(topics,history,now):
    previous=history if isinstance(history,dict) else {}
    next_history={}
    progress={}
    stats={"eligible":0,"new_baselines":0,"advanced":0,"unchanged":0,"anomalies":0}
    for key,item in topics.items():
        if not isinstance(item,dict) or item.get("coin_class")!="coin_candidate":continue
        current=record(item.get("network_evidence"))
        if current is None:continue
        observed=parsed(current["observed_at"])
        if not observed or not timedelta(0)<=now-observed<=SNAPSHOT_TTL:continue
        stats["eligible"]+=1
        old=previous.get(key) or {}
        prior=old.get("baseline") if isinstance(old,dict) else None
        if not isinstance(prior,dict) or (prior.get("coin_id"),prior.get("provider")) != (current["coin_id"],current["provider"]):
            next_history[key]={"baseline":current}
            stats["new_baselines"]+=1
            continue
        former=parsed(prior.get("observed_at"))
        former_height=height(prior.get("height"))
        gap=observed-former if former else timedelta(0)
        if former_height is None or gap<timedelta(0) or gap>MAX_GAP or current["height"]<former_height:
            next_history[key]={"baseline":current}
            stats["anomalies"]+=1
            continue
        if gap<MIN_GAP:
            next_history[key]={"baseline":prior}
            continue
        if current["height"]>former_height:
            growth=current["height"]-former_height
            proof={"source":"BackPoW","coin_id":current["coin_id"],
                   "first_height":former_height,"last_height":current["height"],
                   "blocks_increased":growth,"first_observed_at":prior["observed_at"],
                   "last_observed_at":current["observed_at"],
                   "note":"Рост высоты по двум независимым по времени снимкам агрегатора; не проверка собственной нодой"}
            progress[key]=proof
            next_history[key]={"baseline":current,"last_growth":proof}
            stats["advanced"]+=1
        else:
            next_history[key]={"baseline":current}
            stats["unchanged"]+=1
    return progress,next_history,stats
