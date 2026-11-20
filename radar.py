#!/usr/bin/env python3
"""SOLO Radar: scheduled Bitcointalk scouting; standard library only."""
import os, re, json, html, urllib.request
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
STATE_FILE = Path("data/state.json")
BOARDS = (
    "https://bitcointalk.org/index.php?board=159.0",
    "https://bitcointalk.org/index.php?board=159.40",
)

class Topics(HTMLParser):
    def __init__(self):
        super().__init__()
        self.topic = None
        self.parts = []
        self.items = {}

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        link = dict(attrs).get("href", "")
        m = re.search(r"[?&]topic=(\d+)(?:\.\d+)?", link)
        if m:
            self.topic = m.group(1)
            self.parts = []

    def handle_data(self, text):
        if self.topic is not None:
            self.parts.append(text)

    def handle_endtag(self, tag):
        if tag == "a" and self.topic is not None:
            title = html.unescape(" ".join("".join(self.parts).split()))
            if 12 <= len(title) <= 180:
                self.items[self.topic] = title
            self.topic = None
            self.parts = []

def request(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST" if data is not None else "GET",
        headers={"User-Agent": "Mozilla/5.0 SOLO-Radar/1.0", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=25) as result:
        return result.read().decode("utf-8", errors="replace")

def send(text):
    result = json.loads(request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        {"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}
    ))
    if not result.get("ok"):
        raise RuntimeError("Telegram refused the message")

def score(title):
    value = title.lower()
    points = 0
    for pattern, weight in (
        (r"\b(pow|proof.of.work|mineable)\b", 3),
        (r"\b(gpu|nvidia|cuda|ethash|kawpow|progpow|blake3)\b", 4),
        (r"\b(mainnet|launch|genesis)\b", 3),
        (r"\b(solo)\b", 2),
        (r"\b(fair.launch|no.premine)\b", 2),
    ):
        if re.search(pattern, value):
            points += weight
    if re.search(r"\b(ico|presale|airdrop|staking|token.sale)\b", value):
        points -= 9
    if re.search(r"\b(cpu.only|randomx|yespower)\b", value) and not re.search(r"\bgpu\b", value):
        points -= 5
    return points

def main():
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError(
            "Telegram is not configured: check both GitHub Actions secrets "
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."
        )

    state = {"topics": {}, "initialized": False}
    if STATE_FILE.exists():
        try:
            saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                state.update(saved)
        except (ValueError, OSError):
            pass

    # Connection diagnostic runs independently of public-source availability.
    if not state.get("initialized"):
        send("✅ SOLO Radar подключён к Telegram. Поиск работает по расписанию; сигналы обозначаются как непроверенные.")
        state["initialized"] = True

    found = {}
    good = 0
    for page in BOARDS:
        try:
            p = Topics()
            p.feed(request(page))
            found.update({"btt-" + key: title for key, title in p.items.items()})
            good += 1
        except Exception as exc:
            print("Unavailable Bitcointalk source:", page, type(exc).__name__)

    # Fallback: discover newly updated PoW code repositories.
    # GitHub commits are NOT evidence of a mainnet launch.
    try:
        from urllib.parse import quote
        query = quote('"proof of work" cryptocurrency pushed:>2026-11-01', safe='')
        data = json.loads(request("https://api.github.com/search/repositories?q=" + query + "&sort=updated&order=desc&per_page=30"))
        for item in data.get("items", []):
            name = item.get("full_name", "")
            desc = (item.get("description") or "").replace("\\n", " ")
            if name:
                found["gh-" + str(item["id"])] = "[GitHub] " + name + " — " + desc[:110]
        good += 1
        print("GitHub repository fallback: available")
    except Exception as exc:
        print("GitHub search fallback unavailable:", type(exc).__name__)

    previous = state.get("topics", {})
    new = [(key, title) for key, title in found.items() if key not in previous]
    if good:
        if not state.get("baseline_done"):
            state["baseline_done"] = True
            print("Baseline created; old projects will not be sent as new alerts.")
        else:
            ranking = sorted(((score(title), key, title) for key, title in new), reverse=True)
            for points, key, title in [item for item in ranking if item[0] >= 7][:5]:
                if key.startswith("btt-"):
                    url = f"https://bitcointalk.org/index.php?topic={key[4:]}.0"
                else:
                    url = "https://github.com/" + title.split(" — ", 1)[0].replace("[GitHub] ", "")
                send(
                    "🔎 НОВЫЙ PoW-КАНДИДАТ — НЕ ПРОВЕРЕН\\n\\n"
                    + title + "\\n"
                    + "Оценка заголовка: " + str(points) + " (не прогноз прибыли).\\n\\n"
                    + "⚠️ Не подтверждены время mainnet, GPU/SOLO, premine, сложность и возможность продажи. "
                    + "Наличие репозитория не означает запуск монеты.\\n"
                    + url
                )
    else:
        print("All public sources unavailable. Telegram diagnostic sent; next scan will retry.")

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for key, title in found.items():
        previous[key] = {"title": title, "seen": previous.get(key, {}).get("seen", stamp)}
    if len(previous) > 5000:
        previous = dict(sorted(previous.items(), key=lambda item: item[1]["seen"], reverse=True)[:5000])

    state["topics"] = previous
    state["last_scan"] = stamp
    STATE_FILE.parent.mkdir(exist_ok=True, parents=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Source pages: {good}; topics: {len(found)}; new: {len(new)}")

if __name__ == "__main__":
    main()
