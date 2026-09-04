import unittest
from datetime import datetime,timezone,timedelta
from agent.research_engine.btc_event_expansion import *

class BTCEventExpansionTests(unittest.TestCase):
    def cands(self):
        t=datetime(2026,1,1,tzinfo=timezone.utc)
        return [
            {"time":t,"event_type":"RAPID_UP","return_1m":.01},
            {"time":t+timedelta(minutes=10),"event_type":"BREAKOUT","return_1m":.03},
            {"time":t+timedelta(minutes=120),"event_type":"RAPID_DOWN","return_1m":-.02},
        ]
    def test_cluster_independence(self):self.assertEqual(sum(x["INDEPENDENT_CASE_FLAG"] for x in cluster_events(self.cands(),90)),2)
    def test_overlap_exclusion(self):self.assertEqual(sum(x["OVERLAPPING_EVENT_FLAG"] for x in cluster_events(self.cands(),90)),1)
    def test_cluster_ids(self):self.assertEqual(len(set(x["EVENT_CLUSTER_ID"] for x in cluster_events(self.cands(),90))),2)
    def test_decoupling_up_down(self):self.assertEqual(classify_decoupling(.01,-.01),"BTC_UP_NQ_DOWN")
    def test_decoupling_down_up(self):self.assertEqual(classify_decoupling(-.01,.01),"BTC_DOWN_NQ_UP")
    def test_decoupling_hold(self):self.assertEqual(classify_decoupling(0,-.01),"BTC_HOLDS_NQ_DECLINES")
    def test_session_class(self):self.assertIn(research_session(datetime(2026,9,4,14,tzinfo=timezone.utc)),("ASIA","EUROPE","US_PREMARKET","US_CASH","US_LATE"))
    def test_add_price_decline_not_enough(self):
        f={"regime":{"regime":"LONG_REGIME","h1_direction":"LONG"},"m1":{"direction":"DOWN"},"m5":{"direction":"UP"},"relative":{"state":"NEUTRAL"},"event_type":"RAPID_DOWN"}
        x=add_noadd_candidate(f);self.assertNotEqual(x["ADD_STATE"],"ADD_ALLOWED_CANDIDATE");self.assertFalse(x["PRICE_DECLINE_ALONE_IS_ADD_EVIDENCE"])
    def test_add_candidate(self):
        f={"regime":{"regime":"LONG_REGIME","h1_direction":"LONG"},"m1":{"direction":"UP"},"m5":{"direction":"UP"},"relative":{"state":"NEUTRAL"},"event_type":"RAPID_DOWN"}
        self.assertEqual(add_noadd_candidate(f)["ADD_STATE"],"ADD_ALLOWED_CANDIDATE")
    def test_noadd_candidate(self):
        f={"regime":{"regime":"LONG_REGIME","h1_direction":"SHORT"},"m1":{"direction":"UP"},"m5":{"direction":"UP"},"relative":{"state":"NEUTRAL"},"event_type":"RAPID_DOWN"}
        self.assertEqual(add_noadd_candidate(f)["ADD_STATE"],"NO_ADD_CANDIDATE")
    def test_exit_warning(self):
        f={"regime":{"regime":"LONG_REGIME","h1_direction":"LONG"},"m1":{"direction":"DOWN"},"m5":{"direction":"DOWN"},"relative":{"state":"NEUTRAL"},"event_type":"FAILED_BREAKOUT"}
        self.assertEqual(add_noadd_candidate(f)["EXIT_WARNING_STATE"],"EXIT_WARNING_CANDIDATE")
    def test_macro_gap(self):self.assertEqual(MACRO_GAP["DXY"],"VERIFY_REQUIRED")
    def test_crypto_gap(self):self.assertEqual(CRYPTO_GAP["BTC_ETF_FLOW"],"VERIFY_REQUIRED")
    def test_future_leakage(self):self.assertFalse(future_leakage_contract()["FUTURE_LEAKAGE"])
    def test_add_stats_empty(self):self.assertIsNone(add_stats([])["ADD_SUCCESS_RATE_CANDIDATE"])
    def test_noadd_stats_empty(self):self.assertIsNone(noadd_stats([])["NO_ADD_PROTECTION_RATE"])
    def test_decoupling_stats_empty(self):self.assertEqual(decoupling_stats([])["SAMPLE_STATUS"],"INSUFFICIENT_SAMPLE")
    def test_control_samples(self):
        t=datetime(2026,1,1,tzinfo=timezone.utc);bars=[{"time":t+timedelta(minutes=i)} for i in range(300)]
        self.assertTrue(all(x["classification"]=="NON_EVENT_CONTROL" for x in control_samples(bars,[t+timedelta(minutes=120)],60,30)))
    def test_sample_adequacy(self):self.assertFalse(sample_adequacy(10,{"A":2})["PRODUCTION_READY"])
    def test_session_leadlag_keys(self):self.assertEqual(set(session_leadlag([])),{"ASIA","EUROPE","US_PREMARKET","US_CASH","US_LATE"})