"""Telegram command polling for GitHub Actions scheduled runner.

No long-running process: /start is answered on next workflow execution.
Only the owner chat (TELEGRAM_CHAT_ID) is authorized.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone
from gpu_assessment import assess, signal

def get_updates(token, offset):
    body = json.dumps({"offset": offset, "timeout": 0, "limit": 100,
                       "allowed_updates": ["message"]}).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/getUpdates",
        method="POST", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise RuntimeError("Telegram getUpdates was not successful")
    return result.get("result", [])

def command_name(message):
    if not isinstance(message, dict):
        return None
    text = (message.get("text") or "").strip().split(" ", 1)[0].lower()
    text = text.split("@", 1)[0]
    return text if text in ("/start", "/latest", "/status", "/help") else None

def _history_candidates(state, limit=5):
    """Titles seen in past scans. Not fresh, and not current network evidence."""
    if not isinstance(state, dict):
        return []
    found = []
    for key, item in (state.get("topics") or {}).items():
        title = str(item.get("title") or "")
        if not title or len(title) < 12:
            continue
        a = assess(title)
        if a["excluded"] or not a["gpu"] or not a["pow"]:
            continue
        if key.startswith("btt:"):
            url = "https://bitcointalk.org/index.php?topic=" + key[4:] + ".0"
        elif key.startswith("gh:"):
            url = ""  # Historical GitHub numeric ID cannot be turned into a valid repo URL.
        else:
            url = ""
        found.append((a["score"], str(item.get("seen") or ""), title, url))
    found.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return found[:limit]

def digest(results, now, state=None):
    ranked = []
    for item in results.values():
        if not isinstance(item, dict):
            continue
        body = item.get("body") or item.get("title") or ""
        category = signal(body, now)
        if category:
            ranked.append((assess(body, now)["score"], category, item))
    ranked.sort(key=lambda entry: entry[0], reverse=True)
    recent = ranked[:5]
    lines = ["📡 SOLO RADAR — GPU PoW",
             "NVIDIA и AMD; SOLO и обычный пул-майнинг.",
             f"Записей в текущем скане: {len(results)}",
             f"Кандидатов текущего скана: {len(ranked)}",
             ""]
    if recent:
        for i, (_, category, item) in enumerate(recent, 1):
            label = "🚀 Ранний анонс" if category == "EARLY" else "🪙 Пул / накопление" if category == "HOLD" else "🔎 Кандидат"
            lines += [f"{i}. {label}",
                      str(item.get("title", "Без названия"))[:125],
                      str(item.get("url") or "Нет ссылки")[:300], ""]
    else:
        lines.append("Новых подтверждённых кандидатов в доступных источниках нет.")
        historical = _history_candidates(state)
        if historical:
            lines += ["", "📂 На наблюдении — записи из предыдущих сканирований:",
                      "Не являются свежими анонсами и не означают работающий майнинг."]
            for index, (points, seen_at, title, url) in enumerate(historical, 1):
                lines.append(f"{index}. {title[:135]}")
                if url:
                    lines.append(url)
        else:
            lines.append("Исторических GPU PoW-кандидатов тоже не найдено.")
    lines += ["", "⚠️ Время mainnet, premine, ликвидность и поддержка GPU требуют проверки.",
              "Команды: /start, /latest, /status, /help.",
              "Ответ — после ближайшего GitHub Actions; возможны задержки."]
    return "\n".join(lines)[:3900]

def process_commands(token, owner_chat, state, results, now, send):
    """Keep offset even for unrelated or unauthorized commands. Return count."""
    old_offset = int(state.get("telegram_update_offset", 0))
    updates = get_updates(token, old_offset)
    count = 0
    for update in updates:
        update_id = update.get("update_id")
        if not isinstance(update_id, int):
            continue
        # Don't process a message twice even if the next commit is rebased.
        if update_id < old_offset:
            continue
        msg = update.get("message") or {}
        chat_id = str((msg.get("chat") or {}).get("id", ""))
        command = command_name(msg)
        if chat_id == str(owner_chat) and command:
            if command in ("/start", "/latest"):
                reply = digest(results, now, state)
            elif command == "/status":
                reply = ("📡 SOLO Radar активен\n"
                         f"Последняя проверка: {now.strftime('%Y-%m-%d %H:%M UTC')}\n"
                         f"Записей в скане: {len(results)}\n"
                         "Источники с ограниченным доступом не гарантируют полный охват.\n"
                         "Интервал запуска по расписанию: около 10 минут.")
            else:
                reply = ("Команды:\n"
                         "/start — текущий обзор монет\n"
                         "/latest — повторить обзор\n"
                         "/status — статус сканирования\n"
                         "/help — эта справка\n"
                         "Ответ не мгновенный: GitHub проверяет сообщения по расписанию.")
            send(reply)
            count += 1
        old_offset = update_id + 1
        state["telegram_update_offset"] = old_offset
    print(f"Telegram commands processed: {count}, updates checked: {len(updates)}")
    return count
