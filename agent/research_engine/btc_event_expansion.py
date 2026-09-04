from __future__ import annotations
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Optional

from agent.research_engine.btc_event_replay import (
    return_between, future_return, regime_features, align_relative,
    bar_feature_snapshot, microstructure, bar_at_or_before
)

UTC=timezone.utc
INDEPENDENCE_GAP_MINUTES=90
OUTCOME_MINUTES=(60,180,360,720,1440,2880)
MACRO_GAP={"DXY":"VERIFY_REQUIRED","2Y":"VERIFY_REQUIRED","10Y":"VERIFY_REQUIRED","30Y":"VERIFY_REQUIRED","REAL_YIELD":"VERIFY_REQUIRED"}
CRYPTO_GAP={"BTC_ETF_FLOW":"VERIFY_REQUIRED","STABLECOIN_FLOW":"VERIFY_REQUIRED","INSTITUTIONAL_FLOW":"VERIFY_REQUIRED","REGULATORY_STATE":"REFERENCE_ONLY_OR_VERIFY_REQUIRED"}

def cluster_events(candidates:list[dict],gap_minutes:int=INDEPENDENCE_GAP_MINUTES)->list[dict]:
    if not candidates:return []
    xs=sorted((dict(x) for x in candidates),key=lambda x:x["time"])
    groups=[];cur=[xs[0]]
    for x in xs[1:]:
        if (x["time"]-cur[-1]["time"]).total_seconds()<=gap_minutes*60:cur.append(x)
        else:groups.append(cur);cur=[x]
    groups.append(cur)
    out=[]
    for i,g in enumerate(groups,1):
        rep=max(g,key=lambda x:abs(float(x.get("return_1m") or 0)))
        cid=f"BTC_CLUSTER_{i:04d}"
        for x in g:
            y=dict(x);ind=(x is rep)
            y["EVENT_CLUSTER_ID"]=cid;y["INDEPENDENT_CASE_FLAG"]=ind;y["OVERLAPPING_EVENT_FLAG"]=not ind
            out.append(y)
    return sorted(out,key=lambda x:x["time"])

def research_session(t:datetime)->str:
    if t.tzinfo is None:t=t.replace(tzinfo=UTC)
    u=t.astimezone(UTC);y=u.year
    def sunday(month,n):
        d=datetime(y,month,1,tzinfo=UTC);return d+timedelta(days=(6-d.weekday())%7+7*(n-1))
    start=sunday(3,2).replace(hour=7);end=sunday(11,1).replace(hour=6)
    off=-4 if start<=u<end else -5;et=u+timedelta(hours=off);hm=et.hour+et.minute/60
    if 4<=hm<9.5:return "US_PREMARKET"
    if 9.5<=hm<16:return "US_CASH"
    if 16<=hm<20:return "US_LATE"
    if 2<=hm<4:return "EUROPE"
    return "ASIA"

def classify_decoupling(btc_ret:Optional[float],nq_ret:Optional[float],hold=.001,move=.002)->str:
    if btc_ret is None or nq_ret is None:return "UNCONFIRMED"
    if btc_ret>move and nq_ret<-move:return "BTC_UP_NQ_DOWN"
    if btc_ret<-move and nq_ret>move:return "BTC_DOWN_NQ_UP"
    if abs(btc_ret)<=hold and nq_ret<-move:return "BTC_HOLDS_NQ_DECLINES"
    if btc_ret<-move and abs(nq_ret)<=hold:return "BTC_DECLINES_NQ_HOLDS"
    return "NO_DECOUPLING"

def event_time_features(case,btc_ticks,btc_m1,btc_m5,btc_m30,btc_h1,nq_m1):
    t=case["time"];m1=bar_feature_snapshot(btc_m1,t,"M1");m5=bar_feature_snapshot(btc_m5,t,"M5")
    rg=regime_features(btc_m30,btc_h1,t);rel=align_relative(btc_m1,nq_m1,t)
    return {"time":t,"event_type":case["event_type"],"return_1m":case.get("return_1m"),"session":research_session(t),
            "micro":microstructure(btc_ticks,t,5),"m1":m1,"m5":m5,"regime":rg,"relative":rel,
            "decoupling":classify_decoupling(return_between(btc_m1,t,30),return_between(nq_m1,t,30)),
            "macro_state":dict(MACRO_GAP),"crypto_state":dict(CRYPTO_GAP)}

