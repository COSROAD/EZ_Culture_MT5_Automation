
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Optional, Sequence

FRESHNESS={"FRESH","STALE","MARKET_CLOSED","VERIFY_REQUIRED","NOT_AVAILABLE"}
EVENT_TRIGGERS={"TICK_PRESSURE_SHOCK","VELOCITY_SHOCK","ACCELERATION_SHOCK","SPREAD_SHOCK","M1_REVERSAL","YIELD_SHOCK","DXY_SHOCK","REAL_YIELD_SHOCK","OIL_SHOCK","GOLD_SILVER_RELATIVE_SHIFT","BTC_RELATIVE_SHIFT","CREDIT_PRESSURE_SHIFT","GEOPOLITICAL_EVENT"}
KST=timezone(timedelta(hours=9))

@dataclass(frozen=True)
class SourceSnapshot:
    source_id:str; source_type:str; market:str; broker:Optional[str]; instrument:str
    timestamp_utc:str; received_time_utc:str; freshness:str; latency_ms:Optional[int]
    quality_state:str; available:bool

@dataclass(frozen=True)
class ShadowDecision:
    market:str; time_utc:str; time_kst:str; direction:str; direction_confidence:float
    entry_permission:str; add_permission:str; exit_state:str; risk_state:str
    conflict_level:str; historical_match:dict; regime:dict; trigger_features:tuple[str,...]
    contradicting_features:tuple[str,...]; freshness_summary:dict
    invalidation_condition:Optional[str]; reference_price:Optional[float]
    final_action:str; decision_trace:dict; live_order_allowed:bool=False
    def to_dict(self): return asdict(self)

def parse_iso(v:str)->datetime: return datetime.fromisoformat(v.replace("Z","+00:00"))

def time_health(ts:str, received:str, previous:str|None=None, stale_after:int=300, drift_limit:int=5)->dict:
    a=parse_iso(ts); b=parse_iso(received)
    if a.tzinfo is None or b.tzinfo is None: return {"status":"TIMEZONE_MISMATCH","freshness":"VERIFY_REQUIRED"}
    drift=(b-a).total_seconds()
    if drift < -drift_limit: return {"status":"FUTURE_TIMESTAMP","freshness":"VERIFY_REQUIRED","drift_seconds":drift}
    if previous and a < parse_iso(previous): return {"status":"OUT_OF_ORDER_DATA","freshness":"VERIFY_REQUIRED","drift_seconds":drift}
    if drift > stale_after: return {"status":"STALE_TIMESTAMP","freshness":"STALE","drift_seconds":drift}
    if abs(drift)>drift_limit: return {"status":"CLOCK_DRIFT","freshness":"FRESH","drift_seconds":drift}
    return {"status":"OK","freshness":"FRESH","drift_seconds":drift}

class SourceRegistry:
    def __init__(self): self.items={}
    def register(self,x:SourceSnapshot):
        if x.freshness not in FRESHNESS: raise ValueError("invalid freshness")
        self.items[x.source_id]=x
    def freshness_summary(self): return {k:v.freshness for k,v in self.items.items()}
    def critical_missing(self,ids):
        bad=[]
        for i in ids:
            x=self.items.get(i)
            if x is None or not x.available or x.freshness in {"STALE","VERIFY_REQUIRED","NOT_AVAILABLE"}: bad.append(i)
        return bad

def regime_state(name:str, supporting:Sequence[str], contradicting:Sequence[str], freshness:str)->dict:
    total=len(supporting)+len(contradicting); score=.5 if total==0 else len(supporting)/total
    state="POSITIVE" if score>.6 else ("NEGATIVE" if score<.4 else "MIXED")
    confidence=0.0 if freshness!="FRESH" else abs(score-.5)*2
    return {"name":name,"state":state,"confidence":confidence,"supporting_factors":list(supporting),"contradicting_factors":list(contradicting),"freshness":freshness,"invalidation_condition":None}

