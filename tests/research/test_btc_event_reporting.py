
import unittest
from agent.research_engine.btc_event_expansion import (
    EXPECTED_CASE_CATEGORIES, normalize_case_counts, reporting_safety_snapshot
)

class BTCEventReportingRegressionTests(unittest.TestCase):
    def test_all_categories_populated(self):
        src={k:i+1 for i,k in enumerate(EXPECTED_CASE_CATEGORIES)}
        out=normalize_case_counts(src)
        self.assertEqual(out,src)

    def test_some_categories_zero(self):
        out=normalize_case_counts({"BEARISH_TRANSITION":1})
        self.assertEqual(out["BEARISH_TRANSITION"],1)
        self.assertEqual(out["BULLISH_TRANSITION"],0)
        self.assertEqual(out["HEALTHY_LONG_PULLBACK"],0)

    def test_most_categories_zero(self):
        out=normalize_case_counts({"FALSE_BULLISH_REVERSAL":1})
        self.assertEqual(len(out),len(EXPECTED_CASE_CATEGORIES))
        self.assertEqual(sum(out.values()),1)

    def test_no_decoupling_and_no_healthy_pullback(self):
        out=normalize_case_counts({})
        self.assertEqual(out["BTC_NQ_DECOUPLING"],0)
        self.assertEqual(out["HEALTHY_LONG_PULLBACK"],0)
        self.assertEqual(out["BULLISH_TRANSITION"],0)

    def test_statistical_safety_labels(self):
        snap=reporting_safety_snapshot({
            "CASE_COUNTS":{"FALSE_BULLISH_REVERSAL":1},
            "SAMPLE_ADEQUACY":{"OVERALL":"INSUFFICIENT_SAMPLE","PRODUCTION_READY":False},
            "ADD_STATS":{"ADD_SUCCESS_RATE_CANDIDATE":0.0,"SAMPLE_STATUS":"INSUFFICIENT_SAMPLE"},
            "NO_ADD_STATS":{"NO_ADD_PROTECTION_RATE":1.0,"SAMPLE_STATUS":"INSUFFICIENT_SAMPLE"},
            "MAE_MFE":{"MEDIAN_MAE":-0.014,"MEDIAN_MFE":0.0035},
        })
        self.assertEqual(snap["SAMPLE_ADEQUACY"],"INSUFFICIENT_SAMPLE")
        self.assertFalse(snap["PRODUCTION_READY"])
        self.assertEqual(snap["ADD_SAMPLE_STATUS"],"INSUFFICIENT_SAMPLE")
        self.assertEqual(snap["NO_ADD_SAMPLE_STATUS"],"INSUFFICIENT_SAMPLE")
        self.assertEqual(snap["MAE_MFE_CLASSIFICATION"],"DESCRIPTIVE_RESEARCH_ONLY")
        self.assertEqual(snap["BTC_NQ_PREDICTIVE_STATUS"],"NO_PREDICTIVE_CLAIM")
        self.assertFalse(snap["PRODUCTION_THRESHOLD_PROMOTION"])

    def test_zero_count_report_generation_never_raises(self):
        snap=reporting_safety_snapshot({"CASE_COUNTS":None})
        self.assertEqual(set(snap["CASE_COUNTS"]),set(EXPECTED_CASE_CATEGORIES))
        self.assertTrue(all(isinstance(v,int) for v in snap["CASE_COUNTS"].values()))
