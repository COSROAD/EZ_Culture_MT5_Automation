
from __future__ import annotations
from datetime import datetime,timedelta
import statistics
from .gold_case import load_ticks,minute_bars,five_minute_bars,ticks_between,rolling_tick_series
from .features import m1_features,m5_features

def resolve_case_for_date(raw_root:str,target_date:str)->dict:
    ticks=load_ticks(raw_root,"CultureCapital","XAU")
    date_ticks=[x for x in ticks if x["time"].strftime("%Y-%m-%d")==target_date]
    if not date_ticks: return {"status":"VERIFY_REQUIRED","reason":"NO_TICKS_FOR_TARGET_DATE"}
    m1=minute_bars(date_ticks); m5=five_minute_bars(m1)
    if len(m1)<30:return {"status":"VERIFY_REQUIRED","reason":"INSUFFICIENT_M1_FOR_TARGET_DATE"}
    c=[]
    for i in range(2,len(m1)-61):
        prev=(m1[i-1]["close"]-m1[i-2]["close"])/m1[i-2]["close"] if m1[i-2]["close"] else 0
        cur=(m1[i]["close"]-m1[i-1]["close"])/m1[i-1]["close"] if m1[i-1]["close"] else 0
        if prev<0 and cur>0:
            start=m1[i]["close"]; future=m1[i:i+61]
            mfe=(max(x["high"] for x in future)-start)/start
            mae=(min(x["low"] for x in future)-start)/start
            c.append((mfe-abs(mae)*.5,mfe,mae,i))
    if not c:return {"status":"VERIFY_REQUIRED","reason":"NO_INDEPENDENT_REVERSAL_CANDIDATE"}
    c.sort(reverse=True); i=c[0][3]
    pivot=m1[i]["time"]
    lowbar=min(m1[max(0,i-60):i+1],key=lambda x:x["low"])
    highbar=max(m1[i:i+61],key=lambda x:x["high"])

    series=rolling_tick_series(date_ticks,pivot-timedelta(minutes=30),pivot+timedelta(minutes=30))
    pressure=velocity=accel=spread_norm=None
    for a,b in zip(series,series[1:]):
        if pressure is None and a.get("net_tick_pressure",0)<0 and b.get("net_tick_pressure",0)>=0:pressure=b
        if velocity is None and a.get("mid_price_velocity",0)<0 and b.get("mid_price_velocity",0)>a.get("mid_price_velocity",0):velocity=b
        if accel is None and a.get("price_acceleration",0)<0 and b.get("price_acceleration",0)>=0:accel=b
    spreads=[x["spread_mean"] for x in series if x.get("spread_mean") is not None]
    if spreads:
        med=statistics.median(spreads); peak=max(range(len(series)),key=lambda k:series[k].get("spread_mean") or -1)
        for x in series[peak+1:]:
            if x.get("spread_mean") is not None and x["spread_mean"]<=med:spread_norm=x;break

    failed=m1rev=m1persist=None
    for j in range(max(1,i-30),min(len(m1),i+31)):
        prev={"high":m1[j-1]["high"],"low":m1[j-1]["low"]}; f=m1_features(m1[j],prev)
        if failed is None and f.get("failed_low"):failed=(m1[j],f)
        if m1rev is None and m1[j]["close"]>m1[j]["open"] and (f.get("failed_low") or f.get("higher_low")):m1rev=(m1[j],f)
        if m1persist is None and j>=2 and m1[j]["close"]>m1[j]["open"] and m1[j-1]["close"]>m1[j-1]["open"]:m1persist=(m1[j],f)

    m5conf=None
    for j,b in enumerate(m5):
        if b["time"]<pivot:continue
        prev=None if j==0 else {"high":m5[j-1]["high"],"low":m5[j-1]["low"]}
        f=m5_features(b,prev)
        if b["close"]>b["open"]:m5conf=(b,f);break

    def pack(x):
        if x is None:return None
        if isinstance(x,tuple):return {"time":x[0]["time"].isoformat(),"price":x[0]["close"],"evidence":x[1]}
        return {"time":x["time"].isoformat(),"price":x.get("price")}

    return {
        "status":"PASS","case_id":"GOLD_CASE_002","classification":"REVERSE_EVENT_RESEARCH_CASE","broker":"CultureCapital",
        "event_time":lowbar["time"].isoformat(),"pivot":pivot.isoformat(),"low":lowbar["low"],"high":highbar["high"],"high_time":highbar["time"].isoformat(),
        "features":{
            "TICK_PRESSURE_REVERSAL":pressure is not None,"DOWNSIDE_VELOCITY_DECAY":velocity is not None,
            "ACCELERATION_REVERSAL":accel is not None,"FAILED_LOW":failed is not None,"SPREAD_NORMALIZATION":spread_norm is not None,
            "M1_REVERSAL":m1rev is not None,"M1_PERSISTENCE":m1persist is not None,"M5_CONFIRMATION":m5conf is not None,
        },
        "times":{"tick_pressure":pack(pressure),"velocity_decay":pack(velocity),"acceleration":pack(accel),"spread_normalization":pack(spread_norm),"failed_low":pack(failed),"m1_reversal":pack(m1rev),"m1_persistence":pack(m1persist),"m5_confirmation":pack(m5conf)}
    }

def feature_set_from_case1(case1:dict)->dict:
    c=case1.get("candidates",{})
    return {
        "TICK_PRESSURE_REVERSAL":bool(c.get("tick_pressure_reversal")),"DOWNSIDE_VELOCITY_DECAY":bool(c.get("velocity_decay_start")),
        "ACCELERATION_REVERSAL":bool(c.get("acceleration_reversal")),"FAILED_LOW":bool(c.get("m1_failed_low")),
        "SPREAD_NORMALIZATION":bool(c.get("spread_normalization")),"M1_REVERSAL":bool(c.get("m1_long_candidate")),
        "SILVER_RELATIVE_STRENGTH":bool(case1.get("silver_relative_strength_change")),
    }

def feature_set_from_case2(case2:dict,silver_relative)->dict:
    f=case2.get("features",{})
    return {
        "TICK_PRESSURE_REVERSAL":bool(f.get("TICK_PRESSURE_REVERSAL")),"DOWNSIDE_VELOCITY_DECAY":bool(f.get("DOWNSIDE_VELOCITY_DECAY")),
        "ACCELERATION_REVERSAL":bool(f.get("ACCELERATION_REVERSAL")),"FAILED_LOW":bool(f.get("FAILED_LOW")),
        "SPREAD_NORMALIZATION":bool(f.get("SPREAD_NORMALIZATION")),"M1_REVERSAL":bool(f.get("M1_REVERSAL")),
        "SILVER_RELATIVE_STRENGTH":bool(silver_relative) if silver_relative is not None else False,
    }

def cross_case_matrix(case1,case2,false_cases,silver2):
    c1=feature_set_from_case1(case1);c2=feature_set_from_case2(case2,silver2);rows=[]
    for k in c1:
        fp=sum(1 for x in false_cases if x.get(k,False))
        rep="REPLICATED" if c1[k] and c2[k] else ("PARTIALLY_REPLICATED" if c1[k] or c2[k] else "NOT_REPLICATED")
        rows.append({"feature":k,"CASE001":c1[k],"CASE002":c2[k],"FALSE_POSITIVE_OCCURRENCE":fp,"replication":rep})
    return rows
