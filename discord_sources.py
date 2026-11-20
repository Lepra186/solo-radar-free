"""Read-only authorized Discord announcement discovery for GPU PoW research.

No user tokens, self-bots, joins, invitations, or subscriptions. Requires a
bot installed by a server administrator and channel IDs with permissions.
"""
import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from project_links import from_text

CHANNEL_PATTERN=re.compile(r"^\d{15,22}$")
MAX_CHANNELS=8
MAX_POSTS=30

def date_value(raw):
    try:
        dt=datetime.fromisoformat(str(raw).replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError,TypeError):
        return None

def parse_channels(raw):
    return list(dict.fromkeys(s for s in re.split(r"[,;\s]+", raw or "")
                              if CHANNEL_PATTERN.fullmatch(s)))[:MAX_CHANNELS]

def parse_messages(messages, channel, now):
    result={}
    if not isinstance(messages,list):
        raise ValueError("Discord returned non-list messages")
    for message in messages[:MAX_POSTS]:
        mid=str(message.get("id") or "")
        published=date_value(message.get("timestamp"))
        if not mid.isdigit() or not published:
            continue
        if not timedelta(0)<=now-published<=timedelta(hours=96):
            continue
        chunks=[str(message.get("content") or "")]
        for embed in (message.get("embeds") or [])[:4]:
            if isinstance(embed,dict):
                chunks.extend((str(embed.get("title") or ""),
                               str(embed.get("description") or "")))
                for fld in (embed.get("fields") or [])[:6]:
                    if isinstance(fld,dict):
                        chunks.extend((str(fld.get("name") or ""),
                                       str(fld.get("value") or "")))
        body=" ".join(" ".join(chunks).split())[:1800]
        if len(body)<22:continue
        guild=str(message.get("guild_id") or "")
        if not guild.isdigit():continue
        key="dc:"+channel+":"+mid
        result[key]={
            "title":body[:160],"body":body,
            "url":"https://discord.com/channels/"+guild+"/"+channel+"/"+mid,
            "source":"Discord — разрешённый канал",
            "date":published.isoformat(),"kind":"announcement",
            "links":from_text(body)
        }
    return result

def fetch_channels(token,raw_channels,now,fetcher=None):
    channels=parse_channels(raw_channels)
    if not token or not channels:
        return {},{"status":"not_configured","channels":0,"success":0,"items":0}
    def fetch_default(url,token):
        req=urllib.request.Request(url,headers={
            "Authorization":"Bot "+token,
            "User-Agent":"SOLO-Radar/2.0 (authorized Discord channel reader)"
        })
        with urllib.request.urlopen(req,timeout=15) as response:
            return json.load(response)
    get=fetcher or fetch_default
    all_posts={}; success=0; empty=0; failures=[]
    for channel in channels:
        try:
            data=get("https://discord.com/api/v10/channels/"+channel+"/messages?limit=30",token)
            posts=parse_messages(data,channel,now)
            all_posts.update(posts)
            success+=1
            if data and not posts:empty+=1
            print("Discord authorized channel fetched; matching posts:",len(posts))
        except Exception as exc:
            # Deliberately do not expose token or request URL in logs.
            failures.append(type(exc).__name__)
            print("Discord channel unavailable:",type(exc).__name__)
    status="active" if success else "unavailable"
    return all_posts,{"status":status,"channels":len(channels),"success":success,
                      "items":len(all_posts),"nonempty_without_candidates":empty,
                      "failures":failures[:3]}
