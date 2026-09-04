
import unittest
from datetime import datetime,timezone,timedelta
from agent.research_engine.btc_event_replay import *

class BTCEventReplayTests(unittest.TestCase):
    def ticks(self,symbol="BTCUSD",broker="CultureCapital"):
        t=datetime(2026,1,1,tzinfo=timezone.utc);out=[];p=100.0
        for i in range(300):
            p += .05 if i<150 else (-.03 if i<220 else .08)
            out.append({"time":t+timedelta(seconds=i*20),"BROKER":broker,"SYMBOL":symbol,
                        "BID":p-.1,"ASK":p+.1,"SPREAD":.2,"mid":p,"source_file":"x"})
        return out
    def test_inventory(self):
        x=data_inventory(self.ticks(),"CultureCapital","BTCUSD");self.assertEqual(x["TICK_COUNT"],300);self.assertTrue(x["M1_AVAILABLE"])
    def test_bars(self): self.assertGreater(len(derive_bars(self.ticks(),1)),1)
    def test_candidates_research_only(self):
        b=derive_bars(self.ticks()*1,1);self.assertIsInstance(trailing_event_candidates(b,min_history=10),list)
    def test_lookbacks_actual_only(self):
        b=derive_bars(self.ticks(),1);e=b[-1]["time"];self.assertIsNone(return_between(b,e,1440))
    def test_microstructure(self):
        t=self.ticks()[-1]["time"];self.assertIn("net_tick_pressure",microstructure(self.ticks(),t))
    def test_m1(self):
        b=derive_bars(self.ticks(),1);self.assertEqual(bar_feature_snapshot(b,b[-1]["time"],"M1")["freshness"],"FRESH")
    def test_m5(self):
        b=derive_bars(self.ticks(),5);self.assertEqual(bar_feature_snapshot(b,b[-1]["time"],"M5")["freshness"],"FRESH")
    def test_m30_h1(self):
        b30=derive_bars(self.ticks(),30);h=derive_bars(self.ticks(),60);self.assertIn("regime",regime_features(b30,h,b30[-1]["time"]))
    def test_btc_nq_alignment_missing(self):
        b=derive_bars(self.ticks(),1);self.assertEqual(align_relative(b,[],b[-1]["time"])["state"],"VERIFY_REQUIRED")
    def test_relative_decoupling(self):
        t=datetime(2026,1,1,tzinfo=timezone.utc)
        b=[{"time":t,"close":100},{"time":t+timedelta(minutes=30),"close":102}]
        n=[{"time":t,"close":100},{"time":t+timedelta(minutes=30),"close":99}]
        self.assertEqual(align_relative(b,n,t+timedelta(minutes=30))["state"],"BTC_NQ_DECOUPLING")
    def test_future_return(self):
        t=datetime(2026,1,1,tzinfo=timezone.utc);b=[{"time":t,"close":100},{"time":t+timedelta(minutes=5),"close":101}]
        self.assertAlmostEqual(future_return(b,t,5),.01)
    def test_post_metrics(self):
        b=derive_bars(self.ticks(),1);self.assertIn("5m",post_metrics(b,b[-5]["time"],"LONG"))
    def test_session(self): self.assertIsInstance(session_label(datetime.now(timezone.utc)),str)
    def test_shadow_no_future_leakage(self):
        rec={"PREVIOUS_REGIME":"LONG_REGIME","TACTICAL_STATE":"TACTICAL_PULLBACK","BTC_NQ_STATE":{"state":"NEUTRAL"},
             "M1":{"direction":"UP"},"M5":{"direction":"UP"},"POST_EVENT_METRICS":{"24h":{"mfe":99}}}
        self.assertFalse(shadow_replay(rec)["FUTURE_LEAKAGE"])
    def test_macro_missing_wait(self):
        rec={"PREVIOUS_REGIME":"LONG_REGIME","TACTICAL_STATE":"TACTICAL_PULLBACK","BTC_NQ_STATE":{"state":"NEUTRAL"},
             "M1":{"direction":"UP"},"M5":{"direction":"UP"}}
        self.assertEqual(shadow_replay(rec)["ENTRY_PERMISSION"],"WAIT")
    def test_feature_summary(self): self.assertIn("BEST_ADD_FEATURES",feature_summary([]))
    def test_cross_case_matrix(self): self.assertEqual(cross_case_matrix([]),[])
    def test_broker_identity(self):
        b,s,rows=choose_stream(self.ticks());self.assertEqual(b,"CultureCapital");self.assertEqual(s,"BTCUSD")
