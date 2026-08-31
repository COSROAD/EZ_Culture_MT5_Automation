import json
import tempfile
import unittest
from pathlib import Path

import hashlib
from agent.adapters.filesystem import check_core6
from agent.health.recovery import build_recovery_report

class FDriveCore6Tests(unittest.TestCase):
    def test_core6_sha_match_and_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x"
            p.write_bytes(b"abc")
            h=hashlib.sha256(b"abc").hexdigest().upper()
            good=check_core6([{"source_id":"X","path":str(p),"sha256":h}])
            self.assertEqual(good["status"],"PASS")
            bad=check_core6([{"source_id":"X","path":str(p),"sha256":"0"*64}])
            self.assertEqual(bad["status"],"FAIL")

    def test_recovery_required_generation(self):
        baseline={"baseline_version":"V1","baseline_hash":"ABC"}
        snapshot={"charts":[]}
        comparison={"mismatches":[{"code":"MISSING_CHART"}]}
        report=build_recovery_report(baseline,snapshot,comparison)
        self.assertTrue(report["RECOVERY_REQUIRED"])
        self.assertFalse(report["RECOVERY_AUTHORIZED"])
