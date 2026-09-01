from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Dict, Iterable, List, Optional

KST = timezone(timedelta(hours=9))
UTC = timezone.utc

class MonitorStatus(str, Enum):
    ACTIVE = "ACTIVE"
    OUTSIDE_WINDOW = "OUTSIDE_WINDOW"
    NO_MATERIAL_CHANGE = "NO_MATERIAL_CHANGE"
    ALERT = "ALERT"
    VERIFY_REQUIRED = "VERIFY_REQUIRED"

@dataclass(frozen=True)
class MarketState:
    direction: str
    risk: str
    add_status: str = "N/A"

@dataclass(frozen=True)
class MacroState:
    us2y: str = "N/A"
    us10y: str = "N/A"
    us30y: str = "N/A"
    real_yield: str = "N/A"
    dxy: str = "N/A"
    usd_cnh: str = "N/A"
    corporate_credit_pressure: str = "N/A"

@dataclass(frozen=True)
class IntensiveSnapshot:
    check_id: str
    check_time_kst: str
    markets: Dict[str, MarketState]
    macro: MacroState
    web_market_freshness: str
    signal_data_freshness: str
    market_data_freshness: str
    delivery_status: str = "PASS"
    silver_relative_weakness: bool = False
    gold_downside_acceleration: bool = False
    silver_downside_acceleration: bool = False
    oil_geopolitical_shock: bool = False
    nq_yield_shock: bool = False
    real_yield_shock: bool = False
    dxy_shock: bool = False
    btc_risk_shock: bool = False
    corporate_credit_worsened: bool = False

@dataclass(frozen=True)
class AlertDecision:
    status: str
    alert_required: bool
    triggers: List[str]
    market: str
    direction_before: str
    direction_now: str
    risk_before: str
    risk_now: str
    add_status: str
    action: str
    data_freshness: Dict[str, str]
    delivery_status: str
    current_alert: bool
    note: str = ""

    def to_dict(self):
        return asdict(self)

def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))

def us_dst_for_market_open(us_date: date) -> bool:
    start = _nth_weekday(us_date.year, 3, 6, 2)
    end = _nth_weekday(us_date.year, 11, 6, 1)
    return start <= us_date < end

def us_cash_open_kst(us_date: date) -> datetime:
    offset = -4 if us_dst_for_market_open(us_date) else -5
    eastern_open = datetime.combine(us_date, time(9, 30))
    utc_open = (eastern_open - timedelta(hours=offset)).replace(tzinfo=UTC)
    return utc_open.astimezone(KST)

def intensive_window_kst(us_date: date) -> tuple[datetime, datetime]:
    start = us_cash_open_kst(us_date)
    return start, start + timedelta(hours=3)

def is_inside_first_3h(kst_dt: datetime) -> bool:
    if kst_dt.tzinfo is None:
        raise ValueError("kst_dt must be timezone-aware")
    local = kst_dt.astimezone(KST)
    for candidate in (local.date(), local.date() - timedelta(days=1), local.date() + timedelta(days=1)):
        start, end = intensive_window_kst(candidate)
        if start <= local < end:
            return True
    return False

