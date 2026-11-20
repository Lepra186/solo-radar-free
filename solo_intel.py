"""Evidence-aware SOLO intelligence. Text extraction is *not* network verification."""
import math
import re
from urllib.parse import urlparse
from gpu_assessment import assess

URL = re.compile(r'https?://[^\s<>"\')\]]+', re.I)
BLOCK = re.compile(r'(?:block reward|reward per block|block subsidy)\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*([A-Z]{2,12})?', re.I)
INTERVAL = re.compile(r'(?:block time|block interval|target block time)\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*(seconds?|sec|s|minutes?|mins?|m)\b', re.I)
PREMINE_RISK = re.compile(r'\b(premine|pre-mine|dev allocation|team allocation)\b', re.I)
AUDIT = re.compile(r'\b(open source|source code|github\.com)\b', re.I)
SOURCE_CATEGORIES = (
    ("Пул", ("pool", "miningpool", "miners", "solo")),
    ("Обозреватель", ("explorer", "scan.", "blocks")),
    ("Биржа (заявление)", ("exchange", "trade", "market")),
    ("Исходники", ("github.com", "gitlab.com", "codeberg.org")),
)

def extract_links(text, limit=8):
    urls = []
    for found in URL.findall(text):
        url = found.rstrip(".,;!")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            continue
        if parsed.username or parsed.password or len(url) > 350:
            continue
        if url not in urls:
            urls.append(url)
    return urls[:limit]

def mine_probability(miner_hashrate, network_hashrate, hours, block_seconds):
    """Poisson P(at least one block); equal *units* and independent valid shares."""
    nums = (miner_hashrate, network_hashrate, hours, block_seconds)
    if any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in nums):
        raise ValueError("finite numeric values required")
    if miner_hashrate < 0 or network_hashrate <= 0 or hours < 0 or block_seconds <= 0:
        raise ValueError("invalid mining parameters")
    if miner_hashrate > network_hashrate:
        raise ValueError("miner hashrate cannot exceed network hashrate")
    mean = (miner_hashrate / network_hashrate) * (hours * 3600 / block_seconds)
    return -math.expm1(-mean)

def extract_declared_facts(body):
    reward = BLOCK.search(body)
    interval = INTERVAL.search(body)
    raw_interval = float(interval.group(1)) if interval else None
    if interval and interval.group(2).lower().startswith(("m",)):
        raw_interval *= 60
    return {
        "reward": (float(reward.group(1)), reward.group(2)) if reward else None,
        "block_seconds": raw_interval,
        "premine_mentioned": bool(PREMINE_RISK.search(body)),
        "source_mentioned": bool(AUDIT.search(body)),
    }

def summary(body):
    facts = extract_declared_facts(body)
    links = extract_links(body)
    output = ["🔬 ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА (только по тексту)"]
    if facts["reward"]:
        value, symbol = facts["reward"]
        output.append(f"Награда: заявлено {value:g} {symbol or 'монет'} за блок; не проверено")
    else:
        output.append("Награда за блок: не найдена")
    if facts["block_seconds"]:
        output.append(f"Время блока: заявлено {facts['block_seconds']:g} сек.; не проверено")
    else:
        output.append("Время блока: не найдено")
    output.append("Premine: упоминается, необходим разбор распределения" if facts["premine_mentioned"] else
                  "Premine: подтверждения отсутствия нет")
    output.append("SOLO: необходима проверка пула/ноды и текущих блоков")
    output.append("Продажа: необходима проверка реального стакана и вывода")
    output.append("Шанс SOLO: не рассчитывается без двух хешрейтов в одинаковых единицах и времени блока")
    for label, markers in SOURCE_CATEGORIES:
        matches = [url for url in links if any(m in urlparse(url).netloc.lower() for m in markers)]
        if matches:
            output.append(f"{label} (ссылка из объявления, НЕ проверена): {matches[0]}")
    return "\n".join(output)

def source_quality(item):
    # Published news and repositories should not be asserted as first-party.
    if item.get("kind") == "repository":
        return "Репозиторий — запуск mainnet не доказан"
    if item.get("kind") == "news":
        return "Публикация — это не подтверждение блоков сети"
    return "Анонс — заявления требуют независимой проверки"
