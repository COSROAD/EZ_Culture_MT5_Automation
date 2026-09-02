
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
import hashlib

DIRECTIONS = ("STRONG_LONG","LONG","LONG_CANDIDATE","NEUTRAL","SHORT_CANDIDATE","SHORT","STRONG_SHORT")
ACTIONS = ("BUY_ALLOWED","SELL_ALLOWED","WAIT","HOLD","ADD_ALLOWED","NO_ADD","EXIT_CANDIDATE",
           "LONG_INVALIDATION_WARNING","SHORT_INVALIDATION_WARNING","VOLATILITY_BLOCK","SPREAD_BLOCK")

@dataclass(frozen=True)
class ShadowDecision:
    shadow_id: str
    market: str
    time_utc: str
    direction: str
    action: str
    regime: str
    risk_state: str
    add_permission: str
    trigger_features: tuple[str,...]
    invalidation_condition: str | None
    reference_price: float
    live_order_allowed: bool = False

def make_shadow_id(market: str, time_utc: str, direction: str, action: str) -> str:
    return "SHD_" + hashlib.sha256(f"{market}|{time_utc}|{direction}|{action}".encode()).hexdigest()[:20].upper()

def next_direction(current: str, long_score: float, short_score: float, invalidated: bool=False) -> str:
    if current not in DIRECTIONS: raise ValueError("invalid current")
    if invalidated:
        if current in ("STRONG_LONG","LONG","LONG_CANDIDATE"): return "NEUTRAL"
        if current in ("STRONG_SHORT","SHORT","SHORT_CANDIDATE"): return "NEUTRAL"
    delta = long_score-short_score
    if delta >= 3: return "STRONG_LONG"
    if delta >= 1.5: return "LONG"
    if delta > 0: return "LONG_CANDIDATE"
    if delta <= -3: return "STRONG_SHORT"
    if delta <= -1.5: return "SHORT"
    if delta < 0: return "SHORT_CANDIDATE"
    return "NEUTRAL"

def risk_action(direction: str, volatility_block: bool=False, spread_block: bool=False, add_risk: bool=False, invalidation: bool=False) -> tuple[str,str]:
    if volatility_block: return "VOLATILITY_BLOCK","NO_ADD"
    if spread_block: return "SPREAD_BLOCK","NO_ADD"
    if invalidation:
        if direction in ("STRONG_LONG","LONG","LONG_CANDIDATE"): return "LONG_INVALIDATION_WARNING","NO_ADD"
        if direction in ("STRONG_SHORT","SHORT","SHORT_CANDIDATE"): return "SHORT_INVALIDATION_WARNING","NO_ADD"
    if add_risk: return "HOLD","NO_ADD"
    if direction in ("STRONG_LONG","LONG"): return "BUY_ALLOWED","ADD_ALLOWED"
    if direction in ("STRONG_SHORT","SHORT"): return "SELL_ALLOWED","ADD_ALLOWED"
    return "WAIT","NO_ADD"

def build_shadow(market: str, time_utc: str, direction: str, action: str, regime: str, risk_state: str,
                 add_permission: str, trigger_features: Sequence[str], reference_price: float,
                 invalidation_condition: str|None=None) -> ShadowDecision:
    return ShadowDecision(
        shadow_id=make_shadow_id(market,time_utc,direction,action),
        market=market,time_utc=time_utc,direction=direction,action=action,regime=regime,
        risk_state=risk_state,add_permission=add_permission,trigger_features=tuple(trigger_features),
        invalidation_condition=invalidation_condition,reference_price=float(reference_price),
        live_order_allowed=False,
    )