def connectivity(leading:str,path:Sequence[str],target:str,expected:str,observed:str,lag,confirmation:str)->dict:
    return {"leading_factor":leading,"transmission_path":list(path),"target_market":target,"expected_direction":expected,"observed_direction":observed,"lag":lag,"confirmation":confirmation,"invalidation":None,"relationship_state":"CONFIRMED" if expected==observed and confirmation=="CONFIRMED" else "DYNAMIC_UNCONFIRMED"}

def historical_match(current:set[str],cases:Sequence[dict],session:str,regime:str,freshness_match:bool=True)->dict:
    out=[]
    for c in cases:
        cf=set(c.get("features",[])); u=current|cf; inter=current&cf
        score=0.0 if not u else len(inter)/len(u)
        sm=c.get("session") in (None,session); rm=c.get("regime") in (None,regime)
        score*= (1 if sm else .8)*(1 if rm else .7)*(1 if freshness_match else .5)
        out.append({"case_id":c.get("case_id"),"match_score":score,"matched_features":sorted(inter),"contradicting_features":sorted(cf-current),"session_match":sm,"regime_match":rm,"freshness_match":freshness_match,"outcome":c.get("outcome")})
    out.sort(key=lambda x:x["match_score"],reverse=True)
    return {"match_score":out[0]["match_score"] if out else 0.0,"matched_cases":out[:5],"historical_only_authority":False,"outcome_distribution":[x["outcome"] for x in out[:5] if x.get("outcome") is not None]}

def current_confirmation(tick:str,m1:str,m5:str,cross:str,macro:str,volatility:str)->dict:
    vals=[tick,m1,m5,cross,macro,volatility]; bull=vals.count("LONG"); bear=vals.count("SHORT")
    contradiction=bull>0 and bear>0
    state="LONG" if bull>=4 and not contradiction else ("SHORT" if bear>=4 and not contradiction else "MIXED")
    return {"state":state,"components":vals,"contradiction":contradiction}

def conflict_level(states:Sequence[str])->str:
    vals=[x for x in states if x in ("LONG","SHORT")]
    if not vals:return "NONE"
    l=vals.count("LONG"); s=vals.count("SHORT")
    if l==0 or s==0:return "NONE"
    b=min(l,s)/len(vals)
    if b>=.4 and len(vals)>=4:return "CRITICAL"
    if b>=.33:return "HIGH"
    if b>=.2:return "MEDIUM"
    return "LOW"

def risk_gate(direction:str,conflict:str,critical_missing:list[str],risk:str,health_degraded:bool=False)->dict:
    if critical_missing or health_degraded:return {"entry_permission":"WAIT","add_permission":"NO_ADD","exit_state":"HOLD","state":"VERIFY_REQUIRED"}
    if conflict in ("HIGH","CRITICAL"):return {"entry_permission":"WAIT","add_permission":"NO_ADD","exit_state":"HOLD","state":"CONFLICT_BLOCK"}
    if risk=="HIGH_RISK":return {"entry_permission":"WAIT","add_permission":"NO_ADD","exit_state":"EXIT_CANDIDATE","state":"RISK_BLOCK"}
    if direction=="LONG":return {"entry_permission":"BUY_ALLOWED","add_permission":"ADD_ALLOWED","exit_state":"HOLD","state":"PASS"}
    if direction=="SHORT":return {"entry_permission":"SELL_ALLOWED","add_permission":"ADD_ALLOWED","exit_state":"HOLD","state":"PASS"}
    return {"entry_permission":"WAIT","add_permission":"NO_ADD","exit_state":"HOLD","state":"NEUTRAL"}

def event_driven(trigger:str)->bool: return trigger in EVENT_TRIGGERS

def infer_direction(market:str,historical:dict,current:dict,mt5_signal:str|None,market_specific:dict|None=None):
    state=current.get("state","MIXED"); contradictions=[]; triggers=[]
    if historical.get("match_score",0)>=.6: triggers.append("HISTORICAL_MATCH_HIGH")
    if state in ("LONG","SHORT"): triggers.append("CURRENT_CONFIRMATION_"+state)
    if market=="BTC" and market_specific and market_specific.get("btc_relative_strength")=="POSITIVE" and market_specific.get("crypto_liquidity")=="POSITIVE" and state=="SHORT":
        contradictions.append("BTC_SPECIFIC_CONTEXT_CONTRADICTS_NQ_RISK_OFF"); state="MIXED"
    if state=="MIXED": return "NEUTRAL",min(.49,float(historical.get("match_score",0))),triggers,contradictions
    if mt5_signal and mt5_signal not in (state,"NEUTRAL","VERIFY_REQUIRED"): contradictions.append("MT5_SIGNAL_CONFLICT")
    return state,min(1.0,.55+.25*float(historical.get("match_score",0))-(.2 if contradictions else 0)),triggers,contradictions

