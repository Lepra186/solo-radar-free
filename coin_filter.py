"""Conservative coin-only classifier. No miner applications, services or ASIC/CPU coins.

A candidate is a *claim* of an independently mineable cryptocurrency, not proof
of a functioning network or possible profit. Unknown remains unverified.
"""
import re

GPU_ALGO=re.compile(r'\b(kawpow|ethash|etchash|progpow|fishhash|autolykos|equihash|octopus|verthash|firopow|zelhash|cuckoocycle|ubqhash)\b',re.I)
GPU_WORD=re.compile(r'\b(gpu[- ]?mineable|gpu[- ]?mining|gpu[- ]?pow|gpu[- ]?friendly|gpu[- ]?coin|gpu[- ]?mined|gpu[- ]?based|gpu[- ]?and[- ]?cpu|graphics cards?)\b',re.I)
POW=re.compile(r'\b(proof[- ]of[- ]work|pow|mineable|block reward|gpu mining)\b',re.I)
COIN=re.compile(r'\b(coin|cryptocurrency|blockchain|mainnet|genesis block|ticker|symbol|native currency|network launch|network start|chain)\b',re.I)
ANN=re.compile(r'\b(\[ann\]|\[pre-ann\]|coin\s*name\s*:|ticker\s*:|mainnet|genesis)\b',re.I)
SERVICE=re.compile(r'\b(auto[- ]?profit|profit[- ]?switch(?:er|ing)?|dashboard|mining calculator|hashrate calculator|rental|cloud mining|pool service|exchange ecosystem|wallet app|management software|firmware|driver|benchmark|monitoring bot|telegram bot|stratum proxy|api service)\b',re.I)
SOFTWARE=re.compile(r'\b(mining software|gpu miner|cpu miner|miner (?:for|support(?:s|ing)?|release|v\d|version)|miner\s+v?\d+(?:\.\d+)*|mining tool|miner software|new miner|software release|one binary|no dev fee|dev fee|profit switching|auto switching)\b',re.I)
NONPOW=re.compile(r'\b(proof[- ]of[- ]stake|pos[- ]only|bep[- ]?20|erc[- ]?20|solana token|pump\.fun|nft|airdrop|presale|ico|testnet only)\b',re.I)
CPUASIC=re.compile(r'\b(cpu[- ]only|randomx|yespower|asic[- ]only|sha[- ]?256d?|scrypt)\b',re.I)
REPO_SOFTWARE=re.compile(r'(?:^|[/\-_])(miner|miners|mining[-_]?software|switcher|profit[-_]?switch|pool[-_]?proxy|dashboard|rig[-_]?manager)(?:$|[/\-_])',re.I)

def classify(key,item):
    """Return category: coin_candidate, non_coin, unsupported_mining, or insufficient."""
    title=str(item.get('title') or '')
    body=str(item.get('body') or title)
    combined=(title+' '+body)[:2500]
    kind=str(item.get('kind') or '')
    facts=item.get('facts') or {}
    is_repo=key.startswith(('gh:','gh-')) or kind=='repository'
    name=str((item.get('github') or {}).get('name') or title).split(' — ')[0]
    # News pages are discovery signals, never a coin by themselves.
    if kind=='news' or key.startswith(('pool:','rss:')):
        return 'non_coin','news_or_pool_service'
    if NONPOW.search(combined):
        return 'unsupported_mining','non_pow_or_token'
    if SERVICE.search(title) or SOFTWARE.search(title):
        # Explicit [ANN] coin announcement takes precedence over a feature
        # phrase like "Free Solo Miner" *only* if standalone coin is clear.
        if not (ANN.search(title) and COIN.search(title) and GPU_ALGO.search(combined)):
            return 'non_coin','miner_software_or_service'
    if is_repo and REPO_SOFTWARE.search(name):
        return 'non_coin','software_repository'
    if is_repo and (SERVICE.search(body) or SOFTWARE.search(body)) and not ANN.search(body):
        # A repository mentioning a coin AND bundling a miner can still be a
        # full-node project when name/description clearly references chain.
        if not re.search(r'\b(full node|blockchain|cryptocurrency|mainnet)\b',body,re.I):
            return 'non_coin','software_repository'
    # ASIC-dominated and CPU-only networks aren't GPU PoW accumulation leads.
    if CPUASIC.search(combined) and not GPU_ALGO.search(combined):
        return 'unsupported_mining','cpu_or_asic_dominated'
    gpu=bool(GPU_ALGO.search(combined) or GPU_WORD.search(combined) or facts.get('algorithm') in
             ('KawPow','Ethash','Etchash','ProgPoW','FishHash','Autolykos','Equihash','Octopus','Verthash'))
    if not gpu:
        return 'insufficient','gpu_not_established'
    if not (POW.search(combined) or GPU_ALGO.search(combined)):
        return 'insufficient','pow_not_established'
    if not COIN.search(combined):
        return 'insufficient','coin_identity_missing'
    # A repository creation date alone is never coin evidence.
    if is_repo and not re.search(r'\b(cryptocurrency|blockchain|coin|mainnet|full node|genesis|native currency)\b',body,re.I):
        return 'insufficient','repository_not_coin'
    return 'coin_candidate','gpu_pow_coin_claim'

def is_coin(key,item):
    return classify(key,item)[0]=='coin_candidate'
