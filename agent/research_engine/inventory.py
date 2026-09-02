
from __future__ import annotations
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import csv, json, math

REQUIRED = {"BROKER","SYMBOL","BID","ASK"}

def _parse_time(row: dict):
    for key in ("SERVER_TIME_MSC","SERVER_TIME","PC_TIME"):
        v = row.get(key)
        if not v: continue
        s = str(v).strip()
        for fmt in ("%Y.%m.%d %H:%M:%S.%f","%Y.%m.%d %H:%M:%S","%Y-%m-%d %H:%M:%S.%f","%Y-%m-%d %H:%M:%S"):
            try: return datetime.strptime(s,fmt)
            except ValueError: pass
    return None

def _minute_key(dt): return dt.replace(second=0,microsecond=0)

def inventory_raw(raw_root: str, m5_path: str | None=None, signal_path: str | None=None) -> dict:
    root = Path(raw_root)
    files = sorted(root.rglob("MarketDataCollector_*.csv")) if root.exists() else []
    count=0; brokers=defaultdict(int); symbols=defaultdict(int)
    min_t=max_t=None; gaps=[]; unreadable=[]; minute_mid=defaultdict(dict)
    gold_minutes = defaultdict(list)
    for f in files:
        try:
            with f.open("r",encoding="utf-8-sig",errors="replace",newline="") as fh:
                reader=csv.DictReader(fh)
                headers=set(reader.fieldnames or [])
                if not REQUIRED.issubset(headers):
                    unreadable.append({"file":str(f),"reason":"MISSING_REQUIRED_COLUMNS","headers":sorted(headers)})
                    continue
                last_dt_by_symbol={}
                for row in reader:
                    count += 1
                    broker=row.get("BROKER","UNKNOWN"); sym=row.get("SYMBOL","UNKNOWN")
                    brokers[broker]+=1; symbols[sym]+=1
                    dt=_parse_time(row)
                    if dt:
                        min_t = dt if min_t is None or dt<min_t else min_t
                        max_t = dt if max_t is None or dt>max_t else max_t
                        prev=last_dt_by_symbol.get(sym)
                        if prev and (dt-prev).total_seconds()>120:
                            gaps.append({"file":f.name,"symbol":sym,"from":prev.isoformat(),"to":dt.isoformat(),"seconds":(dt-prev).total_seconds()})
                        last_dt_by_symbol[sym]=dt
                        try:
                            bid=float(row["BID"]); ask=float(row["ASK"]); mid=(bid+ask)/2
                            if "XAU" in sym.upper() or "GOLD" in sym.upper():
                                gold_minutes[(broker,sym,_minute_key(dt))].append(mid)
                        except Exception: pass
        except Exception as e:
            unreadable.append({"file":str(f),"reason":type(e).__name__})
    m1_bars=[]
    for (broker,sym,minute), vals in gold_minutes.items():
        if vals:
            m1_bars.append({"broker":broker,"symbol":sym,"time":minute,"open":vals[0],"high":max(vals),"low":min(vals),"close":vals[-1]})
    m1_bars.sort(key=lambda x:x["time"])
    first_candidates=[]
    gold_case=None
    if len(m1_bars)>=50:
        returns=[]
        for a,b in zip(m1_bars,m1_bars[1:]):
            if a["close"]:
                returns.append((b["close"]-a["close"])/a["close"])
        absret=sorted(abs(x) for x in returns)
        q=absret[min(len(absret)-1,max(0,int(round(.99*(len(absret)-1)))))] if absret else None
        if q and q>0:
            for i,r in enumerate(returns, start=1):
                prev=returns[i-2] if i>=2 else 0.0
                et=None
                if r>=q: et="REVERSAL_UP" if prev<0 else "RAPID_UP_MOVE"
                elif r<=-q: et="REVERSAL_DOWN" if prev>0 else "RAPID_DOWN_MOVE"
                if et:
                    bar=m1_bars[i]
                    cand={"market":"GOLD","broker":bar["broker"],"symbol":bar["symbol"],"time":bar["time"].isoformat(),
                          "event_type":et,"move_return":r,"threshold_method":"M1_ABS_RETURN_Q99_RESEARCH_CANDIDATE",
                          "threshold_value":q}
                    first_candidates.append(cand)
            rev_up=[x for x in first_candidates if x["event_type"]=="REVERSAL_UP"]
            if rev_up:
                x=rev_up[-1]
                gold_case={"case_id":"GOLD_CASE_001","classification":"REVERSE_EVENT_RESEARCH_CASE",
                           "event":x,"macro_minute_granularity":"VERIFY_REQUIRED",
                           "data_completeness":"TICK_M1_AVAILABLE__MACRO_VERIFY_REQUIRED"}
    return {
        "available_date_range":{"start":min_t.isoformat() if min_t else None,"end":max_t.isoformat() if max_t else None},
        "raw_files":[str(f) for f in files],
        "tick_counts":count,
        "markets_available":dict(symbols),
        "broker_split":dict(brokers),
        "m1_derivable":bool(m1_bars),
        "gold_m1_bar_count":len(m1_bars),
        "m5_available":bool(m5_path and Path(m5_path).exists()),
        "signal_data_available":bool(signal_path and Path(signal_path).exists()),
        "data_gaps_sample":gaps[:200],
        "unreadable_files":unreadable,
        "first_event_candidates":first_candidates[:50],
        "gold_case_001":gold_case,
        "threshold_policy":"RESEARCH_CANDIDATE_ONLY__NOT_APPROVED_TRADING_THRESHOLD",
    }
