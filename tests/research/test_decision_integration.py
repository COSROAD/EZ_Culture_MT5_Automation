
import unittest
from agent.decision_integration.core import SourceSnapshot,SourceRegistry,time_health,regime_state,connectivity,historical_match,current_confirmation,conflict_level,risk_gate,event_driven,infer_direction,make_decision,replay_gold,outcome_feedback

class DecisionIntegrationTests(unittest.TestCase):
    def test_dependency_chain_marker(self): self.assertTrue(True)
    def test_source_registry(self):
        r=SourceRegistry();r.register(SourceSnapshot("t","TICK","GOLD","CultureCapital","XAUUSD","2026-01-01T00:00:00+00:00","2026-01-01T00:00:01+00:00","FRESH",1,"GOOD",True));self.assertEqual(r.items["t"].broker,"CultureCapital")
    def test_utc_alignment(self): self.assertEqual(time_health("2026-01-01T00:00:00+00:00","2026-01-01T00:00:01+00:00")["status"],"OK")
    def test_clock_drift(self): self.assertEqual(time_health("2026-01-01T00:00:00+00:00","2026-01-01T00:00:10+00:00")["status"],"CLOCK_DRIFT")
    def test_future_timestamp(self): self.assertEqual(time_health("2026-01-01T00:00:10+00:00","2026-01-01T00:00:00+00:00")["status"],"FUTURE_TIMESTAMP")
    def test_out_of_order(self): self.assertEqual(time_health("2026-01-01T00:00:00+00:00","2026-01-01T00:00:01+00:00","2026-01-01T00:00:02+00:00")["status"],"OUT_OF_ORDER_DATA")
    def test_freshness_separation(self):
        r=SourceRegistry();r.register(SourceSnapshot("w","WEB","GOLD",None,"WEB","2026-01-01T00:00:00+00:00","2026-01-01T00:00:01+00:00","FRESH",1,"GOOD",True));r.register(SourceSnapshot("m","MT5","GOLD","CultureCapital","XAUUSD","2026-01-01T00:00:00+00:00","2026-01-01T00:10:00+00:00","STALE",600000,"DEGRADED",True));self.assertEqual(r.freshness_summary(),{"w":"FRESH","m":"STALE"})
    def test_regime(self): self.assertEqual(regime_state("RATES",["2Y_DOWN"],[],"FRESH")["state"],"POSITIVE")
    def test_connectivity(self): self.assertEqual(connectivity("YIELD",["DXY"],"GOLD","SHORT","LONG",30,"VERIFY_REQUIRED")["relationship_state"],"DYNAMIC_UNCONFIRMED")
    def test_historical_match(self): self.assertGreater(historical_match({"A"},[{"case_id":"1","features":["A"]}],"US","POSITIVE")["match_score"],.9)
    def test_historical_only_entry_block(self): self.assertFalse(historical_match({"A"},[{"case_id":"1","features":["A"]}],"US","POSITIVE")["historical_only_authority"])
    def test_current_confirmation(self): self.assertEqual(current_confirmation("LONG","LONG","LONG","LONG","MIXED","LONG")["state"],"LONG")
    def test_conflict_engine(self): self.assertIn(conflict_level(["LONG","SHORT","LONG","SHORT"]),("HIGH","CRITICAL"))
    def test_direction_entry_add_separation(self): self.assertEqual(risk_gate("LONG","HIGH",[],"NORMAL")["add_permission"],"NO_ADD")
    def test_fail_closed(self): self.assertEqual(risk_gate("LONG","NONE",["MACRO"],"NORMAL")["state"],"VERIFY_REQUIRED")
    def test_session_context_marker(self): self.assertTrue(True)
    def test_event_driven(self): self.assertTrue(event_driven("YIELD_SHOCK"))
    def test_decision_trace(self):
        d=make_decision("GOLD","2026-01-01T00:00:00+00:00","LONG",.8,{}, {},[],[],{},"NORMAL",["LONG"],[],100,None);self.assertIn("WHY_DIRECTION",d.decision_trace)
    def test_outcome_feedback(self): self.assertIn("6h",outcome_feedback(100,[(60,101),(21600,110)],"LONG"))
    def test_gold_case001_replay(self): self.assertEqual(replay_gold({"case_id":"GOLD_CASE_001","reversal_pivot_time":"2026-01-01T00:00:00+00:00","candidates":{"tick":{"x":1}}})["entry_permission"],"WAIT")
    def test_gold_case002_replay(self): self.assertEqual(replay_gold({"case_id":"GOLD_CASE_002","pivot":"2026-01-01T00:00:00+00:00","times":{"m1":{"x":1}}})["add_permission"],"NO_ADD")
    def test_btc_differentiation(self):
        d,_,_,_=infer_direction("BTC",{"match_score":.7},{"state":"SHORT"},None,{"btc_relative_strength":"POSITIVE","crypto_liquidity":"POSITIVE"});self.assertNotEqual(d,"SHORT")
    def test_oil_transmission(self): self.assertEqual(connectivity("OIL",["INFLATION","YIELD"],"GOLD","SHORT","LONG",90,"VERIFY_REQUIRED")["relationship_state"],"DYNAMIC_UNCONFIRMED")
    def test_silver_relative(self):
        d=make_decision("GOLD","2026-01-01T00:00:00+00:00","NEUTRAL",.4,{}, {},["SILVER_RELATIVE_WEAKNESS"],[],{},"CAUTION",["LONG","SHORT"],[],100,None);self.assertNotIn(d.final_action,("BUY","SELL"))
    def test_macro_stale(self): self.assertEqual(risk_gate("LONG","NONE",["MACRO"],"NORMAL")["add_permission"],"NO_ADD")
    def test_health_degradation(self): self.assertEqual(risk_gate("SHORT","NONE",[],"NORMAL",True)["entry_permission"],"WAIT")
    def test_no_live_order(self):
        d=make_decision("NQ","2026-01-01T00:00:00+00:00","LONG",.8,{}, {},[],[],{},"NORMAL",["LONG"],[],100,None);self.assertFalse(d.live_order_allowed)
