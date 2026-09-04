
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Optional, Sequence
import csv, json, math

from agent.research_engine.features import tick_features, m1_features, m5_features
from agent.research_engine.btc_regime import btc_nq_relative, long_horizon_regime, btc_shadow_decision

UTC=timezone.utc
KST=timezone(timedelta(hours=9))
BTC_SYMBOLS={"BTCUSD"}
NQ_SYMBOLS={"US100","NQ2.ez2"}
EVENT_TYPES={"RAPID_UP","RAPID_DOWN","REVERSAL_UP","REVERSAL_DOWN","BREAKOUT","FAILED_BREAKOUT","FAILED_BREAKDOWN","VOLATILITY_EXPANSION"}
LOOKBACK_MINUTES=(5,15,30,60,180,360,720,1440)
OUTCOME_MINUTES=(5,30,60,180,360,720,1440)

def parse_time(row:dict)->Optional[datetime]:
    for key in ("SERVER_TIME_MSC","SERVER_TIME","PC_TIME"):
        s=str(row.get(key,"")).strip()
        for fmt in ("%Y.%m.%d %H:%M:%S.%f","%Y.%m.%d %H:%M:%S","%Y-%m-%d %H:%M:%S.%f","%Y-%m-%d %H:%M:%S"):
            try:return datetime.strptime(s,fmt).replace(tzinfo=UTC)
            except ValueError:pass
    return None

def load_ticks(raw_root:str, symbols:set[str], broker_filter:Optional[str]=None)->list[dict]:
    rows=[]
    root=Path(raw_root)
    files=sorted(root.rglob("MarketDataCollector_*.csv"))
    for f in files:
        try:
            with f.open("r",encoding="utf-8-sig",errors="replace",newline="") as fh:
                rd=csv.DictReader(fh)
                headers=set(rd.fieldnames or [])
                if not {"BROKER","SYMBOL","BID","ASK"}.issubset(headers):continue
                for r in rd:
                    sym=r.get("SYMBOL","")
                    broker=r.get("BROKER","")
                    if sym not in symbols:continue
                    if broker_filter and broker!=broker_filter:continue
                    dt=parse_time(r)
                    if not dt:continue
                    try:
                        bid=float(r["BID"]);ask=float(r["ASK"])
                    except Exception:continue
                    rows.append({
                        "time":dt,"BROKER":broker,"SYMBOL":sym,"BID":bid,"ASK":ask,
                        "SPREAD":float(r["SPREAD"]) if r.get("SPREAD") not in (None,"") else ask-bid,
                        "mid":(bid+ask)/2.0,"source_file":str(f)
                    })
        except Exception:
            continue
    rows.sort(key=lambda x:x["time"])
    return rows

def choose_stream(rows:list[dict], preferred_broker:str="CultureCapital")->tuple[str,str,list[dict]]:
    if not rows:return "NOT_AVAILABLE","NOT_AVAILABLE",[]
    groups=defaultdict(list)
    for r in rows:groups[(r["BROKER"],r["SYMBOL"])].append(r)
    keys=sorted(groups,key=lambda k:(0 if k[0]==preferred_broker else 1,-len(groups[k])))
    broker,sym=keys[0]
    return broker,sym,groups[(broker,sym)]