def cadence_slot(kst_dt: datetime) -> Optional[int]:
    if not is_inside_first_3h(kst_dt):
        return None
    local = kst_dt.astimezone(KST)
    for candidate in (local.date(), local.date() - timedelta(days=1), local.date() + timedelta(days=1)):
        start, end = intensive_window_kst(candidate)
        if start <= local < end:
            return int((local - start).total_seconds() // 600)
    return None

def is_ten_minute_boundary(kst_dt: datetime, tolerance_seconds: int = 90) -> bool:
    if not is_inside_first_3h(kst_dt):
        return False
    local = kst_dt.astimezone(KST)
    for candidate in (local.date(), local.date() - timedelta(days=1), local.date() + timedelta(days=1)):
        start, end = intensive_window_kst(candidate)
        if start <= local < end:
            elapsed = (local - start).total_seconds()
            nearest = round(elapsed / 600) * 600
            return abs(elapsed - nearest) <= tolerance_seconds
    return False

def hourly_collision_context(kst_dt: datetime, guard_minutes: int = 4) -> bool:
    local = kst_dt.astimezone(KST)
    return local.minute < guard_minutes or local.minute >= (60 - guard_minutes)

def _rank_risk(risk: str) -> int:
    return {"NORMAL": 0, "CAUTION": 1, "HIGH_RISK": 2}.get(risk, -1)

def _market_trigger(prev: MarketState, cur: MarketState, market: str) -> List[str]:
    out: List[str] = []
    if prev.direction != cur.direction:
        out.append("DIRECTION_CHANGE")
    if _rank_risk(cur.risk) > _rank_risk(prev.risk):
        out.append("RISK_LEVEL_CHANGE")
    if prev.add_status == "ADD" and cur.add_status == "NO_ADD":
        out.append("ADD_PERMISSION_CHANGE")
    return [f"{market}:{x}" for x in out]

def detect_change_triggers(previous: IntensiveSnapshot, current: IntensiveSnapshot) -> List[str]:
    triggers: List[str] = []
    for market in ("NQ", "GOLD", "SILVER", "OIL", "BTC"):
        if market in previous.markets and market in current.markets:
            triggers.extend(_market_trigger(previous.markets[market], current.markets[market], market))
    if current.nq_yield_shock:
        triggers.append("NQ:YIELD_SHOCK")
    if current.real_yield_shock:
        triggers.append("MACRO:REAL_YIELD_SHOCK")
    if current.dxy_shock:
        triggers.append("MACRO:DXY_SHOCK")
    if current.gold_downside_acceleration:
        triggers.append("GOLD:DOWNSIDE_ACCELERATION")
    if current.silver_downside_acceleration:
        triggers.append("SILVER:DOWNSIDE_ACCELERATION")
    if current.silver_relative_weakness:
        triggers.append("SILVER:SILVER_RELATIVE_WEAKNESS")
    if current.oil_geopolitical_shock:
        triggers.append("OIL:GEOPOLITICAL_SHOCK")
    if current.btc_risk_shock:
        triggers.append("BTC:RISK_SHOCK")
    if current.corporate_credit_worsened:
        triggers.append("MACRO:CORPORATE_CREDIT_PRESSURE_CHANGE")
    return triggers

def _primary_market(triggers: Iterable[str]) -> str:
    for prefix in ("NQ:", "GOLD:", "SILVER:", "OIL:", "BTC:"):
        for trigger in triggers:
            if trigger.startswith(prefix):
                return prefix[:-1]
    return "MACRO"

def _action_for(market: str, current: IntensiveSnapshot, triggers: List[str]) -> str:
    if "OIL:GEOPOLITICAL_SHOCK" in triggers:
        return "SHORT_BLOCK"
    if "SILVER:SILVER_RELATIVE_WEAKNESS" in triggers:
        return "NO_ADD"
    if "SILVER:DOWNSIDE_ACCELERATION" in triggers:
        return "NO_ADD"
    if "GOLD:DOWNSIDE_ACCELERATION" in triggers:
        return "NO_ADD"
    if any(t.endswith("ADD_PERMISSION_CHANGE") for t in triggers):
        return "NO_ADD"
    if market in current.markets:
        direction = current.markets[market].direction
        if direction == "LONG":
            return "LONG_BIAS"
        if direction == "SHORT":
            return "SHORT_BIAS"
        if direction == "BLOCK":
            return "SHORT_BLOCK"
    return "WAIT_CONFIRMATION"

def evaluate_alert(previous: IntensiveSnapshot, current: IntensiveSnapshot) -> AlertDecision:
    freshness = {
        "WEB_MARKET_FRESHNESS": current.web_market_freshness,
        "SIGNAL_DATA_FRESHNESS": current.signal_data_freshness,
        "MARKET_DATA_FRESHNESS": current.market_data_freshness,
    }
    if current.delivery_status != "PASS":
        return AlertDecision(
            status=MonitorStatus.VERIFY_REQUIRED.value,
            alert_required=False,
            triggers=[],
            market="N/A",
            direction_before="N/A",
            direction_now="N/A",
            risk_before="N/A",
            risk_now="N/A",
            add_status="N/A",
            action="WAIT_CONFIRMATION",
            data_freshness=freshness,
            delivery_status=current.delivery_status,
            current_alert=False,
            note="Check execution is not equivalent to successful alert delivery.",
        )
    triggers = detect_change_triggers(previous, current)
    if not triggers:
        return AlertDecision(
            status=MonitorStatus.NO_MATERIAL_CHANGE.value,
            alert_required=False,
            triggers=[],
            market="N/A",
            direction_before="N/A",
            direction_now="N/A",
            risk_before="N/A",
            risk_now="N/A",
            add_status="N/A",
            action="WAIT_CONFIRMATION",
            data_freshness=freshness,
            delivery_status=current.delivery_status,
            current_alert=True,
            note="No alert manufactured.",
        )
    market = _primary_market(triggers)
    prev_state = previous.markets.get(market, MarketState("N/A", "N/A", "N/A"))
    cur_state = current.markets.get(market, MarketState("N/A", "N/A", "N/A"))
    return AlertDecision(
        status=MonitorStatus.ALERT.value,
        alert_required=True,
        triggers=triggers,
        market=market,
        direction_before=prev_state.direction,
        direction_now=cur_state.direction,
        risk_before=prev_state.risk,
        risk_now=cur_state.risk,
        add_status=cur_state.add_status,
        action=_action_for(market, current, triggers),
        data_freshness=freshness,
        delivery_status=current.delivery_status,
        current_alert=True,
    )

def corporate_credit_status(
    ig_issuance: Optional[str],
    hy_issuance: Optional[str],
    ig_spread: Optional[str],
    hy_spread: Optional[str],
    new_issue_concession: Optional[str],
) -> str:
    values = [ig_issuance, hy_issuance, ig_spread, hy_spread, new_issue_concession]
    return "AVAILABLE" if any(v not in (None, "", "N/A") for v in values) else "VERIFY_REQUIRED"

def storage_design() -> dict:
    return {
        "hourly_authority": "MARKET5_LATEST_REPORT",
        "ten_minute_status": "US_OPEN_10M_STATUS.json",
        "ten_minute_alert_pattern": "US_OPEN_10M_ALERT_<CHECK_ID>.json",
        "may_overwrite_hourly_latest": False,
        "authority": "EARLY_WARNING_ONLY",
    }

def scheduler_plan() -> dict:
    return {
        "architecture": "B",
        "runner": "WINDOWS_SCHEDULED_TASK_LOCAL_AGENT",
        "trigger": "EVERY_10_MINUTES",
        "window_gate": "US_09_30_ET_TO_12_30_ET_FIRST_3H",
        "dst_source": "US_EASTERN_09_30_ET_CONVERTED_TO_KST",
        "outside_window": "EXIT_NO_ACTION",
        "hourly_report_preserved": True,
        "live_activation": False,
        "rollback": "DISABLE_DEDICATED_TASK_ONLY",
        "note": "Sub-hour production activation requires a dedicated local runner or another approved sub-hour scheduler.",
    }
