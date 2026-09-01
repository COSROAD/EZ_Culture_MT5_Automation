from collections import Counter

from agent.adapters.mt5_profile import (
    MEASURED,
    MEASURED_RAW,
    VERIFY_REQUIRED,
    PROTECTED_GENERATED,
    PROTECTED_LEGACY,
)

TARGETS = ("US100", "XAUUSD", "XAGUSD", "WTI", "BTCUSD")


def expected_signature(symbol):
    signature = {
        "Ichimoku Kinko Hyo": 1,
        "Moving Average": 2,
        PROTECTED_GENERATED: 1,
        "MACD": 1,
    }
    if symbol == "US100":
        signature[PROTECTED_LEGACY] = 1
    return signature


def compare_measured_chart(chart):
    mismatches = []
    verify_required = []
    symbol = chart["symbol"]

    if chart["chart_period"] != "M30":
        mismatches.append({
            "code": "PERIOD_MISMATCH",
            "symbol": symbol,
            "expected": "M30",
            "actual": chart["chart_period"],
        })

    counts = Counter(i["indicator_name"] for i in chart["indicators"])
    expected = expected_signature(symbol)

    for name, expected_count in expected.items():
        actual_count = counts.get(name, 0)
        if actual_count != expected_count:
            mismatches.append({
                "code": "INDICATOR_COUNT_MISMATCH",
                "symbol": symbol,
                "indicator": name,
                "expected": expected_count,
                "actual": actual_count,
            })

    for name, actual_count in counts.items():
        if name not in expected:
            mismatches.append({
                "code": "UNAPPROVED_INDICATOR",
                "symbol": symbol,
                "indicator": name,
                "actual": actual_count,
            })

    return {"mismatches": mismatches, "verify_required": verify_required}


def extract_parameter_evidence(chart):
    evidence = {"MA": [], "MACD": [], "ICHIMOKU": []}
    for ind in chart["indicators"]:
        row = {
            "identity": ind["indicator_name"],
            "order": ind["indicator_order"],
            "input_parameters": ind.get("input_parameters", {}),
        }
        if ind["indicator_name"] == "Moving Average":
            evidence["MA"].append(row)
        elif ind["indicator_name"] == "MACD":
            evidence["MACD"].append(row)
        elif ind["indicator_name"] == "Ichimoku Kinko Hyo":
            evidence["ICHIMOKU"].append(row)
    return evidence


def build_runtime_snapshot(*, broker, server, charts, captured_at, profile_candidate):
    snapshot = {
        "schema_version": "2.0",
        "captured_at": captured_at,
        "broker": {"value": broker, "class": MEASURED},
        "server": {"value": server, "class": MEASURED},
        "active_runtime_profile": {
            "value": profile_candidate,
            "class": VERIFY_REQUIRED,
            "confirmed": False,
        },
        "charts": [],
    }

    for chart in charts:
        snapshot["charts"].append({
            "symbol": {"value": chart["symbol"], "class": MEASURED},
            "chart_period": {"value": chart["chart_period"], "class": MEASURED},
            "chart_count": {"value": 1, "class": MEASURED},
            "indicators": [{
                "indicator_name": {"value": ind["indicator_name"], "class": MEASURED},
                "indicator_count": {"value": ind["indicator_count"], "class": MEASURED},
                "indicator_order": {"value": ind["indicator_order"], "class": MEASURED},
                "indicator_window": {"value": ind["indicator_window"], "class": MEASURED},
                "input_parameters": {
                    "value": ind.get("input_parameters", {}),
                    "class": MEASURED_RAW if ind.get("input_parameters") else "NOT_AVAILABLE",
                },
            } for ind in chart["indicators"]],
        })
    return snapshot


def summarize_roles(charts):
    result = {}
    for chart in charts:
        counts = Counter(i["indicator_name"] for i in chart["indicators"])
        result[chart["symbol"]] = {
            "generatedtime": counts.get(PROTECTED_GENERATED, 0),
            "legacy": counts.get(PROTECTED_LEGACY, 0),
        }
    return result
