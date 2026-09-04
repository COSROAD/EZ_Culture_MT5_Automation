
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, Sequence

BTC_PRIMARY_ROLE = "PRIMARY_TRADING_RESEARCH_TARGET"
FIVE_MARKET_ROLES = {
    "BTC":"HIGH_PRIMARY_TARGET",
    "NQ":"HIGH_CONNECTIVITY_RISK_LIQUIDITY",
    "GOLD":"MEDIUM_MACRO_REAL_YIELD_SAFE_HAVEN",
    "SILVER":"MEDIUM_METALS_RELATIVE_STRENGTH_RISK",
    "OIL":"MEDIUM_INFLATION_RATE_PRESSURE_GEOPOLITICAL",
}
REGIME_STATES = (
    "STRONG_LONG_REGIME","LONG_REGIME","NEUTRAL_REGIME",
    "SHORT_REGIME","STRONG_SHORT_REGIME"
)
TACTICAL_STATES = (
    "TACTICAL_PULLBACK","TACTICAL_REBOUND","VOLATILITY_SHOCK",
    "LIQUIDITY_SHOCK","TACTICAL_NEUTRAL"
)
EVENT_TYPES = (
    "RAPID_UP","RAPID_DOWN","REVERSAL_UP","REVERSAL_DOWN",
    "BREAKOUT","FAILED_BREAKOUT","FAILED_BREAKDOWN","VOLATILITY_EXPANSION"
)
LOOKBACK_SECONDS = (300,900,1800,3600,10800,21600,43200,86400)

@dataclass(frozen=True)
class ContextState:
    state: str
    confidence: float
    freshness: str
    source: str
    supporting_factors: tuple[str,...] = ()
    contradicting_factors: tuple[str,...] = ()
    invalidation: Optional[str] = None
    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class BTCShadowDecision:
    regime: str
    regime_confidence: float
    tactical_state: str
    direction: str
    entry_permission: str
    add_permission: str
    exit_state: str
    risk_state: str
    nq_relative_state: str
    macro_state: str
    crypto_liquidity_state: str
    etf_flow_state: str
    regulatory_state: str
    historical_match: dict
    conflict_level: str
    why_direction: tuple[str,...]
    why_entry: tuple[str,...]
    why_add: tuple[str,...]
    invalidation: Optional[str]
    final_action: str
    live_order_allowed: bool = False
    def to_dict(self): return asdict(self)

def _score_to_regime(score: float) -> str:
    if score >= 0.70: return "STRONG_LONG_REGIME"
    if score >= 0.20: return "LONG_REGIME"
    if score <= -0.70: return "STRONG_SHORT_REGIME"
    if score <= -0.20: return "SHORT_REGIME"
    return "NEUTRAL_REGIME"

def long_horizon_regime(m30_direction: str, h1_direction: str,
                        nq_relative: str="VERIFY_REQUIRED",
                        macro_state: str="VERIFY_REQUIRED",
                        crypto_liquidity: str="VERIFY_REQUIRED",
                        current_regime: str|None=None,
                        tactical_state: str="TACTICAL_NEUTRAL") -> dict:
    def d(v: str) -> float:
        return 1.0 if v in ("LONG","POSITIVE") else (-1.0 if v in ("SHORT","NEGATIVE") else 0.0)
    score=0.30*d(m30_direction)+0.40*d(h1_direction)+0.10*d(nq_relative)+0.10*d(macro_state)+0.10*d(crypto_liquidity)
    proposed=_score_to_regime(score)
    if current_regime in ("LONG_REGIME","STRONG_LONG_REGIME") and tactical_state in ("TACTICAL_PULLBACK","VOLATILITY_SHOCK"):
        if m30_direction!="SHORT" or h1_direction!="SHORT":
            proposed=current_regime
    if current_regime in ("SHORT_REGIME","STRONG_SHORT_REGIME") and tactical_state in ("TACTICAL_REBOUND","VOLATILITY_SHOCK"):
        if m30_direction!="LONG" or h1_direction!="LONG":
            proposed=current_regime
    available=sum(1 for x in (m30_direction,h1_direction,nq_relative,macro_state,crypto_liquidity) if x!="VERIFY_REQUIRED")
    confidence=min(1.0,abs(score)*(available/5.0)+0.15*(available/5.0))
    return {"regime":proposed,"score":score,"confidence":confidence,"available_components":available}

def btc_nq_relative(btc_return: Optional[float], nq_return: Optional[float],
                    btc_lead_seconds: Optional[float]=None) -> dict:
    if btc_return is None or nq_return is None:
        return {"state":"VERIFY_REQUIRED","lead_lag":"NOT_AVAILABLE","spread":None}
    spread=btc_return-nq_return
    if btc_return>0 and nq_return<0: state="BTC_NQ_DECOUPLING"
    elif spread>0.002: state="BTC_RELATIVE_STRENGTH_POSITIVE"
    elif spread<-0.002: state="BTC_RELATIVE_STRENGTH_NEGATIVE"
    else: state="NEUTRAL"
    return {"state":state,"lead_lag":"LEAD_LAG_CANDIDATE" if btc_lead_seconds is not None else "VERIFY_REQUIRED","lead_seconds":btc_lead_seconds,"spread":spread}

