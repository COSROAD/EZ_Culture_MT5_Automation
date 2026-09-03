
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from pathlib import Path
from collections import defaultdict
import csv,json,os,tempfile

from agent.decision_integration.core import historical_match,current_confirmation,infer_direction,make_decision,risk_gate,conflict_level,event_driven
from agent.research_engine.features import tick_features,m1_features,m5_features

UTC=timezone.utc;KST=timezone(timedelta(hours=9))
MARKETS={
"NQ":{"CultureCapital":"US100","EZSquare":"NQ2.ez2"},
"GOLD":{"CultureCapital":"XAUUSD","EZSquare":"XAUUSD.ez2"},
"SILVER":{"CultureCapital":"XAGUSD","EZSquare":"XAGUSD.ez2"},
"OIL":{"CultureCapital":"WTI","EZSquare":"USOIL.ez2"},
"BTC":{"CultureCapital":"BTCUSD"}}
MACRO=("DXY","US2Y","US10Y","US30Y","REAL_YIELD")

def parse_time(r):
    for k in ("SERVER_TIME_MSC","SERVER_TIME","PC_TIME"):
        s=str(r.get(k,"")).strip()
        for f in ("%Y.%m.%d %H:%M:%S.%f","%Y.%m.%d %H:%M:%S","%Y-%m-%d %H:%M:%S.%f","%Y-%m-%d %H:%M:%S"):
            try:return datetime.strptime(s,f).replace(tzinfo=UTC)
            except:pass
    return None

def latest_ticks(root,broker,symbol,max_files=4):
    out=[]
    files=sorted(Path(root).rglob("MarketDataCollector_*.csv"),key=lambda p:p.stat().st_mtime,reverse=True)[:max_files]
    for p in files:
        try:
            with p.open("r",encoding="utf-8-sig",errors="replace",newline="") as f:
                rd=csv.DictReader(f)
                if not {"BROKER","SYMBOL","BID","ASK"}.issubset(set(rd.fieldnames or [])):continue
                for r in rd:
                    if r.get("BROKER")!=broker or r.get("SYMBOL")!=symbol:continue
                    t=parse_time(r)
                    if not t:continue
                    try:b=float(r["BID"]);a=float(r["ASK"])
                    except:continue
                    out.append({"time":t,"BID":b,"ASK":a,"SPREAD":float(r["SPREAD"]) if r.get("SPREAD") not in ("",None) else a-b,"mid":(a+b)/2})
        except:continue
    out.sort(key=lambda x:x["time"])
    return out

def windows(ticks):
    if not ticks:return {"freshness":"VERIFY_REQUIRED","windows":{}}
    last=ticks[-1]["time"]; out={}
    for sec in (30,60,180,300):
        rows=[x for x in ticks if last-timedelta(seconds=sec)<=x["time"]<=last]
        f=tick_features(rows);f["tick_rate"]=len(rows)/sec;out[str(sec)]=f
    return {"freshness":"FRESH","latest_time_utc":last.isoformat(),"latest_price":ticks[-1]["mid"],"windows":out}

