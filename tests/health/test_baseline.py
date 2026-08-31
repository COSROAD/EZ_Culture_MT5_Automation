import json
import tempfile
import unittest
from pathlib import Path

from agent.health.baseline import baseline_hash, validate_approved_baseline

def minimal_baseline():
    b = {
        "schema_version":"1.0",
        "baseline_version":"V1",
        "baseline_status":"APPROVED",
        "approved_at":"2026-09-01T00:00:00Z",
        "approved_by":"USER",
        "baseline_hash":"",
        "broker":"CultureCapital",
        "server":"CultureCapital-Server",
        "charts":[{
            "symbol":"US100","chart_period":"M30","expected_chart_count":1,
            "indicators":[{
                "indicator_name":"MACD","indicator_count":1,"indicator_order":1,
                "input_parameters":{"fast":12},
                "ma_period":30,"ma_method":"SMA","ma_applied_price":"CLOSE",
                "macd_fast":12,"macd_slow":26,"macd_signal":9,
                "display_rule":"KNOWN","signal_color_rule":"KNOWN",
                "legacy_present":False,"generatedtime_present":False,
                "csv_stream":"NONE","expected_file":"NONE",
                "expected_schema":"NONE","expected_runtime_role":"TECHNICAL_INDICATOR"
            }]
        }]
    }
    b["baseline_hash"] = baseline_hash(b)
    return b

class BaselineTests(unittest.TestCase):
    def test_valid_baseline(self):
        self.assertEqual(validate_approved_baseline(minimal_baseline())["status"], "PASS")

    def test_verify_required_is_not_pass(self):
        b = minimal_baseline()
        b["baseline_hash"] = "VERIFY_REQUIRED"
        self.assertEqual(validate_approved_baseline(b)["status"], "VERIFY_REQUIRED")

    def test_invalid_baseline(self):
        b = minimal_baseline()
        del b["approved_by"]
        self.assertEqual(validate_approved_baseline(b)["status"], "FAIL")

    def test_baseline_hash_stable_and_checked(self):
        b = minimal_baseline()
        h = baseline_hash(b)
        self.assertEqual(len(h), 64)
        b["baseline_hash"] = h
        self.assertEqual(validate_approved_baseline(b)["status"], "PASS")
        b["broker"] = "Changed"
        self.assertIn("BASELINE_HASH_MISMATCH", validate_approved_baseline(b)["errors"])