def context_state(state: str, freshness: str="VERIFY_REQUIRED", source: str="NOT_AVAILABLE",
                  supporting: Sequence[str]=(), contradicting: Sequence[str]=(),
                  invalidation: Optional[str]=None, confidence: float=0.0) -> dict:
    if freshness!="FRESH": confidence=0.0
    return ContextState(state,confidence,freshness,source,tuple(supporting),tuple(contradicting),invalidation).to_dict()

def stablecoin_structural_factor(stablecoin_growth: Optional[float], flow_state: str, freshness: str) -> dict:
    if stablecoin_growth is None or freshness!="FRESH":
        return context_state("VERIFY_REQUIRED",freshness,"STABLECOIN_SOURCE_UNAPPROVED")
    if stablecoin_growth>0 and flow_state=="INFLOW":
        return context_state("STRUCTURAL_LONG_FACTOR","FRESH","CRYPTO_LIQUIDITY_ADAPTER",
                             ["STABLECOIN_SUPPLY_GROWTH","NET_INFLOW"],[],
                             "SUPPLY_OR_FLOW_REVERSAL",0.65)
    if stablecoin_growth<0 or flow_state=="OUTFLOW":
        return context_state("NEGATIVE","FRESH","CRYPTO_LIQUIDITY_ADAPTER",[],
                             ["STABLECOIN_CONTRACTION_OR_OUTFLOW"],
                             "SUPPLY_OR_FLOW_REVERSAL",0.55)
    return context_state("MIXED","FRESH","CRYPTO_LIQUIDITY_ADAPTER",confidence=0.3)

def regulatory_factor(items: Sequence[str], freshness: str, source: str) -> dict:
    if freshness!="FRESH": return context_state("VERIFY_REQUIRED",freshness,source)
    pos=sum(1 for x in items if x.startswith("POSITIVE:"))
    neg=sum(1 for x in items if x.startswith("NEGATIVE:"))
    state="POSITIVE" if pos>neg else ("NEGATIVE" if neg>pos else "MIXED")
    total=max(1,pos+neg)
    return context_state(state,"FRESH",source,
                         [x for x in items if x.startswith("POSITIVE:")],
                         [x for x in items if x.startswith("NEGATIVE:")],
                         "REGULATORY_CONTEXT_CHANGES",abs(pos-neg)/total)

def rates_dollar_observation(rates_state: str, dollar_state: str, btc_response: str,
                             freshness: str) -> dict:
    if freshness!="FRESH":
        return {"state":"VERIFY_REQUIRED","relationship":"DYNAMIC_UNCONFIRMED"}
    return {"rates_state":rates_state,"dollar_state":dollar_state,"btc_response":btc_response,
            "relationship":"OBSERVED_ASSOCIATION","universal_direction_rule":False}

def add_gate(regime: str, tactical_state: str, m1_state: str, m5_state: str,
             cross_market_risk: str, health_fresh: bool) -> dict:
    if not health_fresh: return {"add_permission":"NO_ADD","reason":"HEALTH_OR_FRESHNESS"}
    if regime not in ("LONG_REGIME","STRONG_LONG_REGIME"): return {"add_permission":"NO_ADD","reason":"LONG_REGIME_NOT_VALID"}
    if tactical_state not in ("TACTICAL_PULLBACK","TACTICAL_NEUTRAL"): return {"add_permission":"NO_ADD","reason":"TACTICAL_STATE_UNSAFE"}
    if m1_state!="IMPROVING" or m5_state!="IMPROVING": return {"add_permission":"NO_ADD","reason":"TIMING_NOT_IMPROVING"}
    if cross_market_risk in ("HIGH_RISK","DETERIORATING","VERIFY_REQUIRED"): return {"add_permission":"NO_ADD","reason":"CROSS_MARKET_RISK"}
    return {"add_permission":"ADD_ALLOWED","reason":"ALL_RESEARCH_GATES_PASS"}