def make_decision(market:str,time_utc:str,direction:str,confidence:float,historical:dict,regime:dict,triggers:list[str],contradictions:list[str],freshness:dict,risk:str,source_dirs:list[str],critical_missing:list[str],price:float|None,invalidation:str|None,health_degraded:bool=False)->ShadowDecision:
    conflict=conflict_level(source_dirs); gate=risk_gate(direction,conflict,critical_missing,risk,health_degraded)
    if gate["entry_permission"]=="BUY_ALLOWED": action="BUY"
    elif gate["entry_permission"]=="SELL_ALLOWED": action="SELL"
    elif gate["exit_state"]=="EXIT_CANDIDATE": action="EXIT_CANDIDATE"
    elif gate["add_permission"]=="NO_ADD": action="NO_ADD" if direction in ("LONG","SHORT","LONG_CANDIDATE","SHORT_CANDIDATE") else "WAIT"
    else: action="HOLD"
    dt=parse_iso(time_utc)
    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
    trace={"WHY_DIRECTION":{"direction":direction,"confidence":confidence},"WHY_ENTRY":{"permission":gate["entry_permission"],"missing":critical_missing,"conflict":conflict},"WHY_ADD":{"permission":gate["add_permission"],"risk":risk},"WHY_WAIT":{"contradictions":contradictions,"health_degraded":health_degraded},"WHY_INVALIDATION":{"condition":invalidation}}
    return ShadowDecision(market,dt.astimezone(timezone.utc).isoformat(),dt.astimezone(KST).isoformat(),direction,confidence,gate["entry_permission"],gate["add_permission"],gate["exit_state"],risk,conflict,historical,regime,tuple(triggers),tuple(contradictions),freshness,invalidation,price,action,trace,False)

def replay_gold(case:dict,macro_freshness:str="VERIFY_REQUIRED")->dict:
    candidates=case.get("candidates") or case.get("times") or {}
    triggers=[k for k,v in candidates.items() if v]
    hist={"match_score":.8,"matched_cases":[{"case_id":case.get("case_id")}],"historical_only_authority":False}
    direction="LONG_CANDIDATE" if triggers else "NEUTRAL"
    missing=[] if macro_freshness=="FRESH" else ["MACRO"]
    d=make_decision("GOLD",case.get("reversal_pivot_time") or case.get("pivot") or "2026-01-01T00:00:00+00:00",direction,.6,hist,{"state":"VERIFY_REQUIRED","freshness":macro_freshness},triggers,[],{"MACRO":macro_freshness},"CAUTION",["LONG"],missing,(case.get("opportunity") or {}).get("earliest_long_candidate_price") or case.get("low"),"MICROSTRUCTURE_REVERSAL_FAILS")
    return d.to_dict()

def outcome_feedback(reference_price:float,timed_prices:list[tuple[int,float]],direction:str)->dict:
    out={}
    labels={60:"1m",180:"3m",300:"5m",600:"10m",1800:"30m",3600:"60m",10800:"3h",21600:"6h"}
    for h,label in labels.items():
        vals=[p for sec,p in timed_prices if 0<=sec<=h]
        if not vals or not reference_price: out[label]={"mfe":None,"mae":None,"direction_accuracy":None}; continue
        rets=[(p-reference_price)/reference_price for p in vals]
        if direction=="SHORT": rets=[-x for x in rets]
        out[label]={"mfe":max(rets),"mae":min(rets),"direction_accuracy":rets[-1]>0,"entry_timing_quality":"GOOD" if min(rets)>-.005 else "POOR_EARLY"}
    return out
