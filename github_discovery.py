"""Public GitHub PoW discovery with bounded searches and no account subscriptions.

Queries use GitHub's public repository search. Following is implemented as a
local monitoring list: no stars, watches, joining groups or account mutations.
"""
import json
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from project_facts import get_facts

QUERIES=(
    'gpu mining cryptocurrency created:>{date}',
    'pow coin mainnet created:>{date}',
    'kawpow OR ethash OR fishhash created:>{date}',
)
MAX_PER_QUERY=20
MAX_CALLS=3

def parse_date(raw):
    try:
        dt=datetime.fromisoformat(str(raw).replace('Z','+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError,TypeError):
        return None

def gather(fetch, now, max_calls=MAX_CALLS):
    date=(now-timedelta(days=14)).date().isoformat()
    items={}; successes=0
    for template in QUERIES[:max_calls]:
        query=template.format(date=date)
        url="https://api.github.com/search/repositories?q="+quote(query)+"&sort=created&order=desc&per_page="+str(MAX_PER_QUERY)
        try:
            payload=json.loads(fetch(url))
            if not isinstance(payload.get('items'),list):
                raise ValueError("Invalid GitHub search response")
            successes+=1
            for repo in payload['items']:
                rid=repo.get("id")
                name=str(repo.get("full_name") or "")
                created=parse_date(repo.get("created_at"))
                if not isinstance(rid,int) or not name or not created:
                    continue
                if not timedelta(0)<=now-created<=timedelta(days=14):
                    continue
                if repo.get("fork") or repo.get("archived"):
                    continue
                description=str(repo.get("description") or "")[:500]
                body=name+" "+description
                key="gh:"+str(rid)
                data={
                    "title":name,"body":body,
                    "url":repo.get("html_url") or "https://github.com/"+name,
                    "source":"GitHub — репозиторий, не подтверждённая монета",
                    "date":created.isoformat(),"kind":"repository",
                    "repo_created":repo.get("created_at"),
                    "repo_updated":repo.get("pushed_at") or repo.get("updated_at"),
                    "github":{"name":name,"stars":int(repo.get("stargazers_count") or 0),
                              "forks":int(repo.get("forks_count") or 0),
                              "archived":False,"homepage":repo.get("homepage") or None},
                }
                data["facts"]=get_facts(body,kind="repository",repo_created=data["repo_created"],
                                         repo_updated=data["repo_updated"])
                items[key]=data
            print("GitHub discovery query succeeded:",len(payload["items"]))
        except Exception as exc:
            print("GitHub discovery query unavailable:",type(exc).__name__)
    return items,successes

def refresh_tracked(fetch,topics,tracked,now,limit=3):
    """Recheck selected public repos, but never star/watch an account repository."""
    updated=0
    for key in list(tracked):
        if updated>=limit:break
        item=topics.get(key)
        if not isinstance(item,dict) or not key.startswith(("gh:","gh-")):
            continue
        name=(item.get("github") or {}).get("name")
        if not name:
            from urllib.parse import urlparse
            url=str(item.get("url") or "")
            p=urlparse(url)
            if p.hostname in ("github.com","www.github.com"):
                name="/".join([x for x in p.path.split("/") if x][:2])
        if not name or name.count("/")!=1:continue
        try:
            data=json.loads(fetch("https://api.github.com/repos/"+name))
            if data.get("archived") or data.get("disabled"):
                item["tracked_repo_disabled"]=True
            item["repo_updated"]=data.get("pushed_at") or data.get("updated_at")
            item.setdefault("github",{})["stars"]=int(data.get("stargazers_count") or 0)
            item["github"]["forks"]=int(data.get("forks_count") or 0)
            item["github"]["archived"]=bool(data.get("archived"))
            item["github"]["name"]=str(data.get("full_name") or name)
            item["last_repo_check"]=now.isoformat(timespec="seconds")
            updated+=1
        except Exception as exc:
            print("Tracked GitHub repo refresh unavailable:",type(exc).__name__)
            break
    return updated
