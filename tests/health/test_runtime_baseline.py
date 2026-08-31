import json
import tempfile
import unittest
from pathlib import Path

from agent.health.baseline import compare_runtime

def baseline():
    return {
        "charts":[
            {"symbol":"US100","chart_period":"M30","expected_chart_count":1,"indicators":[
                {"indicator_name":"MACD_Trend_Arrow_Signals_v22_Culture_GeneratedTime",
                 "indicator_count":1,"indicator_order":"VERIFY_REQUIRED",
                 "input_parameters":{},"legacy_present":False,"generatedtime_present":True,
                 "expected_runtime_role":"GENERATEDTIME_SIGNAL"},
                {"indicator_name":"MACD","indicator_count":1,"indicator_order":"VERIFY_REQUIRED",
                 "input_parameters":{"fast":"VERIFY_REQUIRED","slow":"VERIFY_REQUIRED","signal":"VERIFY_REQUIRED"},
                 "legacy_present":False,"generatedtime_present":False,
                 "expected_runtime_role":"TECHNICAL_INDICATOR"}
            ]}
        ]
    }

def runtime(indicators=None, period="M30"):
    if indicators is None:
        indicators=[
            {"indicator_name":"MACD_Trend_Arrow_Signals_v22_Culture_GeneratedTime",
             "input_parameters":{},"generatedtime_present":True,"legacy_present":False,
             "expected_runtime_role":"GENERATEDTIME_SIGNAL"},
            {"indicator_name":"MACD","input_parameters":{"fast":12,"slow":26,"signal":9},
             "generatedtime_present":False,"legacy_present":False,
             "expected_runtime_role":"TECHNICAL_INDICATOR"}
        ]
    return {"schema_version":"1.0","captured_at":"2026-09-01T00:00:00Z","broker":"CultureCapital","server":"VERIFY_REQUIRED","charts":[{"symbol":"US100","chart_period":period,"indicators":indicators}]}

class RuntimeBaselineTests(unittest.TestCase):
    def test_expected_counts_and_unknown_parameter(self):
        result = compare_runtime(baseline(), runtime())
        self.assertEqual(result["status"], "VERIFY_REQUIRED")
        self.assertFalse(result["mismatches"])

    def test_missing_indicator(self):
        r = runtime([{"indicator_name":"MACD","input_parameters":{}}])
        codes={m["code"] for m in compare_runtime(baseline(),r)["mismatches"]}
        self.assertIn("MISSING_INDICATOR", codes)

    def test_duplicate_generatedtime(self):
        r=runtime()
        r["charts"][0]["indicators"].insert(0, dict(r["charts"][0]["indicators"][0]))
        codes={m["code"] for m in compare_runtime(baseline(),r)["mismatches"]}
        self.assertIn("DUPLICATE_INDICATOR", codes)

    def test_unapproved_legacy(self):
        r=runtime()
        r["charts"][0]["indicators"].append({"indicator_name":"MACD_Trend_Arrow_Signals_v22_EZ_Culture_CSV","input_parameters":{}})
        codes={m["code"] for m in compare_runtime(baseline(),r)["mismatches"]}
        self.assertIn("UNAPPROVED_INDICATOR", codes)

    def test_period_mismatch(self):
        result=compare_runtime(baseline(), runtime(period="H1"))
        codes={m["code"] for m in result["mismatches"]}
        self.assertIn("PERIOD_MISMATCH", codes)
        self.assertIn("UNAPPROVED_CHART", codes)

    def test_known_parameter_mismatch(self):
        b=baseline()
        b["charts"][0]["indicators"][1]["input_parameters"]["fast"]=12
        r=runtime()
        r["charts"][0]["indicators"][1]["input_parameters"]["fast"]=9
        codes={m["code"] for m in compare_runtime(b,r)["mismatches"]}
        self.assertIn("PARAMETER_MISMATCH", codes)
    def test_invalid_runtime_snapshot_fails_closed(self):
        result=compare_runtime(baseline(), {"charts":[]})
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["mismatches"][0]["code"], "UNKNOWN")

