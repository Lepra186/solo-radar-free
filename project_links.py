"""Link extraction from official/third-party announcement text and Telegram inline buttons.

Only link to the exact URL provided by the source; no guessed Discord invites.
Links are not independently audited and should not be treated as endorsement.
"""
import html
import re
from html.parser import HTMLParser
from urllib.parse import urlparse, urlunparse

KINDS = ("discord", "pool", "wallet", "miner", "explorer", "website")
LABELS = {
    "discord": "👥 Discord",
    "pool": "⛏️ Пул",
    "wallet": "💰 Кошелёк",
    "miner": "🖥️ Майнер",
    "explorer": "🔎 Обозреватель блоков",
    "website": "🌐 Сайт проекта",
}
LABEL_PATTERNS = (
    ("discord", re.compile(r"\b(discord|дискорд)\b", re.I)),
    ("pool", re.compile(r"\b(pool|пул|stratum)\b", re.I)),
    ("wallet", re.compile(r"\b(wallet|кошел[её]к)\b", re.I)),
    ("miner", re.compile(r"\b(miner|майнер|mining software)\b", re.I)),
    ("explorer", re.compile(r"\b(explorer|block explorer|обозреватель)\b", re.I)),
    ("website", re.compile(r"\b(website|official site|веб.?сайт|сайт проекта)\b", re.I)),
)
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)

def clean_url(raw):
    if not raw or not isinstance(raw, str):
        return None
    raw = html.unescape(raw).strip().rstrip(".,;!>")
    if len(raw) > 500 or any(ord(char) < 32 for char in raw):
        return None
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    # Never reproduce URLs with tracking query strings, fragments or credentials.
    return urlunparse(("https", parsed.netloc, parsed.path or "", "", "", ""))

def category_for(label, url):
    label = " ".join(label.split())
    host = (urlparse(url).hostname or "").lower()
    if host in ("discord.gg", "discord.com", "www.discord.com") and (
        host == "discord.gg" or urlparse(url).path.startswith("/invite/")
    ):
        return "discord"
    for category, pattern in LABEL_PATTERNS:
        if pattern.search(label):
            return category
    # Never guess category from a generic host, especially GitHub links.
    return None

class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.found = []
    def handle_starttag(self, tag, attrs):
        if tag == "a" and self.current is None:
            url = dict(attrs).get("href")
            self.current = [url, []]
    def handle_data(self, data):
        if self.current is not None:
            self.current[1].append(data)
    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            url = clean_url(self.current[0])
            label = html.unescape("".join(self.current[1]).strip())
            if url:
                category = category_for(label, url)
                if category:
                    self.found.append((category, url))
            self.current = None

def from_telegram_fragment(fragment):
    parser = AnchorParser()
    parser.feed(fragment)
    links = {}
    for kind, url in parser.found:
        if kind not in links:
            links[kind] = url
    return links

def from_text(text):
    links = {}
    for line in text.splitlines():
        url_matches = URL_RE.findall(line)
        for raw in url_matches:
            url = clean_url(raw)
            if not url:
                continue
            before = line[:line.find(raw)]
            kind = category_for(before[-70:], url)
            if kind and kind not in links:
                links[kind] = url
    return links

def format_links(links):
    if not isinstance(links, dict):
        return ""
    lines = []
    for kind in KINDS:
        url = clean_url(links.get(kind))
        if url:
            lines.append(f"{LABELS[kind]}: {url}")
    return "\n".join(lines)
