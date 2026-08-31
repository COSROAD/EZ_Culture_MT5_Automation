from datetime import datetime, timedelta, timezone

from agent.health.status import HealthStatus, worst_status


CRITICAL_MODULES = {
    "github",
    "fdrive",
    "recovery_baseline",
    "mt5_runtime_baseline",
}


def new_health_document(agent_version="phase1"):
    now = datetime.now(timezone.utc)
    return {
        "schema_version": "1.0",
        "generated_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=15)).isoformat(),
        "agent_version": agent_version,
        "system_health_status": HealthStatus.UNKNOWN.value,
        "delivery_lifecycle_status": HealthStatus.UNKNOWN.value,
        "modules": {},
        "alerts": [],
        "warnings": [],
        "failures": [],
        "task_candidates": [],
    }


def aggregate_system_health(modules: dict) -> str:
    critical = []
    all_statuses = []
    for name, payload in modules.items():
        status = HealthStatus(payload.get("status", HealthStatus.UNKNOWN.value))
        all_statuses.append(status)
        if name in CRITICAL_MODULES:
            critical.append(status)

    # Fail-closed for critical modules.
    if any(s in (HealthStatus.FAIL, HealthStatus.BASELINE_MISMATCH) for s in critical):
        return HealthStatus.FAIL.value
    if any(s in (HealthStatus.UNKNOWN, HealthStatus.VERIFY_REQUIRED) for s in critical):
        return HealthStatus.UNKNOWN.value

    overall = worst_status(all_statuses)
    if overall is HealthStatus.BASELINE_MISMATCH:
        return HealthStatus.FAIL.value
    return overall.value
