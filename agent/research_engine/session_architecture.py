
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time

@dataclass(frozen=True)
class ArchitecturePrinciple:
    final_target: str = "24/5_CONTINUOUS_REAL_TIME_LEADING_SIGNAL_AUTOMATED_TRADING_SYSTEM"
    execution_clock: str = "CONTINUOUS_TICK_M1_EVENT_DRIVEN_WITH_M5_CONFIRMATION"
    us_open_role: str = "SPECIALIZED_HIGH_VOLATILITY_INTENSIVE_MODE"
    ten_minute_role: str = "REPORTING_RESEARCH_ONLY"
    hourly_role: str = "REPORTING_RESEARCH_ONLY"
    live_order_enabled: bool = False

def classify_session(et: datetime, market_open: bool=True, maintenance: bool=False) -> str:
    if not market_open:
        return "MARKET_CLOSED"
    if maintenance:
        return "ROLLOVER_MAINTENANCE"
    t=et.time()
    if t < time(3,0): return "ASIA"
    if t < time(8,0): return "EUROPE"
    if t < time(9,30): return "US_PREMARKET"
    if t < time(12,30): return "US_CASH_OPEN_INTENSIVE"
    if t < time(15,0): return "US_MIDSESSION"
    return "US_LATE_SESSION"

def execution_due(trigger: str, tick_changed: bool, m1_state_changed: bool, m5_closed: bool) -> bool:
    triggers={
        "TICK_PRESSURE_REVERSAL","VELOCITY_SHOCK","ACCELERATION_SHOCK","SPREAD_SHOCK",
        "M1_REVERSAL","YIELD_SHOCK","REAL_YIELD_SHOCK","DXY_SHOCK",
        "GOLD_SILVER_RELATIVE_SHIFT","OIL_SHOCK","BTC_RELATIVE_STRENGTH_SHIFT","CREDIT_PRESSURE_SHIFT"
    }
    return trigger in triggers or tick_changed or m1_state_changed or m5_closed

def execution_depends_on_reporting_clock(clock_name: str) -> bool:
    return False
