"""Offline, auditable PoW research agent for periodic Telegram shortlists.

Not an LLM. Works on known public source text; cannot verify network activity,
pool payouts, exchange liquidity, or price upside. Rank for further research.
"""
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from gpu_assessment import assess
from project_facts import get_facts
from coin_filter import is_coin

APP = re.compile(r'\b(miner\s*v?\d+(?:\.\d+)*|software release|driver|farm management|'
                 r'benchmark|mining calculator|exchange|rental service)\b', re.I)
NEGATIVE = re.compile(r'\b(airdrop|presale|ico|nft|testnet.only)\b', re.I)
HARDWARE_ONLY = re.compile(r'\b(cpu[- ]only|asic[- ]only|randomx|yespower)\b', re.I)
LAUNCH = re.compile(r'\b(mainnet|genesis|fair.launch|network.launch|block\s*0)\b', re.I)
ALGORITHM = re.compile(r'\b(kawpow|etchash|ethash|progpow|fishhash|autolykos|'
                       r'equihash|octopus|verthash)\b', re.I)
MINING = re.compile(r'\b(solo|mining.pool|stratum|pplns|gpu.mining|mineable)\b', re.I)

def aware(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:
        return None

def origin(key):
    if key.startswith(('gh:', 'gh-')): return 'GitHub'
    if key.startswith('btt:'): return 'Bitcointalk'
    if key.startswith('tg:'): return 'Telegram'
    if key.startswith('dc:'): return 'Discord'
    if key.startswith('pool:'): return 'Пул'
    if key.startswith('rss:'): return 'RSS'
    return 'Другое'

def valid_url(url):
    if not isinstance(url, str) or len(url) > 500:
        return None
    try:
        parsed = urlparse(url)
        if parsed.scheme == 'https' and parsed.hostname and not parsed.username:
            return url
    except ValueError:
        pass
    return None

def examine(key, item, now):
    title = str(item.get('title') or '')[:180]
    content = str(item.get('body') or title)[:2000]
    if not title or not is_coin(key,item) or APP.search(title) or NEGATIVE.search(title):
        return None
    if item.get('kind') == 'news' or origin(key) in ('Пул', 'RSS'):
        return None  # News informs discovery, but isn't inherently a new coin.
    facts = item.get('facts')
    if not isinstance(facts, dict) or not facts:
        facts = get_facts(content, kind=str(item.get('kind') or ''),
                          publication=item.get('date'),
                          repo_created=item.get('repo_created'))
    assessed = assess(content, now)
    gpu = bool(facts.get('gpu_mentioned')) or bool(assessed['gpu'])
    pow_ = bool(assessed['pow']) or bool(ALGORITHM.search(content))
    if not gpu or not pow_ or assessed['excluded']:
        return None
    if HARDWARE_ONLY.search(content) and not ALGORITHM.search(content) and not re.search(r'\bgpu\b',content,re.I):
        return None

    # "Seen by the radar" is not a publication date or mainnet start.
    published = (aware(facts.get('publication_utc')) or
                 aware(facts.get('repo_created_utc')) or
                 aware(item.get('date')) or aware(item.get('repo_created')))
    age_days = (now-published).total_seconds()/86400 if published else None
    if age_days is not None and (age_days < -1 or age_days > 45):
        return None
    launch = aware(facts.get('launch_claim_utc'))
    score = 0
    good, unknown = [], []
    if age_days is not None and age_days <= 3:
        score += 3
        good.append('недавняя публикация или создание репозитория')
    elif age_days is not None and age_days <= 14:
        score += 1
    else:
        unknown.append('дата публикации/создания не установлена либо старая')
    alg = facts.get('algorithm') or (ALGORITHM.search(content).group(0) if ALGORITHM.search(content) else None)
    if alg:
        score += 3
        good.append('указан GPU-алгоритм: '+str(alg)[:32])
    else:
        unknown.append('неизвестен алгоритм')
    if launch:
        score += 3
        good.append('заявлена дата mainnet (не подтверждена)')
    elif LAUNCH.search(content):
        score += 1
        unknown.append('дата mainnet не подтверждена')
    else:
        unknown.append('нет проверенной даты mainnet')
    if facts.get('solo_mentioned') or re.search(r'\bsolo\b',content,re.I):
        score += 1
        good.append('упомянут SOLO')
    if facts.get('pool_mentioned') or MINING.search(content):
        score += 1
        good.append('упомянут майнинг/пул')
    links = item.get('links') or {}
    if valid_url(links.get('pool')):
        score += 1
        good.append('есть ссылка на пул из объявления')
    if valid_url(links.get('explorer')):
        score += 1
        good.append('есть ссылка на обозреватель из объявления')
    if origin(key) == 'GitHub':
        score = max(0, score - 1)
        unknown.append('репозиторий сам по себе не подтверждает mainnet')
    # Do not convert speculation into a confident buy/mine recommendation.
    unknown += ['не проверены блоки сети, награда, premine и сложность',
                'не проверены биржи, объёмы и возможность продажи']
    if score < 3:
        return None
    return {'key':key, 'title':title, 'url':valid_url(item.get('url')),
            'source':origin(key), 'score':score,
            'status':'ИЗУЧИТЬ' if score >= 8 else 'НАБЛЮДАТЬ',
            'published':published.isoformat(timespec='minutes') if published else None,
            'launch_claim':launch.isoformat(timespec='minutes') if launch else None,
            'algorithm':str(alg) if alg else None,
            'reasons':good[:4], 'unknown':unknown[:5]}

def analyze(topics, now=None, limit=8):
    now = now or datetime.now(timezone.utc)
    examined = []
    for key,item in topics.items():
        if not isinstance(item,dict): continue
        candidate = examine(key,item,now)
        if candidate: examined.append(candidate)
    examined.sort(key=lambda c:(-c['score'], -(aware(c['published']).timestamp() if c['published'] else 0), c['key']))
    # Prevent one listing service from consuming all featured slots.
    chosen=[]; origin_counts={}; urls=set()
    for c in examined:
        if origin_counts.get(c['source'],0)>=3:
            continue
        # Old and new GitHub discovery paths may point to the same project.
        url=(c.get('url') or '').rstrip('/').lower()
        # GitHub duplicate IDs from legacy and current scanners are common.
        # Do not merge unrelated ANN source records merely by a shared URL.
        if c['source']=='GitHub' and url and url in urls:
            continue
        chosen.append(c)
        if c['source']=='GitHub' and url: urls.add(url)
        origin_counts[c['source']]=origin_counts.get(c['source'],0)+1
        if len(chosen)>=limit: break
    return chosen

def report(items, checked_at, max_items=3):
    lines=['🧠 SOLO RADAR • АВТОАНАЛИТИК',
           'Анализ открытых анонсов по правилам, НЕ ИИ-модель.',
           'Проверено: '+checked_at.strftime('%Y-%m-%d %H:%M UTC'),'']
    if not items:
        lines += ['Новых обоснованных вариантов пока нет.',
                  'Это не означает отсутствия новых запусков: охват ограничен.']
    for index,c in enumerate(items[:max_items],1):
        lines += [str(index)+'. '+c['title'][:125],
                  'Источник: '+c['source']+' | Баллы: '+str(c['score'])+' | '+c['status'],
                  'Алгоритм: '+str(c['algorithm'] or 'неизвестен'),
                  'Запуск: '+(c['launch_claim'][:16].replace('T',' ')+' UTC (заявлено)' if c['launch_claim'] else 'не подтверждён'),
                  'Почему: '+('; '.join(c['reasons'][:3]) or 'мало подтверждений'),
                  'Риски: '+('; '.join(c['unknown'][:2])),
                  c['url'] or 'Ссылка не получена','']
    lines.append('⚠️ Не инвестиционная рекомендация; рост цены и доступность добычи не проверены.')
    return '\n'.join(lines)[:3900]
