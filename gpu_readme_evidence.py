"""Find *claimed* GeForce model support in official GPU PoW project READMEs.

Read only public GitHub repository READMEs. No miner downloads, execution,
automatic joining, or false claims of benchmarked mining performance.
"""
import base64
import json
import re
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit,quote
from coin_filter import is_coin
from gpu_families import MODEL,identify_model

MAX_READMES_PER_SCAN=2
MAX_BYTES=90_000
TTL=timedelta(hours=24)

def parse_time(x):
    try:
        d=datetime.fromisoformat(x.replace("Z","+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError,AttributeError):return None

def repo_of(item):
    url=str(item.get("url") or "")
    p=urlsplit(url)
    if p.netloc not in ("github.com","www.github.com"):return None
    path=[s for s in p.path.strip("/").split("/") if s]
    if len(path)<2:return None
    parts=path[:2]
    if not all(re.fullmatch(r"[A-Za-z0-9_.-]{1,80}",q) for q in parts):return None
    return "/".join(parts)

def evidence_from_readme(text,url):
    if not isinstance(text,str):return []
    results=[];seen=set()
    for line in text[:MAX_BYTES].splitlines():
        if len(line)>800:continue
        low=line.lower()
        if not any(token in low for token in (
            "nvidia","geforce","gpu","graphics","cuda","gtx","rtx","support","tested","compatible","mine")):
            continue
        for m in MODEL.finditer(line):
            parsed=identify_model(m.group())
            if not parsed or parsed["device"] in seen:continue
            seen.add(parsed["device"])
            results.append({
                "device":parsed["device"],
                "status":"developer_claimed",
                "source_url":url,
                "context":line.strip()[:160],
            })
            if len(results)>=12:return results
    return results

def read_public_readme(fetch,repo):
    url="https://api.github.com/repos/"+repo+"/readme"
    obj=json.loads(fetch(url))
    if not isinstance(obj,dict) or obj.get("encoding")!="base64" or not isinstance(obj.get("content"),str):
        return []
    encoded=obj["content"].replace("\n","")
    if len(encoded)>MAX_BYTES*2:return []
    try:
        data=base64.b64decode(encoded,validate=True)
        if len(data)>MAX_BYTES:return []
        decoded=data.decode("utf-8",errors="replace")
    except (ValueError,UnicodeDecodeError):return []
    source=str(obj.get("html_url") or ("https://github.com/"+repo+"#readme"))
    if not source.startswith("https://github.com/"):
        source="https://github.com/"+repo+"#readme"
    return evidence_from_readme(decoded,source)

def enrich(fetch,topics,now,limit=MAX_READMES_PER_SCAN):
    count=0;projects=0;claims=0;visited=set()
    for key,item in topics.items():
        if count>=limit:break
        if not isinstance(item,dict) or not key.startswith(("gh:","gh-")) or not is_coin(key,item):
            continue
        repo=repo_of(item)
        if not repo or repo.lower() in visited:continue
        visited.add(repo.lower())
        last=parse_time(item.get("gpu_support_checked_at"))
        if last and timedelta(0)<=now-last<TTL:continue
        count+=1
        try:
            findings=read_public_readme(fetch,repo)
        except Exception as exc:
            print("Public GPU support README unavailable:",type(exc).__name__)
            # Do not keep repeatedly requesting failed readmes on every scan.
            item["gpu_support_checked_at"]=now.isoformat(timespec="seconds")
            continue
        item["gpu_support_evidence"]=findings
        item["gpu_support_checked_at"]=now.isoformat(timespec="seconds")
        if findings:projects+=1;claims+=len(findings)
    return {"readmes_checked":count,"projects_with_claims":projects,
            "model_claims":claims,"source":"public GitHub READMEs"}
