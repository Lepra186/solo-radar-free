"""Read-only public EVM JSON-RPC for source-documented GPU PoW projects.

Network configurations are pinned to official public documentation and exact
project identities. Calls: eth_chainId, eth_blockNumber, eth_getBlockByNumber.
Do not sign/broadcast transactions, send funds, mine, or connect to Stratum.
Successful RPC reads are stronger evidence than catalog blurbs but do NOT
independently verify GPU mining, PoW consensus rules, rewards, or withdrawals.
"""
import json
import re
import urllib.request
from datetime import datetime,timezone,timedelta

# URLs and chain IDs from each project's published first-party sources:
# Quinvium: https://github.com/Lakylife/quinvium/blob/main/README.md
# NEX Chain: https://bitcointalk.org/index.php?topic=5599371.0
NETWORKS={
 "quinvium":{
  "url":"https://rpc.quinvium.com",
  "chain_id":52401,
  "keys":("gh:1457186269","gh-1457186269","btt:5600215"),
  "name":"Quinvium","reference":"https://github.com/Lakylife/quinvium/blob/main/README.md"
 },
 "nexchain":{
  "url":"https://rpc.getnexwallet.com",
  "chain_id":6396,
  "keys":("btt:5599371",),
  "name":"NEX Chain","reference":"https://bitcointalk.org/index.php?topic=5599371.0"
 }
}
RETRY=timedelta(minutes=22)
MAX_LAG=timedelta(hours=48)
GAP=timedelta(minutes=10)

def time_value(s):
    if not isinstance(s,str):return None
    try:
        t=datetime.fromisoformat(s.replace("Z","+00:00"))
        return t.astimezone(timezone.utc) if t.tzinfo else None
    except ValueError:return None

def unhex(value):
    if not isinstance(value,str) or not re.fullmatch(r"0x[0-9a-fA-F]{1,18}",value):return None
    return int(value,16)

def transport(endpoint,method,params):
    # Endpoint chosen only from fixed first-party config; never user-supplied.
    data=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode()
    req=urllib.request.Request(endpoint,data=data,
        headers={"Content-Type":"application/json","User-Agent":"SOLO-Radar/2.2 read-only RPC"},
        method="POST")
    # Prevent redirecting POST to an arbitrary host (SSRF defense).
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            return None
    with urllib.request.build_opener(NoRedirect).open(req,timeout=10) as r:
        raw=r.read(180000)
    obj=json.loads(raw)
    if not isinstance(obj,dict) or obj.get("error") or "result" not in obj:
        raise ValueError("Invalid or failed JSON-RPC response")
    return obj["result"]

def poll_network(config,now,caller=transport):
    endpoint=config["url"]
    chain=unhex(caller(endpoint,"eth_chainId",[]))
    if chain!=config["chain_id"]:
        raise ValueError("RPC chain ID differs from official documentation")
    number=unhex(caller(endpoint,"eth_blockNumber",[]))
    if number is None or number<=0:raise ValueError("RPC has no valid chain height")
    head=caller(endpoint,"eth_getBlockByNumber",[hex(number),False])
    if not isinstance(head,dict):raise ValueError("Missing RPC head")
    h=unhex(head.get("number"))
    timestamp=unhex(head.get("timestamp"))
    digest=str(head.get("hash") or "")
    if h!=number or timestamp is None or not re.fullmatch(r"0x[0-9a-fA-F]{64}",digest):
        raise ValueError("Invalid or inconsistent RPC block header")
    at=datetime.fromtimestamp(timestamp,tz=timezone.utc)
    if not timedelta(0)<=now-at<=MAX_LAG:
        raise ValueError("RPC block head is stale or future-dated")
    difficulty=unhex(head.get("difficulty"))
    return {
       "provider":"public project JSON-RPC","endpoint":endpoint,
       "chain_id":chain,"last_block_height":number,"last_block_hash":digest[:66],
       "last_block_time":at.isoformat(timespec="seconds"),
       "difficulty_from_header":difficulty,
       "checked_at":now.isoformat(timespec="seconds"),
       "source_reference":config["reference"],
       "note":"RPC chain ID совпал; это не независимый аудит PoW и не проверка выплат"
    }

def update(topics,state,now,caller=transport):
    previous=state.get("evm_rpc") or {}
    samples={};growth={};summary={"configured_networks":len(NETWORKS),
                                   "rpc_checks":0,"available":0,"height_advanced":0}
    for network_id,config in NETWORKS.items():
        matching=[k for k in config["keys"]
                   if k in topics and isinstance(topics[k],dict)
                   and topics[k].get("coin_class")=="coin_candidate"]
        if not matching:continue
        old=previous.get(network_id) or {}
        previous_checked=time_value(old.get("checked_at"))
        if previous_checked and timedelta(0)<=now-previous_checked<RETRY:
            if old.get("rpc") and old.get("rpc",{}).get("last_block_height"):
                result=old["rpc"]
                # Existing observations are not new scans; do not claim
                # growth on a repeated cached snapshot.
                for key in matching:
                    topics[key]["rpc_evidence"]=result
            samples[network_id]=old
            continue
        summary["rpc_checks"]+=1
        try:
            fresh=poll_network(config,now,caller)
        except Exception as exc:
            print("Public project RPC unavailable:",network_id,type(exc).__name__)
            samples[network_id]={"checked_at":now.isoformat(timespec="seconds"),
                                 "status":"unavailable","rpc":old.get("rpc")}
            for key in matching:
                topics[key].pop("rpc_evidence",None)
                topics[key].pop("rpc_progress",None)
            continue
        summary["available"]+=1
        previous_result=old.get("rpc") or {}
        last_time=time_value(previous_result.get("checked_at"))
        delta=now-last_time if last_time else timedelta(0)
        advanced=(last_time is not None and GAP<=delta<=timedelta(hours=36)
                  and previous_result.get("chain_id")==fresh["chain_id"]
                  and isinstance(previous_result.get("last_block_height"),int)
                  and fresh["last_block_height"]>previous_result["last_block_height"])
        progress=None
        if advanced:
            progress={
                "source":"project public JSON-RPC","chain_id":fresh["chain_id"],
                "first_height":previous_result["last_block_height"],
                "last_height":fresh["last_block_height"],
                "blocks_increased":fresh["last_block_height"]-previous_result["last_block_height"],
                "first_checked":previous_result["checked_at"],
                "last_checked":fresh["checked_at"],
                "note":"Рост между чтениями RPC; PoW и получение выплат не проверены"}
            summary["height_advanced"]+=1
        samples[network_id]={"checked_at":fresh["checked_at"],"status":"active",
                            "rpc":fresh}
        for key in matching:
            topics[key]["rpc_evidence"]=fresh
            if progress:topics[key]["rpc_progress"]=progress
            else:topics[key].pop("rpc_progress",None)
    return samples,summary