def label_case(f,btc_m1):
    future3=future_return(btc_m1,f["time"],180)
    if future3 is None:return "UNUSABLE_FUTURE_GAP"
    rg=f["regime"]["regime"];et=f["event_type"]
    if rg in ("LONG_REGIME","STRONG_LONG_REGIME") and et in ("RAPID_DOWN","REVERSAL_DOWN","FAILED_BREAKOUT","VOLATILITY_EXPANSION"):
        return "HEALTHY_LONG_PULLBACK" if future3>0 else "FAILED_LONG_PULLBACK"
    if rg in ("SHORT_REGIME","STRONG_SHORT_REGIME") and et in ("RAPID_UP","REVERSAL_UP","BREAKOUT","VOLATILITY_EXPANSION"):
        return "BEARISH_CONTINUATION" if future3<0 else "FAILED_BEARISH_CONTINUATION"
    if et in ("REVERSAL_UP","BREAKOUT","RAPID_UP"):return "BULLISH_TRANSITION" if future3>0 else "FALSE_BULLISH_REVERSAL"
    if et in ("REVERSAL_DOWN","FAILED_BREAKOUT","RAPID_DOWN"):return "BEARISH_TRANSITION" if future3<0 else "FALSE_BEARISH_REVERSAL"
    return "OTHER_EVENT"

def _trend(x):
    d=x.get("direction");return "IMPROVING" if d=="UP" else ("DETERIORATING" if d=="DOWN" else "MIXED")

def add_noadd_candidate(f):
    rg=f["regime"]["regime"];h1=f["regime"].get("h1_direction");m1=_trend(f["m1"]);m5=_trend(f["m5"]);rel=f["relative"].get("state","VERIFY_REQUIRED")
    if rg in ("LONG_REGIME","STRONG_LONG_REGIME"):
        if h1=="SHORT" or rel=="BTC_RELATIVE_STRENGTH_NEGATIVE" or m5=="DETERIORATING":add="NO_ADD_CANDIDATE"
        elif m1=="IMPROVING" and m5=="IMPROVING" and rel not in ("BTC_RELATIVE_STRENGTH_NEGATIVE","VERIFY_REQUIRED"):add="ADD_ALLOWED_CANDIDATE"
        else:add="WAIT_CANDIDATE"
    else:add="NO_ADD_CANDIDATE"
    exitw="EXIT_WARNING_CANDIDATE" if f["event_type"]=="FAILED_BREAKOUT" or (h1=="SHORT" and m5=="DETERIORATING") else "NO_EXIT_WARNING"
    return {"ADD_STATE":add,"EXIT_WARNING_STATE":exitw,"PRICE_DECLINE_ALONE_IS_ADD_EVIDENCE":False}

def outcome_by_horizon(btc_m1,t):
    ref=bar_at_or_before(btc_m1,t)
    if not ref:return {}
    rp=ref["close"];out={}
    for mins in OUTCOME_MINUTES:
        bars=[b for b in btc_m1 if t<=b["time"]<=t+timedelta(minutes=mins)]
        if not bars:out[f"{mins}m"]={"mfe":None,"mae":None,"final_return":None};continue
        rs=[(b["close"]-rp)/rp for b in bars];out[f"{mins}m"]={"mfe":max(rs),"mae":min(rs),"final_return":rs[-1]}
    return out

def add_stats(cases):
    xs=[c for c in cases if c["candidate"]["ADD_STATE"]=="ADD_ALLOWED_CANDIDATE"];vals=[];mae=[]
    for c in xs:
        h=c["outcomes"].get("1440m",{});v=h.get("final_return")
        if v is not None:vals.append(v)
        for z in c["outcomes"].values():
            if z.get("mae") is not None:mae.append(z["mae"])
    return {"ADD_SUCCESS_RATE_CANDIDATE":sum(v>0 for v in vals)/len(vals) if vals else None,
            "ADD_FALSE_POSITIVE_RATE":sum(v<=0 for v in vals)/len(vals) if vals else None,
            "ADD_MAX_ADVERSE_EXCURSION":min(mae) if mae else None,
            "SAMPLE_STATUS":"ADEQUATE_FOR_DESCRIPTIVE_RESEARCH" if len(xs)>=10 else "INSUFFICIENT_SAMPLE"}

def noadd_stats(cases):
    xs=[c for c in cases if c["candidate"]["ADD_STATE"]=="NO_ADD_CANDIDATE"];p=f=0;downs=[];miss=[];n=0
    for c in xs:
        h=c["outcomes"].get("180m",{});mae=h.get("mae");fr=h.get("final_return")
        if mae is None or fr is None:continue
        n+=1;p+=mae<0;f+=fr>0 and mae>-0.005;downs.append(abs(min(0,mae)));miss.append(max(0,fr))
    return {"NO_ADD_PROTECTION_RATE":p/n if n else None,"NO_ADD_FALSE_BLOCK_RATE":f/n if n else None,
            "DOWNSIDE_AVOIDANCE":median(downs) if downs else None,"MISSED_UPSIDE":median(miss) if miss else None}

