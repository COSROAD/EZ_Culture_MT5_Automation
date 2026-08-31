import json
import tempfile
import unittest
from pathlib import Path

from agent.health.status import HealthStatus, worst_status, fail_closed_pass

class StatusTests(unittest.TestCase):
    def test_priority_fail(self):
        self.assertEqual(worst_status([HealthStatus.PASS, HealthStatus.FAIL]), HealthStatus.FAIL)

    def test_priority_baseline_mismatch(self):
        self.assertEqual(worst_status([HealthStatus.PASS, HealthStatus.BASELINE_MISMATCH]), HealthStatus.BASELINE_MISMATCH)

    def test_unknown_not_pass(self):
        self.assertFalse(fail_closed_pass(HealthStatus.UNKNOWN))
        self.assertFalse(fail_closed_pass(HealthStatus.VERIFY_REQUIRED))
        self.assertFalse(fail_closed_pass(HealthStatus.PENDING_VALIDATION))
        self.assertTrue(fail_closed_pass(HealthStatus.PASS))
