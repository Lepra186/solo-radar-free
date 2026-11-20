"""Conservative GPU PoW unit economics for SOLO Radar.

Never invent GPU hashrate, coin price, pool fees or network hashrate. Calculations
are conditional on externally measured/reported inputs and fresh timestamps.
"""
from datetime import datetime,timezone,timedelta
import math
from coin_filter import is_coin
from gpu_families import identify_model, FAMILIES

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
    # Accept measured rigs with any supported GeForce generation, including
    # mixed rigs. Never double count a total rig measurement and its per-card rows.
    # Hashrate is H/s for the identical algorithm and must be an observed value.
    local=item.get("gpu_measurement") or {}
    devices=local.get("devices")
    valid_devices=[]
    valid_gpu=False
    valid_hashrate=None
    if isinstance(devices,list) and devices:
        for device in devices[:24]:
            if not isinstance(device,dict):continue
            parsed=identify_model(device.get("device"))
            measured_at=date_time(device.get("measured_at"))
            stamp_ok=bool(measured_at and timedelta(0)<=now-measured_at<=timedelta(days=7))
            value=positive(device.get("hashrate_hs"))
            if (parsed and stamp_ok and value and matching_algorithm
                    and str(device.get("algorithm") or "").lower()==algorithm
                    and str(device.get("origin") or "")=="measured_hiveos"):
                valid_devices.append({"device":parsed["device"],"family":parsed["family"],
                                      "hashrate_hs":value})
        # Partial measurements cannot be mistaken for a full rig:
        # all configured entries must have complete independently measured data.
        if len(valid_devices)==len(devices) and len(devices)<=24:
            valid_gpu=True
            valid_hashrate=sum(x["hashrate_hs"] for x in valid_devices)
    elif isinstance(local,dict):
        parsed=identify_model(local.get("device"))
        measured_at=date_time(local.get("measured_at"))
        stamp_ok=bool(measured_at and timedelta(0)<=now-measured_at<=timedelta(days=7))
        measured_hashrate=positive(local.get("hashrate_hs"))
        valid_gpu=bool(parsed and stamp_ok and measured_hashrate and matching_algorithm
                  and str(local.get("algorithm") or "").lower()==algorithm
                  and str(local.get("origin") or "")=="measured_hiveos")
        if valid_gpu:
            valid_hashrate=measured_hashrate
            valid_devices=[{"device":parsed["device"],"family":parsed["family"],
                            "hashrate_hs":measured_hashrate}]
    fee=local.get("pool_fee_fraction") if isinstance(local,dict) else None
    valid_fee=(isinstance(fee,(int,float)) and not isinstance(fee,bool)
               and math.isfinite(fee) and 0<=fee<1)
    if not valid_fee:fee=None
    expected=None
    if valid_gpu and hashrate and reward and block_time and fee is not None:
        expected=estimate_daily_coins(valid_hashrate,hashrate,reward,block_time,fee)
    missing=[]
    if not current:missing.append("свежие сетевые данные")
    if not hashrate:missing.append("хешрейт сети (H/s)")
    if not reward:missing.append("награда за блок")
    if not block_time:missing.append("время блока")
    if not valid_gpu:missing.append("замер всех видеокарт рига (GTX 10xx / RTX 20xx–50xx) на этом алгоритме")
    if fee is None:missing.append("комиссия пула")
    # Power is total rig draw at the wall; avoid GPU-only readings.
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
        "gpu_families_in_scope":list(FAMILIES),
        "measured_devices":valid_devices,
        "measured_rig_hashrate_hs":valid_hashrate if valid_gpu else None,
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