def decoupling_stats(cases):
    xs=[c for c in cases if c["features"]["decoupling"] not in ("NO_DECOUPLING","UNCONFIRMED")];counts=Counter(c["features"]["decoupling"] for c in xs);follow={}
    for m in (5,30,60,180,360,720,1440):
        vals=[c["outcomes"].get(f"{m}m",{}).get("final_return") for c in xs];vals=[v for v in vals if v is not None]
        follow[f"{m}m"]={"count":len(vals),"median_btc_return":median(vals) if vals else None}
    return {"CASE_COUNTS":dict(counts),"FOLLOW_THROUGH":follow,"SAMPLE_STATUS":"ADEQUATE_FOR_DESCRIPTIVE_RESEARCH" if len(xs)>=20 else "INSUFFICIENT_SAMPLE"}

def session_leadlag(cases):
    out={}
    for s in ("ASIA","EUROPE","US_PREMARKET","US_CASH","US_LATE"):
        vals=[c["features"]["relative"].get("lead_lag","UNCONFIRMED") for c in cases if c["features"]["session"]==s];cnt=Counter(vals)
        out[s]={"BTC_LEADS":cnt.get("BTC_LEADS_NQ",0),"NQ_LEADS":cnt.get("NQ_LEADS_BTC",0),"SIMULTANEOUS":cnt.get("SIMULTANEOUS",0),"UNCONFIRMED":cnt.get("UNCONFIRMED",0)+cnt.get("VERIFY_REQUIRED",0),"TOTAL":len(vals)}
    return out

def control_samples(bars,event_times,step=60,exclude=90,max_samples=200):
    out=[]
    for b in bars[::max(1,step)]:
        if any(abs((b["time"]-e).total_seconds())<exclude*60 for e in event_times):continue
        out.append({"time":b["time"],"classification":"NON_EVENT_CONTROL"})
        if len(out)>=max_samples:break
    return out

def aggregate_mae_mfe(cases):
    a=[];b=[]
    for c in cases:
        for v in c["outcomes"].values():
            if v.get("mae") is not None:a.append(v["mae"])
            if v.get("mfe") is not None:b.append(v["mfe"])
    ma=median(a) if a else None;mf=median(b) if b else None
    return {"MEDIAN_MAE":ma,"MEDIAN_MFE":mf,"MFE_MAE_RATIO":mf/abs(ma) if ma not in (None,0) and mf is not None else None}

def sample_adequacy(n,class_counts):
    return {"OVERALL":"ADEQUATE_FOR_DESCRIPTIVE_RESEARCH" if n>=50 else "INSUFFICIENT_SAMPLE","SPARSE_CLASSES":[k for k,v in class_counts.items() if v<10],"PRODUCTION_READY":False}

def future_leakage_contract():return {"FUTURE_LEAKAGE":False,"DECISION_INPUTS":"EVENT_TIME_OR_EARLIER_ONLY","FUTURE_DATA_ROLE":"OUTCOME_EVALUATION_ONLY"}
def add_safety_statistics(cases):
    from statistics import median
    xs=[c for c in cases if c["candidate"].get("ADD_STATE")=="ADD_ALLOWED_CANDIDATE"]
    finals=[]; maes=[]; costs=[]
    for c in xs:
        h=c["outcomes"].get("1440m",{})
        if h.get("final_return") is not None:
            finals.append(h["final_return"])
        for v in c["outcomes"].values():
            if v.get("mae") is not None:
                maes.append(v["mae"])
        costs.append(abs(float(c["features"].get("m1",{}).get("return") or 0.0)))
    return {
        "ADD_SUCCESS_RATE_CANDIDATE":sum(v>0 for v in finals)/len(finals) if finals else None,
        "ADD_FALSE_POSITIVE_RATE":sum(v<=0 for v in finals)/len(finals) if finals else None,
        "ADD_MAX_ADVERSE_EXCURSION":min(maes) if maes else None,
        "ADD_CONFIRMATION_COST":median(costs) if costs else None,
        "SAMPLE_STATUS":"ADEQUATE_FOR_DESCRIPTIVE_RESEARCH" if len(xs)>=10 else "INSUFFICIENT_SAMPLE"
    }

