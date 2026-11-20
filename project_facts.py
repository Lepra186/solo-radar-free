"""Conservative per-project facts extracted from sourced metadata and announcement text.

Never confuse repository creation, publication, discovery, and mainnet dates.
"""
import re
from datetime import datetime, timezone
from gpu_assessment import extract_utc_launch

ALGORITHMS = (
    ("KawPow", r"\bkawpow\b"),
    ("Etchash", r"\betchash\b"),
    ("Ethash", r"\bethash\b"),
    ("ProgPoW", r"\bprogpow\b"),
    ("FishHash", r"\bfishhash\b"),
    ("Autolykos", r"\bautolykos\b"),
    ("Equihash", r"\bequihash\b"),
    ("Octopus", r"\boctopus\b"),
    ("Verthash", r"\bverthash\b"),
    ("RandomX", r"\brandomx\b"),
    ("SHA-256", r"\bsha[\s-]?256d?\b"),
)
GPU = re.compile(r"\b(gpu|nvidia|geforce|cuda|radeon|amd|opencl)\b", re.I)
SOLO = re.compile(r"\bsolo(?:[- ]pool|[- ]mining)?\b", re.I)
POOL = re.compile(r"\b(pool|stratum|pplns|pps\+?)\b", re.I)
TICKER = re.compile(r"\b(?:ticker|symbol)\s*[:：]\s*\$?([A-Za-z0-9]{2,12})\b", re.I)
COIN = re.compile(r"\bcoin\s*name\s*[:：]\s*([^\r\n|]{2,60})", re.I)

def valid_iso(raw):
    if not raw or not isinstance(raw, str):
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if not value.tzinfo:
            return None
        return value.astimezone(timezone.utc).isoformat(timespec="minutes")
    except ValueError:
        return None

def get_facts(body, *, publication=None, repo_created=None, repo_updated=None, kind=""):
    body = re.sub(r"<[^>]{0,300}>", " ", body or "")[:2400]
    algorithms = [name for name, regex in ALGORITHMS if re.search(regex, body, re.I)]
    tick = TICKER.search(body)
    coin = COIN.search(body)
    launch = extract_utc_launch(body)
    return {
        "algorithm": ", ".join(algorithms[:2]) if algorithms else None,
        "ticker": tick.group(1).upper() if tick else None,
        "coin_name": coin.group(1).strip()[:50] if coin else None,
        "gpu_mentioned": bool(GPU.search(body)) or any(x in algorithms for x in (
            "KawPow","Etchash","Ethash","ProgPoW","FishHash","Autolykos","Equihash","Octopus","Verthash")),
        "solo_mentioned": bool(SOLO.search(body)),
        "pool_mentioned": bool(POOL.search(body)),
        "launch_claim_utc": launch.isoformat(timespec="minutes") if launch else None,
        "publication_utc": valid_iso(publication),
        "repo_created_utc": valid_iso(repo_created) if kind=="repository" else None,
        "repo_updated_utc": valid_iso(repo_updated) if kind=="repository" else None,
    }
