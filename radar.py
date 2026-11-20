#!/usr/bin/env python3
"""SOLO Radar: free scheduled candidate discovery with explicit uncertainty."""
import os
import re
import json
import html
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote
from telegram_sources import CHANNELS, parse_public_channel

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT = os.getenv("TELEGRAM_CHAT_ID", "").strip()
STATE = Path("data/state.json")
NOW = datetime.now(timezone.utc)
KNOWN = {"neb", "qu", "nexc", "tape", "pearl", "karlsen", "kls"}
HEADERS = {"User-Agent": "SOLO-Radar/1.2 (+personal PoW announcements)"}
BTT = ("https://bitcointalk.org/index.php?board=159.0",
       "https://bitcointalk.org/index.php?board=159.40")
RSS = ("https://2miners.com/blog/feed/",)
POOL_NEWS = ("https://pool-pay.com/",)

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=22) as res:
        return res.read().decode("utf-8", errors="replace")

def notify(message):
    if not TOKEN or not CHAT:
        raise RuntimeError("Set both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in Actions secrets")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=json.dumps({"chat_id": CHAT, "text": message,
                         "disable_web_page_preview": True}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as res:
        response = json.load(res)
    if not response.get("ok"):
        raise RuntimeError("Telegram did not accept message")

class Topics(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.text = []
        self.topics = {}
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            m = re.search(r"[?&]topic=(\d+)", dict(attrs).get("href", ""))
            if m:
                self.current, self.text = m.group(1), []
    def handle_data(self, data):
        if self.current:
            self.text.append(data)
    def handle_endtag(self, tag):
        if tag == "a" and self.current:
            title = " ".join(html.unescape("".join(self.text)).split())
            if 12 <= len(title) <= 180:
                self.topics[self.current] = title
            self.current = None

def ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        try:
            return parsedate_to_datetime(value).astimezone(timezone.utc)
        except (ValueError, TypeError, IndexError):
            return None

def eligible(text):
    t = text.lower()
    if re.search(r"\b(ico|presale|airdrop|meme.?token|staking|nft)\b", t):
        return -10
    score = 0
    for regex, points in (
        (r"\b(pow|proof.of.work|mineable|mining)\b", 3),
        (r"\b(gpu|nvidia|cuda|ethash|etchash|kawpow|progpow|blake3|autolykos)\b", 5),
        (r"\b(mainnet|genesis|launch|new.pool|solo)\b", 2),
        (r"\b(fair.launch|no.premine|0%.premine)\b", 2),
        (r"coin name\s*:", 2),
        (r"\balgo\s*:", 2),
    ):
        if re.search(regex, t):
            score += points
    if re.search(r"\b(cpu.only|randomx|yespower|sha.?256.asic)\b", t) and "gpu" not in t:
        score -= 8
    return score

def analyze(text):
    t = text.lower()
    gpu = bool(re.search(r"\b(gpu|nvidia|cuda|ethash|kawpow|progpow|blake3|autolykos)\b", t))
    solo = bool(re.search(r"\bsolo\b", t))
    premine = "заявлено отсутствие" if re.search(r"(no.premine|0%.premine|zero.premine)", t) else "не проверен"
    return (
        f"RTX 5070 Ti: {'GPU упоминается; совместимость НЕ проверена' if gpu else 'совместимость не подтверждена'}\n"
        f"SOLO: {'упоминается; доступность НЕ проверена' if solo else 'не подтверждено'}\n"
        f"Premine: {premine}\n"
        "Mainnet и точное время: не подтверждены\n"
        "Сложность и шанс блока: нет измерений\n"
        "Биржа и ликвидность: не проверены"
    )

def main():
    if not TOKEN or not CHAT:
        raise RuntimeError("Telegram secrets missing: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
    state = {"initialized": False, "baseline_done": False, "topics": {}}
    if STATE.exists():
        try:
            saved = json.loads(STATE.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                state.update(saved)
        except (OSError, ValueError):
            pass

    if not state.get("initialized"):
        notify("✅ SOLO Radar подключён. Источники: GitHub, Bitcointalk (если доступен), RSS 2Miners и новости пулов. Кандидаты будут помечены как непроверенные.")
        state["initialized"] = True

    results = {}
    ok = 0

    # GitHub: newly created repos only. An update is not mainnet evidence.
    try:
        since = (NOW - timedelta(days=7)).date().isoformat()
        q = quote(f'cryptocurrency proof of work created:>{since}')
        data = json.loads(fetch("https://api.github.com/search/repositories?q=" + q
                                + "&sort=created&order=desc&per_page=50"))
        for item in data.get("items", []):
            name = item.get("full_name", "")
            created = ts(item.get("created_at"))
            if not name or not created or NOW - created > timedelta(days=7):
                continue
            description = (item.get("description") or "")[:350]
            results["gh:" + str(item["id"])] = {
                "title": name, "body": f"{name} {description}",
                "url": item.get("html_url") or "https://github.com/" + name,
                "source": "GitHub — новый репозиторий, НЕ запуск сети",
                "date": created.isoformat(), "kind": "repository"}
        ok += 1
        print("GitHub source OK:", len(results))
    except Exception as exc:
        print("GitHub source unavailable:", repr(exc)[:140])

    # Bitcointalk: these pages are frequently blocked to scheduled cloud workers.
    for url in BTT:
        try:
            parser = Topics()
            parser.feed(fetch(url))
            for topic, title in parser.topics.items():
                results["btt:" + topic] = {
                    "title": title, "body": title,
                    "url": f"https://bitcointalk.org/index.php?topic={topic}.0",
                    "source": "Bitcointalk ANN — дата первого сообщения не проверена",
                    "date": None, "kind": "announcement"}
            ok += 1
            print("Bitcointalk source OK:", len(parser.topics))
        except Exception as exc:
            print("Bitcointalk unavailable:", type(exc).__name__)

    # Industry RSS: publications are news evidence, not proof of actual block production.
    for url in RSS:
        try:
            feed = ET.fromstring(fetch(url))
            count = 0
            for item in feed.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                published = ts(item.findtext("pubDate"))
                description = re.sub(r"<[^>]+>", " ", item.findtext("description") or "")
                if not title or not link or not published:
                    continue
                if NOW - published > timedelta(days=7) or published > NOW + timedelta(days=1):
                    continue
                results["rss:" + link] = {
                    "title": title, "body": title + " " + html.unescape(description[:400]),
                    "url": link, "source": "2Miners — публикация",
                    "date": published.isoformat(), "kind": "news"}
                count += 1
            ok += 1
            print("2Miners RSS OK:", count)
        except Exception as exc:
            print("2Miners RSS unavailable:", type(exc).__name__)

    # Pool operator announcement pages: keep distinct from exchange listings.
    for url in POOL_NEWS:
        try:
            raw = fetch(url)
            plain = html.unescape(re.sub(r"<[^>]+>", " ", raw))
            plain = " ".join(plain.split())
            count = 0
            for match in re.finditer(r"2026-\d{2}-\d{2}\s*[—–-]\s*", plain):
                date = ts(match.group(0)[:10])
                if date and timedelta(0) <= NOW - date <= timedelta(days=7):
                    snippet = plain[match.end():match.end()+360].split("2026-", 1)[0].strip()
                    if snippet:
                        key = "pool:" + match.group(0)[:10] + ":" + str(count)
                        results[key] = {"title": snippet[:150], "body": snippet,
                                        "url": url, "source": "Pool operator — публичное обновление",
                                        "date": date.isoformat(), "kind": "news"}
                        count += 1
            ok += 1
            print("Pool operator news OK:", count)
        except Exception as exc:
            print("Pool operator source unavailable:", type(exc).__name__)

    # Public Telegram mining launch channels; not equivalent to verified mainnet.
    for channel in CHANNELS:
        url = "https://t.me/s/" + channel
        try:
            posts = parse_public_channel(fetch(url), channel, now=NOW)
            results.update(posts)
            ok += 1
            print("Telegram public channel:", channel, "recent posts:", len(posts))
        except Exception as exc:
            print("Telegram public source unavailable:", channel, type(exc).__name__)

    # Optional Discord integration. Requires a bot invited to each selected
    # channel with View Channel, Read Message History and message content access.
    discord_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    discord_channels = [v.strip() for v in os.getenv("DISCORD_CHANNEL_IDS", "").split(",") if v.strip()]
    if discord_token and discord_channels:
        for channel in discord_channels[:10]:
            if not channel.isdigit():
                print("Discord invalid channel ID (must be numeric)")
                continue
            try:
                req = urllib.request.Request(
                    f"https://discord.com/api/v10/channels/{channel}/messages?limit=30",
                    headers={"Authorization": "Bot " + discord_token,
                             "User-Agent": "SOLO-Radar/1.2"})
                with urllib.request.urlopen(req, timeout=20) as res:
                    messages = json.load(res)
                count = 0
                for msg in messages:
                    published = ts(msg.get("timestamp"))
                    if not published or not timedelta(0) <= NOW - published <= timedelta(days=7):
                        continue
                    contents = [msg.get("content") or ""]
                    for embed in msg.get("embeds", [])[:3]:
                        contents.extend((embed.get("title") or "", embed.get("description") or ""))
                    body = " ".join(contents).strip()[:1500]
                    if len(body) < 15:
                        continue
                    results["dc:" + channel + ":" + msg["id"]] = {
                        "title": body[:160], "body": body,
                        "url": f"https://discord.com/channels/{msg.get('guild_id', '@me')}/{channel}/{msg['id']}",
                        "source": "Discord — сообщение выбранного канала",
                        "date": published.isoformat(), "kind": "announcement"}
                    count += 1
                ok += 1
                print("Discord channel available:", channel, "messages:", count)
            except Exception as exc:
                print("Discord channel unavailable:", channel, type(exc).__name__)
    else:
        print("Discord not configured; optional DISCORD_BOT_TOKEN and DISCORD_CHANNEL_IDS")

    if ok == 0:
        print("All discovery sources unavailable; no state baseline change")
        # Still write connection state so greeting isn't repeated.
    seen = state.setdefault("topics", {})
    unseen = [(key, item) for key, item in results.items() if key not in seen]
    if ok and state.get("baseline_done"):
        candidates = sorted(((eligible(item["body"]), key, item)
                             for key, item in unseen), key=lambda x: x[0], reverse=True)
        sent = 0
        for points, key, item in candidates:
            if points < 8 or sent >= 3:
                continue
            # Require both mining/PoW and GPU evidence; otherwise don't waste user alerts.
            if not re.search(r"\b(pow|proof.of.work|mining|mineable|coin name)\b", item["body"], re.I):
                continue
            if not re.search(r"\b(gpu|nvidia|cuda|ethash|etchash|kawpow|progpow|blake3|autolykos)\b", item["body"], re.I):
                continue
            notify(
                "🔎 SOLO RADAR — КАНДИДАТ, НЕ ПРОВЕРЕН\n\n"
                + item["title"][:160] + "\n"
                + "Источник: " + item["source"] + "\n"
                + "Дата публикации/создания: " + (item["date"] or "не определена") + "\n\n"
                + analyze(item["body"]) + "\n\n"
                + "⚠️ Это повод изучить проект, НЕ сигнал начинать майнинг.\n"
                + item["url"]
            )
            sent += 1
        print("Alerts sent:", sent)
    elif ok:
        state["baseline_done"] = True
        print("Baseline saved; old entries suppressed.")

    stamp = NOW.isoformat(timespec="seconds")
    if ok:
        for key, item in results.items():
            seen[key] = {"title": item["title"], "seen": seen.get(key, {}).get("seen", stamp)}
        if len(seen) > 6000:
            seen = dict(sorted(seen.items(), key=lambda x: x[1]["seen"], reverse=True)[:6000])
    state["last_scan"] = stamp
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Sources available: {ok}, items: {len(results)}, new items: {len(unseen)}")

if __name__ == "__main__":
    main()
