
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Iterable, Sequence, Optional
import math

def _safe_div(a: float, b: float) -> float | None:
    return None if b == 0 else a / b

def tick_features(rows: Sequence[dict]) -> dict:
    """Compute only from bid/ask/spread/timestamp-like fields actually present."""
    if not rows:
        return {"freshness": "VERIFY_REQUIRED", "tick_count": 0}
    mids, bids, asks, spreads = [], [], [], []
    for r in rows:
        bid = float(r["BID"]) if r.get("BID") not in (None, "") else None
        ask = float(r["ASK"]) if r.get("ASK") not in (None, "") else None
        if bid is not None: bids.append(bid)
        if ask is not None: asks.append(ask)
        if bid is not None and ask is not None:
            mids.append((bid + ask) / 2.0)
        if r.get("SPREAD") not in (None, ""):
            spreads.append(float(r["SPREAD"]))
        elif bid is not None and ask is not None:
            spreads.append(ask - bid)
    if len(mids) < 2:
        return {"freshness": "VERIFY_REQUIRED", "tick_count": len(rows)}
    diffs = [b-a for a,b in zip(mids, mids[1:])]
    up = sum(1 for x in diffs if x > 0)
    down = sum(1 for x in diffs if x < 0)
    runs, cur, sign = [], 0, 0
    reversals = 0
    for x in diffs:
        s = 1 if x > 0 else (-1 if x < 0 else 0)
        if s == 0:
            continue
        if sign == 0 or s == sign:
            cur += 1
        else:
            runs.append(cur)
            cur = 1
            reversals += 1
        sign = s
    if cur: runs.append(cur)
    velocity = mids[-1] - mids[0]
    acceleration = (diffs[-1] - diffs[0]) if len(diffs) >= 2 else 0.0
    result = {
        "freshness": "FRESH",
        "tick_count": len(rows),
        "up_tick_count": up,
        "down_tick_count": down,
        "up_down_ratio": _safe_div(up, down),
        "net_tick_pressure": up - down,
        "bid_velocity": (bids[-1]-bids[0]) if len(bids)>=2 else None,
        "ask_velocity": (asks[-1]-asks[0]) if len(asks)>=2 else None,
        "mid_price_velocity": velocity,
        "price_acceleration": acceleration,
        "short_range": max(mids)-min(mids),
        "rolling_range": max(mids)-min(mids),
        "spread": spreads[-1] if spreads else None,
        "spread_change": (spreads[-1]-spreads[0]) if len(spreads)>=2 else None,
        "spread_expansion_rate": _safe_div((spreads[-1]-spreads[0]), abs(spreads[0])) if len(spreads)>=2 else None,
        "max_spread": max(spreads) if spreads else None,
        "directional_run_length": max(runs) if runs else 0,
        "reversal_tick_count": reversals,
        "volatility_shock": max(abs(x) for x in diffs) if diffs else 0.0,
        "micro_pullback_depth": max(mids)-mids[-1] if velocity >= 0 else mids[-1]-min(mids),
    }
    return result

def bar_features(open_: float, high: float, low: float, close: float, prev: Optional[dict] = None) -> dict:
    rng = high-low
    body = close-open_
    out = {
        "return": _safe_div(close-open_, open_),
        "range": rng,
        "body_range": _safe_div(abs(body), rng),
        "direction": "UP" if body > 0 else ("DOWN" if body < 0 else "FLAT"),
        "higher_low": None,
        "lower_high": None,
        "higher_high": None,
        "lower_low": None,
        "failed_low": None,
        "failed_high": None,
        "momentum": body,
        "short_term_volatility": rng,
    }
    if prev:
        out.update({
            "higher_low": low > prev["low"],
            "lower_high": high < prev["high"],
            "higher_high": high > prev["high"],
            "lower_low": low < prev["low"],
            "failed_low": low < prev["low"] and close > prev["low"],
            "failed_high": high > prev["high"] and close < prev["high"],
        })
    return out

def m1_features(bar: dict, prev: Optional[dict] = None) -> dict:
    return bar_features(float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"]), prev)

def m5_features(bar: dict, prev: Optional[dict] = None) -> dict:
    x = bar_features(float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"]), prev)
    x["role"] = "SETUP_CONFIRMATION"
    x["early_detection_source"] = False
    x["breakout_candidate"] = bool(prev and float(bar["close"]) > prev["high"])
    x["failed_breakout_candidate"] = bool(prev and float(bar["high"]) > prev["high"] and float(bar["close"]) < prev["high"])
    return x
