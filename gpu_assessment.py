"""Conservative GPU PoW launch assessment. No invented hashrate or availability."""
import re
from datetime import datetime, timezone, timedelta

GPU = re.compile(r"\b(gpu|graphics cards?|nvidia|geforce|amd|radeon|opencl|cuda|"
                 r"ethash|etchash|kawpow|progpow|firopow|autolykos|"
                 r"fishhash|octopus|zelhash|equihash|cuckoo(?:cycle|29|32)?|"
                 r"verthash|ubqhash|heavyhash)\b", re.I)
POW = re.compile(r"\b(pow|proof[\s-]of[\s-]work|mineable|mining|minable|"
                 r"coin name|gpu[- ]?mining|gpu miner)\b", re.I)
START = re.compile(r"\b(mainnet|genesis|launch(?:ing|ed)?|network start|"
                   r"block\s*0|fair launch|starts? in)\b", re.I)
SOLO = re.compile(r"\bsolo(?:[- ]mining|[- ]pool)?\b", re.I)
POOL = re.compile(r"\b(pool|pool mining|pplns|pps\+?|stratum|miner|flight sheet|hiveos)\b", re.I)
NEGATIVE = re.compile(r"\b(ico|presale|airdrop|staking|nft|testnet only)\b", re.I)
CPU_ONLY = re.compile(r"\b(cpu.only|cpu[- ]only|randomx|yespower)\b", re.I)
ASIC_ONLY = re.compile(r"\b(asic[- ]only|sha[- ]?256d?\s+asic)\b", re.I)
GPU_DENIED = re.compile(r'\b(?:no|not|non[- ]|without|unsupported|cannot|does not support)\s+gpu(?:[- ]?(?:mining|mineable|support))?\b|\bgpu(?:[- ]?(?:mining|mineable|support))?\s+(?:is\s+)?(?:not supported|disabled|unavailable|unsupported)\b',re.I)
MAINNET_PENDING = re.compile(r'\b(?:testnet[- ]only|only\s+(?:a\s+)?testnet|mainnet\s+(?:not\s+launched|pending|unreleased)|no\s+mainnet\s+yet)\b',re.I)
NO_PREMINE = re.compile(r"\b(no[\s-]?premine|zero[\s-]?premine|0%\s*premine)\b", re.I)

# Accept only explicitly marked UTC timestamps, not bare dates or inferred time zones.
UTC_LAUNCH = re.compile(
    r"(?:mainnet|genesis|launch|start)[^\n]{0,65}?"
    r"(20\d\d[-/.]\d\d[-/.]\d\d)[ T]+(\d{1,2}:\d\d)"
    r"\s*(UTC|GMT|Z)\b", re.I)

def extract_utc_launch(body):
    m = UTC_LAUNCH.search(body)
    if not m:
        return None
    try:
        d = m.group(1).replace("/", "-").replace(".", "-")
        dt = datetime.strptime(d + " " + m.group(2), "%Y-%m-%d %H:%M")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None

def assess(body, now=None):
    now = now or datetime.now(timezone.utc)
    gpu = bool(GPU.search(body)) and not bool(GPU_DENIED.search(body))
    pow_ = bool(POW.search(body))
    solo = bool(SOLO.search(body))
    launch = bool(START.search(body))
    pool = bool(POOL.search(body))
    exclude = bool(GPU_DENIED.search(body) or MAINNET_PENDING.search(body) or NEGATIVE.search(body)) or (bool(CPU_ONLY.search(body)) and not gpu) or (bool(ASIC_ONLY.search(body)) and not gpu)
    time = extract_utc_launch(body)
    score = (5 if gpu else 0) + (3 if pow_ else 0) + (2 if launch else 0) + (2 if solo else 0) + (2 if pool else 0) + (1 if NO_PREMINE.search(body) else 0)
    if time and not exclude:
        delta = time - now
        if timedelta(hours=-24) <= delta <= timedelta(hours=72):
            score += 4
    if exclude:
        score -= 12
    return {"gpu": gpu, "pow": pow_, "solo": solo, "pool": pool, "launch": launch,
            "launch_utc": time, "score": score, "excluded": exclude}

def signal(body, now=None):
    v = assess(body, now)
    if v["excluded"] or not (v["gpu"] and v["pow"]):
        return None
    if v["launch_utc"]:
        offset = v["launch_utc"] - (now or datetime.now(timezone.utc))
        if timedelta(hours=-24) <= offset <= timedelta(hours=72):
            return "EARLY"
    if v["score"] >= 10 and v["launch"] and v["pool"]:
        return "HOLD"
    if v["score"] >= 10 and (v["launch"] or v["solo"]):
        return "WATCH"
    return None

def description(body, now=None):
    v = assess(body, now)
    launch = v["launch_utc"].strftime("%Y-%m-%d %H:%M UTC") if v["launch_utc"] else "нет подтверждённого времени UTC"
    return (
        "GPU: " + ("есть признаки поддержки видеокарт (NVIDIA/AMD требуют отдельной проверки)" if v["gpu"] else "не подтверждено") + "\n"
        "SOLO: " + ("упомянуто, доступность не подтверждена" if v["solo"] else "не обязательно / не подтверждено") + "\n"
        "Пул: " + ("упоминается, выплаты не проверены" if v["pool"] else "не подтверждён") + "\n"
        "Mainnet: " + launch + " (из текста анонса, не проверено по блокчейну)\n"
        "Premine: " + ("автор заявляет отсутствие; не проверено" if NO_PREMINE.search(body) else "не проверен") + "\n"
        "Сложность/шанс блока: нет проверенных данных\n"
        "Продажа/ликвидность: не проверены; накопление может оказаться неликвидным\n"
        "Действие: проверить официальный анонс, кошелёк, майнер и сеть перед майнингом"
    )
