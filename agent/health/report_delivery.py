from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import secrets
from typing import Optional


class DeliveryStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    STALE = "STALE"
    VERIFY_REQUIRED = "VERIFY_REQUIRED"


class FreshnessStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    MARKET_CLOSED = "MARKET_CLOSED"
    VERIFY_REQUIRED = "VERIFY_REQUIRED"


@dataclass(frozen=True)
class DataFreshness:
    check_time: str
    last_update_time: Optional[str]
    age_seconds: Optional[int]
    expected_max_age: int
    market_open_status: str
    freshness_status: str
    note: str = ""


@dataclass(frozen=True)
class DeliveryState:
    report_id: str
    scheduled_run_time_kst: str
    generated_time_kst: str
    drive_saved_time_kst: Optional[str]
    history_saved: bool
    history_verified: bool
    latest_updated: bool
    latest_verified: bool
    latest_report_id: Optional[str]
    report_id_match: bool
    content_hash_match: bool
    control_readable: bool
    report_freshness: str
    signal_freshness: str
    market_freshness: str
    web_market_freshness: str
    delivery_status: str
    failure_stage: Optional[str]
    last_error: Optional[str]
    verified_at_kst: str
    last_valid_report_time: Optional[str] = None
    last_valid_report_id: Optional[str] = None

    def to_dict(self):
        return asdict(self)


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def generate_report_id(scheduled_run_time_kst: str, unique_suffix: Optional[str] = None) -> str:
    dt = parse_iso(scheduled_run_time_kst)
    suffix = unique_suffix or secrets.token_hex(3).upper()
    return f"MARKET5_{dt.strftime('%Y%m%d_%H%M')}_KST_{suffix}"


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest().upper()


def _extract_report_id(content: str) -> Optional[str]:
    for line in content.splitlines():
        if line.startswith("REPORT_ID:"):
            value = line.split(":", 1)[1].strip()
            return value or None
    return None


def verify_reopened_report(expected_report_id: str, expected_content: str, reopened_content: Optional[str]) -> dict:
    if reopened_content is None:
        return {
            "verified": False,
            "report_id_match": False,
            "content_hash_match": False,
            "failure": "REOPEN_FAILED",
        }
    reopened_id = _extract_report_id(reopened_content)
    report_id_match = reopened_id == expected_report_id
    content_hash_match = content_sha256(reopened_content) == content_sha256(expected_content)
    return {
        "verified": report_id_match and content_hash_match,
        "report_id_match": report_id_match,
        "content_hash_match": content_hash_match,
        "failure": None if (report_id_match and content_hash_match) else "CONTENT_OR_ID_MISMATCH",
    }


def evaluate_freshness(
    *,
    check_time: str,
    last_update_time: Optional[str],
    expected_max_age: int,
    market_open_status: str,
    no_new_signal_is_failure: bool = True,
) -> DataFreshness:
    if market_open_status == "MARKET_CLOSED":
        return DataFreshness(
            check_time=check_time,
            last_update_time=last_update_time,
            age_seconds=None,
            expected_max_age=expected_max_age,
            market_open_status=market_open_status,
            freshness_status=FreshnessStatus.MARKET_CLOSED.value,
            note="Market closed; stale classification suppressed only for this stream.",
        )

    if last_update_time is None:
        if not no_new_signal_is_failure:
            return DataFreshness(
                check_time=check_time,
                last_update_time=None,
                age_seconds=None,
                expected_max_age=expected_max_age,
                market_open_status=market_open_status,
                freshness_status=FreshnessStatus.FRESH.value,
                note="No new signal is allowed for this stream; absence is not treated as failure.",
            )
        return DataFreshness(
            check_time=check_time,
            last_update_time=None,
            age_seconds=None,
            expected_max_age=expected_max_age,
            market_open_status=market_open_status,
            freshness_status=FreshnessStatus.VERIFY_REQUIRED.value,
            note="No timestamp available.",
        )

    age = int((parse_iso(check_time) - parse_iso(last_update_time)).total_seconds())
    if age < 0:
        return DataFreshness(
            check_time=check_time,
            last_update_time=last_update_time,
            age_seconds=age,
            expected_max_age=expected_max_age,
            market_open_status=market_open_status,
            freshness_status=FreshnessStatus.VERIFY_REQUIRED.value,
            note="Future timestamp detected.",
        )
    status = FreshnessStatus.FRESH if age <= expected_max_age else FreshnessStatus.STALE
    return DataFreshness(
        check_time=check_time,
        last_update_time=last_update_time,
        age_seconds=age,
        expected_max_age=expected_max_age,
        market_open_status=market_open_status,
        freshness_status=status.value,
    )


