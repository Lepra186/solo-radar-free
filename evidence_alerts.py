"""Notify when a tracked coin acquires fresh, source-attributed mining evidence.

Baseline silently. Alert at most twice a run, only when source evidence changes,
never on mining app updates, external source outages, or stale-field renewal.
"""
from datetime import datetime, timezone
from coin_filter import is_coin

def evidence_id(item):
    pool=item.get("pool_evidence") or {}
    net=item.get("network_evidence") or {}
    parts=[
        str(pool.get("source") or ""),str(pool.get("last_block_at") or ""),
        str(pool.get("blocks_48h_reported") or ""),
        str(net.get("source") or ""),str(net.get("coin_id") or ""),
        str(net.get("last_block_height") or "")]
    progress=item.get("chain_progress") or {}
    parts.extend([str(progress.get("coin_id") or ""),str(progress.get("last_height") or "")])
    return "|".join(parts)

def transitions(topics,previous,now,max_messages=2):
    known=dict(previous) if isinstance(previous,dict) else {}
    notices=[]
    for key,item in topics.items():
        if not isinstance(item,dict) or not is_coin(key,item):continue
        verdict=item.get("mining_readiness") or {}
        current=str(verdict.get("stage") or "announcement_only")
        marker=evidence_id(item) if current in ("activity_reported","height_advanced") else ""
        old=known.get(key)
        # Initial scan is a baseline, not a claimed new on-chain event.
        if isinstance(old,dict) and current in ("activity_reported","height_advanced") and marker:
            prior=str(old.get("last_stage") or "")
            announced=str(old.get("last_alert_marker") or "")
            is_upgrade=(current=="height_advanced" and prior!="height_advanced") or (
                current=="activity_reported" and prior not in ("activity_reported","height_advanced"))
            if is_upgrade and marker!=announced and len(notices)<max_messages:
                evidence=verdict.get("evidence") or []
                note=("🧪 SOLO RADAR • ИЗМЕНИЛАСЬ АКТИВНОСТЬ\n\n"+
                    str(item.get("title") or "GPU PoW монета")[:150]+"\n"+
                    "Источник данных: "+str((item.get("chain_progress") or {}).get("source")
                        or (item.get("pool_evidence") or {}).get("source")
                        or (item.get("network_evidence") or {}).get("source") or "не уточнён")+"\n"+
                    "Сообщается: "+("; ".join(str(x)[:130] for x in evidence[:3]) or
                                      "есть внешние сведения о блоках")+"\n"+
                    "⚠️ Не проверены совместимость GTX 10xx / RTX 20xx–50xx, подключение к пулу, выплаты и продажа.\n"+
                    str(item.get("url") or "")[:330])
                notices.append((key,marker,note[:1400]))
        remembered=old if isinstance(old,dict) else {}
        known[key]={
          "last_stage":current,
          "last_alert_marker":remembered.get("last_alert_marker",""),
          "checked_at":now.isoformat(timespec="seconds")}
    # Keep only records for current verified candidate topics.
    known={k:v for k,v in known.items() if k in topics and is_coin(k,topics[k])}
    return notices,known

def confirmed(known,key,marker):
    if key in known:
        known[key]["last_alert_marker"]=marker
    return known
