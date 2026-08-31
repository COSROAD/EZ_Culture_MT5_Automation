import hashlib
import json


def runtime_hash(snapshot: dict) -> str:
    data = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest().upper()


def build_recovery_report(baseline: dict, snapshot: dict, comparison: dict) -> dict:
    mismatches = comparison.get("mismatches", [])
    required = bool(mismatches)
    return {
        "RECOVERY_REQUIRED": required,
        "BASELINE_VERSION": baseline.get("baseline_version", "UNKNOWN"),
        "BASELINE_HASH": baseline.get("baseline_hash", "UNKNOWN"),
        "CURRENT_RUNTIME_HASH": runtime_hash(snapshot),
        "MISMATCHES": mismatches,
        "RECOVERY_ACTION_CANDIDATE": (
            "RESTORE_FROM_APPROVED_BASELINE" if required else "NONE"
        ),
        "RECOVERY_AUTHORIZED": False,
    }
