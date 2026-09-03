
import unittest,tempfile,os,json,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
from agent.shadow_runtime.hardening import *

class HardeningTests(unittest.TestCase):
    def test_lock_first(self):
        with tempfile.TemporaryDirectory() as d:
            l=SingleInstanceLock(str(Path(d)/"lock"));r=l.acquire();self.assertTrue(r.acquired);self.assertEqual(r.state,"LOCK_ACQUIRED");l.release()
    def test_lock_second_denied(self):
        with tempfile.TemporaryDirectory() as d:
            a=SingleInstanceLock(str(Path(d)/"lock"));self.assertTrue(a.acquire().acquired)
            b=SingleInstanceLock(str(Path(d)/"lock"));r=b.acquire();self.assertFalse(r.acquired);self.assertEqual(r.reason,"PROCESS_DUPLICATE");a.release()
    def test_stale_lock_recovery(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"lock";p.mkdir();(p/"owner.json").write_text(json.dumps({"pid":99999999,"heartbeat_utc":"2020-01-01T00:00:00+00:00"}))
            l=SingleInstanceLock(str(p));r=l.acquire();self.assertTrue(r.acquired);self.assertTrue(r.recovered_stale);l.release()
    def test_atomic_write(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x.json";atomic_write_json(str(p),{"a":1});self.assertEqual(json.loads(p.read_text())["a"],1)
    def test_atomic_validation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x.json";self.assertEqual(safe_atomic_state_write(str(p),{"a":1})["status"],"PASS")
    def test_reference_only_previous(self):
        x=prior_state_reference_only({"time_utc":"2026-01-01T00:00:00+00:00"},datetime(2026,1,1,0,10,tzinfo=timezone.utc));self.assertEqual(x["classification"],"REFERENCE_ONLY");self.assertFalse(x["fresh"])
    def test_restart_recompute_required(self):
        x=prior_state_reference_only({"time_utc":"2026-01-01T00:00:00+00:00"},datetime(2026,1,1,0,1,tzinfo=timezone.utc));self.assertEqual(x["reason"],"RECOMPUTE_REQUIRED")
    def test_decision_identity_stable(self):
        d={"market":"GOLD","direction":"LONG","entry_permission":"WAIT","add_permission":"NO_ADD","exit_state":"HOLD","risk_state":"CAUTION","conflict_level":"LOW","final_action":"NO_ADD"};self.assertEqual(make_decision_id(d),make_decision_id(d))
    def test_decision_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            l=DuplicateLedger(str(Path(d)/"l.json"));x={"market":"GOLD","direction":"LONG"};self.assertFalse(l.decision_seen(x));l.record_decision(x);self.assertTrue(l.decision_seen(x))
    def test_event_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            l=DuplicateLedger(str(Path(d)/"l.json"));e=make_event_id("GOLD","REVERSAL","2026-01-01T00:00:00Z");l.record_event(e);self.assertTrue(l.event_seen(e))
    def test_meaningful_suppress(self):
        a={"direction":"LONG","entry_permission":"WAIT","add_permission":"NO_ADD","exit_state":"HOLD","risk_state":"CAUTION","conflict_level":"LOW","invalidation_condition":None,"final_action":"NO_ADD"};self.assertFalse(meaningful_change(a,a.copy()))
    def test_meaningful_change(self):
        self.assertTrue(meaningful_change({"direction":"LONG"},{"direction":"SHORT"}))
    def test_heartbeat(self):
        x=heartbeat_payload(os.getpid(),"t",None,"LOCK_ACQUIRED","FRESH","FRESH","FRESH","FRESH","VERIFY_REQUIRED",{"GOLD":"PASS"},None,"NONE");self.assertIn(x["RUNTIME_STATUS"],("RUNNING","DEGRADED"))
    def test_market_closed_not_error(self):
        x=heartbeat_payload(os.getpid(),"t",None,"LOCK_ACQUIRED","FRESH","FRESH","FRESH","FRESH","VERIFY_REQUIRED",{},None,"NONE",True);self.assertEqual(x["RUNTIME_STATUS"],"MARKET_CLOSED")
    def test_macro_gap_preserved(self):
        x=heartbeat_payload(os.getpid(),"t",None,"LOCK_ACQUIRED","FRESH","FRESH","FRESH","FRESH","VERIFY_REQUIRED",{},None,"NONE");self.assertEqual(x["MACRO_STATUS"],"VERIFY_REQUIRED")
    def test_stale_tick_health_degraded(self):
        x=heartbeat_payload(os.getpid(),"t",None,"LOCK_ACQUIRED","STALE","FRESH","FRESH","FRESH","VERIFY_REQUIRED",{},None,"NONE");self.assertEqual(x["RUNTIME_STATUS"],"DEGRADED")
    def test_role_lock_identity(self):
        with tempfile.TemporaryDirectory() as d:
            l=SingleInstanceLock(str(Path(d)/"lock"),role="SHADOW_RUNTIME");r=l.acquire();o=json.loads((Path(d)/"lock"/"owner.json").read_text());self.assertEqual(o["role"],"SHADOW_RUNTIME");l.release()
    def test_no_order_path(self):
        text=Path(__import__("agent.shadow_runtime.hardening").shadow_runtime.hardening.__file__).read_text(encoding="utf-8");self.assertNotIn("OrderSend",text);self.assertNotIn("CTrade",text)
