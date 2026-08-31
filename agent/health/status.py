from enum import Enum
from typing import Iterable


class HealthStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    MARKET_CLOSED = "MARKET_CLOSED"
    PENDING_VALIDATION = "PENDING_VALIDATION"
    VERIFY_REQUIRED = "VERIFY_REQUIRED"
    BASELINE_MISMATCH = "BASELINE_MISMATCH"
    NOT_REQUESTED = "NOT_REQUESTED"


# Highest severity first. Special non-failure states are deliberately below UNKNOWN.
_PRIORITY = {
    HealthStatus.FAIL: 100,
    HealthStatus.BASELINE_MISMATCH: 90,
    HealthStatus.WARN: 80,
    HealthStatus.UNKNOWN: 70,
    HealthStatus.VERIFY_REQUIRED: 70,
    HealthStatus.PENDING_VALIDATION: 70,
    HealthStatus.MARKET_CLOSED: 20,
    HealthStatus.NOT_REQUESTED: 10,
    HealthStatus.PASS: 0,
}


def normalize_status(value):
    if isinstance(value, HealthStatus):
        return value
    return HealthStatus(str(value))


def worst_status(statuses: Iterable[HealthStatus]) -> HealthStatus:
    values = [normalize_status(s) for s in statuses]
    if not values:
        return HealthStatus.UNKNOWN
    return max(values, key=lambda s: _PRIORITY[s])


def fail_closed_pass(status: HealthStatus) -> bool:
    """Only literal PASS is treated as a pass."""
    return normalize_status(status) is HealthStatus.PASS
