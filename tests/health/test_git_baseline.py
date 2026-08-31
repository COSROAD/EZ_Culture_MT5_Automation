import json
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch
from agent.adapters.git import read_git_health

class GitBaselineTests(unittest.TestCase):
    @patch("agent.adapters.git._run")
    def test_local_remote_match_parsing(self, run):
        outputs={
            ("remote","get-url","origin"):"https://github.com/COSROAD/EZ_Culture_MT5_Automation.git",
            ("rev-parse","main"):"abc",
            ("ls-remote","origin","refs/heads/main"):"abc\trefs/heads/main",
            ("status","--porcelain","--untracked-files=all"):"",
        }
        run.side_effect=lambda workspace,*args: outputs[args]
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            (p/"docs/protection").mkdir(parents=True)
            (p/"docs/protection/PROTECTED_BASELINE_SHA256.md").write_text("x")
            (p/"a").write_text("x")
            result=read_git_health(
                p,
                "https://github.com/COSROAD/EZ_Culture_MT5_Automation.git",
                "abc",
                ["a"],
            )
        self.assertEqual(result["status"],"PASS")
        self.assertEqual(result["remote_main"],"abc")
