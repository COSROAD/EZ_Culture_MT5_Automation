
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Sequence, Optional
import hashlib, json, math

EVENT_TYPES = {
    "RAPID_UP_MOVE","RAPID_DOWN_MOVE","REVERSAL_UP","REVERSAL_DOWN",
    "VOLATILITY_EXPANSION","BREAKOUT","FAILED_BREAKDOWN","FAILED_BREAKOUT","DIRECTION_FLIP"
}

LOOKBACK_SECONDS = (60,180,300,600,900,1200,1800,3600)

@dataclass(frozen=True)
class ThresholdPolicy:
    mode: str
    value: float | None = None
    quantile: float | None = None
    approved_production_threshold: bool = False

@dataclass(frozen=True)
class EventRecord:
    event_id: str
    market: str
    broker: str
    source: str
    event_type: str
    event_time_utc: str
    event_time_kst: str
    start_price: float
    end_price: float
    move: float
    normalized_move: float | None
    event_window: str
    pre_event_features: dict
    cross_market_context: dict
    signal_context: dict
    freshness_context: dict
    post_event_mfe: float | None = None
    post_event_mae: float | None = None
    result_class: str = "OBSERVED_ASSOCIATION"
    notes: str = ""

def make_event_id(market: str, event_time_utc: str, event_type: str, source: str) -> str:
    seed = f"{market}|{event_time_utc}|{event_type}|{source}".encode()
    return "EVT_" + hashlib.sha256(seed).hexdigest()[:20].upper()

def candidate_threshold(values: Sequence[float], policy: ThresholdPolicy) -> float:
    if policy.approved_production_threshold:
        raise ValueError("Research framework must not silently approve production threshold")
    vals = sorted(abs(float(v)) for v in values if v is not None and math.isfinite(float(v)))
    if not vals:
        raise ValueError("No values")
    if policy.mode == "absolute":
        if policy.value is None: raise ValueError("value required")
        return abs(policy.value)
    if policy.mode == "quantile":
        q = 0.99 if policy.quantile is None else policy.quantile
        idx = min(len(vals)-1, max(0, int(round(q*(len(vals)-1)))))
        return vals[idx]
    if policy.mode == "zscore_candidate":
        mean = sum(vals)/len(vals)
        var = sum((v-mean)**2 for v in vals)/len(vals)
        z = 2.0 if policy.value is None else policy.value
        return mean + z*(var**0.5)
    raise ValueError("Unsupported research threshold mode")

def detect_event(previous_return: float, current_return: float, threshold: float) -> str | None:
    if current_return >= threshold:
        if previous_return < 0: return "REVERSAL_UP"
        return "RAPID_UP_MOVE"
    if current_return <= -threshold:
        if previous_return > 0: return "REVERSAL_DOWN"
        return "RAPID_DOWN_MOVE"
    if previous_return * current_return < 0 and abs(current_return) >= threshold * 0.5:
        return "DIRECTION_FLIP"
    return None

def reverse_lookback(event_time: datetime, snapshots: Sequence[dict], time_key: str = "time") -> dict:
    out = {}
    ordered = sorted(snapshots, key=lambda x: x[time_key])
    for sec in LOOKBACK_SECONDS:
        target = event_time - timedelta(seconds=sec)
        eligible = [x for x in ordered if x[time_key] <= target]
        out[f"T_MINUS_{sec}S"] = eligible[-1] if eligible else {"freshness":"VERIFY_REQUIRED","missing":True}
    return out

def build_control_sample(records: Sequence[dict], event_indexes: set[int]) -> list[dict]:
    return [dict(r, sample_class="CONTROL") for i,r in enumerate(records) if i not in event_indexes]

def lead_lag_record(factor: str, target: str, observed_lag_seconds: float, response: str, classification: str = "LEAD_LAG_CANDIDATE") -> dict:
    if classification not in {"OBSERVED_ASSOCIATION","LEAD_LAG_CANDIDATE","CAUSAL_HYPOTHESIS","VALIDATED_SIGNAL"}:
        raise ValueError("invalid classification")
    return {
        "leading_factor": factor,
        "transmission_path": [],
        "target_market": target,
        "observed_lag_seconds": observed_lag_seconds,
        "target_response": response,
        "invalidation_condition": None,
        "classification": classification,
    }
