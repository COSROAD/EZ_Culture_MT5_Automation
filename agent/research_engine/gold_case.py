
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import csv, json, math, statistics
from typing import Iterable, Optional

from .features import tick_features, m1_features, m5_features

LOOKBACK_SECONDS = (60, 180, 300, 600, 900, 1200, 1800, 3600, 5400)

@dataclass(frozen=True)
class CandidatePoint:
    name: str
    time: str
    price: float
    lead_seconds: float
    confidence: str
    freshness: str
    evidence: dict

def parse_time(row: dict) -> Optional[datetime]:
    for key in ("SERVER_TIME_MSC","SERVER_TIME","PC_TIME"):
        v = row.get(key)
        if not v:
            continue
        s = str(v).strip()
        for fmt in ("%Y.%m.%d %H:%M:%S.%f","%Y.%m.%d %H:%M:%S","%Y-%m-%d %H:%M:%S.%f","%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                pass
    return None

def load_ticks(raw_root: str, broker: str, symbol_contains: str) -> list[dict]:
    root = Path(raw_root)
    out=[]
    for f in sorted(root.rglob("MarketDataCollector_*.csv")):
        try:
            with f.open("r",encoding="utf-8-sig",errors="replace",newline="") as fh:
                r=csv.DictReader(fh)
                headers=set(r.fieldnames or [])
                if not {"BROKER","SYMBOL","BID","ASK"}.issubset(headers):
                    continue
                for row in r:
                    if row.get("BROKER") != broker:
                        continue
                    sym=row.get("SYMBOL","")
                    if symbol_contains.upper() not in sym.upper():
                        continue
                    dt=parse_time(row)
                    if not dt:
                        continue
                    try:
                        bid=float(row["BID"]); ask=float(row["ASK"])
                    except Exception:
                        continue
                    out.append({
                        "time":dt,
                        "BID":bid,
                        "ASK":ask,
                        "SPREAD":float(row["SPREAD"]) if row.get("SPREAD") not in (None,"") else ask-bid,
                        "mid":(bid+ask)/2.0,
                        "symbol":sym,
                        "broker":broker,
                        "source_file":str(f),
                    })
        except Exception:
            continue
    out.sort(key=lambda x:x["time"])
    return out

def minute_bars(ticks: list[dict]) -> list[dict]:
    buckets=defaultdict(list)
    for t in ticks:
        key=t["time"].replace(second=0,microsecond=0)
        buckets[key].append(t)
    bars=[]
    for tm, rows in sorted(buckets.items()):
        vals=[r["mid"] for r in rows]
        bars.append({"time":tm,"open":vals[0],"high":max(vals),"low":min(vals),"close":vals[-1],"tick_count":len(rows)})
    return bars

def five_minute_bars(m1: list[dict]) -> list[dict]:
    buckets=defaultdict(list)
    for b in m1:
        minute=(b["time"].minute//5)*5
        key=b["time"].replace(minute=minute,second=0,microsecond=0)
        buckets[key].append(b)
    bars=[]
    for tm, rows in sorted(buckets.items()):
        rows=sorted(rows,key=lambda x:x["time"])
        bars.append({"time":tm,"open":rows[0]["open"],"high":max(x["high"] for x in rows),"low":min(x["low"] for x in rows),"close":rows[-1]["close"],"m1_count":len(rows)})
    return bars

def returns(bars: list[dict]) -> list[float]:
    out=[]
    for a,b in zip(bars,bars[1:]):
        out.append((b["close"]-a["close"])/a["close"] if a["close"] else 0.0)
    return out

def resolve_reversal_case(m1: list[dict]) -> dict:
    if len(m1) < 100:
        return {"status":"VERIFY_REQUIRED","reason":"INSUFFICIENT_M1_BARS"}
    rets=returns(m1)
    absret=sorted(abs(x) for x in rets)
    q=absret[min(len(absret)-1,max(0,int(round(.99*(len(absret)-1)))))]
    cands=[]
    for i,r in enumerate(rets, start=1):
        prev=rets[i-2] if i>=2 else 0.0
        if r>=q and prev<0:
            cands.append((i,r,prev))
    if not cands:
        return {"status":"VERIFY_REQUIRED","reason":"NO_REVERSAL_UP_CANDIDATE"}
    # Prefer a candidate with meaningful subsequent follow-through.
    scored=[]
    for i,r,prev in cands:
        future=m1[i:min(len(m1),i+31)]
        if not future:
            continue
        start=m1[i]["close"]
        high=max(x["high"] for x in future)
        low=min(x["low"] for x in future)
        follow=(high-start)/start if start else 0
        mae=(low-start)/start if start else 0
        scored.append((follow, -abs(mae), i, r, prev))
    if not scored:
        return {"status":"VERIFY_REQUIRED","reason":"NO_FOLLOWTHROUGH_WINDOW"}
    scored.sort(reverse=True)
    _,_,i,r,prev=scored[0]
    pivot=m1[i]["time"]
    search=m1[max(0,i-60):i+1]
    low_bar=min(search,key=lambda x:x["low"])
    future=m1[i:min(len(m1),i+61)]
    post_high=max(future,key=lambda x:x["high"])
    return {
        "status":"PASS",
        "threshold_method":"M1_ABS_RETURN_Q99_RESEARCH_CANDIDATE",
        "threshold_value":q,
        "event_start_time":low_bar["time"],
        "pivot_time":pivot,
        "event_low":low_bar["low"],
        "pivot_price":m1[i]["close"],
        "post_event_high_time":post_high["time"],
        "post_event_high":post_high["high"],
        "pivot_index":i,
    }

def ticks_between(ticks: list[dict], start: datetime, end: datetime) -> list[dict]:
    return [x for x in ticks if start <= x["time"] <= end]

def window_snapshot(ticks: list[dict], pivot: datetime, seconds: int) -> dict:
    rows=ticks_between(ticks,pivot-timedelta(seconds=seconds),pivot)
    feat=tick_features(rows)
    feat["window_seconds"]=seconds
    if rows:
        feat["start_time"]=rows[0]["time"].isoformat()
        feat["end_time"]=rows[-1]["time"].isoformat()
        feat["tick_rate"]=len(rows)/seconds
        feat["spread_mean"]=statistics.mean(float(r["SPREAD"]) for r in rows)
        feat["spread_max"]=max(float(r["SPREAD"]) for r in rows)
    else:
        feat["tick_rate"]=0
        feat["spread_mean"]=None
        feat["spread_max"]=None
    return feat

def rolling_tick_series(ticks: list[dict], start: datetime, end: datetime, window_seconds: int=60, step_seconds: int=10) -> list[dict]:
    out=[]
    t=start
    while t<=end:
        rows=ticks_between(ticks,t-timedelta(seconds=window_seconds),t)
        if rows:
            f=tick_features(rows)
            f["time"]=t
            f["price"]=rows[-1]["mid"]
            f["spread_mean"]=statistics.mean(float(r["SPREAD"]) for r in rows)
            f["spread_max"]=max(float(r["SPREAD"]) for r in rows)
            out.append(f)
        t += timedelta(seconds=step_seconds)
    return out

def earliest_candidates(ticks: list[dict], m1: list[dict], m5: list[dict], case: dict) -> dict:
    pivot=case["pivot_time"]
    series=rolling_tick_series(ticks,pivot-timedelta(minutes=30),pivot+timedelta(minutes=30))
    if not series:
        return {"status":"VERIFY_REQUIRED"}
    # Research candidates only: changes in observed sign/structure, not production thresholds.
    pressure_rev=None; velocity_decay=None; accel_rev=None; spread_norm=None
    for a,b in zip(series,series[1:]):
        if pressure_rev is None and a.get("net_tick_pressure",0)<0 and b.get("net_tick_pressure",0)>=0:
            pressure_rev=b
        if velocity_decay is None and a.get("mid_price_velocity",0)<0 and b.get("mid_price_velocity",0)>a.get("mid_price_velocity",0):
            velocity_decay=b
        if accel_rev is None and a.get("price_acceleration",0)<0 and b.get("price_acceleration",0)>=0:
            accel_rev=b
    spreads=[x["spread_mean"] for x in series if x.get("spread_mean") is not None]
    if spreads:
        med=statistics.median(spreads)
        peak_idx=max(range(len(series)),key=lambda i: series[i].get("spread_mean") or -1)
        for x in series[peak_idx+1:]:
            if x.get("spread_mean") is not None and x["spread_mean"] <= med:
                spread_norm=x; break

    # M1 first failed-low / higher-low and positive body candidate.
    m1_failed=None; m1_long=None; m1_confirm=None
    start_idx=max(1,case["pivot_index"]-30)
    end_idx=min(len(m1),case["pivot_index"]+31)
    for i in range(start_idx,end_idx):
        prev={"high":m1[i-1]["high"],"low":m1[i-1]["low"]}
        f=m1_features(m1[i],prev)
        if m1_failed is None and f.get("failed_low"):
            m1_failed=(m1[i],f)
        if m1_long is None and m1[i]["close"]>m1[i]["open"] and (f.get("failed_low") or f.get("higher_low")):
            m1_long=(m1[i],f)
        if m1_confirm is None and i>=2 and m1[i]["close"]>m1[i]["open"] and m1[i-1]["close"]>m1[i-1]["open"]:
            m1_confirm=(m1[i],f)

    # M5 first positive confirmation after pivot.
    m5_confirm=None
    for i,b in enumerate(m5):
        if b["time"] < pivot:
            continue
        prev=None if i==0 else {"high":m5[i-1]["high"],"low":m5[i-1]["low"]}
        f=m5_features(b,prev)
        if b["close"]>b["open"]:
            m5_confirm=(b,f); break

    def pack(x):
        if not x: return None
        return {"time":x["time"].isoformat(),"price":x.get("price"),"evidence":{k:v for k,v in x.items() if k not in ("time",)}}

    out={
        "tick_pressure_reversal":pack(pressure_rev),
        "velocity_decay_start":pack(velocity_decay),
        "acceleration_reversal":pack(accel_rev),
        "spread_normalization":pack(spread_norm),
        "m1_failed_low": None if not m1_failed else {"time":m1_failed[0]["time"].isoformat(),"price":m1_failed[0]["close"],"evidence":m1_failed[1]},
        "m1_long_candidate": None if not m1_long else {"time":m1_long[0]["time"].isoformat(),"price":m1_long[0]["close"],"evidence":m1_long[1]},
        "m1_confirm": None if not m1_confirm else {"time":m1_confirm[0]["time"].isoformat(),"price":m1_confirm[0]["close"],"evidence":m1_confirm[1]},
        "m5_confirm": None if not m5_confirm else {"time":m5_confirm[0]["time"].isoformat(),"price":m5_confirm[0]["close"],"evidence":m5_confirm[1]},
    }
    return out

def relative_context(primary_m1: list[dict], other_ticks: dict[str,list[dict]], pivot: datetime, minutes: int=10) -> dict:
    out={}
    start=pivot-timedelta(minutes=minutes)
    end=pivot+timedelta(minutes=minutes)
    for name,ticks in other_ticks.items():
        rows=ticks_between(ticks,start,end)
        if len(rows)>=2:
            out[name]={
                "start_price":rows[0]["mid"],
                "end_price":rows[-1]["mid"],
                "return":(rows[-1]["mid"]-rows[0]["mid"])/rows[0]["mid"] if rows[0]["mid"] else None,
                "freshness":"FRESH",
            }
        else:
            out[name]={"freshness":"VERIFY_REQUIRED","return":None}
    return out

def false_positive_cases(m1: list[dict], pivot: datetime, exclude_minutes: int=90, max_cases: int=3) -> list[dict]:
    rets=returns(m1)
    cases=[]
    for i in range(2,len(m1)-30):
        if abs((m1[i]["time"]-pivot).total_seconds()) < exclude_minutes*60:
            continue
        prev={"high":m1[i-1]["high"],"low":m1[i-1]["low"]}
        f=m1_features(m1[i],prev)
        if f.get("failed_low") and m1[i]["close"]>m1[i]["open"]:
            start=m1[i]["close"]
            future=m1[i+1:i+16]
            follow=(max(x["high"] for x in future)-start)/start if future and start else 0
            if follow < 0.0015:
                cases.append({"time":m1[i]["time"].isoformat(),"price":start,"follow_15m":follow,"features":f})
                if len(cases)>=max_cases: break
    return cases

def reconstruct_gold_case(raw_root: str) -> dict:
    culture=load_ticks(raw_root,"CultureCapital","XAU")
    if not culture:
        return {"status":"VERIFY_REQUIRED","reason":"NO_CULTURE_GOLD_TICKS"}
    m1=minute_bars(culture); m5=five_minute_bars(m1)
    case=resolve_reversal_case(m1)
    if case.get("status")!="PASS":
        return case
    pivot=case["pivot_time"]

    snapshots={f"T_MINUS_{sec}S":window_snapshot(culture,pivot,sec) for sec in LOOKBACK_SECONDS}
    candidates=earliest_candidates(culture,m1,m5,case)

    # Compare available silver/NQ/oil/BTC on Culture first.
    other={
        "SILVER":load_ticks(raw_root,"CultureCapital","XAG"),
        "NQ":load_ticks(raw_root,"CultureCapital","US100"),
        "OIL":load_ticks(raw_root,"CultureCapital","WTI"),
        "BTC":load_ticks(raw_root,"CultureCapital","BTC"),
    }
    context=relative_context(m1,other,pivot,10)

    silver_change=None
    if context.get("SILVER",{}).get("return") is not None:
        # gold +/-10m return
        gold_rows=ticks_between(culture,pivot-timedelta(minutes=10),pivot+timedelta(minutes=10))
        if len(gold_rows)>=2:
            gr=(gold_rows[-1]["mid"]-gold_rows[0]["mid"])/gold_rows[0]["mid"]
            sr=context["SILVER"]["return"]
            silver_change={"gold_return":gr,"silver_return":sr,"silver_minus_gold":sr-gr}

    false_cases=false_positive_cases(m1,pivot)
    event_low=case["event_low"]; post_high=case["post_event_high"]
    cand_price=(candidates.get("m1_long_candidate") or {}).get("price")
    conf_price=(candidates.get("m1_confirm") or {}).get("price")
    strong_price=(candidates.get("m5_confirm") or {}).get("price")

    def pct(a,b):
        return None if a in (None,0) or b is None else (b-a)/a

    # Earliest short invalidation candidate = earliest of pressure/velocity/accel/failed-low evidence.
    time_candidates=[]
    for k in ("tick_pressure_reversal","velocity_decay_start","acceleration_reversal","m1_failed_low"):
        x=candidates.get(k)
        if x: time_candidates.append((datetime.fromisoformat(x["time"]),k,x))
    time_candidates.sort(key=lambda x:x[0])
    invalidation=time_candidates[0] if time_candidates else None

    # Lead-lag findings
    tick_times=[datetime.fromisoformat(candidates[k]["time"]) for k in ("tick_pressure_reversal","velocity_decay_start","acceleration_reversal") if candidates.get(k)]
    tick_earliest=min(tick_times) if tick_times else None
    m1_long_t=datetime.fromisoformat(candidates["m1_long_candidate"]["time"]) if candidates.get("m1_long_candidate") else None
    m5_t=datetime.fromisoformat(candidates["m5_confirm"]["time"]) if candidates.get("m5_confirm") else None

    leadlag={
        "tick_lead_vs_m1_seconds":None if not tick_earliest or not m1_long_t else (m1_long_t-tick_earliest).total_seconds(),
        "m1_lead_vs_m5_seconds":None if not m1_long_t or not m5_t else (m5_t-m1_long_t).total_seconds(),
        "tick_lead_vs_m5_seconds":None if not tick_earliest or not m5_t else (m5_t-tick_earliest).total_seconds(),
    }

    # MFE/MAE from earliest long candidate if available
    post_rows=ticks_between(culture, pivot, pivot+timedelta(minutes=60))
    mfe=mae=None
    if cand_price and post_rows:
        rets=[(r["mid"]-cand_price)/cand_price for r in post_rows]
        mfe=max(rets); mae=min(rets)

    return {
        "status":"PASS",
        "case_id":"GOLD_CASE_001",
        "classification":"REVERSE_EVENT_RESEARCH_CASE",
        "broker_analyzed":"CultureCapital",
        "broker_compare":"EZSquare_SEPARATE_NOT_MERGED",
        "data_range_used":{"start":culture[0]["time"].isoformat(),"end":culture[-1]["time"].isoformat(),"ticks":len(culture)},
        "event_start_time":case["event_start_time"].isoformat(),
        "reversal_pivot_time":case["pivot_time"].isoformat(),
        "event_low":event_low,
        "post_event_high_time":case["post_event_high_time"].isoformat(),
        "post_event_high":post_high,
        "threshold_method":case["threshold_method"],
        "threshold_value":case["threshold_value"],
        "lookback_snapshots":snapshots,
        "candidates":candidates,
        "cross_context":context,
        "silver_relative_strength_change":silver_change,
        "false_positive_cases":false_cases,
        "control_sample_count":len(false_cases),
        "earliest_short_invalidation":None if not invalidation else {"time":invalidation[0].isoformat(),"source":invalidation[1],"detail":invalidation[2]},
        "earliest_long_candidate":candidates.get("m1_long_candidate"),
        "earliest_long_confirm":candidates.get("m1_confirm"),
        "earliest_strong_long_candidate":candidates.get("m5_confirm"),
        "lead_lag_findings":leadlag,
        "opportunity":{
            "earliest_long_candidate_price":cand_price,
            "long_confirm_price":conf_price,
            "strong_long_price":strong_price,
            "confirmation_cost":pct(cand_price,conf_price) if cand_price and conf_price else None,
            "opportunity_loss_strong_vs_candidate":pct(cand_price,strong_price) if cand_price and strong_price else None,
            "missed_move_candidate_vs_post_high":pct(cand_price,post_high) if cand_price else None,
            "post_event_mfe":mfe,
            "post_event_mae":mae,
        },
        "candidate_signals":[
            "GOLD_TICK_PRESSURE_REVERSAL_CANDIDATE",
            "GOLD_DOWNSIDE_VELOCITY_DECAY_CANDIDATE",
            "GOLD_FAILED_LOW_CANDIDATE",
            "GOLD_SILVER_REL_STRENGTH_CANDIDATE",
            "GOLD_SPREAD_NORMALIZATION_CANDIDATE",
            "GOLD_M1_REVERSAL_CANDIDATE",
        ],
        "candidate_combinations":[
            ["GOLD_TICK_PRESSURE_REVERSAL_CANDIDATE","GOLD_DOWNSIDE_VELOCITY_DECAY_CANDIDATE","GOLD_FAILED_LOW_CANDIDATE"],
            ["GOLD_TICK_PRESSURE_REVERSAL_CANDIDATE","GOLD_SILVER_REL_STRENGTH_CANDIDATE","GOLD_M1_REVERSAL_CANDIDATE"],
        ],
        "macro_history":{
            "DXY":"VERIFY_REQUIRED","US2Y":"VERIFY_REQUIRED","US10Y":"VERIFY_REQUIRED","US30Y":"VERIFY_REQUIRED","REAL_YIELD":"VERIFY_REQUIRED"
        },
        "gold_case_completeness":"TICK_M1_M5_AVAILABLE__MACRO_MINUTE_HISTORY_VERIFY_REQUIRED",
        "production_signal_promoted":False,
        "live_order":False,
    }
