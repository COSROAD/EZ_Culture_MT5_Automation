
import unittest,tempfile,json
from datetime import datetime,timezone,timedelta
from pathlib import Path
from agent.shadow_runtime.runtime import *

class T(unittest.TestCase):
    def ticks(self):
        t=datetime(2026,1,1,tzinfo=timezone.utc)
        return [{"time":t+timedelta(seconds=i*10),"BID":100+i*.1,"ASK":100.2+i*.1,"SPREAD":.2,"mid":100.1+i*.1} for i in range(40)]
    def test_01_mapping(self):self.assertEqual(set(MARKETS),{"NQ","GOLD","SILVER","OIL","BTC"})
    def test_02_broker(self):self.assertEqual(MARKETS["NQ"]["EZSquare"],"NQ2.ez2")
    def test_03_tick(self):self.assertEqual(windows(self.ticks())["freshness"],"FRESH")
    def test_04_30(self):self.assertIn("30",windows(self.ticks())["windows"])
    def test_05_60(self):self.assertIn("60",windows(self.ticks())["windows"])
    def test_06_180(self):self.assertIn("180",windows(self.ticks())["windows"])
    def test_07_300(self):self.assertIn("300",windows(self.ticks())["windows"])
    def test_08_m1(self):self.assertEqual(m1_state(self.ticks())["freshness"],"FRESH")
    def test_09_m5(self):self.assertIn("source",m5_state(self.ticks()))
    def test_10_signal(self):
        with tempfile.TemporaryDirectory() as d:self.assertIn("freshness",signal_state(d,"GOLD","CultureCapital","XAUUSD"))
    def test_11_macro(self):self.assertEqual(macro_gap()["DXY"]["status"],"VERIFY_REQUIRED")
    def test_12_session(self):self.assertIsInstance(session(datetime(2026,1,1,tzinfo=timezone.utc)),str)
    def test_13_dst(self):self.assertIsInstance(session(datetime(2026,7,1,tzinfo=timezone.utc)),str)
    def test_14_event(self):self.assertTrue(event_driven("YIELD_SHOCK"))
    def test_15_duplicate(self):
        a={"direction":"LONG","entry_permission":"WAIT","add_permission":"NO_ADD","risk_state":"CAUTION","conflict_level":"LOW","final_action":"NO_ADD"};self.assertFalse(meaningful(a,a.copy()))
    def test_16_change(self):self.assertTrue(meaningful({"direction":"LONG"},{"direction":"SHORT"}))
    def test_17_atomic(self):
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/"x.json");atomic_json(p,{"a":1});self.assertEqual(json.loads(Path(p).read_text())["a"],1)
    def test_18_stale_restart(self):self.assertFalse(restart_guard({"time_utc":"2026-01-01T00:00:00+00:00"},datetime(2026,1,1,0,10,tzinfo=timezone.utc))["reuse_current"])
    def test_19_fresh_restart(self):self.assertTrue(restart_guard({"time_utc":"2026-01-01T00:00:00+00:00"},datetime(2026,1,1,0,1,tzinfo=timezone.utc))["reuse_current"])
    def test_20_ooo(self):self.assertEqual(__import__("agent.decision_integration.core").decision_integration.core.time_health("2026-01-01T00:00:00+00:00","2026-01-01T00:00:01+00:00","2026-01-01T00:00:02+00:00")["status"],"OUT_OF_ORDER_DATA")
    def test_21_drift(self):self.assertEqual(__import__("agent.decision_integration.core").decision_integration.core.time_health("2026-01-01T00:00:00+00:00","2026-01-01T00:00:10+00:00")["status"],"CLOCK_DRIFT")
    def test_22_hist(self):self.assertFalse(historical_match({"A"},[{"case_id":"1","features":["A"]}],"US","MIXED")["historical_only_authority"])
    def test_23_conflict(self):self.assertIn(conflict_level(["LONG","SHORT","LONG","SHORT"]),("HIGH","CRITICAL"))
    def test_24_risk(self):self.assertEqual(risk_gate("LONG","HIGH",[],"NORMAL")["add_permission"],"NO_ADD")
    def test_25_gold(self):
        d=decide("GOLD","CultureCapital","XAUUSD",windows(self.ticks()),m1_state(self.ticks()),m5_state(self.ticks()),{"signal":"BUY","freshness":"FRESH"},[],True);self.assertEqual(d["entry_permission"],"WAIT")
    def test_26_btc(self):self.assertNotEqual(MARKETS["BTC"]["CultureCapital"],MARKETS["NQ"]["CultureCapital"])
    def test_27_oil(self):self.assertTrue(event_driven("OIL_SHOCK"))
    def test_28_silver(self):self.assertIn("GOLD_SILVER",cross({"GOLD":{"price":1},"SILVER":{"price":2}}))
    def test_29_nq(self):self.assertIn("OIL_NQ",cross({"OIL":{"price":1},"NQ":{"price":2}}))
    def test_30_no_order(self):self.assertNotIn("OrderSend",Path(__import__("agent.shadow_runtime.runtime").shadow_runtime.runtime.__file__).read_text(encoding="utf-8"))
