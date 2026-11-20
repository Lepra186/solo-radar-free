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

def digest(results, now):
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
    lines = ["📡 SOLO RADAR — ОБЗОР GPU PoW",
             "Поиск NVIDIA и AMD, без привязки к модели карты.",
             f"Записей в текущем скане: {len(results)}",
             f"Предварительных GPU PoW-кандидатов: {len(ranked)}",
             ""]
    if recent:
        for i, (_, category, item) in enumerate(recent, 1):
            lines.append(f"{i}. {'🚀 Ранний анонс' if category == 'EARLY' else '🪙 Пул / накопление' if category == 'HOLD' else '🔎 Кандидат'}")
            lines.append(str(item.get("title", "Без названия"))[:125])
            lines.append(str(item.get("url") or "Нет ссылки")[:300])
            lines.append("")
    else:
        lines += ["Подходящих кандидатов в доступных источниках пока нет.",
                  "Это не означает, что новые монеты не запускаются: часть площадок может быть недоступна.", ""]
    lines += ["⚠️ Накопление не гарантирует продажу с прибылью; сложность, premine и ликвидность не подтверждены.",
              "Команды: /start, /latest, /status, /help.",
              "Ответ приходит после ближайшей проверки GitHub Actions."]
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
                reply = digest(results, now)
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
