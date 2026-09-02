
from __future__ import annotations
from typing import Sequence

def mfe_mae(reference_price: float, future_prices: Sequence[float], direction: str) -> tuple[float,float]:
    if not future_prices: return (0.0,0.0)
    rets = [(float(p)-reference_price)/reference_price for p in future_prices]
    if direction in ("SHORT","STRONG_SHORT","SHORT_CANDIDATE"):
        rets = [-r for r in rets]
    return max(rets), min(rets)

def evaluate_shadow(outcomes: Sequence[dict]) -> dict:
    if not outcomes:
        return {"count":0,"hit_rate":None,"false_positive_rate":None,"avg_mfe":None,"avg_mae":None}
    hits = sum(1 for x in outcomes if x.get("hit"))
    fps = sum(1 for x in outcomes if x.get("false_positive"))
    mfes = [float(x.get("mfe",0.0)) for x in outcomes]
    maes = [float(x.get("mae",0.0)) for x in outcomes]
    return {
        "count":len(outcomes),
        "hit_rate":hits/len(outcomes),
        "precision":hits/max(1,hits+fps),
        "false_positive_rate":fps/len(outcomes),
        "avg_mfe":sum(mfes)/len(mfes),
        "avg_mae":sum(maes)/len(maes),
        "mfe_mae_ratio":(sum(mfes)/len(mfes))/abs(sum(maes)/len(maes)) if sum(maes) != 0 else None,
    }
