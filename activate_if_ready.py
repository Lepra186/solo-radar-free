#!/usr/bin/env python3
"""Safely activate Telegram webhook only when required secrets are configured.

Never log token, chat IDs or webhook authentication secret.
"""
import os
import sys
import json
import urllib.request
import urllib.error

url = "https://solo-radar-free.leprikon18.workers.dev/webhook"
required = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_WEBHOOK_SECRET")
missing = [key for key in required if not os.getenv(key)]
if missing:
    print("NOT READY: Missing GitHub Actions secrets:", ", ".join(missing))
    print("Cloudflare must also have TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_WEBHOOK_SECRET.")
    sys.exit(0)

request = urllib.request.Request(
    url, data=b"{}", method="POST", headers={"Content-Type": "application/json"}
)
try:
    with urllib.request.urlopen(request, timeout=20) as response:
        status = response.status
except urllib.error.HTTPError as exc:
    status = exc.code
except Exception as exc:
    print("NOT READY: Worker unreachable:", type(exc).__name__)
    sys.exit(0)

if status != 403:
    print(f"NOT READY: Worker /webhook replied HTTP {status}; expected 403 to an unauthenticated probe.")
    print("Add all 3 Worker secrets in Cloudflare, then trigger this workflow again.")
    sys.exit(0)

print("Worker authenticated webhook endpoint is reachable (403 as expected).")
try:
    req = urllib.request.Request(
        "https://api.telegram.org/bot" + os.environ["TELEGRAM_BOT_TOKEN"] + "/getWebhookInfo",
        headers={"User-Agent": "SOLO-Radar-Setup"})
    with urllib.request.urlopen(req, timeout=20) as response:
        info = json.load(response).get("result", {})
        current = info.get("url", "")
        current_updates = info.get("allowed_updates") or []
    if current == url and "callback_query" in current_updates:
        print("Webhook already active with callback_query updates")
        sys.exit(0)
except Exception as exc:
    print("NOT READY: Cannot inspect current Telegram webhook:", type(exc).__name__)
    sys.exit(0)
os.environ["TELEGRAM_WEBHOOK_URL"] = url
import configure_webhook
