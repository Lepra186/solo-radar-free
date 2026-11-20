"""Evidence-based readiness for GPU PoW accumulation, independent of advertising.

No status implies that RTX 5070 Ti mining, withdrawals, exchange execution or
profit is proven. Network and pool catalog data may be incomplete and stale.
"""
from datetime import datetime,timezone,timedelta
from coin_filter import is_coin

POOL_MAX_AGE=timedelta(hours=12)
NETWORK_MAX_AGE=timedelta(hours=48)
BLOCK_MAX_AGE=timedelta(hours=48)
GPU_ALGOS={"ethash","etchash","kawpow","progpow","fishhash","autolykos",
           "equihash","octopus","verthash","firopow","zelhash","cuckoocycle"}

def date_value(raw):
    if not isinstance(raw,str):return None
    try:
        dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:
        return None

def recent(raw,now,max_age):
    parsed=date_value(raw)
    return parsed is not None and timedelta(0)<=now-parsed<=max_age

def number(raw):
    if isinstance(raw,bool) or not isinstance(raw,(int,float)):return None
    if raw!=raw or raw<0:return None
    return raw

def evaluate(key,item,now):
    if not is_coin(key,item):
        return {"stage":"excluded","label":"Не GPU PoW-монета",
                "evidence":[],"missing":[],"gpu_5070ti":"не проверена"}
    evidence=[]; missing=[]
    pool=item.get("pool_evidence") or {}
    network=item.get("network_evidence") or {}
    release=item.get("github_release_evidence") or []
    fresh_pool=recent(pool.get("checked_at"),now,POOL_MAX_AGE)
    fresh_net=recent(network.get("fetched_at"),now,NETWORK_MAX_AGE)
    pool_blocks=number(pool.get("blocks_48h_reported"))
    pool_count=number(pool.get("pools_reported"))
    network_height=number(network.get("last_block_height"))
    difficulty=number(network.get("difficulty"))
    activity=False; listing=False
    if fresh_pool and pool_count is not None and pool_count>0:
        listing=True
        evidence.append("Пулы в каталоге Mining Scan: "+str(int(pool_count)))
    if fresh_pool and pool_blocks is not None and pool_blocks>0:
        activity=True
        evidence.append("Mining Scan сообщает "+str(int(pool_blocks))+" блоков за 48 ч")
    # A single block time stamp may be more useful than a malformed zero block
    # counter, but must be within both source freshness and block-age windows.
    if fresh_pool and recent(pool.get("last_block_at"),now,BLOCK_MAX_AGE):
        activity=True
        evidence.append("В каталоге есть недавняя отметка найденного блока")
    # Pool-directory rows are pool-wide. A matched coin listing or recorded
    # Stratum address is a research lead, never proof of shares or payouts.
    validated=item.get("pool_validation") or {}
    for pool_info in (validated.get("pools") or [])[:3]:
        if not isinstance(pool_info,dict) or not pool_info.get("pool_metrics_fresh"):
            continue
        listing=True
        evidence.append("Пул перечисляет тикер монеты: "+str(pool_info.get("name") or "неизвестный")[:55])
        if pool_info.get("stratum_endpoints"):
            evidence.append("Опубликован Stratum-адрес; соединение и выплаты не проверены")
        break
    if fresh_net and network_height is not None and network_height>0:
        activity=True
        evidence.append("BackPoW сообщает высоту цепи: "+str(int(network_height)))
    if fresh_net and difficulty is not None and difficulty>0:
        evidence.append("BackPoW сообщает сложность сети")
    if isinstance(release,list) and any(
       isinstance(x,dict) and recent(x.get("published_at"),now,timedelta(days=45))
       for x in release):
        evidence.append("Есть свежий релиз проекта на GitHub")
    if not listing:missing.append("Рабочий пул не проверен")
    if not activity:missing.append("Свежие блоки сети не подтверждены")
    missing.append("RTX 5070 Ti, подключение Stratum и фактические выплаты не проверены")
    missing.append("Ликвидность и возможность продажи не проверены")
    if activity:
        stage,label="activity_reported","Есть сообщения об активности сети"
    elif listing:
        stage,label="pool_listed","Пулы перечислены, добыча не подтверждена"
    else:
        stage,label="announcement_only","Только анонс или код проекта"
    return {
        "stage":stage,"label":label,"evidence":evidence[:5],
        "missing":missing,"gpu_5070ti":"не проверена",
        "source_freshness":{"pool":fresh_pool,"network":fresh_net},
        "checked_at":now.isoformat(timespec="minutes")
    }

def evaluate_all(topics,now):
    counts={}
    for key,item in topics.items():
        if not isinstance(item,dict):continue
        verdict=evaluate(key,item,now)
        item["mining_readiness"]=verdict
        counts[verdict["stage"]]=counts.get(verdict["stage"],0)+1
    return counts
