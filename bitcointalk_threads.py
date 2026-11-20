"""Read known Bitcointalk coin threads, not just their announcement titles.

Bounded read-only requests, first-page content only. Claims, pool addresses
and allegations from a discussion are *not verified technical facts*.
No arbitrary URL fetching: only numeric topic IDs at bitcointalk.org.
"""
import re
from html.parser import HTMLParser
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit

MAX_THREADS=3
MAX_HTML=400_000
CACHE=timedelta(hours=12)
WARNINGS={
  "withdrawal_complaint":re.compile(r"\b(?:withdrawals?\s+(?:are|is|were)\s+not\s+(?:happening|working)|unable\s+to\s+withdraw|stuck\s+withdrawals?|can't\s+withdraw)\b",re.I),
  "liquidity_concern":re.compile(r"\b(?:no\s+(?:\w+\s+){0,3}liquidity|liquidity\s+is\s+(?:missing|zero|low)|lack\s+of\s+liquidity)\b",re.I),
  "fraud_allegation":re.compile(r"\b(?:scam|fraud|rug\s*pull)\b",re.I)
}
PREMINE=re.compile(r"\b(?:premine|pre[- ]?mine|premined)\b.{0,65}?\b(\d{1,2}(?:\.\d+)?)\s*%|\b(\d{1,2}(?:\.\d+)?)\s*%\s*(?:premine|pre[- ]?mine|premined)\b",re.I)
POOL_TERMS=re.compile(r"\b(?:pplns|solo\s+pool|pool\s+(?:fee|stats|operators)|stratum\+tcp|stratum\+ssl)\b",re.I)

def timestamp(value):
    if not isinstance(value,str):return None
    try:
        d=datetime.fromisoformat(value.replace("Z","+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except ValueError:return None

def topic_id(key):
    match=re.fullmatch(r"btt:(\d{3,12})",str(key))
    return match.group(1) if match else None

class ThreadParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth=0;self.posts=[];self.current=None;self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        classes=str(a.get("class") or "").split()
        if self.current is not None:
            if tag=="div":self.depth+=1
            if tag=="a":
                href=str(a.get("href") or "")
                if href.startswith(("https://","http://")) and len(href)<400:
                    self.current["links"].append(href)
        elif tag=="div" and "post" in classes:
            self.current={"chunks":[],"links":[]}
            self.depth=1
    def handle_endtag(self,tag):
        if self.current is None:return
        if tag=="div":
            self.depth-=1
            if self.depth<=0:
                text=" ".join(" ".join(self.current["chunks"]).split())
                if text and len(self.posts)<35:
                    self.posts.append({"text":text[:9000],
                                      "links":list(dict.fromkeys(self.current["links"]))[:30]})
                self.current=None;self.depth=0
    def handle_data(self,data):
        if self.current is not None and len(self.current["chunks"])<3000:
            self.current["chunks"].append(data)

def parse(html,source_url,now):
    if not isinstance(html,str) or not html or len(html)>MAX_HTML:
        raise ValueError("Bitcointalk page invalid or too large")
    parser=ThreadParser()
    parser.feed(html)
    posts=parser.posts
    if not posts:raise ValueError("No thread posts could be parsed")
    announcement=posts[0]["text"]
    premine=None
    m=PREMINE.search(announcement[:5000])
    if m:
        n=float(m.group(1) or m.group(2))
        if 0<=n<=100:premine=n
    warnings=[]
    for label,pattern in WARNINGS.items():
        for post in posts[1:]:
            if pattern.search(post["text"]):
                warnings.append({"type":label,
                  "context":" ".join(post["text"].split())[:240],
                  "attribution":"утверждение участника обсуждения, не проверено"})
                break
    pool_notes=sum(bool(POOL_TERMS.search(post["text"])) for post in posts)
    urls=list(dict.fromkeys(link for post in posts[:20] for link in post["links"]))
    safe_urls=[]
    for url in urls:
        p=urlsplit(url)
        if p.scheme!="https" or not p.hostname or p.username or p.password:continue
        safe_urls.append(url)
    return {
        "source":"Bitcointalk public thread",
        "source_url":source_url,
        "checked_at":now.isoformat(timespec="seconds"),
        "posts_read":len(posts),
        "premine_percent_claimed_by_announcement":premine,
        "reported_pool_related_posts":pool_notes,
        "discussion_warnings":warnings[:3],
        "links_mentioned":safe_urls[:12],
        "announcement_excerpt":announcement[:350],
        "note":"Заявления из форума не равны подтверждённому майнингу, выплатам или листингу"
    }

def enrich(fetch,topics,now,limit=MAX_THREADS):
    checked=0;found=0;warned=0
    for key,item in topics.items():
        if checked>=limit:break
        tid=topic_id(key)
        if not tid or not isinstance(item,dict) or item.get("coin_class")!="coin_candidate":
            continue
        old=item.get("thread_evidence") or {}
        last=timestamp(old.get("checked_at"))
        if last and timedelta(0)<=now-last<CACHE:continue
        checked+=1
        url="https://bitcointalk.org/index.php?topic="+tid+".0"
        try:
            evidence=parse(fetch(url),url,now)
            item["thread_evidence"]=evidence
            found+=1
            if evidence["discussion_warnings"]:warned+=1
        except Exception as exc:
            print("Bitcointalk thread detail unavailable:",type(exc).__name__)
            item["thread_evidence"]={"source":"Bitcointalk","checked_at":now.isoformat(timespec="seconds"),
                                     "status":"could_not_parse"}
    return {"threads_checked":checked,"threads_parsed":found,"threads_with_warnings":warned}
