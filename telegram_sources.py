"""Parse recent, publicly previewable Telegram channel posts (no user account tokens)."""
import html
import re
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser

CHANNELS = ("miningrelease", "mining_note", "kryptex_channel_en")
POST = re.compile(r'data-post=["\']([a-zA-Z0-9_]+)/(\d+)["\']')
TIME = re.compile(r'<time\b[^>]*datetime=["\']([^"\']+)')

class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.depth = 0
        self.capture = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and "tgme_widget_message_text" in attrs.get("class", ""):
            self.capture = True
            self.depth = 1
        elif self.capture and tag == "div":
            self.depth += 1
        elif self.capture and tag == "br":
            self.parts.append("\n")
    def handle_endtag(self, tag):
        if self.capture and tag == "div":
            self.depth -= 1
            if self.depth == 0:
                self.capture = False
    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)

def parse_public_channel(body, channel, now=None):
    now = now or datetime.now(timezone.utc)
    matches = list(POST.finditer(body))
    found = {}
    for i, match in enumerate(matches):
        if match.group(1).lower() != channel.lower():
            continue
        fragment = body[match.end(): matches[i+1].start() if i+1 < len(matches) else len(body)]
        # Only messages with a verifiable timestamp can be sent as recent.
        stamp = TIME.search(fragment)
        if not stamp:
            continue
        try:
            published = datetime.fromisoformat(html.unescape(stamp.group(1)).replace("Z", "+00:00"))
            if not published.tzinfo:
                published = published.replace(tzinfo=timezone.utc)
            published = published.astimezone(timezone.utc)
        except ValueError:
            continue
        if not timedelta(0) <= now - published <= timedelta(hours=72):
            continue
        parser = Text()
        parser.feed(fragment)
        message = " ".join(html.unescape("".join(parser.parts)).split())
        if len(message) < 20:
            continue
        identifier = match.group(2)
        found[f"tg:{channel}:{identifier}"] = {
            "title": message[:160],
            "body": message[:1400],
            "url": f"https://t.me/{channel}/{identifier}",
            "source": f"Telegram / @{channel} — сторонний анонс",
            "date": published.isoformat(),
            "kind": "announcement",
        }
    return found
