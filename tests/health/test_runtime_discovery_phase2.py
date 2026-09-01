import json
import unittest

from agent.adapters.mt5_profile import (
    parse_chart_text,
    PROTECTED_GENERATED,
    PROTECTED_LEGACY,
)
from agent.health.runtime_discovery import (
    build_runtime_snapshot,
    compare_measured_chart,
    extract_parameter_evidence,
    summarize_roles,
)

def chart_text(symbol, legacy=False):
    custom_legacy = f"""
<indicator>
name=Custom Indicator
path={PROTECTED_LEGACY}.ex5
</indicator>
""" if legacy else ""
    return f"""
<chart>
symbol={symbol}
period=30
<window>
<indicator>
name=Main
</indicator>
<indicator>
name=Ichimoku Kinko Hyo
tenkan=9
kijun=26
senkou=52
</indicator>
<indicator>
name=Moving Average
period=30
shift=0
method=0
apply=0
</indicator>
<indicator>
name=Moving Average
period=60
shift=0
method=0
apply=0
</indicator>
{custom_legacy}
<indicator>
name=Custom Indicator
path={PROTECTED_GENERATED}.ex5
</indicator>
</window>
<window>
<indicator>
name=MACD
fast=12
slow=26
signal=9
apply=0
</indicator>
</window>
</chart>
"""

class Phase2RuntimeDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.charts = [
            parse_chart_text(chart_text("US100", legacy=True)),
            parse_chart_text(chart_text("XAUUSD")),
            parse_chart_text(chart_text("XAGUSD")),
            parse_chart_text(chart_text("WTI")),
            parse_chart_text(chart_text("BTCUSD")),
        ]

    def test_main_metadata_excluded(self):
        self.assertTrue(all(
            "Main" not in [i["indicator_name"] for i in chart["indicators"]]
            for chart in self.charts
        ))

    def test_all_five_m30(self):
        self.assertEqual([c["chart_period"] for c in self.charts], ["M30"] * 5)

    def test_generatedtime_exactly_one(self):
        roles = summarize_roles(self.charts)
        self.assertTrue(all(roles[s]["generatedtime"] == 1 for s in roles))

    def test_us100_legacy_one(self):
        roles = summarize_roles(self.charts)
        self.assertEqual(roles["US100"]["legacy"], 1)

    def test_other_legacy_zero(self):
        roles = summarize_roles(self.charts)
        self.assertTrue(all(roles[s]["legacy"] == 0 for s in ("XAUUSD","XAGUSD","WTI","BTCUSD")))

    def test_ma_30_60_parse(self):
        ev = extract_parameter_evidence(self.charts[0])
        periods = [row["input_parameters"]["period"] for row in ev["MA"]]
        self.assertEqual(periods, ["30","60"])

    def test_macd_12_26_9_parse(self):
        ev = extract_parameter_evidence(self.charts[0])
        params = ev["MACD"][0]["input_parameters"]
        self.assertEqual((params["fast"],params["slow"],params["signal"]), ("12","26","9"))

    def test_ichimoku_9_26_52_parse(self):
        ev = extract_parameter_evidence(self.charts[0])
        params = ev["ICHIMOKU"][0]["input_parameters"]
        self.assertEqual((params["tenkan"],params["kijun"],params["senkou"]), ("9","26","52"))

    def test_verify_required_preserved_in_snapshot(self):
        snap = build_runtime_snapshot(
            broker="CultureCapital",
            server="CultureCapital-Server",
            charts=self.charts,
            captured_at="2026-09-01T00:00:00Z",
            profile_candidate="PROFILE 3",
        )
        self.assertFalse(snap["active_runtime_profile"]["confirmed"])
        self.assertEqual(snap["active_runtime_profile"]["class"], "VERIFY_REQUIRED")

    def test_snapshot_classification_preserved(self):
        snap = build_runtime_snapshot(
            broker="CultureCapital",
            server="CultureCapital-Server",
            charts=self.charts,
            captured_at="2026-09-01T00:00:00Z",
            profile_candidate="PROFILE 3",
        )
        self.assertEqual(snap["broker"]["class"], "MEASURED")
        self.assertEqual(snap["charts"][0]["chart_period"]["class"], "MEASURED")

    def test_no_credential_fields(self):
        snap = build_runtime_snapshot(
            broker="CultureCapital",
            server="CultureCapital-Server",
            charts=self.charts,
            captured_at="2026-09-01T00:00:00Z",
            profile_candidate="PROFILE 3",
        )
        text = json.dumps(snap).lower()
        for forbidden in ("password","private_key","oauth","api_key","account_number"):
            self.assertNotIn(forbidden, text)

    def test_compare_has_no_mismatch(self):
        for chart in self.charts:
            self.assertEqual(compare_measured_chart(chart)["mismatches"], [])

if __name__ == "__main__":
    unittest.main()