def entry_gate(regime: str, m1_state: str, m5_state: str, macro_state: str,
               conflict_level: str, health_fresh: bool) -> dict:
    if not health_fresh: return {"entry_permission":"WAIT","reason":"HEALTH_OR_FRESHNESS"}
    if macro_state=="VERIFY_REQUIRED": return {"entry_permission":"WAIT","reason":"MACRO_VERIFY_REQUIRED"}
    if conflict_level in ("HIGH","CRITICAL"): return {"entry_permission":"WAIT","reason":"CONFLICT_BLOCK"}
    if regime in ("LONG_REGIME","STRONG_LONG_REGIME") and m1_state=="IMPROVING" and m5_state=="IMPROVING":
        return {"entry_permission":"BUY_ALLOWED","reason":"LONG_SETUP_CONFIRMED"}
    if regime in ("SHORT_REGIME","STRONG_SHORT_REGIME") and m1_state=="DETERIORATING" and m5_state=="DETERIORATING":
        return {"entry_permission":"SELL_ALLOWED","reason":"SHORT_SETUP_CONFIRMED"}
    return {"entry_permission":"WAIT","reason":"SETUP_INCOMPLETE"}

def btc_shadow_decision(regime_result: dict, tactical_state: str, nq_relative_state: str,
                        macro_state: str, crypto_liquidity_state: str, etf_flow_state: str,
                        regulatory_state: str, historical_match: dict, conflict_level: str,
                        m1_state: str, m5_state: str, cross_market_risk: str,
                        health_fresh: bool, invalidation: Optional[str]=None) -> dict:
    regime=regime_result["regime"]
    direction="LONG" if regime in ("LONG_REGIME","STRONG_LONG_REGIME") else ("SHORT" if regime in ("SHORT_REGIME","STRONG_SHORT_REGIME") else "NEUTRAL")
    e=entry_gate(regime,m1_state,m5_state,macro_state,conflict_level,health_fresh)
    a=add_gate(regime,tactical_state,m1_state,m5_state,cross_market_risk,health_fresh)
    if e["entry_permission"]=="BUY_ALLOWED": action="BUY"
    elif e["entry_permission"]=="SELL_ALLOWED": action="SELL"
    elif a["add_permission"]=="NO_ADD" and direction in ("LONG","SHORT"): action="NO_ADD"
    else: action="WAIT"
    return BTCShadowDecision(
        regime,regime_result["confidence"],tactical_state,direction,e["entry_permission"],
        a["add_permission"],"HOLD","CAUTION",nq_relative_state,macro_state,
        crypto_liquidity_state,etf_flow_state,regulatory_state,historical_match,
        conflict_level,(f"REGIME={regime}",f"NQ_RELATIVE={nq_relative_state}"),
        (e["reason"],),(a["reason"],),invalidation,action,False
    ).to_dict()

def detect_event(prices: Sequence[float], threshold: float=0.02) -> str:
    if len(prices)<3 or not prices[0]: return "NOT_AVAILABLE"
    start,end=prices[0],prices[-1]
    change=(end-start)/start
    if change>=threshold: return "RAPID_UP"
    if change<=-threshold: return "RAPID_DOWN"
    if min(prices)<start*(1-threshold) and end>start: return "REVERSAL_UP"
    if max(prices)>start*(1+threshold) and end<start: return "REVERSAL_DOWN"
    return "NEUTRAL"

def reverse_lookback_windows(event_time: datetime, available_start: Optional[datetime]=None) -> dict:
    out={}
    for sec in LOOKBACK_SECONDS:
        target=event_time-timedelta(seconds=sec)
        out[f"T_MINUS_{sec}S"]={"target_time":target.isoformat(),
            "status":"VERIFY_REQUIRED" if available_start and target<available_start else "AVAILABLE"}
    return out

def outcome_metrics(reference_price: float, timed_prices: Sequence[tuple[int,float]], direction: str) -> dict:
    labels={60:"1m",180:"3m",300:"5m",600:"10m",1800:"30m",3600:"60m",10800:"3h",21600:"6h",43200:"12h",86400:"24h",172800:"48h",259200:"72h"}
    out={}
    for sec,label in labels.items():
        vals=[p for s,p in timed_prices if 0<=s<=sec]
        if not vals or not reference_price:
            out[label]={"mfe":None,"mae":None,"direction_accuracy":None}
            continue
        rs=[(p-reference_price)/reference_price for p in vals]
        if direction=="SHORT": rs=[-x for x in rs]
        out[label]={"mfe":max(rs),"mae":min(rs),"direction_accuracy":rs[-1]>0,
                    "entry_quality":"GOOD" if min(rs)>-0.01 else "POOR_EARLY"}
    return out

def event_record(event_id: str, event_type: str, tick: dict, m1: dict, m5: dict,
                 m30_h1: dict, nq_relative: dict, macro: dict, crypto: dict) -> dict:
    if event_type not in EVENT_TYPES: raise ValueError("unsupported event type")
    return {"event_id":event_id,"event_type":event_type,"tick":tick,"m1":m1,"m5":m5,
            "m30_h1_context":m30_h1,"nq_relative_state":nq_relative,"macro_context":macro,
            "crypto_specific_context":crypto,"classification":"RESEARCH_CANDIDATE_ONLY",
            "production_threshold":False,"live_order_allowed":False}