def evaluate_delivery(
    *,
    report_id: str,
    scheduled_run_time_kst: str,
    generated_time_kst: str,
    drive_saved_time_kst: Optional[str],
    history_saved: bool,
    history_reopened_content: Optional[str],
    latest_updated: bool,
    latest_reopened_content: Optional[str],
    expected_content: str,
    latest_completed_run_report_id: str,
    control_readable: bool,
    report_cycle_matches: bool,
    signal_freshness: str,
    market_freshness: str,
    web_market_freshness: str,
    verified_at_kst: str,
    last_valid_report_time: Optional[str] = None,
    last_valid_report_id: Optional[str] = None,
) -> DeliveryState:
    history_check = verify_reopened_report(report_id, expected_content, history_reopened_content)
    latest_check = verify_reopened_report(report_id, expected_content, latest_reopened_content)
    latest_report_id = _extract_report_id(latest_reopened_content or "")

    stages = [
        ("HISTORY_SAVE", history_saved),
        ("HISTORY_REOPEN_VERIFY", history_check["verified"]),
        ("LATEST_UPDATE", latest_updated),
        ("LATEST_REOPEN_VERIFY", latest_check["verified"]),
        ("LATEST_REPORT_ID_MATCH", latest_report_id == latest_completed_run_report_id == report_id),
        ("CONTROL_READABLE", control_readable),
    ]

    failure_stage = next((name for name, ok in stages if not ok), None)

    if failure_stage:
        status = DeliveryStatus.FAIL
    elif not report_cycle_matches:
        failure_stage = "REPORT_FRESHNESS"
        status = DeliveryStatus.STALE
    else:
        status = DeliveryStatus.PASS

    return DeliveryState(
        report_id=report_id,
        scheduled_run_time_kst=scheduled_run_time_kst,
        generated_time_kst=generated_time_kst,
        drive_saved_time_kst=drive_saved_time_kst,
        history_saved=history_saved,
        history_verified=history_check["verified"],
        latest_updated=latest_updated,
        latest_verified=latest_check["verified"],
        latest_report_id=latest_report_id,
        report_id_match=latest_check["report_id_match"],
        content_hash_match=latest_check["content_hash_match"],
        control_readable=control_readable,
        report_freshness="FRESH" if report_cycle_matches else "STALE",
        signal_freshness=signal_freshness,
        market_freshness=market_freshness,
        web_market_freshness=web_market_freshness,
        delivery_status=status.value,
        failure_stage=failure_stage,
        last_error=None if status is DeliveryStatus.PASS else failure_stage,
        verified_at_kst=verified_at_kst,
        last_valid_report_time=last_valid_report_time,
        last_valid_report_id=last_valid_report_id,
    )


def control_current_report(state: DeliveryState, current_report_content: Optional[str], last_valid_content: Optional[str]) -> dict:
    if state.delivery_status == DeliveryStatus.PASS.value:
        return {
            "classification": "CURRENT",
            "current_report": current_report_content,
            "alert": None,
            "last_valid": None,
        }
    return {
        "classification": "UNAVAILABLE",
        "current_report": None,
        "alert": "[CURRENT_REPORT_DELIVERY_FAILURE]",
        "last_valid": {
            "classification": "REFERENCE_ONLY",
            "report_time": state.last_valid_report_time,
            "report_id": state.last_valid_report_id,
            "content": last_valid_content,
        } if state.last_valid_report_id else None,
    }


def delivery_status_json(state: DeliveryState) -> str:
    return json.dumps(state.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