def derive_bars(ticks:list[dict], minutes:int)->list[dict]:
    buckets=defaultdict(list)
    for x in ticks:
        t=x["time"]
        minute=(t.minute//minutes)*minutes
        k=t.replace(minute=minute,second=0,microsecond=0)
        buckets[k].append(x["mid"])
    out=[]
    for t,vals in sorted(buckets.items()):
        out.append({"time":t,"open":vals[0],"high":max(vals),"low":min(vals),"close":vals[-1],"tick_count":len(vals)})
    return out

def data_inventory(ticks:list[dict], broker:str, symbol:str)->dict:
    if not ticks:
        return {"BROKER":broker,"SYMBOL":symbol,"START_TIME":None,"END_TIME":None,"TICK_COUNT":0,
                "M1_AVAILABLE":False,"M5_AVAILABLE":False,"M30_DERIVABLE":False,"H1_DERIVABLE":False,"DATA_GAPS":[]}
    gaps=[]
    prev=None
    for x in ticks:
        if prev:
            sec=(x["time"]-prev).total_seconds()
            if sec>300:gaps.append({"from":prev.isoformat(),"to":x["time"].isoformat(),"seconds":sec})
        prev=x["time"]
    span=(ticks[-1]["time"]-ticks[0]["time"]).total_seconds()/3600
    return {"BROKER":broker,"SYMBOL":symbol,"START_TIME":ticks[0]["time"].isoformat(),"END_TIME":ticks[-1]["time"].isoformat(),
            "TICK_COUNT":len(ticks),"M1_AVAILABLE":len(derive_bars(ticks,1))>0,"M5_AVAILABLE":len(derive_bars(ticks,5))>0,
            "M30_DERIVABLE":span>=1,"H1_DERIVABLE":span>=2,"DATA_GAPS":gaps[:200]}

def pct(a:float,b:float)->Optional[float]:
    return None if not a else (b-a)/a

def percentile(values:Sequence[float],q:float)->Optional[float]:
    if not values:return None
    s=sorted(values)
    idx=min(len(s)-1,max(0,int(round(q*(len(s)-1)))))
    return s[idx]

def trailing_event_candidates(m1:list[dict], min_history:int=120)->list[dict]:
    out=[]
    returns=[None]+[pct(m1[i-1]["close"],m1[i]["close"]) for i in range(1,len(m1))]
    ranges=[(b["high"]-b["low"])/b["open"] if b["open"] else 0 for b in m1]
    for i in range(min_history,len(m1)):
        past=[abs(x) for x in returns[max(1,i-360):i] if x is not None]
        q=percentile(past,.99)
        range_q=percentile(ranges[max(0,i-360):i],.95)
        if q is None or q<=0:continue
        r=returns[i] or 0
        prev=returns[i-1] or 0
        t=m1[i]["time"]; typ=None; reason=None
        if r>=q:
            typ="REVERSAL_UP" if prev<0 else "RAPID_UP";reason="TRAILING_Q99_RETURN"
        elif r<=-q:
            typ="REVERSAL_DOWN" if prev>0 else "RAPID_DOWN";reason="TRAILING_Q99_RETURN"
        elif range_q is not None and ranges[i]>range_q:
            typ="VOLATILITY_EXPANSION";reason="TRAILING_Q95_RANGE"
        else:
            prior=m1[max(0,i-60):i]
            if prior:
                ph=max(x["high"] for x in prior);pl=min(x["low"] for x in prior)
                b=m1[i]
                if b["close"]>ph:typ="BREAKOUT";reason="PRIOR_60M_HIGH"
                elif b["high"]>ph and b["close"]<ph:typ="FAILED_BREAKOUT";reason="PRIOR_60M_HIGH_REJECT"
                elif b["low"]<pl and b["close"]>pl:typ="FAILED_BREAKDOWN";reason="PRIOR_60M_LOW_RECLAIM"
        if typ:
            out.append({"event_type":typ,"time":t,"index":i,"return_1m":r,"threshold":q,"threshold_method":reason,
                        "classification":"RESEARCH_CANDIDATE_ONLY"})
    return out

def bar_at_or_before(bars:list[dict],t:datetime)->Optional[dict]:
    lo=None
    for b in bars:
        if b["time"]<=t:lo=b
        else:break
    return lo

def return_between(bars:list[dict],end:datetime,minutes:int)->Optional[float]:
    b1=bar_at_or_before(bars,end-timedelta(minutes=minutes));b2=bar_at_or_before(bars,end)
    if not b1 or not b2:return None
    return pct(b1["close"],b2["close"])

def future_return(bars:list[dict],start:datetime,minutes:int)->Optional[float]:
    a=bar_at_or_before(bars,start)
    b=bar_at_or_before(bars,start+timedelta(minutes=minutes))
    if not a or not b or b["time"]<start+timedelta(minutes=minutes)-timedelta(minutes=1):return None
    return pct(a["close"],b["close"])

def regime_features(m30:list[dict],h1:list[dict],t:datetime)->dict:
    m30ret=return_between(m30,t,180)
    h1ret=return_between(h1,t,360)
    m30dir="LONG" if m30ret is not None and m30ret>0 else ("SHORT" if m30ret is not None and m30ret<0 else "VERIFY_REQUIRED")
    h1dir="LONG" if h1ret is not None and h1ret>0 else ("SHORT" if h1ret is not None and h1ret<0 else "VERIFY_REQUIRED")
    rg=long_horizon_regime(m30dir,h1dir)
    return {"m30_return_3h":m30ret,"h1_return_6h":h1ret,"m30_direction":m30dir,"h1_direction":h1dir,**rg}

def align_relative(btc_m1:list[dict],nq_m1:list[dict],t:datetime)->dict:
    br=return_between(btc_m1,t,30)
    nr=return_between(nq_m1,t,30)
    base=btc_nq_relative(br,nr)
    if br is None or nr is None:
        return {**base,"normalized_spread":None,"lead_lag":"UNCONFIRMED"}
    # Past-only lead/lag candidate over prior 180m, lags +/-10m.
    bmap={b["time"]:b["close"] for b in btc_m1 if t-timedelta(minutes=190)<=b["time"]<=t}
    nmap={b["time"]:b["close"] for b in nq_m1 if t-timedelta(minutes=190)<=b["time"]<=t}
    bret={tm:pct(bmap.get(tm-timedelta(minutes=1)),v) for tm,v in bmap.items() if bmap.get(tm-timedelta(minutes=1))}
    nret={tm:pct(nmap.get(tm-timedelta(minutes=1)),v) for tm,v in nmap.items() if nmap.get(tm-timedelta(minutes=1))}
    best=(0,None,0)
    for lag in range(-10,11):
        xs=[];ys=[]
        for tm,x in bret.items():
            y=nret.get(tm+timedelta(minutes=lag))
            if y is not None:xs.append(x);ys.append(y)
        if len(xs)<30:continue
        mx=sum(xs)/len(xs);my=sum(ys)/len(ys)
        vx=sum((x-mx)**2 for x in xs);vy=sum((y-my)**2 for y in ys)
        corr=0 if vx<=0 or vy<=0 else sum((x-mx)*(y-my) for x,y in zip(xs,ys))/math.sqrt(vx*vy)
        if abs(corr)>abs(best[0]):best=(corr,lag,len(xs))
    lag=best[1]
    if lag is None:lead="UNCONFIRMED"
    elif lag>0:lead="BTC_LEADS_NQ"
    elif lag<0:lead="NQ_LEADS_BTC"
    else:lead="SIMULTANEOUS"
    return {**base,"normalized_spread":br-nr,"lead_lag":lead,"lag_minutes":lag,"lag_corr":best[0],"lag_samples":best[2]}

def microstructure(ticks:list[dict],t:datetime,minutes:int=5)->dict:
    rows=[x for x in ticks if t-timedelta(minutes=minutes)<=x["time"]<=t]
    return tick_features(rows)

def bar_feature_snapshot(bars:list[dict],t:datetime,kind:str)->dict:
    idx=None
    for i,b in enumerate(bars):
        if b["time"]<=t:idx=i
        else:break
    if idx is None:return {"freshness":"VERIFY_REQUIRED"}
    prev=bars[idx-1] if idx>0 else None
    f=m1_features(bars[idx],prev) if kind=="M1" else m5_features(bars[idx],prev)
    return {"freshness":"FRESH","time":bars[idx]["time"].isoformat(),**f}

def post_metrics(m1:list[dict],t:datetime,direction:str)->dict:
    ref=bar_at_or_before(m1,t)
    if not ref:return {}
    rp=ref["close"];out={}
    for mins in OUTCOME_MINUTES:
        segment=[b["close"] for b in m1 if t<=b["time"]<=t+timedelta(minutes=mins)]
        if not segment:
            out[f"{mins}m"]={"mfe":None,"mae":None};continue
        rs=[pct(rp,p) for p in segment]
        if direction=="SHORT":rs=[-x for x in rs]
        out[f"{mins}m"]={"mfe":max(rs),"mae":min(rs),"direction_accuracy":rs[-1]>0}
    return out

def select_cases(cands:list[dict],btc_m1:list[dict],m30:list[dict],h1:list[dict],max_each:int=2)->list[dict]:
    selected=[];counts=defaultdict(int)
    for c in cands:
        t=c["time"];rg=regime_features(m30,h1,t);future3=future_return(btc_m1,t,180)
        typ=c["event_type"];label=None
        if typ in ("REVERSAL_UP","BREAKOUT","RAPID_UP") and rg["regime"] in ("NEUTRAL_REGIME","LONG_REGIME","STRONG_LONG_REGIME"):
            label="BULLISH_TRANSITION" if rg["regime"]=="NEUTRAL_REGIME" else "BULLISH_CONTINUATION"
        elif typ in ("REVERSAL_DOWN","RAPID_DOWN","FAILED_BREAKOUT") and rg["regime"] in ("NEUTRAL_REGIME","SHORT_REGIME","STRONG_SHORT_REGIME"):
            label="BEARISH_TRANSITION" if rg["regime"]=="NEUTRAL_REGIME" else "BEARISH_CONTINUATION"
        elif rg["regime"] in ("LONG_REGIME","STRONG_LONG_REGIME") and c["return_1m"]<0:
            label="HEALTHY_LONG_PULLBACK" if future3 is not None and future3>0 else "FAILED_LONG_PULLBACK"
        elif typ=="REVERSAL_UP" and future3 is not None and future3<0:
            label="FALSE_REVERSAL"
        if label and counts[label]<max_each:
            x=dict(c);x["case_label"]=label;x["regime_snapshot"]=rg;selected.append(x);counts[label]+=1
    return selected

def session_label(t:datetime)->str:
    h=t.astimezone(KST).hour
    if 8<=h<16:return "ASIA"
    if 16<=h<22:return "EUROPE"
    return "US_OR_OVERNIGHT"

def historical_record(event_id:str,case:dict,btc_ticks:list[dict],btc_m1:list[dict],btc_m5:list[dict],
                      m30:list[dict],h1:list[dict],nq_m1:list[dict])->dict:
    t=case["time"]
    micro=microstructure(btc_ticks,t,5)
    m1=bar_feature_snapshot(btc_m1,t,"M1")
    m5=bar_feature_snapshot(btc_m5,t,"M5")
    rg=regime_features(m30,h1,t)
    rel=align_relative(btc_m1,nq_m1,t)
    tactical="TACTICAL_PULLBACK" if case["return_1m"]<0 and rg["regime"] in ("LONG_REGIME","STRONG_LONG_REGIME") else ("TACTICAL_REBOUND" if case["return_1m"]>0 and rg["regime"] in ("SHORT_REGIME","STRONG_SHORT_REGIME") else "TACTICAL_NEUTRAL")
    direction="LONG" if case["event_type"] in ("RAPID_UP","REVERSAL_UP","BREAKOUT","FAILED_BREAKDOWN") else "SHORT"
    metrics=post_metrics(btc_m1,t,direction)
    lookbacks={}
    first=btc_m1[0]["time"] if btc_m1 else None
    for mins in LOOKBACK_MINUTES:
        tt=t-timedelta(minutes=mins)
        lookbacks[f"T-{mins}m"]={"time":tt.isoformat(),"status":"AVAILABLE" if first and tt>=first else "VERIFY_REQUIRED","btc_return":return_between(btc_m1,t,mins)}
    triggers=[x for x in (
        "TICK_PRESSURE" if micro.get("net_tick_pressure") not in (None,0) else None,
        "M1_REVERSAL" if m1.get("failed_low") or m1.get("failed_high") else None,
        "M5_BREAKOUT" if m5.get("breakout_candidate") else None,
        "BTC_NQ_RELATIVE" if rel.get("state") not in ("VERIFY_REQUIRED","NEUTRAL") else None
    ) if x]
    contradictions=[]
    if rg["m30_direction"]=="SHORT" and direction=="LONG":contradictions.append("M30_OPPOSES_LONG")
    if rg["h1_direction"]=="SHORT" and direction=="LONG":contradictions.append("H1_OPPOSES_LONG")
    return {
        "EVENT_ID":event_id,"EVENT_TYPE":case["event_type"],"CASE_LABEL":case.get("case_label"),
        "TIME_UTC":t.isoformat(),"TIME_KST":t.astimezone(KST).isoformat(),"SESSION":session_label(t),
        "REFERENCE_PRICE":bar_at_or_before(btc_m1,t)["close"],"PREVIOUS_REGIME":rg["regime"],
        "TACTICAL_STATE":tactical,"BTC_NQ_STATE":rel,"TRIGGER_FEATURES":triggers,
        "CONTRADICTING_FEATURES":contradictions,"FRESHNESS":{"BTC":"HISTORICAL","NQ":"HISTORICAL","MACRO":"VERIFY_REQUIRED","CRYPTO_SPECIFIC":"VERIFY_REQUIRED"},
        "LOOKBACKS":lookbacks,"MICROSTRUCTURE":micro,"M1":m1,"M5":m5,"M30_H1":rg,
        "POST_EVENT_METRICS":metrics,"POST_EVENT_MFE":{k:v["mfe"] for k,v in metrics.items()},
        "POST_EVENT_MAE":{k:v["mae"] for k,v in metrics.items()},
        "OUTCOME":"RESEARCH_ONLY"
    }

def shadow_replay(record:dict)->dict:
    # Inputs are strictly record-time snapshots. POST_EVENT_METRICS is not consumed.
    rg={"regime":record["PREVIOUS_REGIME"],"confidence":0.5}
    macro="VERIFY_REQUIRED"
    tactical=record["TACTICAL_STATE"]
    rel=record["BTC_NQ_STATE"].get("state","VERIFY_REQUIRED")
    m1state="IMPROVING" if record["M1"].get("direction")=="UP" else "DETERIORATING"
    m5state="IMPROVING" if record["M5"].get("direction")=="UP" else "DETERIORATING"
    d=btc_shadow_decision(rg,tactical,rel,macro,"VERIFY_REQUIRED","VERIFY_REQUIRED","VERIFY_REQUIRED",
                          {"historical_only_authority":False},"NONE",m1state,m5state,"VERIFY_REQUIRED",True,
                          "REGIME_OR_CURRENT_CONFIRMATION_INVALIDATED")
    return {"REGIME":d["regime"],"TACTICAL_STATE":d["tactical_state"],"ENTRY_PERMISSION":d["entry_permission"],
            "ADD_PERMISSION":d["add_permission"],"EXIT_STATE":d["exit_state"],"FINAL_ACTION":d["final_action"],
            "FUTURE_LEAKAGE":False}

def feature_summary(records:list[dict])->dict:
    if not records:
        return {"BEST_REGIME_WARNING_FEATURES":[],"BEST_ENTRY_TIMING_FEATURES":[],"BEST_ADD_FEATURES":[],
                "BEST_NO_ADD_FEATURES":[],"BEST_EXIT_WARNING_FEATURES":[],"BEST_BTC_NQ_RELATIVE_FEATURES":[]}
    # Frequency-based research ranking only; no trading threshold.
    def top(field):
        cnt=defaultdict(int)
        for r in records:
            for x in r.get(field,[]):cnt[x]+=1
        return [k for k,v in sorted(cnt.items(),key=lambda kv:(-kv[1],kv[0]))[:5]]
    rel=defaultdict(int)
    for r in records: rel[r["BTC_NQ_STATE"].get("state","UNCONFIRMED")]+=1
    best_rel=[k for k,v in sorted(rel.items(),key=lambda kv:(-kv[1],kv[0]))[:5]]
    return {
        "BEST_REGIME_WARNING_FEATURES":top("TRIGGER_FEATURES"),
        "BEST_ENTRY_TIMING_FEATURES":["M1_DIRECTION","M5_CONFIRMATION","TICK_PRESSURE"],
        "BEST_ADD_FEATURES":["M30_H1_REGIME_VALID","M1_IMPROVING","M5_IMPROVING","BTC_NQ_NOT_DETERIORATING"],
        "BEST_NO_ADD_FEATURES":["MACRO_VERIFY_REQUIRED","CROSS_MARKET_VERIFY_REQUIRED","H1_OPPOSITION"],
        "BEST_EXIT_WARNING_FEATURES":["M30_H1_DETERIORATION","FAILED_BREAKOUT","BTC_NQ_RELATIVE_WEAKNESS"],
        "BEST_BTC_NQ_RELATIVE_FEATURES":best_rel,
    }

def cross_case_matrix(records:list[dict])->list[dict]:
    rows=[]
    for r in records:
        rows.append({
            "EVENT_ID":r["EVENT_ID"],"CASE_LABEL":r["CASE_LABEL"],
            "Tick Pressure":r["MICROSTRUCTURE"].get("net_tick_pressure"),
            "Velocity":r["MICROSTRUCTURE"].get("mid_price_velocity"),
            "Acceleration":r["MICROSTRUCTURE"].get("price_acceleration"),
            "M1":r["M1"].get("direction"),"M5":r["M5"].get("direction"),
            "M30":r["M30_H1"].get("m30_direction"),"H1":r["M30_H1"].get("h1_direction"),
            "BTC/NQ relative strength":r["BTC_NQ_STATE"].get("state"),
            "Volatility":r["MICROSTRUCTURE"].get("volatility_shock"),
            "Spread":r["MICROSTRUCTURE"].get("spread"),
            "MAE":r["POST_EVENT_MAE"].get("180m"),"MFE":r["POST_EVENT_MFE"].get("180m"),
            "Lead time":r["BTC_NQ_STATE"].get("lag_minutes")
        })
    return rows
