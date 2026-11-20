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
from project_facts import get_facts
from coin_filter import classify, is_coin
from research_agent import analyze, report
from github_discovery import gather as discover_github, refresh_tracked
from project_watch import reconcile
from mineability import evaluate_all
from mining_economics import calculate_all
from gpu_readme_evidence import enrich as enrich_gpu_readmes
from github_releases_source import check_releases
from network_evidence import update as update_network_evidence
from discord_sources import fetch_channels as scan_discord
from mining_scan_source import refresh as refresh_mining_scan, matches_for
from pool_validation import update as update_pool_directory, match_pools, stratum_by_coin, parsed as parse_pool_time
from coincalculators_source import update as update_coin_calculators, matched as match_coin_calculators
from evidence_alerts import transitions as evidence_transitions, confirmed as confirm_evidence_alert

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

    # Multiple bounded GitHub searches. Creation ≠ launch; do not star/watch repositories.
    github_results, github_ok = discover_github(fetch, NOW)
    results.update(github_results)
    ok += github_ok
    print("GitHub discovery: sources:", github_ok, "repos:", len(github_results))

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

    # Discord requires an explicitly installed bot and permitted channel IDs.
    discord_results, discord_status = scan_discord(
        os.getenv("DISCORD_BOT_TOKEN", "").strip(),
        os.getenv("DISCORD_CHANNEL_IDS", ""), NOW)
    results.update(discord_results)
    ok += discord_status["success"]
    state["discord_status"] = discord_status
    print("Discord discovery status:", discord_status["status"],
          "authorized channels:", discord_status["success"],
          "posts:", discord_status["items"])

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
            classification, exclusion = classify(key, item)
            tier = signal(item["body"], NOW) if classification == "coin_candidate" else None
            reason = None
            if sent >= 3:
                reason = "limit 3 alerts per run"
            elif any(name in item["body"].lower() for name in PREVIOUSLY_REPORTED):
                reason = "already discussed project"
            elif classification != "coin_candidate":
                reason = "not a GPU PoW coin: " + exclusion
            elif not tier:
                reason = "not enough evidence for alert"
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

    # Gradually enrich legacy GitHub records created by an older radar version.
    # Limit API calls per scan to avoid GitHub unauthenticated rate limits.
    enriched = 0
    for key, previous in list(seen.items()):
        if enriched >= 3:
            break
        if not key.startswith("gh-") or previous.get("repo_created") or previous.get("metadata_checked"):
            continue
        label = str(previous.get("title") or "")
        found = re.search(r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", label)
        if not found:
            continue
        full_name = found.group(1)
        try:
            repo = json.loads(fetch("https://api.github.com/repos/" + full_name))
            created = repo.get("created_at")
            if created:
                previous["repo_created"] = created
                previous["repo_updated"] = repo.get("pushed_at") or repo.get("updated_at")
                previous["date"] = created
                previous["kind"] = "repository"
                previous["url"] = repo.get("html_url") or "https://github.com/" + full_name
                previous["source"] = "GitHub — репозиторий (историческая запись)"
                previous["body"] = (label + " " + str(repo.get("description") or ""))[:1600]
                previous["facts"] = get_facts(previous["body"],repo_created=created,
                    repo_updated=previous["repo_updated"],kind="repository")
            previous["metadata_checked"] = True
            enriched += 1
        except Exception as exc:
            print("Legacy GitHub metadata unavailable:", type(exc).__name__)
            break
    print("Legacy GitHub records enriched:", enriched)

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
                         "date": item.get("date") or old.get("date"),
                         "facts": get_facts(
                             item.get("body") or old.get("body") or item["title"],
                             publication=item.get("date") or old.get("date"),
                             repo_created=item.get("repo_created") or old.get("repo_created"),
                             repo_updated=item.get("repo_updated") or old.get("repo_updated"),
                             kind=item.get("kind") or old.get("kind") or ""),
                         "repo_created": item.get("repo_created") or old.get("repo_created"),
                         "repo_updated": item.get("repo_updated") or old.get("repo_updated"),
                         "github": item.get("github") or old.get("github") or {},
                         "gpu_support_evidence": old.get("gpu_support_evidence") or [],
                         "gpu_support_checked_at": old.get("gpu_support_checked_at"),
                         "coin_class": classify(key, item)[0],
                         "coin_reason": classify(key, item)[1]}
        if len(seen) > 6000:
            seen = dict(sorted(seen.items(), key=lambda x: x[1]["seen"], reverse=True)[:6000])
    # Reclassify historical records so legacy miners never remain in shortlists.
    breakdown = {}
    for historic_key, historic_item in seen.items():
        coin_class, coin_reason = classify(historic_key, historic_item)
        historic_item["coin_class"] = coin_class
        historic_item["coin_reason"] = coin_reason
        breakdown[coin_class] = breakdown.get(coin_class, 0) + 1
    state["coin_filter_stats"] = breakdown
    print("Coin-only classification:", breakdown)

    # Supplement known coin announcements with independent pool-directory clues.
    # Never create coin alerts from pool data by itself.
    pool_catalog, updated_pool_catalog = refresh_mining_scan(fetch, state, NOW)
    if updated_pool_catalog:
        state["mining_scan"] = pool_catalog
    pool_matches = matches_for(seen,pool_catalog)
    for coin_key,info in pool_matches.items():
        seen[coin_key]["pool_evidence"] = info
    state["mining_scan_status"] = {
        "available":bool(pool_catalog.get("coins")),
        "updated_this_run":updated_pool_catalog,
        "matched_coin_records":len(pool_matches),
        "attribution":"mining-scan.com"
    }
    print("Mining Scan reference:", state["mining_scan_status"])

    # Read-only cross-check of pools already associated with a coin by full
    # name plus ticker. Do not use pool-wide block totals as coin data.
    pool_dir, pool_dir_changed = update_pool_directory(fetch,state,NOW)
    pool_checks = match_pools(seen,pool_dir,NOW)
    # Store ONLY the relevant pools: raw export can have thousands of records,
    # which would bloat state.json and exceed GitHub Content API limits.
    if pool_dir_changed:
        needed={(p["id"],p["domain"]) for info in pool_checks.values() for p in info["pools"]}
        state["pool_directory"]={**pool_dir,"pools":[p for p in pool_dir.get("pools",[])
            if (p["id"],p["domain"]) in needed][:30]}
    last_details = parse_pool_time(state.get("pool_stratum_checked_at"))
    details_due = not last_details or not timedelta(0)<=NOW-last_details<timedelta(hours=6)
    requests=0
    if details_due and pool_checks:
        for pool_info in list(pool_checks.values())[:2]:
            requests+=stratum_by_coin(fetch,pool_info,limit=2)
        state["pool_stratum_checked_at"]=NOW.isoformat(timespec="seconds")
    for pool_key,existing in seen.items():
        if pool_key not in pool_checks:
            existing.pop("pool_validation",None)
            continue
        old_info=existing.get("pool_validation") or {}
        new_info=pool_checks[pool_key]
        if not details_due:
            for row in new_info["pools"]:
                previous_row=next((old for old in old_info.get("pools",[])
                    if old.get("id")==row["id"] and old.get("domain")==row["domain"]),None)
                if previous_row and previous_row.get("stratum_endpoints"):
                    row["stratum"]=previous_row.get("stratum","не подтверждён")
                    row["stratum_endpoints"]=previous_row["stratum_endpoints"]
        existing["pool_validation"]=new_info
    state["pool_validation_status"]={
        "directory_available":bool(pool_dir.get("pools")),
        "coin_matches":len(pool_checks),
        "stratum_requests":requests,
        "source":"Mining Scan; pool-wide metrics are not coin-specific"
    }
    print("Coin pool validation:",state["pool_validation_status"])

    # Independent keyless network snapshot. Match by provider's actual coin id
    # and confirmed coin name, never by ambiguous ticker alone.
    backpow, backpow_updated = update_network_evidence(fetch,seen,state,NOW)
    if backpow_updated:
        state["backpow"] = backpow
    for evidence_key, record in (backpow.get("verified") or {}).items():
        if evidence_key in seen and seen[evidence_key].get("coin_class")=="coin_candidate":
            seen[evidence_key]["network_evidence"] = record
    state["network_evidence_status"] = {
        "available":bool(backpow.get("verified")),
        "checked":backpow.get("attempted",0),
        "matched":backpow.get("successful",0),
        "updated_this_run":backpow_updated,
        "source":"BackPoW"}
    print("Network evidence:",state["network_evidence_status"])

    # Free network stats from another independent catalog. API does not
    # provide per-coin freshness: never treat retrieval time as live telemetry.
    calculator_catalog,calculator_changed=update_coin_calculators(fetch,state,NOW)
    if calculator_changed:
        state["coin_calculators"]=calculator_catalog
    calculator_matches=match_coin_calculators(seen,calculator_catalog,NOW)
    for key,item in seen.items():
        if key in calculator_matches:
            item["aggregator_network"]=calculator_matches[key]
        else:
            item.pop("aggregator_network",None)
    state["coin_calculators_status"]={
        "catalog_available":bool(calculator_catalog.get("coins")),
        "matched":len(calculator_matches),
        "live_network_verified":False,
        "source":"CoinCalculators"
    }
    print("CoinCalculators reference:",state["coin_calculators_status"])

    # Public GitHub release history, strictly for already screened coin projects.
    # Releases provide development evidence, never proof of live mining.
    release_stats = check_releases(fetch,seen,NOW,limit=3)
    state["github_release_status"] = release_stats
    print("GitHub coin releases:",release_stats)

    model_clues=enrich_gpu_readmes(fetch,seen,NOW,limit=2)
    state["gpu_support_status"]=model_clues
    print("GPU support README clues:",model_clues)

    readiness_counts=evaluate_all(seen,NOW)
    state["mining_readiness_counts"]=readiness_counts
    print("GPU mining readiness:",readiness_counts)

    # Alert only after a previously seen coin gains fresh activity evidence.
    # Persist the baseline before sending; mark alerted only after delivery.
    new_evidence, evidence_history = evidence_transitions(
        seen,state.get("evidence_history"),NOW,max_messages=2)
    for key,marker_id,announcement in new_evidence:
        try:
            notify(announcement)
            confirm_evidence_alert(evidence_history,key,marker_id)
            print("New mining evidence notified:",key)
        except Exception as exc:
            print("Evidence alert delivery failed:",type(exc).__name__)
    state["evidence_history"]=evidence_history

    economic_counts=calculate_all(seen,NOW)
    state["mining_economics_counts"]=economic_counts
    print("5070 Ti economics:",economic_counts)

    previous_watch = state.get("tracked_projects") or {}
    # Check selected GitHub projects for repository activity before deciding if
    # they remain worth monitoring. No external subscriptions are created.
    tracked_git = [k for k in previous_watch if k.startswith(("gh:","gh-"))]
    refreshed = refresh_tracked(fetch, seen, tracked_git, NOW, limit=3)
    tracked, changes = reconcile(seen, previous_watch, NOW)
    state["tracked_projects"] = tracked
    state["tracking_stats"] = {**changes, "github_rechecked":refreshed}
    print("Project watchlist:", state["tracking_stats"])

    # Autonomous watchlist evaluation runs on every scan. Daily delivery is separate.
    shortlist = analyze(seen, NOW, limit=8)
    previous_report = ts(state.get("agent_last_digest"))
    state["agent"] = {
        "updated_at": stamp,
        "total_scanned": len(seen),
        "items": shortlist,
        "engine": "rule_based_v1",
        "disclaimer": "GPU evidence and project claims only; no verified network or market data",
    }
    # Daily analytical notifications are handled by daily-ai.yml, not this frequent
    # discovery scan. Keep fresh rule-based evidence in state for that job.
    print("Research agent: analyzed", len(seen), "records; shortlist:", len(shortlist),
          "daily delivery delegated to Daily OpenAI PoW Analyst")

    state["last_scan"] = stamp
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Sources available: {ok}, items: {len(results)}, new items: {len(unseen)}")

if __name__ == "__main__":
    main()
