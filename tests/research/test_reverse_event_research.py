
import unittest
from datetime import datetime, timezone, timedelta

from agent.research_engine.event_engine import ThresholdPolicy, candidate_threshold, detect_event, reverse_lookback, build_control_sample, lead_lag_record, make_event_id
from agent.research_engine.features import tick_features, m1_features, m5_features
from agent.research_engine.shadow import next_direction, risk_action, build_shadow, make_shadow_id
from agent.research_engine.performance import mfe_mae, evaluate_shadow
from agent.research_engine.time_alignment import align_time

class ReverseEventResearchTests(unittest.TestCase):
    def test_event_up_detection(self): self.assertEqual(detect_event(.001,.02,.01),"RAPID_UP_MOVE")
    def test_event_down_detection(self): self.assertEqual(detect_event(-.001,-.02,.01),"RAPID_DOWN_MOVE")
    def test_reversal_up_detection(self): self.assertEqual(detect_event(-.01,.02,.01),"REVERSAL_UP")
    def test_reversal_down_detection(self): self.assertEqual(detect_event(.01,-.02,.01),"REVERSAL_DOWN")
    def test_threshold_config_separation(self):
        p=ThresholdPolicy("quantile",quantile=.5); self.assertFalse(p.approved_production_threshold); self.assertEqual(candidate_threshold([1,2,3],p),2)
    def test_production_threshold_not_silent(self):
        with self.assertRaises(ValueError): candidate_threshold([1,2],ThresholdPolicy("absolute",1,approved_production_threshold=True))
    def test_tick_feature_calculation(self):
        r=[{"BID":"100","ASK":"101","SPREAD":"1"},{"BID":"101","ASK":"102","SPREAD":"1"},{"BID":"100.5","ASK":"101.5","SPREAD":"1"}]
        x=tick_features(r); self.assertEqual(x["tick_count"],3); self.assertEqual(x["up_tick_count"],1); self.assertEqual(x["down_tick_count"],1)
    def test_spread_shock(self):
        r=[{"BID":"100","ASK":"101","SPREAD":"1"},{"BID":"101","ASK":"104","SPREAD":"3"}]
        self.assertEqual(tick_features(r)["spread_change"],2)
    def test_tick_pressure_reversal(self):
        r=[{"BID":"100","ASK":"100.2"},{"BID":"101","ASK":"101.2"},{"BID":"100.5","ASK":"100.7"}]
        self.assertGreaterEqual(tick_features(r)["reversal_tick_count"],1)
    def test_m1_feature_calculation(self):
        x=m1_features({"open":100,"high":103,"low":99,"close":102}); self.assertEqual(x["direction"],"UP")
    def test_m5_feature_calculation(self):
        x=m5_features({"open":100,"high":103,"low":99,"close":102}); self.assertEqual(x["role"],"SETUP_CONFIRMATION"); self.assertFalse(x["early_detection_source"])
    def test_reverse_lookback_windows(self):
        t=datetime(2026,1,1,1,0,tzinfo=timezone.utc); snaps=[{"time":t-timedelta(seconds=61),"x":1},{"time":t-timedelta(seconds=181),"x":2}]
        x=reverse_lookback(t,snaps); self.assertIn("T_MINUS_60S",x); self.assertIn("T_MINUS_3600S",x)
    def test_time_alignment(self):
        x=align_time("2026-01-01T00:00:00+00:00",timezone.utc); self.assertTrue(x.utc.startswith("2026-01-01T00:00:00")); self.assertIn("+09:00",x.kst)
    def test_timezone_mapping_broker_identity(self):
        x=align_time("2026-01-01T00:00:00+00:00",timezone.utc,"CultureCapital","Server"); self.assertEqual(x.broker,"CultureCapital")
    def test_stale_data_isolation(self):
        x=tick_features([]); self.assertEqual(x["freshness"],"VERIFY_REQUIRED")
    def test_missing_data_verify_required(self):
        x=tick_features([{"BID":"","ASK":""}]); self.assertEqual(x["freshness"],"VERIFY_REQUIRED")
    def test_control_sample_support(self):
        x=build_control_sample([{"v":1},{"v":2},{ "v":3}],{1}); self.assertEqual(len(x),2); self.assertEqual(x[0]["sample_class"],"CONTROL")
    def test_lead_lag_record(self):
        x=lead_lag_record("DXY","Gold",30,"DOWN"); self.assertEqual(x["classification"],"LEAD_LAG_CANDIDATE")
    def test_causation_separation(self):
        x=lead_lag_record("DXY","Gold",30,"DOWN","OBSERVED_ASSOCIATION"); self.assertEqual(x["classification"],"OBSERVED_ASSOCIATION")
    def test_shadow_long_transition(self): self.assertEqual(next_direction("NEUTRAL",2,0),"LONG")
    def test_shadow_short_transition(self): self.assertEqual(next_direction("NEUTRAL",0,2),"SHORT")
    def test_invalidation_transition(self): self.assertEqual(next_direction("LONG",2,0,True),"NEUTRAL")
    def test_add_no_add_independence(self):
        action,add=risk_action("LONG",add_risk=True); self.assertEqual(action,"HOLD"); self.assertEqual(add,"NO_ADD")
    def test_invalidation_warning(self):
        action,add=risk_action("SHORT",invalidation=True); self.assertEqual(action,"SHORT_INVALIDATION_WARNING"); self.assertEqual(add,"NO_ADD")
    def test_no_live_order_path(self):
        s=build_shadow("Gold","2026-01-01T00:00:00Z","LONG","BUY_ALLOWED","R","NORMAL","ADD_ALLOWED",["x"],100); self.assertFalse(s.live_order_allowed)
    def test_broker_identity_preservation(self):
        x=align_time("2026-01-01T00:00:00+00:00",timezone.utc,"EZSquare","S"); self.assertEqual(x.broker,"EZSquare")
    def test_event_id_uniqueness(self):
        a=make_event_id("Gold","2026-01-01T00:00:00Z","REVERSAL_UP","A"); b=make_event_id("Gold","2026-01-01T00:00:01Z","REVERSAL_UP","A"); self.assertNotEqual(a,b)
    def test_shadow_id_uniqueness(self):
        a=make_shadow_id("Gold","t1","LONG","WAIT"); b=make_shadow_id("Gold","t2","LONG","WAIT"); self.assertNotEqual(a,b)
    def test_mfe_calculation(self):
        mfe,mae=mfe_mae(100,[101,103,99],"LONG"); self.assertAlmostEqual(mfe,.03); self.assertAlmostEqual(mae,-.01)
    def test_mae_calculation_short(self):
        mfe,mae=mfe_mae(100,[99,97,101],"SHORT"); self.assertAlmostEqual(mfe,.03); self.assertAlmostEqual(mae,-.01)
    def test_performance_framework(self):
        x=evaluate_shadow([{"hit":True,"false_positive":False,"mfe":.02,"mae":-.01},{"hit":False,"false_positive":True,"mfe":.005,"mae":-.02}]); self.assertEqual(x["count"],2); self.assertAlmostEqual(x["hit_rate"],.5)
    def test_no_raw_runtime_git_commit_path(self):
        prohibited=("raw","csv","xlsx","ex5","log","backup"); paths=["agent/research_engine/event_engine.py","agent/schemas/reverse_event_schema.json","docs/research/REVERSE_EVENT_RESEARCH_ENGINE.md"]
        self.assertFalse(any(any(tok in p.lower().split("/")[-1].split(".")[-1:] for tok in prohibited) for p in paths))
