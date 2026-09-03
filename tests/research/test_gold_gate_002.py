
import unittest
from datetime import datetime
from agent.research_engine.session_architecture import ArchitecturePrinciple,classify_session,execution_due,execution_depends_on_reporting_clock
from agent.research_engine.gold_gate import persistence_flags,discriminate,combination_results,horizon_metrics,early_warning_vs_entry
from agent.research_engine.gold_case2 import cross_case_matrix

class GoldGate002Tests(unittest.TestCase):
    def test_24_5_architecture(self): self.assertTrue(ArchitecturePrinciple().final_target.startswith("24/5"))
    def test_session_classification(self): self.assertEqual(classify_session(datetime(2026,1,1,10,0)),"US_CASH_OPEN_INTENSIVE")
    def test_market_closed(self): self.assertEqual(classify_session(datetime(2026,1,1,10,0),market_open=False),"MARKET_CLOSED")
    def test_event_driven(self): self.assertTrue(execution_due("TICK_PRESSURE_REVERSAL",False,False,False))
    def test_no_10m_dependency(self): self.assertFalse(execution_depends_on_reporting_clock("10M"))
    def test_no_1h_dependency(self): self.assertFalse(execution_depends_on_reporting_clock("1H"))
    def test_persistence(self): self.assertTrue(persistence_flags(120)["PERSIST_60S"])
    def test_false_positive(self): self.assertEqual(discriminate({"FAILED_LOW":True},[{"FAILED_LOW":True}])["FAILED_LOW"]["false_positive_occurrence_count"],1)
    def test_combination(self): self.assertTrue(combination_results({"TICK_PRESSURE_REVERSAL":True,"DOWNSIDE_VELOCITY_DECAY":True,"FAILED_LOW":True},[])["A"]["true_reversal_match"])
    def test_warning_vs_entry(self): self.assertEqual(early_warning_vs_entry(-.02,-.005,120)["entry_signal_utility"],"BETTER_THAN_EARLY_WARNING")
    def test_horizon(self): self.assertIn("NEXT_3M_MFE",horizon_metrics(100,[(60,99),(180,103)]))
    def test_matrix(self):
        rows=cross_case_matrix({"candidates":{"tick_pressure_reversal":{"x":1}}},{"features":{"TICK_PRESSURE_REVERSAL":True}},[],None)
        self.assertTrue(any(x["feature"]=="TICK_PRESSURE_REVERSAL" for x in rows))
    def test_live_order_disabled(self): self.assertFalse(ArchitecturePrinciple().live_order_enabled)
