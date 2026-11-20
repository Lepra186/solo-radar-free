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
from gpu_assessment import assess, signal, description
from solo_intel import summary, source_quality
from telegram_commands import process_commands
from project_links import from_text, format_links
from telegram_recipients import parse_recipients

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT = os.getenv("TELEGRAM_CHAT_ID", "").strip()
EXTRA_CHATS = os.getenv("TELEGRAM_EXTRA_CHAT_IDS", "").strip()
STATE = Path("data/state.json")
NOW = datetime.now(timezone.utc)
PREVIOUSLY_REPORTED = ("neural engine byte", "quinvium", "nex chain", "retro boomer", "karlsen", "pearl")
HEADERS = {"User-Agent": "SOLO-Radar/1.2 (+personal PoW announcements)"}
BTT = ("https://bitcointalk.org/index.php?board=159.0",
       "https://bitcointalk.org/index.php?board=159.40")
RSS = ("https://2miners.com/blog/feed/",)
POOL_NEWS = ("https://pool-pay.com/",)

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=22) as res:
        return res.read().decode("utf-8", errors="replace")

def send_to_chat(message, chat_id):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": message,
                         "disable_web_page_preview": True}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as res:
        response = json.load(res)
    if not response.get("ok"):
        raise RuntimeError("Telegram did not accept message")

def notify(message):
    if not TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN secret")
    recipients = parse_recipients(CHAT, EXTRA_CHATS)
    sent = 0
    for recipient in recipients:
        try:
            send_to_chat(message, recipient)
            sent += 1
        except Exception as exc:
            print("Telegram delivery error for configured recipient:", type(exc).__name__)
    if sent == 0:
        raise RuntimeError("Message delivery failed for all authorized recipients")
    print("Telegram delivery succeeded for", sent, "recipient(s)")


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

    # One-time welcome for the newly authorized recipient. Telegram permits
    # this only after the person has started a private chat with the bot.
    additional_id = "812" + "612" + "452"
    if not state.get("second_user_welcomed"):
        try:
            send_to_chat("✅ Доступ к SOLO Radar открыт! Напишите /start для меню GPU PoW-монет.", additional_id)
            state["second_user_welcomed"] = True
            print("Second authorized recipient: welcome delivered")
        except Exception as exc:
            print("Second authorized recipient: welcome pending user /start:", type(exc).__name__)

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

    # Retain project-specific URLs only when explicitly present in the source.
    for candidate in results.values():
        extracted = from_text(candidate.get("body") or "")
        for kind, url in extracted.items():
            candidate.setdefault("links", {}).setdefault(kind, url)

    if ok == 0:
        print("All discovery sources unavailable; no state baseline change")
        # Still write connection state so greeting isn't repeated.
    seen = state.setdefault("topics", {})
    unseen = [(key, item) for key, item in results.items() if key not in seen]
    if ok and state.get("baseline_done"):
        candidates = sorted(((assess(item["body"], NOW)["score"], key, item)
                             for key, item in unseen), key=lambda x: x[0], reverse=True)
        sent = 0
        for points, key, item in candidates:
            tier = signal(item["body"], NOW)
            reason = None
            if sent >= 3:
                reason = "limit 3 alerts per run"
            elif any(name in item["body"].lower() for name in PREVIOUSLY_REPORTED):
                reason = "already discussed project"
            elif not tier:
                reason = "no enough GPU/PoW and launch, pool or SOLO evidence"
            print("Candidate review:", item["source"], "| score:", points,
                  "|", "rejected: " + reason if reason else "alert: " + tier,
                  "|", item["url"])
            if reason:
                continue
            notify(
                ("🚀 РАННИЙ GPU PoW-КАНДИДАТ — НЕ ПРОВЕРЕН" if tier == "EARLY" else
                 "🪙 ПУЛ / НАКОПЛЕНИЕ — КАНДИДАТ, НЕ ПРОВЕРЕН" if tier == "HOLD" else
                 "🔎 GPU PoW-КАНДИДАТ — НЕ ПРОВЕРЕН") + "\n\n"
                + item["title"][:160] + "\n"
                + "Источник: " + item["source"] + "\n"
                + "Дата публикации/создания: " + (item["date"] or "не определена") + "\n\n"
                + description(item["body"], NOW) + "\n\n"
                + summary(item["body"]) + "\n\n"
                + ("🔗 ССЫЛКИ ИЗ АНОНСА (НЕ ПРОВЕРЕНЫ):\n"
                   + format_links(item.get("links")) + "\n\n"
                   if format_links(item.get("links")) else "")
                + "Надёжность источника: " + source_quality(item) + "\n\n"
                + "⚠️ Это не подтверждённый запуск и не совет майнить.\n"
                + item["url"]
            )
            sent += 1
        print("Alerts sent:", sent)
    elif ok:
        state["baseline_done"] = True
        print("Baseline saved; old entries suppressed.")

    # Reply to commands from the authorized owner's chat after building the current snapshot.
    # A failed Telegram API request must not stop the scanning state from being saved.
    try:
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo",
            headers={"User-Agent": "SOLO-Radar/1.5"})
        with urllib.request.urlopen(request, timeout=15) as response:
            info = json.load(response)
        webhook_active = bool(info.get("result", {}).get("url"))
        if webhook_active:
            print("Webhook active in Telegram; polling disabled to avoid getUpdates conflicts")
        else:
            process_commands(TOKEN, parse_recipients(CHAT, EXTRA_CHATS), state, results, NOW, send_to_chat)
    except Exception as exc:
        print("Telegram command check failed:", type(exc).__name__, str(exc)[:140])

    stamp = NOW.isoformat(timespec="seconds")
    if ok:
        for key, item in results.items():
            old = seen.get(key, {})
            seen[key] = {"title": item["title"],
                         "seen": old.get("seen", stamp),
                         "last_seen": stamp,
                         "url": item.get("url") or old.get("url"),
                         "links": item.get("links") or old.get("links") or {},
                         "body": (item.get("body") or old.get("body") or item["title"])[:1600],
                         "source": item.get("source") or old.get("source") or "",
                         "kind": item.get("kind") or old.get("kind") or "",
                         "date": item.get("date") or old.get("date")}
        if len(seen) > 6000:
            seen = dict(sorted(seen.items(), key=lambda x: x[1]["seen"], reverse=True)[:6000])
    state["last_scan"] = stamp
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Sources available: {ok}, items: {len(results)}, new items: {len(unseen)}")

if __name__ == "__main__":
    main()
