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
    rpc=item.get("rpc_evidence") or {}
    parts.extend([str(rpc.get("chain_id") or ""),str(rpc.get("last_block_height") or "")])
    return "|".join(parts)

def transitions(topics,previous,now,max_messages=2):
    known=dict(previous) if isinstance(previous,dict) else {}
    notices=[]
    observed_groups=set()
    for key,item in topics.items():
        if not isinstance(item,dict) or not is_coin(key,item):continue
        verdict=item.get("mining_readiness") or {}
        current=str(verdict.get("stage") or "announcement_only")
        marker=evidence_id(item) if current in ("activity_reported","height_advanced","rpc_height_advanced") else ""
        # One RPC growth notification per network, not one per reposted ANN.
        rpc=item.get("rpc_evidence") or {}
        if current=="rpc_height_advanced" and isinstance(rpc.get("chain_id"),int):
            marker="rpc-chain-"+str(rpc["chain_id"])
        group=("rpc",str(rpc.get("chain_id"))) if current=="rpc_height_advanced" and rpc.get("chain_id") else ("record",key)
        old=known.get(key)
        # Initial scan is a baseline, not a claimed new on-chain event.
        if isinstance(old,dict) and current in ("activity_reported","height_advanced","rpc_height_advanced") and marker:
            prior=str(old.get("last_stage") or "")
            announced=str(old.get("last_alert_marker") or "")
            is_upgrade=(current=="rpc_height_advanced" and prior!="rpc_height_advanced") or (
                current=="height_advanced" and prior!="height_advanced") or (
                current=="activity_reported" and prior not in
                   ("activity_reported","height_advanced","rpc_height_advanced"))
            if is_upgrade and marker!=announced and group not in observed_groups and len(notices)<max_messages:
                observed_groups.add(group)
                evidence=verdict.get("evidence") or []
                note=("🧪 SOLO RADAR • ИЗМЕНИЛАСЬ АКТИВНОСТЬ\n\n"+
                    str(item.get("title") or "GPU PoW монета")[:150]+"\n"+
                    "Источник данных: "+str((item.get("rpc_progress") or {}).get("source")
                        or (item.get("chain_progress") or {}).get("source")
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
          "project_group":("rpc-chain-"+str(rpc.get("chain_id"))) if rpc.get("chain_id") else None,
          "last_alert_marker":remembered.get("last_alert_marker",""),
          "checked_at":now.isoformat(timespec="seconds")}
    # Keep only records for current verified candidate topics.
    known={k:v for k,v in known.items() if k in topics and is_coin(k,topics[k])}
    return notices,known

def confirmed(known,key,marker):
    if key in known:
        known[key]["last_alert_marker"]=marker
        # A single network can have ANN and GitHub records in the same scan.
        # Once delivered, suppress all duplicates of the same RPC chain.
        if marker.startswith("rpc-chain-"):
            for value in known.values():
                if value.get("project_group")==marker:
                    value["last_alert_marker"]=marker
    return known