def no_add_statistics(cases):
    from statistics import median
    xs=[c for c in cases if c["candidate"].get("ADD_STATE")=="NO_ADD_CANDIDATE"]
    n=prot=fb=0; downs=[]; missed=[]
    for c in xs:
        h=c["outcomes"].get("180m",{})
        mae=h.get("mae"); fr=h.get("final_return")
        if mae is None or fr is None:
            continue
        n+=1
        prot += 1 if mae<0 else 0
        fb += 1 if (fr>0 and mae>-0.005) else 0
        downs.append(abs(min(0.0,mae)))
        missed.append(max(0.0,fr))
    return {
        "NO_ADD_PROTECTION_RATE":prot/n if n else None,
        "NO_ADD_FALSE_BLOCK_RATE":fb/n if n else None,
        "DOWNSIDE_AVOIDANCE":median(downs) if downs else None,
        "MISSED_UPSIDE":median(missed) if missed else None,
        "SAMPLE_STATUS":"ADEQUATE_FOR_DESCRIPTIVE_RESEARCH" if n>=10 else "INSUFFICIENT_SAMPLE"
    }

def exit_warning_statistics(cases):
    from statistics import median
    xs=[c for c in cases if c["candidate"].get("EXIT_WARNING_STATE")=="EXIT_WARNING_CANDIDATE"]
    finals=[]; maes=[]; mfes=[]
    for c in xs:
        h=c["outcomes"].get("180m",{})
        if h.get("final_return") is None:
            continue
        finals.append(h["final_return"])
        if h.get("mae") is not None:
            maes.append(h["mae"])
        if h.get("mfe") is not None:
            mfes.append(h["mfe"])
    return {
        "EXIT_WARNING_FALSE_RATE":sum(v>0 for v in finals)/len(finals) if finals else None,
        "POST_WARNING_MAE_MEDIAN":median(maes) if maes else None,
        "POST_WARNING_MFE_MEDIAN":median(mfes) if mfes else None,
        "SAMPLE_STATUS":"ADEQUATE_FOR_DESCRIPTIVE_RESEARCH" if len(finals)>=10 else "INSUFFICIENT_SAMPLE"
    }

def decoupling_statistics(cases):
    from collections import Counter
    from statistics import median
    xs=[c for c in cases if c["features"].get("decoupling") not in ("NO_DECOUPLING","UNCONFIRMED",None)]
    counts=Counter(c["features"].get("decoupling") for c in xs)
    follow={}
    for mins in (5,30,60,180,360,720,1440):
        vals=[c["outcomes"].get(f"{mins}m",{}).get("final_return") for c in xs]
        vals=[v for v in vals if v is not None]
        follow[f"{mins}m"]={"count":len(vals),"median_btc_return":median(vals) if vals else None}
    return {
        "CASE_COUNTS":dict(counts),
        "FOLLOW_THROUGH":follow,
        "SAMPLE_STATUS":"ADEQUATE_FOR_DESCRIPTIVE_RESEARCH" if len(xs)>=20 else "INSUFFICIENT_SAMPLE"
    }

def session_leadlag(cases):
    from collections import Counter
    out={}
    for s in ("ASIA","EUROPE","US_PREMARKET","US_CASH","US_LATE"):
        vals=[c["features"].get("relative",{}).get("lead_lag","UNCONFIRMED") for c in cases if c.get("SESSION")==s]
        cnt=Counter(vals)
        out[s]={
            "BTC_LEADS":cnt.get("BTC_LEADS_NQ",0),
            "NQ_LEADS":cnt.get("NQ_LEADS_BTC",0),
            "SIMULTANEOUS":cnt.get("SIMULTANEOUS",0),
            "UNCONFIRMED":cnt.get("UNCONFIRMED",0)+cnt.get("VERIFY_REQUIRED",0),
            "TOTAL":len(vals)
        }
    return out

def control_samples(btc_m1,event_times,step_minutes=60,exclusion_minutes=90,max_samples=200):
    out=[]
    if not btc_m1:
        return out
    for b in btc_m1[::max(1,step_minutes)]:
        if any(abs((b["time"]-e).total_seconds())<exclusion_minutes*60 for e in event_times):
            continue
        out.append({"time":b["time"],"close":b["close"],"classification":"NON_EVENT_CONTROL"})
        if len(out)>=max_samples:
            break
    return out

