"""GPU family coverage for early PoW discoveries.

All NVIDIA GeForce GTX 10xx and RTX 20xx/30xx/40xx/50xx are in research
scope. An algorithm mention is NOT proof that a specific card, driver, miner,
VRAM capacity or DAG works. No model receives a synthetic hashrate.
"""
import re

FAMILIES=("GTX 10xx","RTX 20xx","RTX 30xx","RTX 40xx","RTX 50xx")
MODEL=re.compile(r"\b(?:nvidia\s+|geforce\s+)*(GTX|RTX)\s*-?\s*(10\d{2}|20\d{2}|30\d{2}|40\d{2}|50\d{2})\s*(ti|super)?\b",re.I)
SUPPORTED_SERIES={"10":"GTX","20":"RTX","30":"RTX","40":"RTX","50":"RTX"}

def identify_model(text):
    if not isinstance(text,str):return None
    match=MODEL.search(text)
    if not match:return None
    prefix,model,suffix=match.groups()
    if SUPPORTED_SERIES.get(model[:2])!=prefix.upper():return None
    return {"device":(prefix.upper()+" "+model+(" "+suffix.title() if suffix else "")),
            "series":model[:2]+"xx","family":prefix.upper()+" "+model[:2]+"xx"}

def provenance(item):
    """Return only explicit per-coin miner/driver/card support evidence.

    Mentions such as 'GPU friendly' or 'supports NVIDIA' are mere *claims*,
    not proof of performance or that 10xx+ generations all work.
    """
    raw=item.get("gpu_support_evidence") or []
    proof=[]
    for row in raw[:20] if isinstance(raw,list) else []:
        if not isinstance(row,dict):continue
        model=identify_model(row.get("device"))
        if not model or row.get("status") not in ("tested","developer_claimed"):continue
        url=str(row.get("source_url") or "")
        if not url.startswith(("https://","http://")):continue
        proof.append({"family":model["family"],"device":model["device"],
                      "status":row["status"],"source_url":url[:400]})
    return proof[:12]

def summary(item):
    proof=provenance(item)
    return {"scope":list(FAMILIES),
            "family_status":[{
                "family":f,
                "status":"tested_model_reported" if any(
                    x["family"]==f and x["status"]=="tested" for x in proof)
                    else "developer_claim_only" if any(x["family"]==f for x in proof)
                    else "not_verified",
                "models":[x["device"] for x in proof if x["family"]==f][:4]
            } for f in FAMILIES],
            "evidence":proof,
            "note":"В поиске все поколения; совместимость каждого GPU, майнера и памяти проверяется отдельно"}
