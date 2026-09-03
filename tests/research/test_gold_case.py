
import unittest
from datetime import datetime, timedelta
from agent.research_engine.gold_case import minute_bars, five_minute_bars, resolve_reversal_case, window_snapshot, false_positive_cases

class GoldCaseTests(unittest.TestCase):
    def test_minute_bars(self):
        t=datetime(2026,1,1,0,0)
        ticks=[{"time":t,"mid":100,"BID":99.9,"ASK":100.1,"SPREAD":.2},{"time":t+timedelta(seconds=20),"mid":101,"BID":100.9,"ASK":101.1,"SPREAD":.2}]
        b=minute_bars(ticks); self.assertEqual(len(b),1); self.assertEqual(b[0]["high"],101)
    def test_five_minute_bars(self):
        t=datetime(2026,1,1,0,0)
        m1=[{"time":t+timedelta(minutes=i),"open":100+i,"high":101+i,"low":99+i,"close":100.5+i,"tick_count":1} for i in range(5)]
        b=five_minute_bars(m1); self.assertEqual(len(b),1); self.assertEqual(b[0]["m1_count"],5)
    def test_resolve_insufficient(self):
        self.assertEqual(resolve_reversal_case([])["status"],"VERIFY_REQUIRED")
    def test_window_snapshot_empty(self):
        t=datetime(2026,1,1)
        x=window_snapshot([],t,60); self.assertEqual(x["tick_count"],0)
    def test_false_positive_returns_list(self):
        t=datetime(2026,1,1)
        m1=[]
        for i in range(100):
            o=100; c=100.05 if i%2==0 else 99.95
            m1.append({"time":t+timedelta(minutes=i),"open":o,"high":100.1,"low":99.9,"close":c,"tick_count":1})
        self.assertIsInstance(false_positive_cases(m1,t+timedelta(hours=5)),list)
