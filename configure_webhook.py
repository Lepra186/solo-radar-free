#!/usr/bin/env python3
"""Register an HTTPS Telegram webhook without printing the bot token."""
import json
import os
import urllib.request
from urllib.parse import urlparse

url = os.environ.get("TELEGRAM_WEBHOOK_URL", "").strip()
token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()

p = urlparse(url)
if p.scheme != "https" or not p.hostname or p.path != "/webhook" or p.query or p.fragment:
    raise RuntimeError("Set TELEGRAM_WEBHOOK_URL to HTTPS Cloudflare Worker /webhook endpoint")
if not token or not secret:
    raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET")
if not (1 <= len(secret) <= 256) or not all(x.isascii() and (x.isalnum() or x in "_-") for x in secret):
    raise RuntimeError("Webhook secret must be 1–256 ASCII letters/digits/_/-")
payload = json.dumps({
    "url": url,
    "secret_token": secret,
    "allowed_updates": ["message", "callback_query"],
    "drop_pending_updates": False,
}).encode()
req = urllib.request.Request(
    "https://api.telegram.org/bot" + token + "/setWebhook",
    data=payload, headers={"Content-Type": "application/json"}, method="POST"
)
with urllib.request.urlopen(req, timeout=20) as response:
    result = json.load(response)
if not result.get("ok"):
    raise RuntimeError("Telegram setWebhook rejected the settings")
print("Telegram webhook configured successfully (token and secret hidden)")