def aggregate_mae_mfe(cases):
    from statistics import median
    maes=[]; mfes=[]
    for c in cases:
        for v in c["outcomes"].values():
            if v.get("mae") is not None:
                maes.append(v["mae"])
            if v.get("mfe") is not None:
                mfes.append(v["mfe"])
    med_mae=median(maes) if maes else None
    med_mfe=median(mfes) if mfes else None
    return {
        "MEDIAN_MAE":med_mae,
        "MEDIAN_MFE":med_mfe,
        "MFE_MAE_RATIO":med_mfe/abs(med_mae) if med_mae not in (None,0) and med_mfe is not None else None
    }

def sample_adequacy(independent_count,class_counts):
    sparse=[k for k,v in class_counts.items() if v<10]
    return {
        "OVERALL":"ADEQUATE_FOR_DESCRIPTIVE_RESEARCH" if independent_count>=50 else "INSUFFICIENT_SAMPLE",
        "SPARSE_CLASSES":sparse,
        "PRODUCTION_READY":False
    }

def control_samples(btc_m1,event_times,step_minutes=60,exclusion_minutes=90,max_samples=200):
    """
    Build non-event controls defensively.
    Test/replay inputs may expose close, mid, price, or BID/ASK.
    """
    out=[]
    if not btc_m1:
        return out
    step=max(1,int(step_minutes))
    for b in btc_m1[::step]:
        t=b.get("time")
        if t is None:
            continue
        if any(abs((t-e).total_seconds()) < exclusion_minutes*60 for e in event_times):
            continue

        value=b.get("close")
        if value is None:
            value=b.get("mid")
        if value is None:
            value=b.get("price")
        if value is None and b.get("BID") is not None and b.get("ASK") is not None:
            try:
                value=(float(b["BID"])+float(b["ASK"]))/2.0
            except Exception:
                value=None

        out.append({
            "time":t,
            "close":value,
            "classification":"NON_EVENT_CONTROL"
        })
        if len(out)>=max_samples:
            break
    return out

# --- TASK-BTC-EVENT-REPLAY-004 zero-count reporting contract ---
EXPECTED_CASE_CATEGORIES = (
    "BULLISH_TRANSITION",
    "BEARISH_TRANSITION",
    "BULLISH_CONTINUATION",
    "BEARISH_CONTINUATION",
    "HEALTHY_LONG_PULLBACK",
    "FAILED_LONG_PULLBACK",
    "FALSE_BULLISH_REVERSAL",
    "FALSE_BEARISH_REVERSAL",
    "BTC_NQ_DECOUPLING",
)

def normalize_case_counts(counts):
    """Return every expected case category as an explicit numeric count."""
    src = counts or {}
    out = {name: 0 for name in EXPECTED_CASE_CATEGORIES}
    for key, value in dict(src).items():
        if key in out:
            try:
                out[key] = int(value)
            except (TypeError, ValueError):
                out[key] = 0
    return out

def reporting_safety_snapshot(summary):
    """Reporting-only normalization. Does not create trading authority."""
    summary = summary or {}
    add_stats = dict(summary.get("ADD_STATS") or {})
    no_add_stats = dict(summary.get("NO_ADD_STATS") or {})
    mae_mfe = dict(summary.get("MAE_MFE") or {})
    adequacy = dict(summary.get("SAMPLE_ADEQUACY") or {})
    return {
        "CASE_COUNTS": normalize_case_counts(summary.get("CASE_COUNTS")),
        "SAMPLE_ADEQUACY": adequacy.get("OVERALL", "INSUFFICIENT_SAMPLE"),
        "PRODUCTION_READY": bool(adequacy.get("PRODUCTION_READY", False)),
        "ADD_SUCCESS_RATE_CANDIDATE": add_stats.get("ADD_SUCCESS_RATE_CANDIDATE"),
        "ADD_SAMPLE_STATUS": add_stats.get("SAMPLE_STATUS", "INSUFFICIENT_SAMPLE"),
        "NO_ADD_PROTECTION_RATE": no_add_stats.get("NO_ADD_PROTECTION_RATE"),
        "NO_ADD_SAMPLE_STATUS": no_add_stats.get("SAMPLE_STATUS", "INSUFFICIENT_SAMPLE"),
        "MEDIAN_MAE": mae_mfe.get("MEDIAN_MAE"),
        "MEDIAN_MFE": mae_mfe.get("MEDIAN_MFE"),
        "MAE_MFE_CLASSIFICATION": "DESCRIPTIVE_RESEARCH_ONLY",
        "BTC_NQ_PREDICTIVE_STATUS": "NO_PREDICTIVE_CLAIM",
        "PRODUCTION_THRESHOLD_PROMOTION": False,
    }
# --- END TASK-BTC-EVENT-REPLAY-004 ---

