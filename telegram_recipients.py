"""Authorized Telegram recipients. Keep numeric chat IDs in GitHub Secrets, never source."""
import re

def parse_recipients(primary, additional=""):
    ids = []
    for raw in [primary] + re.split(r"[,;\s]+", additional or ""):
        value = str(raw).strip()
        if not value:
            continue
        if not re.fullmatch(r"-?\d{1,20}", value):
            raise ValueError("Chat IDs must be numeric and comma-separated")
        if value not in ids:
            ids.append(value)
    if not ids:
        raise ValueError("No Telegram chat IDs configured")
    return ids
