
import unittest
from datetime import datetime,timezone,timedelta
from agent.research_engine.btc_regime import *

class BTCPrimaryRegimeTests(unittest.TestCase):
    def test_primary_role(self): self.assertEqual(BTC_PRIMARY_ROLE,"PRIMARY_TRADING_RESEARCH_TARGET")
    def test_five_market_preserved(self): self.assertEqual(set(FIVE_MARKET_ROLES),{"BTC","NQ","GOLD","SILVER","OIL"})
    def test_priority(self): self.assertTrue(FIVE_MARKET_ROLES["BTC"].startswith("HIGH"))
    def test_long_regime(self): self.assertIn(long_horizon_regime("LONG","LONG")["regime"],("LONG_REGIME","STRONG_LONG_REGIME"))
    def test_pullback_does_not_flip(self):
        x=long_horizon_regime("LONG","LONG",current_regime="LONG_REGIME",tactical_state="TACTICAL_PULLBACK");self.assertEqual(x["regime"],"LONG_REGIME")
    def test_short_support(self): self.assertIn(long_horizon_regime("SHORT","SHORT")["regime"],("SHORT_REGIME","STRONG_SHORT_REGIME"))
    def test_btc_nq_decoupling(self): self.assertEqual(btc_nq_relative(.02,-.01)["state"],"BTC_NQ_DECOUPLING")
    def test_btc_relative_positive(self): self.assertEqual(btc_nq_relative(.01,.001)["state"],"BTC_RELATIVE_STRENGTH_POSITIVE")
    def test_nq_missing(self): self.assertEqual(btc_nq_relative(.01,None)["state"],"VERIFY_REQUIRED")
    def test_stablecoin_structural(self): self.assertEqual(stablecoin_structural_factor(.05,"INFLOW","FRESH")["state"],"STRUCTURAL_LONG_FACTOR")
    def test_stablecoin_not_entry_authority(self): self.assertNotIn("entry_permission",stablecoin_structural_factor(.05,"INFLOW","FRESH"))
    def test_regulatory_context(self): self.assertEqual(regulatory_factor(["POSITIVE:X"],"FRESH","WEB")["state"],"POSITIVE")
    def test_macro_dynamic_not_hardcoded(self): self.assertFalse(rates_dollar_observation("UP","UP","LONG","FRESH")["universal_direction_rule"])
    def test_entry_macro_missing(self): self.assertEqual(entry_gate("LONG_REGIME","IMPROVING","IMPROVING","VERIFY_REQUIRED","NONE",True)["entry_permission"],"WAIT")
    def test_add_price_fall_not_enough(self): self.assertEqual(add_gate("LONG_REGIME","TACTICAL_PULLBACK","DETERIORATING","IMPROVING","NORMAL",True)["add_permission"],"NO_ADD")
    def test_add_allowed_research(self): self.assertEqual(add_gate("LONG_REGIME","TACTICAL_PULLBACK","IMPROVING","IMPROVING","NORMAL",True)["add_permission"],"ADD_ALLOWED")
    def test_direction_entry_add_separation(self):
        r=long_horizon_regime("LONG","LONG");d=btc_shadow_decision(r,"TACTICAL_PULLBACK","POSITIVE","VERIFY_REQUIRED","POSITIVE","MIXED","MIXED",{"historical_only_authority":False},"NONE","IMPROVING","IMPROVING","NORMAL",True);self.assertEqual(d["direction"],"LONG");self.assertEqual(d["entry_permission"],"WAIT")
    def test_no_live_order(self):
        r=long_horizon_regime("LONG","LONG");d=btc_shadow_decision(r,"TACTICAL_PULLBACK","POSITIVE","VERIFY_REQUIRED","POSITIVE","MIXED","MIXED",{},"NONE","IMPROVING","IMPROVING","NORMAL",True);self.assertFalse(d["live_order_allowed"])
    def test_event_detection(self): self.assertEqual(detect_event([100,99,103],.02),"RAPID_UP")
    def test_event_record_research_only(self):
        x=event_record("1","REVERSAL_UP",{}, {}, {}, {}, {}, {}, {});self.assertEqual(x["classification"],"RESEARCH_CANDIDATE_ONLY");self.assertFalse(x["live_order_allowed"])
    def test_long_lookbacks(self): self.assertEqual(len(reverse_lookback_windows(datetime(2026,1,2,tzinfo=timezone.utc))),8)
    def test_missing_lookback_verify(self):
        e=datetime(2026,1,2,tzinfo=timezone.utc);a=e-timedelta(minutes=10);x=reverse_lookback_windows(e,a);self.assertEqual(x["T_MINUS_86400S"]["status"],"VERIFY_REQUIRED")
    def test_outcome_horizons(self):
        x=outcome_metrics(100,[(60,101),(259200,120)],"LONG");self.assertIn("72h",x);self.assertIn("24h",x)
    def test_short_outcome_direction(self):
        x=outcome_metrics(100,[(60,99)],"SHORT");self.assertTrue(x["1m"]["direction_accuracy"])
