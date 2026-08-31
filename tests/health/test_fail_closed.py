import json
import tempfile
import unittest
from pathlib import Path

from agent.health.core import aggregate_system_health

class FailClosedTests(unittest.TestCase):
    def test_critical_unknown_not_pass(self):
        modules={
            "github":{"status":"PASS"},
            "fdrive":{"status":"UNKNOWN"},
            "recovery_baseline":{"status":"PASS"},
            "mt5_runtime_baseline":{"status":"PASS"},
        }
        self.assertEqual(aggregate_system_health(modules),"UNKNOWN")

    def test_baseline_mismatch_becomes_fail(self):
        modules={
            "github":{"status":"PASS"},
            "fdrive":{"status":"PASS"},
            "recovery_baseline":{"status":"PASS"},
            "mt5_runtime_baseline":{"status":"BASELINE_MISMATCH"},
        }
        self.assertEqual(aggregate_system_health(modules),"FAIL")