def bars(ticks,mins):
    d=defaultdict(list)
    for x in ticks:
        t=x["time"]; key=t.replace(minute=(t.minute//mins)*mins,second=0,microsecond=0);d[key].append(x)
    out=[]
    for t,rs in sorted(d.items()):
        v=[x["mid"] for x in rs];out.append({"time":t,"open":v[0],"high":max(v),"low":min(v),"close":v[-1]})
    return out

def m1_state(ticks):
    b=bars(ticks,1)
    if not b:return {"freshness":"VERIFY_REQUIRED"}
    prev=None if len(b)<2 else {"high":b[-2]["high"],"low":b[-2]["low"]}
    f=m1_features(b[-1],prev);f["freshness"]="FRESH";f["time_utc"]=b[-1]["time"].isoformat()
    return f

def m5_state(ticks):
    b=bars(ticks,5)
    if not b:return {"freshness":"VERIFY_REQUIRED","source":"TICK_DERIVED_REFERENCE_ONLY"}
    prev=None if len(b)<2 else {"high":b[-2]["high"],"low":b[-2]["low"]}
    f=m5_features(b[-1],prev);f["freshness"]="FRESH";f["source"]="TICK_DERIVED_REFERENCE_ONLY";f["time_utc"]=b[-1]["time"].isoformat()
    return f

def file_fresh(path,mins):
    p=Path(path)
    if not p.exists():return "NOT_AVAILABLE"
    age=(datetime.now()-datetime.fromtimestamp(p.stat().st_mtime)).total_seconds()/60
    return "FRESH" if age<=mins else "STALE"

def signal_state(root,market,broker,symbol):
    return {"source":"MT5_Signal_Data.xlsx","freshness":file_fresh(str(Path(root)/"MT5_Signal_Data.xlsx"),90),"signal":"VERIFY_REQUIRED","market":market,"broker":broker,"instrument":symbol}

def _nth_weekday(year:int,month:int,weekday:int,n:int):
    from datetime import date,timedelta
    first=date(year,month,1)
    offset=(weekday-first.weekday())%7
    return first+timedelta(days=offset+7*(n-1))

def _us_eastern_offset_hours(us_date):
    start=_nth_weekday(us_date.year,3,6,2)
    end=_nth_weekday(us_date.year,11,6,1)
    return -4 if start <= us_date < end else -5

def session(now):
    if now.tzinfo is None:
        now=now.replace(tzinfo=UTC)
    utc=now.astimezone(UTC)
    et4=utc+timedelta(hours=-4)
    et5=utc+timedelta(hours=-5)
    et=et4 if _us_eastern_offset_hours(et4.date())==-4 else et5
    t=et.time()
    if t.hour<3:return "ASIA"
    if t.hour<8:return "EUROPE"
    if (t.hour,t.minute)<(9,30):return "US_PREMARKET"
    if (t.hour,t.minute)<(12,30):return "US_CASH_INTENSIVE"
    if t.hour<15:return "US_MIDSESSION"
    return "US_LATE"

def macro_gap():
    return {k:{"current_source":"NOT_APPROVED","timestamp_precision":"NOT_AVAILABLE","freshness_capability":"VERIFY_REQUIRED","historical_depth":"NOT_AVAILABLE","status":"VERIFY_REQUIRED","recommended_source_class":"LICENSED_INTRADAY"} for k in MACRO}

def cross(obs):
    def r(a,b):
        if not obs.get(a,{}).get("price") or not obs.get(b,{}).get("price"):return {"status":"VERIFY_REQUIRED"}
        return {"status":"OBSERVED_CURRENT","relationship":"DYNAMIC_REFERENCE_ONLY","a":obs[a]["price"],"b":obs[b]["price"]}
    return {"GOLD_SILVER":r("GOLD","SILVER"),"NQ_BTC":r("NQ","BTC"),"OIL_NQ":r("OIL","NQ"),"OIL_GOLD":r("OIL","GOLD"),"GOLD_DXY":{"status":"VERIFY_REQUIRED"},"GOLD_YIELD":{"status":"VERIFY_REQUIRED"}}

def atomic_json(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=str(p.parent),prefix=p.name+".",suffix=".tmp");os.close(fd)
    try:Path(tmp).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding="utf-8");os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.remove(tmp)

def append_jsonl(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8") as f:f.write(json.dumps(obj,ensure_ascii=False,default=str)+"\n")

def meaningful(prev,cur):
    if prev is None:return True
    return any(prev.get(k)!=cur.get(k) for k in ("direction","entry_permission","add_permission","risk_state","conflict_level","final_action"))

def restart_guard(last,now,max_age=120):
    if not last or not last.get("time_utc"):return {"reuse_current":False,"reason":"NO_VALID_PREVIOUS_STATE"}
    t=datetime.fromisoformat(last["time_utc"].replace("Z","+00:00"));age=(now-t.astimezone(UTC)).total_seconds()
    return {"reuse_current":age<=max_age,"reason":"FRESH_PREVIOUS_STATE" if age<=max_age else "STALE_PREVIOUS_STATE","age_seconds":age}

def decide(market,broker,symbol,tick,m1,m5,sig,hist,health_ok=True):
    td="LONG" if tick.get("windows",{}).get("60",{}).get("net_tick_pressure",0)>0 else ("SHORT" if tick.get("windows",{}).get("60",{}).get("net_tick_pressure",0)<0 else "MIXED")
    m1d="LONG" if m1.get("direction")=="UP" else ("SHORT" if m1.get("direction")=="DOWN" else "MIXED")
    m5d="LONG" if m5.get("direction")=="UP" else ("SHORT" if m5.get("direction")=="DOWN" else "MIXED")
    cur=current_confirmation(td,m1d,m5d,"MIXED","MIXED","MIXED")
    feats={x for x in ("TICK_POSITIVE" if td=="LONG" else None,"M1_REVERSAL" if m1.get("momentum_reversal") else None,"M5_POSITIVE" if m5d=="LONG" else None) if x}
    hm=historical_match(feats,hist,session(datetime.now(UTC)),"VERIFY_REQUIRED",False)
    d,conf,tr,con=infer_direction(market,hm,cur,sig.get("signal"),None)
    missing=["MACRO"]
    if tick.get("freshness")!="FRESH":missing.append("TICK")
    if not health_ok:missing.append("HEALTH")
    dec=make_decision(market,datetime.now(UTC).isoformat(),d,conf,hm,{"state":"VERIFY_REQUIRED","freshness":"VERIFY_REQUIRED"},tr,con,{"TICK":tick.get("freshness"),"M1":m1.get("freshness"),"M5":m5.get("freshness"),"SIGNAL":sig.get("freshness"),"MACRO":"VERIFY_REQUIRED"},"CAUTION",[x for x in (td,m1d,m5d) if x in ("LONG","SHORT")],missing,tick.get("latest_price"),"CURRENT_CONFIRMATION_INVALIDATED",not health_ok)
    x=dec.to_dict();x["broker"]=broker;x["instrument"]=symbol;return x

def bounded(root,raw,hist):
    obs={};markets={}
    for market,mapping in MARKETS.items():
        broker="CultureCapital";symbol=mapping[broker]
        ts=latest_ticks(raw,broker,symbol);tw=windows(ts);m1=m1_state(ts);m5=m5_state(ts);sig=signal_state(root,market,broker,symbol)
        obs[market]={"price":tw.get("latest_price"),"tick":tw,"m1":m1,"m5":m5,"signal":sig,"broker":broker,"symbol":symbol}
        markets[market]={"broker":broker,"symbol":symbol,"available":bool(ts),"tick_count":len(ts),"tick_freshness":tw.get("freshness")}
    health_ok=all(v["available"] for v in markets.values())
    dec={m:decide(m,x["broker"],x["symbol"],x["tick"],x["m1"],x["m5"],x["signal"],hist,health_ok) for m,x in obs.items()}
    now=datetime.now(UTC)
    return {"time_utc":now.isoformat(),"time_kst":now.astimezone(KST).isoformat(),"session":session(now),"markets":markets,"cross_market":cross(obs),"macro_gap":macro_gap(),"health":{"state":"PASS" if health_ok else "DEGRADED","signal_freshness":file_fresh(str(Path(root)/"MT5_Signal_Data.xlsx"),90),"market_freshness":file_fresh(str(Path(root)/"MT5_Market_Data.xlsx"),15)},"decisions":dec}
