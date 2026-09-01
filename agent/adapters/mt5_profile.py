import re
from collections import Counter

MEASURED = "MEASURED"
MEASURED_RAW = "MEASURED_RAW"
REFERENCE_ONLY = "REFERENCE_ONLY"
VERIFY_REQUIRED = "VERIFY_REQUIRED"
NOT_AVAILABLE = "NOT_AVAILABLE"

PROTECTED_LEGACY = "MACD_Trend_Arrow_Signals_v22_EZ_Culture_CSV"
PROTECTED_GENERATED = "MACD_Trend_Arrow_Signals_v22_Culture_GeneratedTime"


def _blocks(text: str, tag: str):
    return re.findall(rf"<{tag}>(.*?)</{tag}>", text, flags=re.I | re.S)


def _kv_lines(block: str):
    out = {}
    for line in block.splitlines():
        line = line.strip().strip("\x00")
        if not line or line.startswith("<") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out.setdefault(key.strip(), []).append(value.strip())
    return out


def _first(mapping, *names):
    lower = {k.lower(): v for k, v in mapping.items()}
    for name in names:
        vals = lower.get(name.lower())
        if vals:
            return vals[0]
    return None


def normalize_period(value):
    if value is None:
        return NOT_AVAILABLE
    s = str(value).strip().upper()
    direct = {
        "1":"M1","2":"M2","3":"M3","4":"M4","5":"M5","6":"M6",
        "10":"M10","12":"M12","15":"M15","20":"M20","30":"M30",
        "60":"H1","120":"H2","180":"H3","240":"H4","360":"H6",
        "480":"H8","720":"H12","1440":"D1","10080":"W1","43200":"MN1",
    }
    enum_map = {
        "16385":"H1","16386":"H2","16387":"H3","16388":"H4",
        "16390":"H6","16392":"H8","16396":"H12",
        "16408":"D1","32769":"W1","49153":"MN1",
    }
    if s in direct:
        return direct[s]
    if s in enum_map:
        return enum_map[s]
    if s.startswith(("M","H","D","W","MN")):
        return s
    return s


def canonical_indicator_name(candidates):
    joined = " | ".join(candidates)
    if PROTECTED_GENERATED in joined:
        return PROTECTED_GENERATED
    if PROTECTED_LEGACY in joined:
        return PROTECTED_LEGACY
    if re.search(r"(?i)Ichimoku", joined):
        return "Ichimoku Kinko Hyo"
    if re.search(r"(?i)Moving Average", joined):
        return "Moving Average"
    if re.search(r"(?i)\bCustom Indicator\b", joined):
        return "Custom Indicator"
    for candidate in candidates:
        base = candidate.replace("\\", "/").split("/")[-1]
        base = re.sub(r"\.(ex5|mq5)$", "", base, flags=re.I)
        if re.fullmatch(r"(?i)MACD", base):
            return "MACD"
        if base == "Main":
            return "Main"
    return candidates[0] if candidates else NOT_AVAILABLE


def _name_candidates(kv, raw_block):
    vals = []
    for key, values in kv.items():
        if key.lower() in {"name","short_name","shortname","path","program","indicator","source","filename","file"}:
            vals.extend(values)
    for protected in (PROTECTED_LEGACY, PROTECTED_GENERATED):
        if protected in raw_block:
            vals.append(protected)
    return list(dict.fromkeys(vals))


def _safe_params(kv):
    params = {}
    for key, values in kv.items():
        kl = key.lower()
        if any(secret in kl for secret in ("password","token","secret","credential","login","account","privatekey","api_key","apikey")):
            continue
        if any(term in kl for term in (
            "period","shift","method","apply","price","fast","slow","signal",
            "tenkan","kijun","senkou","parameter","input"
        )):
            params[key] = values[0] if len(values) == 1 else values
    return params


def parse_chart_text(text: str):
    header = text.split("<window>", 1)[0]
    hkv = _kv_lines(header)
    symbol = _first(hkv, "symbol") or NOT_AVAILABLE
    period_raw = _first(hkv, "period", "timeframe", "tf")
    period = normalize_period(period_raw)

    indicators = []
    order = 0
    for window_index, window_block in enumerate(_blocks(text, "window")):
        for indicator_block in _blocks(window_block, "indicator"):
            ikv = _kv_lines(indicator_block)
            candidates = _name_candidates(ikv, indicator_block)
            name = canonical_indicator_name(candidates)

            # MT5 .chr "Main" describes the chart pane and is not an attached indicator.
            if name == "Main":
                continue

            order += 1
            indicators.append({
                "indicator_name": name,
                "indicator_order": order,
                "indicator_window": window_index,
                "input_parameters": _safe_params(ikv),
                "identity_candidates": candidates,
            })

    counts = Counter(i["indicator_name"] for i in indicators)
    for item in indicators:
        item["indicator_count"] = counts[item["indicator_name"]]

    return {
        "symbol": symbol,
        "chart_period": period,
        "period_raw": period_raw if period_raw is not None else NOT_AVAILABLE,
        "indicators": indicators,
    }


def classify_value(value, classification=MEASURED):
    if value in (None, "", "UNKNOWN", NOT_AVAILABLE):
        return {"value": NOT_AVAILABLE, "class": NOT_AVAILABLE}
    return {"value": value, "class": classification}
