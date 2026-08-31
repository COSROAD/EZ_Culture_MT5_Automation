import hashlib
import json
from collections import Counter
from copy import deepcopy

from agent.health.status import HealthStatus


UNKNOWN_VALUES = {"UNKNOWN", "VERIFY_REQUIRED", None}


def is_unknown(value):
    return value is None or (isinstance(value, str) and value in {"UNKNOWN", "VERIFY_REQUIRED"})


def canonical_json_bytes(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def baseline_hash(baseline: dict) -> str:
    copy = deepcopy(baseline)
    copy.pop("baseline_hash", None)
    return hashlib.sha256(canonical_json_bytes(copy)).hexdigest().upper()


def validate_approved_baseline(baseline: dict):
    errors = []
    required = [
        "schema_version",
        "baseline_version",
        "baseline_status",
        "approved_at",
        "approved_by",
        "broker",
        "server",
        "charts",
    ]
    for key in required:
        if key not in baseline:
            errors.append(f"MISSING_FIELD:{key}")

    if baseline.get("baseline_status") != "APPROVED":
        errors.append("BASELINE_NOT_APPROVED")

    if baseline.get("approved_by") != "USER":
        errors.append("APPROVED_BY_NOT_USER")

    charts = baseline.get("charts")
    if not isinstance(charts, list) or not charts:
        errors.append("CHARTS_INVALID")
        charts = []

    required_indicator = [
        "indicator_name",
        "indicator_count",
        "indicator_order",
        "input_parameters",
        "ma_period",
        "ma_method",
        "ma_applied_price",
        "macd_fast",
        "macd_slow",
        "macd_signal",
        "display_rule",
        "signal_color_rule",
        "legacy_present",
        "generatedtime_present",
        "csv_stream",
        "expected_file",
        "expected_schema",
        "expected_runtime_role",
    ]

    for cidx, chart in enumerate(charts):
        for field in ("symbol", "chart_period", "expected_chart_count", "indicators"):
            if field not in chart:
                errors.append(f"CHART_{cidx}_MISSING:{field}")
        indicators = chart.get("indicators", [])
        if not isinstance(indicators, list):
            errors.append(f"CHART_{cidx}_INDICATORS_INVALID")
            continue
        for iidx, ind in enumerate(indicators):
            for field in required_indicator:
                if field not in ind:
                    errors.append(f"CHART_{cidx}_IND_{iidx}_MISSING:{field}")

    verify_required = []

    for top_key in ("approved_at", "server", "baseline_hash"):
        if is_unknown(baseline.get(top_key)):
            verify_required.append(top_key)

    for cidx, chart in enumerate(charts):
        for iidx, ind in enumerate(chart.get("indicators", [])):
            for field in required_indicator:
                value = ind.get(field)
                if is_unknown(value):
                    verify_required.append(f"charts[{cidx}].indicators[{iidx}].{field}")
            for pkey, pvalue in ind.get("input_parameters", {}).items():
                if is_unknown(pvalue):
                    verify_required.append(
                        f"charts[{cidx}].indicators[{iidx}].input_parameters.{pkey}"
                    )

    supplied_hash = baseline.get("baseline_hash")
    if supplied_hash and not is_unknown(supplied_hash):
        if supplied_hash.upper() != baseline_hash(baseline):
            errors.append("BASELINE_HASH_MISMATCH")

    if errors:
        status = HealthStatus.FAIL
    elif verify_required:
        status = HealthStatus.VERIFY_REQUIRED
    else:
        status = HealthStatus.PASS

    return {
        "status": status.value,
        "errors": errors,
        "verify_required": verify_required,
    }


def _chart_key(chart):
    return (chart.get("symbol"), chart.get("chart_period"))



def validate_runtime_snapshot(snapshot: dict):
    errors = []
    for key in ("schema_version", "captured_at", "broker", "server", "charts"):
        if key not in snapshot:
            errors.append(f"MISSING_FIELD:{key}")
    charts = snapshot.get("charts")
    if not isinstance(charts, list):
        errors.append("CHARTS_INVALID")
        charts = []
    for cidx, chart in enumerate(charts):
        for field in ("symbol", "chart_period", "indicators"):
            if field not in chart:
                errors.append(f"CHART_{cidx}_MISSING:{field}")
        indicators = chart.get("indicators", [])
        if not isinstance(indicators, list):
            errors.append(f"CHART_{cidx}_INDICATORS_INVALID")
            continue
        for iidx, ind in enumerate(indicators):
            if "indicator_name" not in ind:
                errors.append(f"CHART_{cidx}_IND_{iidx}_MISSING:indicator_name")
    return {
        "status": HealthStatus.PASS.value if not errors else HealthStatus.FAIL.value,
        "errors": errors,
    }

def compare_runtime(baseline: dict, snapshot: dict) -> dict:
    """Read-only comparison. Never mutates baseline or snapshot."""
    snapshot_validation = validate_runtime_snapshot(snapshot)
    if snapshot_validation["status"] != HealthStatus.PASS.value:
        return {
            "status": HealthStatus.FAIL.value,
            "mismatches": [{
                "code": "UNKNOWN",
                "detail": "RUNTIME_SNAPSHOT_SCHEMA_INVALID",
                "errors": snapshot_validation["errors"],
            }],
            "verify_required": [],
        }
    mismatches = []
    verification_items = []

    baseline_charts = baseline.get("charts", [])
    runtime_charts = snapshot.get("charts", [])

    baseline_by_key = {_chart_key(c): c for c in baseline_charts}
    runtime_by_key = {_chart_key(c): c for c in runtime_charts}

    baseline_symbols = {}
    runtime_symbols = {}
    for chart in baseline_charts:
        baseline_symbols.setdefault(chart.get("symbol"), set()).add(chart.get("chart_period"))
    for chart in runtime_charts:
        runtime_symbols.setdefault(chart.get("symbol"), set()).add(chart.get("chart_period"))

    # Expected charts and explicit period mismatches.
    for key, expected in baseline_by_key.items():
        if key not in runtime_by_key:
            symbol, period = key
            if symbol in runtime_symbols:
                mismatches.append({
                    "code": "PERIOD_MISMATCH",
                    "symbol": symbol,
                    "expected": period,
                    "actual": sorted(runtime_symbols[symbol]),
                })
            else:
                mismatches.append({
                    "code": "MISSING_CHART",
                    "symbol": symbol,
                    "period": period,
                })

    # Any runtime chart not approved is unapproved unless already the wrong-period view
    # of an approved symbol; wrong-period charts remain unapproved as well.
    for key in runtime_by_key:
        if key not in baseline_by_key:
            mismatches.append({
                "code": "UNAPPROVED_CHART",
                "symbol": key[0],
                "period": key[1],
            })

    for key, expected_chart in baseline_by_key.items():
        actual_chart = runtime_by_key.get(key)
        if not actual_chart:
            continue

        expected_inds = expected_chart.get("indicators", [])
        actual_inds = actual_chart.get("indicators", [])

        expected_counts = Counter()
        for ind in expected_inds:
            expected_counts[ind.get("indicator_name")] += int(ind.get("indicator_count", 1))

        actual_counts = Counter(ind.get("indicator_name") for ind in actual_inds)

        for name, expected_count in expected_counts.items():
            actual_count = actual_counts.get(name, 0)
            if actual_count == 0:
                mismatches.append({
                    "code": "MISSING_INDICATOR",
                    "symbol": key[0],
                    "period": key[1],
                    "indicator": name,
                    "expected": expected_count,
                    "actual": 0,
                })
            elif actual_count > expected_count:
                mismatches.append({
                    "code": "DUPLICATE_INDICATOR",
                    "symbol": key[0],
                    "period": key[1],
                    "indicator": name,
                    "expected": expected_count,
                    "actual": actual_count,
                })
            elif actual_count < expected_count:
                mismatches.append({
                    "code": "MISSING_INDICATOR",
                    "symbol": key[0],
                    "period": key[1],
                    "indicator": name,
                    "expected": expected_count,
                    "actual": actual_count,
                })

        for name, actual_count in actual_counts.items():
            if name not in expected_counts:
                mismatches.append({
                    "code": "UNAPPROVED_INDICATOR",
                    "symbol": key[0],
                    "period": key[1],
                    "indicator": name,
                    "actual": actual_count,
                })

        # Compare order and known parameters instance-by-instance when uniquely addressable.
        expected_by_name = {}
        actual_by_name = {}
        for ind in expected_inds:
            expected_by_name.setdefault(ind.get("indicator_name"), []).append(ind)
        for ind in actual_inds:
            actual_by_name.setdefault(ind.get("indicator_name"), []).append(ind)

        for name, expected_instances in expected_by_name.items():
            actual_instances = actual_by_name.get(name, [])
            if len(expected_instances) != len(actual_instances):
                continue

            for idx, expected_ind in enumerate(expected_instances):
                actual_ind = actual_instances[idx]

                exp_order = expected_ind.get("indicator_order")
                act_order = actual_ind.get("indicator_order")
                if not is_unknown(exp_order) and not is_unknown(act_order) and exp_order != act_order:
                    mismatches.append({
                        "code": "INDICATOR_ORDER_MISMATCH",
                        "symbol": key[0],
                        "period": key[1],
                        "indicator": name,
                        "expected": exp_order,
                        "actual": act_order,
                    })
                elif is_unknown(exp_order):
                    verification_items.append({
                        "code": "UNKNOWN",
                        "field": "indicator_order",
                        "symbol": key[0],
                        "period": key[1],
                        "indicator": name,
                    })

                expected_params = expected_ind.get("input_parameters", {})
                actual_params = actual_ind.get("input_parameters", {})
                for pkey, pvalue in expected_params.items():
                    if is_unknown(pvalue):
                        verification_items.append({
                            "code": "UNKNOWN",
                            "field": f"input_parameters.{pkey}",
                            "symbol": key[0],
                            "period": key[1],
                            "indicator": name,
                        })
                        continue
                    if pkey not in actual_params:
                        mismatches.append({
                            "code": "PARAMETER_MISMATCH",
                            "symbol": key[0],
                            "period": key[1],
                            "indicator": name,
                            "parameter": pkey,
                            "expected": pvalue,
                            "actual": "MISSING",
                        })
                    elif actual_params[pkey] != pvalue:
                        mismatches.append({
                            "code": "PARAMETER_MISMATCH",
                            "symbol": key[0],
                            "period": key[1],
                            "indicator": name,
                            "parameter": pkey,
                            "expected": pvalue,
                            "actual": actual_params[pkey],
                        })

                # Role fields are only enforced when explicitly known.
                for role_key in ("legacy_present", "generatedtime_present", "expected_runtime_role"):
                    expected_role = expected_ind.get(role_key)
                    actual_role = actual_ind.get(role_key, "UNKNOWN")
                    if is_unknown(expected_role):
                        verification_items.append({
                            "code": "UNKNOWN",
                            "field": role_key,
                            "symbol": key[0],
                            "period": key[1],
                            "indicator": name,
                        })
                    elif not is_unknown(actual_role) and actual_role != expected_role:
                        mismatches.append({
                            "code": "ROLE_MISMATCH",
                            "symbol": key[0],
                            "period": key[1],
                            "indicator": name,
                            "field": role_key,
                            "expected": expected_role,
                            "actual": actual_role,
                        })

    if mismatches:
        status = HealthStatus.BASELINE_MISMATCH
    elif verification_items:
        status = HealthStatus.VERIFY_REQUIRED
    else:
        status = HealthStatus.PASS

    return {
        "status": status.value,
        "mismatches": mismatches,
        "verify_required": verification_items,
    }
