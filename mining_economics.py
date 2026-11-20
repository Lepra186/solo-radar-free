"""Conservative GPU PoW unit economics for SOLO Radar.

Never invent GPU hashrate, coin price, pool fees or network hashrate. Calculations
are conditional on externally measured/reported inputs and fresh timestamps.
"""
from datetime import datetime,timezone,timedelta
import math
from coin_filter import is_coin

TARIFF_EUR_KWH=0.10
HOURS_DAY=24
NETWORK_FRESH=timedelta(hours=48)
POWER_SCENARIOS_W=(150,200,250,300)
MINING_ALGOS={"ethash","etchash","kawpow","progpow","fishhash","autolykos",
              "equihash","octopus","verthash","firopow","zelhash","cuckoocycle"}

def date_time(value):
    if not isinstance(value,str):return None
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:return None

def positive(value):
    if isinstance(value,bool) or not isinstance(value,(float,int)):return None
    return float(value) if math.isfinite(value) and value>0 else None

def energy_eur_day(watts,tariff=TARIFF_EUR_KWH):
    w=positive(watts)
    if w is None or not isinstance(tariff,(int,float)) or isinstance(tariff,bool) or not math.isfinite(tariff) or tariff<0:
        return None
    return round(w/1000*HOURS_DAY*tariff,4)

def estimate_daily_coins(gpu_hashrate_hs,network_hashrate_hs,reward_coin,block_time_seconds,pool_fee_fraction=0):
    """Expected coins/day assuming stable network and pool luck; NOT guaranteed.
    Hashrate must be measured for the exact same coin/algorithm and in H/s.
    """
    values=[positive(gpu_hashrate_hs),positive(network_hashrate_hs),
            positive(reward_coin),positive(block_time_seconds)]
    if any(v is None for v in values):return None
    if gpu_hashrate_hs>network_hashrate_hs:return None
    if isinstance(pool_fee_fraction,bool) or not isinstance(pool_fee_fraction,(int,float)):
        return None
    if not math.isfinite(pool_fee_fraction) or not 0<=pool_fee_fraction<1:return None
    return round((gpu_hashrate_hs/network_hashrate_hs)*86400/block_time_seconds*
                 reward_coin*(1-pool_fee_fraction),8)

def assess_economics(key,item,now):
    if not is_coin(key,item):
        return {"status":"excluded","expected_coin_day":None,"net_eur_day":None}
    network=item.get("network_evidence") or {}
    fetched=date_time(network.get("fetched_at"))
    current=fetched and timedelta(0)<=now-fetched<=NETWORK_FRESH
    algorithm=str((item.get("facts") or {}).get("algorithm") or network.get("algorithm") or "").lower()
    matching_algorithm=any(a==algorithm for a in MINING_ALGOS)
    hashrate=positive(network.get("network_hashrate_hs")) if current else None
    reward=positive(network.get("block_reward")) if current else None
    block_time=positive(network.get("block_time_seconds")) if current else None
    local=item.get("gpu_measurement") or {}
    measured_hashrate=positive(local.get("hashrate_hs"))
    measured_at=date_time(local.get("measured_at"))
    measurement_fresh=bool(measured_at and timedelta(0)<=now-measured_at<=timedelta(days=7))
    measured_algorithm=str(local.get("algorithm") or "").lower()
    # A valid GPU measurement needs provenance and exact algorithm match;
    # there are no default hashrates for RTX 5070 Ti.
    valid_gpu=bool(measurement_fresh and matching_algorithm and measured_algorithm==algorithm
                   and measured_hashrate and str(local.get("device") or "").lower()=="rtx 5070 ti"
                   and str(local.get("origin") or "")=="measured_hiveos")
    expected=None
    if valid_gpu and hashrate and reward and block_time:
        expected=estimate_daily_coins(measured_hashrate,hashrate,reward,block_time)
    fee=None
    if expected is not None:
        fee=local.get("pool_fee_fraction")
        if fee is not None and (not isinstance(fee,(int,float)) or isinstance(fee,bool)
                                or not math.isfinite(fee) or not 0<=fee<1):fee=None
        # For no verified fee, cannot assert after-pool payout.
        if fee is not None:
            expected=estimate_daily_coins(measured_hashrate,hashrate,reward,block_time,fee)
        else:expected=None
    missing=[]
    if not current:missing.append("свежие сетевые данные")
    if not hashrate:missing.append("хешрейт сети (H/s)")
    if not reward:missing.append("награда за блок")
    if not block_time:missing.append("время блока")
    if not valid_gpu:missing.append("замер RTX 5070 Ti на этом алгоритме (HiveOS)")
    if fee is None:missing.append("комиссия пула")
    # Actual power is total-at-wall; scenario power is NEVER assumed hardware telemetry.
    watts=positive(local.get("wall_power_w"))
    power_actual=bool(watts and valid_gpu)
    cost=energy_eur_day(watts) if power_actual else None
    missing.append("проверенная цена продажи в EUR и ликвидность")
    return {
        "status":"conditional_estimate" if expected is not None else "insufficient_data",
        "expected_coin_day":expected,
        "net_eur_day":None,
        "power_cost_eur_day":cost,
        "energy_scenarios_eur_day":[{"wall_power_w":w,"eur_day":energy_eur_day(w)}
                                    for w in POWER_SCENARIOS_W],
        "tariff_eur_kwh":TARIFF_EUR_KWH,
        "power_scenarios_are_assumptions":True,
        "network_fresh":bool(current),
        "gpu_measured":valid_gpu,
        "required":list(dict.fromkeys(missing)),
        "note":"Сценарии энергии — не измерение GPU/рига. Доходность и продажа не подтверждены."
    }

def calculate_all(topics,now):
    counts={}
    for key,item in topics.items():
        if not isinstance(item,dict):continue
        econ=assess_economics(key,item,now)
        item["economics"]=econ
        counts[econ["status"]]=counts.get(econ["status"],0)+1
    return counts
