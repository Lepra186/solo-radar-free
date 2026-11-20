"""Local subscriptions to projects: automatic add/review/untrack, not social follows."""
from datetime import datetime,timezone,timedelta
from research_agent import examine,aware

MAX_TRACKED=80

def reconcile(topics,previous,now):
    tracked=dict(previous) if isinstance(previous,dict) else {}
    promoted,removed=0,0
    for key,item in topics.items():
        if not isinstance(item,dict):continue
        result=examine(key,item,now)
        if result and result['score']>=5:
            if key not in tracked:promoted+=1
            tracked[key]={
                'name':item.get('title','')[:155],
                'source':result['source'],
                'score':result['score'],
                'last_reviewed':now.isoformat(timespec='seconds'),
                'reason':'; '.join(result['reasons'][:2])[:250],
                'status':'MONITOR',
            }
        elif key in tracked:
            tracked.pop(key,None)
            removed+=1
    # Remove projects that have disappeared from the available archive or
    # have become stale. This never modifies external GitHub/Discord accounts.
    for key in list(tracked):
        item=topics.get(key)
        first=aware(item.get('date') or item.get('repo_created')) if isinstance(item,dict) else None
        if (not item or item.get('tracked_repo_disabled')
            or (first and now-first>timedelta(days=45))):
            tracked.pop(key,None)
            removed+=1
    if len(tracked)>MAX_TRACKED:
        kept=sorted(tracked.items(),key=lambda x:(-x[1]['score'],x[0]))[:MAX_TRACKED]
        removed+=len(tracked)-len(kept)
        tracked=dict(kept)
    return tracked, {'added':promoted,'removed':removed,'active':len(tracked)}
