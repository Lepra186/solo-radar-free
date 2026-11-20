"""Free public GitHub release evidence for previously classified GPU PoW coins.

Never generate a new coin alert from a miner release. Attach releases only to
already screened GitHub-based coin projects. Three bounded requests per scan.
"""
import json,re
from datetime import datetime,timezone,timedelta
from urllib.parse import urlparse
from coin_filter import is_coin

def parse_time(raw):
    try:
        dt=datetime.fromisoformat(str(raw).replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError,TypeError):return None

def repo_name(item):
    url=str(item.get("url") or "")
    parsed=urlparse(url)
    if parsed.hostname not in ("github.com","www.github.com"):return None
    parts=[p for p in parsed.path.strip("/").split("/") if p]
    if len(parts)<2 or not all(re.fullmatch(r"[\w.-]+",p,re.ASCII) for p in parts[:2]):return None
    return "/".join(parts[:2])

def check_releases(fetch,topics,now,limit=3):
    seen=set();checked=0;matched=0
    for key,item in topics.items():
        if checked>=limit:break
        if not isinstance(item,dict) or not key.startswith(("gh:","gh-")) or not is_coin(key,item):
            continue
        name=repo_name(item)
        if not name or name.lower() in seen:continue
        seen.add(name.lower());checked+=1
        try:
            payload=json.loads(fetch("https://api.github.com/repos/"+name+"/releases?per_page=5"))
            if not isinstance(payload,list):continue
            candidates=[]
            for release in payload[:5]:
                if not isinstance(release,dict) or release.get("draft") or release.get("prerelease"):continue
                dt=parse_time(release.get("published_at"))
                if not dt or not timedelta(0)<=now-dt<=timedelta(days=45):continue
                title=str(release.get("name") or release.get("tag_name") or "")[:100]
                # A software release is not proof the chain is mining.
                candidates.append({"title":title,"published_at":dt.isoformat(timespec="minutes"),
                    "url":str(release.get("html_url") or "")[:400],
                    "note":"Релиз проекта; работу сети, выплат и майнинга не подтверждает"})
            if candidates:
                item["github_release_evidence"]=candidates[:2]
                matched+=1
        except Exception as exc:
            print("GitHub release evidence unavailable:",type(exc).__name__)
    return {"checked":checked,"projects_with_releases":matched}
